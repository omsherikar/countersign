"""Signals for officers: run the detectors, list and read them, open cases, dismiss (D45, R5).

`run` reads records and writes only `signals` rows: an upsert by `dedupe_key` that never
deletes a signal and never touches its status, its cases, its note or who decided it. Signals
never call `status.mark`. Only `open_cases` makes cases, each through the flags engine with
the officer as actor, and only through those cases can a record's status change.

AICTE officers see every signal; a regional officer sees a signal when one of its colleges is
in its region, and inside it the members and colleges of other regions are counted, not
listed. Every function runs in the caller's transaction and flushes, never commits.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, case, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cases import service as cases
from app.core import audit
from app.core.audit import AuditEntry
from app.core.crypto import mask_apaar
from app.core.errors import ApiError, not_found
from app.core.rules import get_rules
from app.engine import status
from app.engine.evidence import AUDIENCE_OFFICER, fmt_date
from app.engine.flags import raise_flag
from app.engine.status_text import ist_date
from app.models.enums import (
    AuditAction,
    CaseActionKind,
    EnrolmentStatus,
    FlagType,
    Severity,
    SignalStatus,
    SignalType,
    UserRole,
)
from app.models.geo import Region, State
from app.models.institution import Institution, Programme
from app.models.signal import Signal
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Flag
from app.signals import anomaly, rings

SOURCE_SIGNALS = "Countersign signals"
SOURCE_UPLOADS = "College uploads"
SOURCE_MODEL = "Countersign signals, Isolation Forest"
DEFAULT_SEVERITY = {SignalType.GHOST_RING: Severity.HIGH, SignalType.ANOMALY: Severity.MEDIUM}
CHOOSE_COLLEGES = "Choose colleges from this signal."
CHOOSE_ONE = "Choose at least one college."
ALREADY_HANDLED = "This signal already has a case or was dismissed."
# copy deck signal.fact.*
FACT_STUDENTS = "Students"
FACT_COLLEGES = "Colleges"
FACT_MEMBERS = "Members"
FACT_SHARED = {
    rings.MOBILE: "Shared mobile numbers",
    rings.EMAIL: "Shared email addresses",
    rings.ADDRESS: "Shared addresses",
}
LOCK_NOT_AVAILABLE = "55P03"


@dataclass(frozen=True, slots=True)
class SignalQuery:
    academic_year: str | None = None
    type: SignalType | None = None
    status: SignalStatus | None = None
    institution_id: uuid.UUID | None = None
    state: str | None = None
    sort: Literal["newest", "score"] = "newest"
    page: int = 1
    page_size: int = 25


@dataclass(slots=True)
class _Draft:
    type: SignalType
    academic_year: str
    dedupe_key: str
    institution_ids: list[uuid.UUID]
    enrolment_ids: list[uuid.UUID]
    summary: str
    facts: dict[str, Any]
    rule: str
    score: Decimal | None = None


@dataclass(slots=True)
class _Scope:
    """What the caller may see: every institution (None) or a region's."""

    region_ids: frozenset[uuid.UUID] | None = None

    def sees(self, institution_id: uuid.UUID) -> bool:
        return self.region_ids is None or institution_id in self.region_ids


@dataclass(slots=True)
class OpenCases:
    flags: list[Flag] = field(default_factory=list)
    created: list[Flag] = field(default_factory=list)


def _uuid_array(ids: Sequence[uuid.UUID]) -> Any:
    return literal(list(ids), type_=ARRAY(UUID(as_uuid=True)))


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _join(parts: Sequence[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# --------------------------------------------------------------------------- run


def _ring_draft(
    ring: rings.Ring, academic_year: str, names: Mapping[uuid.UUID, str], rule_line: str
) -> _Draft:
    colleges = sorted(names.get(i, str(i)) for i in ring.institution_ids)
    items = [
        {"label": FACT_STUDENTS, "value": str(ring.students), "source": SOURCE_SIGNALS},
        {"label": FACT_COLLEGES, "value": "; ".join(colleges), "source": SOURCE_UPLOADS},
    ]
    for kind, label in FACT_SHARED.items():
        n = ring.shared_count(kind)
        if n:
            items.append({"label": label, "value": str(n), "source": SOURCE_UPLOADS})
    return _Draft(
        type=SignalType.GHOST_RING,
        academic_year=academic_year,
        dedupe_key=f"GHOST_RING:{academic_year}:{ring.student_ids[0]}",
        institution_ids=sorted(ring.institution_ids, key=str),
        enrolment_ids=sorted({m.enrolment_id for m in ring.members}, key=str),
        summary=rings.summary(ring, names),
        facts={
            "items": items,
            "students": ring.students,
            "shared": [
                {"kind": kind, "masked": masked, "students": n} for kind, masked, n in ring.shared
            ],
        },
        rule=rule_line,
    )


def _anomaly_draft(
    outlier: anomaly.Outlier,
    academic_year: str,
    names: Mapping[uuid.UUID, str],
    peers: int,
    rule_line: str,
) -> _Draft:
    name = names.get(outlier.institution_id, str(outlier.institution_id))
    features = [dict(f) for f in outlier.features]
    return _Draft(
        type=SignalType.ANOMALY,
        academic_year=academic_year,
        dedupe_key=f"ANOMALY:{academic_year}:{outlier.institution_id}",
        institution_ids=[outlier.institution_id],
        enrolment_ids=[],
        summary=anomaly.summary(name, peers, academic_year, outlier.standing_out),
        facts={
            "items": [anomaly.feature_fact(f, SOURCE_MODEL) for f in features],
            "features": features,
            "peers": peers,
        },
        rule=rule_line,
        score=Decimal(str(outlier.score)),
    )


def _content(signal: Signal | _Draft) -> tuple[Any, ...]:
    facts = {k: v for k, v in (signal.facts or {}).items() if k != "cases"}
    score = None if signal.score is None else float(signal.score)
    return (
        signal.summary,
        signal.rule,
        score,
        sorted(map(str, signal.institution_ids)),
        sorted(map(str, signal.enrolment_ids or [])),
        facts,
    )


async def run(
    session: AsyncSession, academic_year: str, *, actor_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Both detectors over the ACTIVE enrolments of the year; upserts their signals."""
    started = time.perf_counter()
    thresholds = get_rules().ghost_ring
    min_cross = thresholds.min_component_cross_college if thresholds else 3
    min_colleges = thresholds.min_colleges if thresholds else 2
    min_single = thresholds.min_component_single_college if thresholds else 5
    model = anomaly.settings()

    members = await rings.load_members(session, academic_year)
    found = rings.find_rings(
        members, min_cross=min_cross, min_colleges=min_colleges, min_single=min_single
    )
    features = await anomaly.load_features(
        session, academic_year, min_records=model.min_records, members=members
    )
    outliers = anomaly.score(
        features,
        contamination=model.contamination,
        n_estimators=model.n_estimators,
        random_state=model.random_state,
    )
    wanted = {i for r in found for i in r.institution_ids} | {o.institution_id for o in outliers}
    names = dict(
        (
            await session.execute(
                select(Institution.id, Institution.name).where(Institution.id.in_(wanted))
            )
        ).all()
        if wanted
        else []
    )
    ring_rule = rings.rule(min_cross=min_cross, min_colleges=min_colleges, min_single=min_single)
    model_rule = anomaly.rule(model.contamination, len(features))
    drafts = [_ring_draft(r, academic_year, names, ring_rule) for r in found] + [
        _anomaly_draft(o, academic_year, names, len(features) - 1, model_rule) for o in outliers
    ]

    existing = {
        s.dedupe_key: s
        for s in (
            await session.execute(
                select(Signal).where(Signal.dedupe_key.in_([d.dedupe_key for d in drafts]))
            )
        ).scalars()
    }
    created = updated = 0
    entries: list[AuditEntry] = []
    for draft in drafts:
        signal = existing.get(draft.dedupe_key)
        if signal is None:
            signal = Signal(
                id=uuid.uuid4(),
                type=draft.type,
                academic_year=draft.academic_year,
                institution_ids=draft.institution_ids,
                enrolment_ids=draft.enrolment_ids,
                summary=draft.summary,
                facts={**draft.facts, "cases": []},
                rule=draft.rule,
                score=draft.score,
                status=SignalStatus.NEW,
                dedupe_key=draft.dedupe_key,
            )
            session.add(signal)
            created += 1
            action = AuditAction.CREATE
        elif _content(signal) != _content(draft):
            # the officer's side (status, cases, note, who decided) stays as it is
            signal.institution_ids = draft.institution_ids
            signal.enrolment_ids = draft.enrolment_ids
            signal.summary = draft.summary
            signal.facts = {**draft.facts, "cases": list((signal.facts or {}).get("cases", []))}
            signal.rule = draft.rule
            signal.score = draft.score
            updated += 1
            action = AuditAction.UPDATE
        else:
            continue
        entries.append(
            AuditEntry(
                action=action,
                entity_type="signal",
                entity_id=signal.id,
                actor_id=actor_id,
                after={"type": draft.type.value, "dedupe_key": draft.dedupe_key},
            )
        )
    await session.flush()
    if entries:
        await audit.record_many(session, entries)
    return {
        "academic_year": academic_year,
        "rings": len(found),
        "anomalies": len(outliers),
        "created": created,
        "updated": updated,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "model": {
            "name": anomaly.MODEL_NAME,
            "contamination": model.contamination,
            "n_estimators": model.n_estimators,
            "random_state": model.random_state,
            "institutions": len(features),
        },
    }


# ------------------------------------------------------------------------- scope


async def _scope(session: AsyncSession, user: User) -> _Scope:
    if user.role is UserRole.RO_OFFICER:
        ids = (
            await session.execute(
                select(Institution.id).where(Institution.region_id == user.region_id)
            )
        ).scalars()
        return _Scope(region_ids=frozenset(ids))
    return _Scope()


def _scoped(stmt: Select, scope: _Scope) -> Select:
    if scope.region_ids is None:
        return stmt
    return stmt.where(
        Signal.institution_ids.op("&&")(_uuid_array(sorted(scope.region_ids, key=str)))
    )


async def _scoped_signal(
    session: AsyncSession, scope: _Scope, signal_id: uuid.UUID, *, lock: bool = False
) -> Signal:
    stmt = _scoped(select(Signal).where(Signal.id == signal_id), scope)
    signal = (await session.execute(stmt)).scalar_one_or_none()
    if signal is None:
        raise not_found("Signal")
    if lock:
        try:
            await session.execute(
                select(Signal.id).where(Signal.id == signal_id).with_for_update(nowait=True)
            )
        except DBAPIError as exc:
            # another officer holds the signal: answer as if they had already acted
            code = getattr(exc.orig, "sqlstate", None)
            if code != LOCK_NOT_AVAILABLE and "could not obtain lock" not in str(exc):
                raise
            raise _handled(signal.status) from None
        await session.refresh(signal)
    return signal


def _handled(current: SignalStatus) -> ApiError:
    return ApiError(409, "SIGNAL_ALREADY_HANDLED", ALREADY_HANDLED, {"status": current.value})


# ------------------------------------------------------------------------- reads


async def _institutions(
    session: AsyncSession, ids: set[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    if not ids:
        return {}
    rows = await session.execute(
        select(
            Institution.id,
            Institution.name,
            Institution.aicte_permanent_id,
            State.code,
            Region.code,
        )
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .where(Institution.id.in_(ids))
    )
    return {
        i: {"id": str(i), "name": name, "aicte_permanent_id": aid, "state_code": st, "region": rg}
        for i, name, aid, st, rg in rows.all()
    }


async def _case_statuses(session: AsyncSession, signals: Sequence[Signal]) -> dict[str, str]:
    ids = {uuid.UUID(c["flag_id"]) for s in signals for c in (s.facts or {}).get("cases", [])}
    if not ids:
        return {}
    rows = await session.execute(select(Flag.id, Flag.status).where(Flag.id.in_(ids)))
    return {str(i): st.value for i, st in rows.all()}


async def _member_owners(
    session: AsyncSession, signals: Sequence[Signal]
) -> dict[uuid.UUID, uuid.UUID]:
    ids = {e for s in signals for e in (s.enrolment_ids or [])}
    if not ids:
        return {}
    rows = await session.execute(
        select(Enrolment.id, Enrolment.institution_id).where(Enrolment.id.in_(ids))
    )
    return dict(rows.all())


def _row(
    signal: Signal,
    scope: _Scope,
    institutions: Mapping[uuid.UUID, dict[str, Any]],
    owners: Mapping[uuid.UUID, uuid.UUID],
    case_status: Mapping[str, str],
) -> dict[str, Any]:
    visible = [i for i in signal.institution_ids if scope.sees(i)]
    members = list(signal.enrolment_ids or [])
    hidden_members = sum(1 for e in members if e in owners and not scope.sees(owners[e]))
    cases_out = [
        {
            "id": c["flag_id"],
            "institution_id": c["institution_id"],
            "status": case_status.get(c["flag_id"], "OPEN"),
        }
        for c in (signal.facts or {}).get("cases", [])
        if scope.sees(uuid.UUID(c["institution_id"]))
    ]
    return {
        "id": str(signal.id),
        "type": signal.type.value,
        "academic_year": signal.academic_year,
        "status": signal.status.value,
        "summary": signal.summary,
        "member_count": len(members),
        "members_hidden": hidden_members,
        "score": None if signal.score is None else float(signal.score),
        "institutions": sorted(
            (institutions[i] for i in visible if i in institutions), key=lambda r: r["name"]
        ),
        "institutions_hidden": len(signal.institution_ids) - len(visible),
        "rule": signal.rule,
        "cases": cases_out,
        "created_at": _iso(signal.created_at) or "",
        "updated_at": _iso(signal.updated_at or signal.created_at) or "",
    }


async def _rows(
    session: AsyncSession, scope: _Scope, signals: Sequence[Signal]
) -> list[dict[str, Any]]:
    institutions = await _institutions(session, {i for s in signals for i in s.institution_ids})
    owners = await _member_owners(session, signals)
    statuses = await _case_statuses(session, signals)
    return [_row(s, scope, institutions, owners, statuses) for s in signals]


async def list_signals(session: AsyncSession, user: User, query: SignalQuery) -> dict[str, Any]:
    scope = await _scope(session, user)
    stmt = _scoped(select(Signal), scope)
    if query.academic_year:
        stmt = stmt.where(Signal.academic_year == query.academic_year)
    if query.type is not None:
        stmt = stmt.where(Signal.type == query.type)
    if query.status is not None:
        stmt = stmt.where(Signal.status == query.status)
    if query.institution_id is not None:
        stmt = stmt.where(Signal.institution_ids.op("@>")(_uuid_array([query.institution_id])))
    if query.state:
        in_state = (
            await session.execute(
                select(Institution.id)
                .join(State, State.id == Institution.state_id)
                .where(State.code == query.state.upper())
            )
        ).scalars()
        stmt = stmt.where(Signal.institution_ids.op("&&")(_uuid_array(sorted(in_state, key=str))))
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    if query.sort == "score":
        stmt = stmt.order_by(
            case((Signal.type == SignalType.ANOMALY, 0), else_=1),
            Signal.score.asc().nulls_last(),
            func.cardinality(Signal.enrolment_ids).desc(),
            Signal.created_at.desc(),
            Signal.id,
        )
    else:
        stmt = stmt.order_by(Signal.created_at.desc(), Signal.id)
    offset = (query.page - 1) * query.page_size
    signals = list((await session.execute(stmt.offset(offset).limit(query.page_size))).scalars())
    return {
        "items": await _rows(session, scope, signals),
        "total": total,
        "page": query.page,
        "page_size": query.page_size,
    }


def _member_id(student: Student) -> str:
    return mask_apaar(student.apaar_last4) or student.provisional_id or "No id"


async def _members(
    session: AsyncSession, signal: Signal
) -> list[tuple[Enrolment, Student, Institution, str]]:
    if not signal.enrolment_ids:
        return []
    rows = await session.execute(
        select(Enrolment, Student, Institution, Programme.code)
        .join(Student, Student.id == Enrolment.student_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .where(Enrolment.id.in_(list(signal.enrolment_ids)))
        .order_by(Institution.name, Student.name, Enrolment.id)
    )
    return [tuple(r) for r in rows.all()]  # type: ignore[misc]


def _ring_facts(
    signal: Signal,
    scope: _Scope,
    institutions: Mapping[uuid.UUID, dict[str, Any]],
    members: Sequence[tuple[Enrolment, Student, Institution, str]],
) -> list[dict[str, Any]]:
    """The stored facts with the colleges and members the caller may see; the rest counted."""
    items = [dict(f) for f in (signal.facts or {}).get("items", [])]
    visible_colleges = sorted(
        institutions[i]["name"]
        for i in signal.institution_ids
        if scope.sees(i) and i in institutions
    )
    hidden_colleges = len(signal.institution_ids) - len(visible_colleges)
    for item in items:
        if item["label"] == FACT_COLLEGES and hidden_colleges:
            item["value"] = "; ".join(
                [
                    *visible_colleges,
                    f"{_plural(hidden_colleges, 'college', 'colleges')} in other regions",
                ]
            )
    shown = [
        f"{_member_id(student)} ({institution.name})"
        for enrolment, student, institution, _ in members
        if scope.sees(enrolment.institution_id)
    ]
    hidden = sum(1 for e, *_ in members if not scope.sees(e.institution_id))
    if hidden:
        shown.append(f"{_plural(hidden, 'record', 'records')} in other regions")
    if shown:
        items.append({"label": FACT_MEMBERS, "value": "; ".join(shown), "source": SOURCE_UPLOADS})
    return items


async def _detail(
    session: AsyncSession,
    user: User,
    scope: _Scope,
    signal: Signal,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    [row] = await _rows(session, scope, [signal])
    members = await _members(session, signal)
    facts = signal.facts or {}
    if signal.type is SignalType.GHOST_RING:
        institutions = await _institutions(session, set(signal.institution_ids))
        items = _ring_facts(signal, scope, institutions, members)
    else:
        items = [dict(f) for f in facts.get("items", [])]
    shown = [m for m in members if scope.sees(m[0].institution_id)]
    dismissal = None
    if signal.status is SignalStatus.DISMISSED and signal.decided_by_id is not None:
        officer = await session.get(User, signal.decided_by_id)
        dismissal = {
            "note": signal.note or "",
            "by": {"id": str(signal.decided_by_id), "name": officer.name if officer else ""},
            "at": _iso(signal.decided_at) or "",
        }
    await audit.record_read(
        session,
        user.id,
        "student",
        [student.id for _, student, _, _ in shown],
        request_id=request_id,
    )
    return {
        **row,
        "facts": [
            {"label": f["label"], "value": f["value"], "source": f.get("source")} for f in items
        ],
        "shared": list(facts.get("shared", [])),
        "features": [
            {
                k: f[k]
                for k in (
                    "name",
                    "value",
                    "peer_low",
                    "peer_high",
                    "peer_median",
                    "robust_z",
                    "stands_out",
                )
            }
            for f in facts.get("features", [])
        ],
        "members": [
            {
                "enrolment_id": str(enrolment.id),
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "apaar_masked": mask_apaar(student.apaar_last4),
                    "provisional_id": student.provisional_id,
                },
                "institution": {"id": str(institution.id), "name": institution.name},
                "programme_code": programme_code,
                "record_status": enrolment.record_status.value
                if enrolment.status is EnrolmentStatus.ACTIVE
                else None,
            }
            for enrolment, student, institution, programme_code in shown
        ],
        "dismissal": dismissal,
    }


async def detail(
    session: AsyncSession, user: User, signal_id: uuid.UUID, *, request_id: str | None = None
) -> dict[str, Any]:
    scope = await _scope(session, user)
    signal = await _scoped_signal(session, scope, signal_id)
    return await _detail(session, user, scope, signal, request_id=request_id)


# ------------------------------------------------------------------------- cases


def _ring_evidence(
    signal: Signal,
    institution: Institution,
    members_here: Sequence[tuple[Enrolment, Student, Institution, str]],
    college_names: Sequence[str],
) -> dict[str, Any]:
    facts = signal.facts or {}
    students = int(facts.get("students") or len({s.id for _, s, _, _ in members_here}))
    contacts = len(facts.get("shared", []))
    colleges = len(signal.institution_ids)
    shared_items = [
        {**f, "source": SOURCE_UPLOADS}
        for f in facts.get("items", [])
        if f["label"] in FACT_SHARED.values()
    ]
    return {
        # copy deck flag.GHOST_RING.summary
        "summary": f"{_plural(students, 'student', 'students')} across "
        f"{_plural(colleges, 'institution', 'institutions')} share "
        f"{_plural(contacts, 'contact detail', 'contact details')}.",
        "facts": [
            {"label": FACT_STUDENTS, "value": str(len(members_here)), "source": SOURCE_UPLOADS},
            {
                "label": FACT_MEMBERS,
                "value": "; ".join(_member_id(s) for _, s, _, _ in members_here) or "None",
                "source": SOURCE_UPLOADS,
            },
            *shared_items,
            {
                "label": FACT_COLLEGES,
                "value": "; ".join(college_names),
                "source": SOURCE_UPLOADS,
                "audience": AUDIENCE_OFFICER,
            },
            {
                "label": "Signal",
                "value": f"Shared contact ring found on {fmt_date(ist_date(signal.created_at))}",
                "source": SOURCE_SIGNALS,
                "audience": AUDIENCE_OFFICER,
            },
        ],
        "related_enrolment_ids": [str(e.id) for e, _, _, _ in members_here],
        "rule_source": signal.rule,
        "signal_id": str(signal.id),
    }


def _anomaly_evidence(signal: Signal, institution: Institution) -> dict[str, Any]:
    facts = signal.facts or {}
    standing = [f["name"] for f in facts.get("features", []) if f.get("stands_out")]
    return {
        # copy deck flag.ANOMALY.summary
        "summary": f"{institution.name} stands out from similar colleges on "
        f"{anomaly.feature_words(standing)} ({signal.academic_year}).",
        "facts": [
            *({**f, "source": SOURCE_SIGNALS} for f in facts.get("items", [])),
            {
                "label": "Signal",
                "value": f"Unusual pattern found on {fmt_date(ist_date(signal.created_at))}",
                "source": SOURCE_SIGNALS,
                "audience": AUDIENCE_OFFICER,
            },
            {
                "label": "Model score",
                "value": str(signal.score),
                "source": SOURCE_MODEL,
                "audience": AUDIENCE_OFFICER,
            },
        ],
        "related_enrolment_ids": [],
        "rule_source": signal.rule,
        "signal_id": str(signal.id),
    }


def _field_error(field_name: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{field_name}: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": field_name, "message": message}]},
    )


def _chosen(
    signal: Signal, scope: _Scope, institution_ids: Sequence[uuid.UUID | str] | None
) -> list[uuid.UUID]:
    allowed = [i for i in signal.institution_ids if scope.sees(i)]
    if not institution_ids:
        if len(signal.institution_ids) == 1 and allowed:
            return allowed
        raise _field_error("institution_ids", CHOOSE_ONE)
    chosen: list[uuid.UUID] = []
    for raw in institution_ids:
        try:
            value = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
        except ValueError:
            raise _field_error("institution_ids", CHOOSE_COLLEGES) from None
        if value not in allowed:
            raise _field_error("institution_ids", CHOOSE_COLLEGES)
        if value not in chosen:
            chosen.append(value)
    return chosen


def case_key(signal: Signal, institution_id: uuid.UUID) -> str:
    """API_CONTRACT §A4.11: one ring case per college, one anomaly case per signal."""
    if signal.type is SignalType.GHOST_RING:
        return f"GHOST_RING:{signal.id}:{institution_id}"
    return f"ANOMALY:{signal.id}"


async def open_cases(
    session: AsyncSession,
    user: User,
    signal_id: uuid.UUID,
    *,
    institution_ids: Sequence[uuid.UUID | str] | None,
    note: str,
    severity: Severity | None,
) -> list[Flag]:
    """Open a case from the signal for each chosen college (or return the one it has). The
    records each case names are queued for `status.settle`; nothing else about them changes."""
    scope = await _scope(session, user)
    signal = await _scoped_signal(session, scope, signal_id, lock=True)
    if signal.status is SignalStatus.DISMISSED:
        raise _handled(signal.status)
    chosen = _chosen(signal, scope, institution_ids)
    severity = severity or DEFAULT_SEVERITY[signal.type]
    flag_type = FlagType(signal.type.value)
    members = await _members(session, signal)
    names = sorted(
        r["name"] for r in (await _institutions(session, set(signal.institution_ids))).values()
    )
    out = OpenCases()
    for institution_id in chosen:
        key = case_key(signal, institution_id)
        flag = (
            await session.execute(select(Flag).where(Flag.dedupe_key == key))
        ).scalar_one_or_none()
        if flag is not None:
            out.flags.append(flag)
            continue
        institution = await session.get(Institution, institution_id)
        assert institution is not None
        if signal.type is SignalType.GHOST_RING:
            here = [
                m
                for m in members
                if m[0].institution_id == institution_id and m[0].status is EnrolmentStatus.ACTIVE
            ]
            evidence = _ring_evidence(signal, institution, here, names)
        else:
            evidence = _anomaly_evidence(signal, institution)
        raised = await raise_flag(
            session,
            type=flag_type,
            severity=severity,
            institution_id=institution_id,
            programme_id=None,
            enrolment_id=None,
            academic_year=signal.academic_year,
            dedupe_key=key,
            evidence=evidence,
            actor_id=user.id,
        )
        # the officer's note starts the case's history
        await cases.apply_action(
            session,
            user,
            raised.flag.id,
            action=CaseActionKind.NOTE,
            note=note,
            due_date=None,
            assignee_id=None,
        )
        status.mark(session, status.named_enrolments(raised.flag))
        out.flags.append(raised.flag)
        out.created.append(raised.flag)

    if out.created:
        before = signal.status
        now = datetime.now(UTC)
        if signal.status is SignalStatus.NEW:
            signal.status = SignalStatus.CASE_OPENED
        if signal.case_flag_id is None:
            signal.case_flag_id = out.created[0].id
            signal.note = note
            signal.decided_by_id = user.id
            signal.decided_at = now
        facts = dict(signal.facts or {})
        facts["cases"] = [
            *facts.get("cases", []),
            *({"flag_id": str(f.id), "institution_id": str(f.institution_id)} for f in out.created),
        ]
        signal.facts = facts
        await session.flush()
        await session.refresh(signal)  # updated_at moved on the server
        await audit.record(
            session,
            user.id,
            AuditAction.UPDATE,
            "signal",
            signal.id,
            before={"status": before.value},
            after={"status": signal.status.value, "case_ids": [str(f.id) for f in out.created]},
        )
    return out.flags


async def dismiss(
    session: AsyncSession,
    user: User,
    signal_id: uuid.UUID,
    *,
    note: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Only from NEW. No record or case changes; the note is never written to the audit log."""
    scope = await _scope(session, user)
    signal = await _scoped_signal(session, scope, signal_id, lock=True)
    if signal.status is not SignalStatus.NEW:
        raise _handled(signal.status)
    signal.status = SignalStatus.DISMISSED
    signal.note = note
    signal.decided_by_id = user.id
    signal.decided_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(signal)  # updated_at moved on the server
    await audit.record(
        session,
        user.id,
        AuditAction.UPDATE,
        "signal",
        signal.id,
        before={"status": SignalStatus.NEW.value},
        after={"status": SignalStatus.DISMISSED.value},
    )
    return await _detail(session, user, scope, signal, request_id=request_id)


async def new_count(session: AsyncSession, user: User, academic_year: str) -> int:
    """NEW signals of the year touching the caller's scope (the dashboard's `signals_new`)."""
    scope = await _scope(session, user)
    stmt = _scoped(
        select(func.count())
        .select_from(Signal)
        .where(Signal.academic_year == academic_year, Signal.status == SignalStatus.NEW),
        scope,
    )
    return (await session.execute(stmt)).scalar_one()
