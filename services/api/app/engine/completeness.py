"""Completeness per college against the state admission authority (D40; API_CONTRACT §A4.18;
ENGINES §17.10).

The reconciliation of one institution and academic year reads the authority's joinings list
once, matches each joining to the institution's enrolments (any status) whose joining year
is that year, by programme code, date of birth and a name score of 90 or more, and stores
the result in `institution_scores`: `completeness_pct` (null when nothing joined) and, in
`components`, the counts and the missing students. Missing students raise or refresh one
MISSING_FROM_UPLOAD case per college and year (MEDIUM); the case's status is never changed
here, only officers decide it. The authority being unavailable keeps the last stored result
and says so.

Missing students are the college's own admitted students, so the college and officers see
their names, roll numbers, programmes and joining dates; an APAAR is only ever masked. The
case's evidence lists them by masked id only. Dashboards and reports read `institution_scores`
and never call the authority.

`python -m app.engine.completeness --academic-year 2026-27 [--institution 1-ABC-0001]`
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import AdapterError, AdapterSet
from app.core import audit, cohort
from app.core.audit import AuditEntry
from app.core.crypto import mask_apaar
from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine import matching, status
from app.engine.flags import dedupe_key, raise_flag
from app.engine.upload.types import INDIA
from app.models.credential import InstitutionScore
from app.models.enums import (
    AdmissionRoute,
    AuditAction,
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagType,
    Severity,
    UploadStatus,
    UserRole,
)
from app.models.geo import State
from app.models.institution import Approval, Institution, Programme
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import Check, Flag

NAME_MIN = 90
AUTHORITY = "State admission authority"
RECONCILIATION = "Reconciliation"
SCHEDULE = "AICTE reporting schedule"
NOT_IN_JOINING_RECORD = FlagType.NOT_IN_JOINING_RECORD.value


class DeadlineState(StrEnum):
    NOT_DUE = "NOT_DUE"
    ON_TIME = "ON_TIME"
    LATE = "LATE"
    OVERDUE = "OVERDUE"


class JoiningLike(Protocol):
    """One line of the authority's joinings list (`adapters.base.Joining`)."""

    roll_no: str | None
    name: str
    dob: date
    programme: str
    joined_on: date | None
    round: int | None
    route: str | None
    category: str | None
    apaar_last4: str | None


@dataclass(frozen=True, slots=True)
class UploadedFact:
    enrolment_id: uuid.UUID
    programme_code: str
    dob: date
    name_normalised: str


@dataclass(slots=True)
class Reconciliation:
    joined: int = 0
    uploaded_and_joined: int = 0
    missing: int = 0
    uploaded_not_joined: int = 0
    # name, roll_no, programme_code, joined_on, round, route, apaar_masked
    missing_students: list[dict[str, Any]] = field(default_factory=list)
    published: bool = False
    source_unavailable: bool = False
    first_upload_at: datetime | None = None
    completeness_pct: float | None = None
    case_raised: bool = False
    case_updated: bool = False


# ----------------------------------------------------------------------- pure parts


def match(
    joinings: Sequence[JoiningLike], uploaded: Sequence[UploadedFact]
) -> list[tuple[JoiningLike, uuid.UUID | None]]:
    """Pair each joining with at most one uploaded enrolment and each enrolment with at most
    one joining: same programme and date of birth, `match_names` 90 or more, best score
    first. Pure; the joinings come back in their order."""
    buckets: dict[tuple[str, date], list[UploadedFact]] = {}
    for fact in uploaded:
        buckets.setdefault((fact.programme_code.upper(), fact.dob), []).append(fact)
    candidates: list[tuple[int, int, int, uuid.UUID]] = []
    for i, joining in enumerate(joinings):
        bucket = buckets.get(((joining.programme or "").upper(), joining.dob), [])
        for j, fact in enumerate(bucket):
            score = matching.match_names(joining.name, fact.name_normalised).score
            if score >= NAME_MIN:
                candidates.append((-score, i, j, fact.enrolment_id))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    taken_joinings: dict[int, uuid.UUID] = {}
    taken_records: set[uuid.UUID] = set()
    for _score, i, _j, enrolment_id in candidates:
        if i in taken_joinings or enrolment_id in taken_records:
            continue
        taken_joinings[i] = enrolment_id
        taken_records.add(enrolment_id)
    return [(joining, taken_joinings.get(i)) for i, joining in enumerate(joinings)]


def deadline_state(deadline: date, first_upload_at: datetime | None, today: date) -> DeadlineState:
    """ON_TIME (first upload on or before the deadline, IST), LATE (after it), OVERDUE (no
    upload and the deadline has passed), NOT_DUE (no upload, deadline ahead). Pure."""
    if first_upload_at is not None:
        moment = first_upload_at if first_upload_at.tzinfo else first_upload_at.replace(tzinfo=UTC)
        uploaded_on = moment.astimezone(INDIA).date()
        return DeadlineState.ON_TIME if uploaded_on <= deadline else DeadlineState.LATE
    return DeadlineState.OVERDUE if today > deadline else DeadlineState.NOT_DUE


def joining_year(academic_year: str, year_of_study: int, route: AdmissionRoute) -> str:
    """The year the student joined this programme: the cohort year, or for a lateral
    entrant the year it entered year 2 (ENGINES §17.4)."""
    shared = getattr(cohort, "joining_year", None)
    if shared is not None:
        return shared(academic_year, year_of_study, route)
    first = 2 if route is AdmissionRoute.LATERAL else 1
    return cohort.year_label(cohort.start_year(academic_year) - max(year_of_study - first, 0))


def pct(uploaded_and_joined: int, joined: int) -> float | None:
    if joined == 0:
        return None
    return round(100 * uploaded_and_joined / joined, 1)


def pct_words(value: float | None) -> str:
    """One decimal, a trailing ".0" dropped (copy deck completeness.line)."""
    if value is None:
        return "not computed"
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def masked_id(student: dict[str, Any]) -> str:
    """The masked APAAR, else the roll number masked to its last four, never a full id."""
    if student.get("apaar_masked"):
        return str(student["apaar_masked"])
    roll = student.get("roll_no") or ""
    if roll:
        return f"Roll XXXX{roll[-4:]}"
    return "No id"


def today_ist() -> date:
    return datetime.now(INDIA).date()


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value.isoformat()


def _date(value: Any) -> date | None:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def missing_item(joining: JoiningLike) -> dict[str, Any]:
    joined_on = _date(joining.joined_on)
    return {
        "name": joining.name,
        "roll_no": joining.roll_no,
        "programme_code": joining.programme,
        "joined_on": joined_on.isoformat() if joined_on else None,
        "round": joining.round,
        "route": joining.route,
        "apaar_masked": mask_apaar(joining.apaar_last4),
    }


def case_key(institution_id: uuid.UUID, academic_year: str) -> str:
    return dedupe_key(FlagType.MISSING_FROM_UPLOAD, institution_id, academic_year)


def case_evidence(
    result: Reconciliation,
    *,
    state_name: str,
    institution_name: str,
    academic_year: str,
    deadline: date,
) -> dict[str, Any]:
    """Copy deck §5 MISSING_FROM_UPLOAD: the summary, the deck's four counts with the
    deadline, and the students by masked id."""
    deadline_words = ev.fmt_date(deadline)
    return {
        "summary": (
            f"{result.missing} students the {state_name} admission authority lists as joined "
            f"at {institution_name} in {academic_year} are not in the college's uploads."
        ),
        "facts": [
            ev.fact("Joined (authority)", result.joined, AUTHORITY),
            ev.fact("Uploaded and joined", result.uploaded_and_joined, RECONCILIATION),
            ev.fact("Missing", result.missing, RECONCILIATION),
            ev.fact("Completeness", f"{pct_words(result.completeness_pct)}%", RECONCILIATION),
            ev.fact("Reporting deadline", deadline_words, SCHEDULE),
            ev.fact(
                "Missing students",
                ", ".join(masked_id(s) for s in result.missing_students) or "None",
                AUTHORITY,
            ),
        ],
        "related_enrolment_ids": [],
        "rule_source": (
            f"State admission authority joining record; reporting deadline {deadline_words}"
        ),
    }


def _missing_in(evidence: dict[str, Any] | None) -> int:
    for item in (evidence or {}).get("facts") or []:
        if isinstance(item, dict) and item.get("label") == "Missing":
            try:
                return int(item.get("value") or 0)
            except ValueError:
                return 0
    return 0


# ------------------------------------------------------------------------- reads


async def first_upload_at(
    session: AsyncSession, institution_ids: Sequence[uuid.UUID], academic_year: str
) -> dict[uuid.UUID, datetime]:
    """The time of each institution's first DONE batch for the year (`uploaded_at`)."""
    if not institution_ids:
        return {}
    rows = await session.execute(
        select(UploadBatch.institution_id, func.min(UploadBatch.created_at))
        .where(
            UploadBatch.institution_id.in_(list(institution_ids)),
            UploadBatch.academic_year == academic_year,
            UploadBatch.status == UploadStatus.DONE,
        )
        .group_by(UploadBatch.institution_id)
    )
    return dict(rows.all())


async def _uploaded(
    session: AsyncSession, institution_id: uuid.UUID, academic_year: str
) -> list[UploadedFact]:
    rows = await session.execute(
        select(
            Enrolment.id,
            Enrolment.academic_year,
            Enrolment.year_of_study,
            Enrolment.admission_route,
            Programme.code,
            Student.dob,
            Student.name_normalized,
        )
        .join(Programme, Programme.id == Enrolment.programme_id)
        .join(Student, Student.id == Enrolment.student_id)
        .where(Enrolment.institution_id == institution_id)
    )
    return [
        UploadedFact(
            enrolment_id=r.id, programme_code=r.code, dob=r.dob, name_normalised=r.name_normalized
        )
        for r in rows.all()
        if joining_year(r.academic_year, r.year_of_study, r.admission_route) == academic_year
    ]


async def _uploaded_not_joined(
    session: AsyncSession, institution_id: uuid.UUID, academic_year: str
) -> int:
    """The institution's ACTIVE records of that joining year whose Joining record row is
    CONTRADICTED as not in the joining record."""
    rows = await session.execute(
        select(Enrolment.academic_year, Enrolment.year_of_study, Enrolment.admission_route)
        .join(Check, Check.enrolment_id == Enrolment.id)
        .where(
            Enrolment.institution_id == institution_id,
            Enrolment.status == EnrolmentStatus.ACTIVE,
            Check.type == CheckType.ADMISSION,
            Check.status == CheckStatus.CONTRADICTED,
            or_(
                Check.detail["basis"].astext == NOT_IN_JOINING_RECORD,
                Check.detail["case_type"].astext == NOT_IN_JOINING_RECORD,
            ),
        )
    )
    return sum(
        1
        for year, year_of_study, route in rows.all()
        if joining_year(year, year_of_study, route) == academic_year
    )


async def _stored(
    session: AsyncSession, institution_id: uuid.UUID, academic_year: str
) -> InstitutionScore | None:
    return (
        await session.execute(
            select(InstitutionScore)
            .where(
                InstitutionScore.institution_id == institution_id,
                InstitutionScore.academic_year == academic_year,
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


def _from_components(components: dict[str, Any], score: InstitutionScore | None) -> Reconciliation:
    return Reconciliation(
        joined=int(components.get("joined") or 0),
        uploaded_and_joined=int(components.get("uploaded_and_joined") or 0),
        missing=int(components.get("missing") or 0),
        uploaded_not_joined=int(components.get("uploaded_not_joined") or 0),
        missing_students=list(components.get("missing_students") or []),
        published=bool(components.get("published")),
        source_unavailable=bool(components.get("source_unavailable")),
        completeness_pct=float(score.completeness_pct)
        if score is not None and score.completeness_pct is not None
        else None,
    )


# ----------------------------------------------------------------------- the writer


async def _store(
    session: AsyncSession,
    institution_id: uuid.UUID,
    academic_year: str,
    result: Reconciliation,
    now: datetime,
) -> None:
    components = {
        "joined": result.joined,
        "uploaded_and_joined": result.uploaded_and_joined,
        "missing": result.missing,
        "uploaded_not_joined": result.uploaded_not_joined,
        "published": result.published,
        "source_unavailable": result.source_unavailable,
        "missing_students": result.missing_students,
    }
    value = Decimal(str(result.completeness_pct)) if result.completeness_pct is not None else None
    await session.execute(
        pg_insert(InstitutionScore)
        .values(
            id=uuid.uuid4(),
            institution_id=institution_id,
            academic_year=academic_year,
            completeness_pct=value,
            components=components,
            computed_at=now,
        )
        .on_conflict_do_update(
            index_elements=[InstitutionScore.institution_id, InstitutionScore.academic_year],
            set_={"completeness_pct": value, "components": components, "computed_at": now},
        )
    )


async def _refresh_case(
    session: AsyncSession,
    institution: Institution,
    state_name: str,
    academic_year: str,
    deadline: date,
    result: Reconciliation,
    actor_id: uuid.UUID | None,
) -> None:
    """Raise the MISSING_FROM_UPLOAD case, or refresh its evidence; never its status. A
    decided case whose missing students were partly uploaded gets the system note."""
    from app.cases.service import EVIDENCE_UPDATED_NOTE, add_system_note
    from app.engine.contracts import DECIDED_FLAG_STATUSES

    key = case_key(institution.id, academic_year)
    evidence = case_evidence(
        result,
        state_name=state_name,
        institution_name=institution.name,
        academic_year=academic_year,
        deadline=deadline,
    )
    existing = (
        await session.execute(
            select(Flag)
            .where(Flag.dedupe_key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if existing is None:
        if result.missing == 0:
            return
        raised = await raise_flag(
            session,
            type=FlagType.MISSING_FROM_UPLOAD,
            severity=Severity.MEDIUM,
            institution_id=institution.id,
            programme_id=None,
            enrolment_id=None,
            academic_year=academic_year,
            dedupe_key=key,
            evidence=evidence,
            actor_id=actor_id,
        )
        result.case_raised = raised.created
        return
    if existing.evidence == evidence:
        return
    before = _missing_in(existing.evidence)
    existing.evidence = evidence
    await session.flush()
    result.case_updated = True
    await audit.record(
        session,
        actor_id,
        AuditAction.UPDATE,
        "flag",
        existing.id,
        before={"missing": before},
        after={"missing": result.missing, "summary": evidence["summary"]},
    )
    if existing.status in DECIDED_FLAG_STATUSES:
        uploaded = before - result.missing
        note = (
            f"The college uploaded {uploaded} of the missing students on "
            f"{ev.fmt_date(today_ist())}; {result.missing} still missing."
            if uploaded > 0
            else EVIDENCE_UPDATED_NOTE
        )
        await add_system_note(session, existing, note)


async def reconcile(
    session: AsyncSession,
    adapters: AdapterSet | Any,
    institution_id: uuid.UUID,
    academic_year: str,
    *,
    actor_id: uuid.UUID | None = None,
) -> Reconciliation:
    """One joinings call; writes `institution_scores` and raises or refreshes the
    MISSING_FROM_UPLOAD case. Flushes, never commits."""
    institution = await session.get(Institution, institution_id)
    if institution is None:
        raise LookupError(f"institution {institution_id} does not exist")
    state = await session.get(State, institution.state_id)
    state_name = state.name if state is not None else ""
    deadline = get_rules().reporting.deadline_for(academic_year)
    now = datetime.now(UTC)
    first = (await first_upload_at(session, [institution_id], academic_year)).get(institution_id)

    authority = getattr(adapters, "admission_authority", None)
    try:
        if authority is None:
            raise AdapterError("admission_authority: no adapter")
        listed = await authority.joinings(
            institution_code=institution.aicte_permanent_id, academic_year=academic_year
        )
    except AdapterError:
        stored = await _stored(session, institution_id, academic_year)
        result = _from_components(dict(stored.components) if stored else {}, stored)
        result.source_unavailable = True
        result.first_upload_at = first
        await _store(session, institution_id, academic_year, result, now)
        return result

    joinings = list(listed.items)
    pairs = match(joinings, await _uploaded(session, institution_id, academic_year))
    missing = [missing_item(j) for j, enrolment_id in pairs if enrolment_id is None]
    result = Reconciliation(
        joined=len(joinings),
        uploaded_and_joined=len(joinings) - len(missing),
        missing=len(missing),
        uploaded_not_joined=await _uploaded_not_joined(session, institution_id, academic_year),
        missing_students=missing,
        published=bool(listed.published),
        source_unavailable=False,
        first_upload_at=first,
    )
    result.completeness_pct = pct(result.uploaded_and_joined, result.joined)
    await _store(session, institution_id, academic_year, result, now)
    await _refresh_case(session, institution, state_name, academic_year, deadline, result, actor_id)
    return result


async def institutions_for(session: AsyncSession, academic_year: str) -> list[uuid.UUID]:
    """Every institution with an approval for the year."""
    return list(
        (
            await session.execute(
                select(Programme.institution_id)
                .join(Approval, Approval.programme_id == Programme.id)
                .where(Approval.academic_year == academic_year)
                .distinct()
            )
        ).scalars()
    )


async def reconcile_all(
    factory: async_sessionmaker[AsyncSession],
    adapters: AdapterSet | Any,
    academic_year: str,
    *,
    concurrency: int = 8,
    institution_ids: Sequence[uuid.UUID] | None = None,
) -> dict[str, int]:
    """Every institution with an approval for the year, each in its own transaction that
    settles the statuses of the records its case names before it commits."""
    if institution_ids is None:
        async with factory() as session:
            institution_ids = await institutions_for(session, academic_year)
    gate = asyncio.Semaphore(max(1, concurrency))
    totals = {
        "institutions": 0,
        "missing": 0,
        "cases_raised": 0,
        "cases_updated": 0,
        "unavailable": 0,
    }

    async def one(institution_id: uuid.UUID) -> Reconciliation:
        async with gate, factory() as session:
            result = await reconcile(session, adapters, institution_id, academic_year)
            await status.commit(session)
            return result

    for result in await asyncio.gather(*(one(i) for i in institution_ids)):
        totals["institutions"] += 1
        totals["missing"] += result.missing
        totals["cases_raised"] += int(result.case_raised)
        totals["cases_updated"] += int(result.case_updated)
        totals["unavailable"] += int(result.source_unavailable)
    return totals


async def refresh_one(
    factory: async_sessionmaker[AsyncSession],
    institution_id: uuid.UUID,
    academic_year: str,
    *,
    adapters: AdapterSet | Any | None = None,
) -> int:
    """The worker's `countersign.refresh_completeness`: one college and year in its own
    transaction, settling the statuses it touched; returns how many students are missing."""
    from app.adapters.factory import build_adapters

    own = adapters is None
    adapters = adapters if adapters is not None else build_adapters()
    try:
        async with factory() as session:
            result = await reconcile(session, adapters, institution_id, academic_year)
            await status.commit(session)
        return result.missing
    finally:
        if own:
            await adapters.aclose()


async def case_for(
    session: AsyncSession, institution_ids: Sequence[uuid.UUID], academic_year: str
) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
    """The MISSING_FROM_UPLOAD case of each institution: (id, status)."""
    if not institution_ids:
        return {}
    keys = {case_key(i, academic_year): i for i in institution_ids}
    rows = await session.execute(
        select(Flag.dedupe_key, Flag.id, Flag.status).where(Flag.dedupe_key.in_(list(keys)))
    )
    return {keys[key]: (flag_id, flag_status.value) for key, flag_id, flag_status in rows.all()}


async def read(
    session: AsyncSession,
    user: User,
    institution: Institution,
    academic_year: str,
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """`GET /institutions/{id}/completeness` for an institution in the caller's scope; a
    university sees the counts only. Returning the missing students is audited."""
    stored = await _stored(session, institution.id, academic_year)
    result = _from_components(dict(stored.components) if stored else {}, stored)
    first = (await first_upload_at(session, [institution.id], academic_year)).get(institution.id)
    deadline = get_rules().reporting.deadline_for(academic_year)
    case = (await case_for(session, [institution.id], academic_year)).get(institution.id)
    missing = [] if user.role is UserRole.UNIVERSITY else result.missing_students
    if missing:
        await audit.record_many(
            session,
            [
                AuditEntry(
                    action=AuditAction.READ,
                    entity_type="institution_score",
                    entity_id=stored.id if stored else institution.id,
                    actor_id=user.id,
                    after={"via": "completeness", "missing": len(missing)},
                    request_id=request_id,
                )
            ],
        )
    return {
        "academic_year": academic_year,
        "joined": result.joined,
        "uploaded_and_joined": result.uploaded_and_joined,
        "missing": result.missing,
        "uploaded_not_joined": result.uploaded_not_joined,
        "completeness_pct": result.completeness_pct,
        "published": result.published,
        "deadline": deadline.isoformat(),
        "first_upload_at": _iso(first),
        "deadline_state": deadline_state(deadline, first, today_ist()).value,
        "computed_at": _iso(stored.computed_at) if stored else None,
        "source_unavailable": result.source_unavailable,
        "case": {"id": str(case[0]), "status": case[1]} if case else None,
        "missing_students": missing,
    }


async def missing_for_case(session: AsyncSession, flag: Flag) -> list[dict[str, Any]]:
    """The missing students of a MISSING_FROM_UPLOAD case, from its reconciliation."""
    if flag.type is not FlagType.MISSING_FROM_UPLOAD or not flag.academic_year:
        return []
    stored = await _stored(session, flag.institution_id, flag.academic_year)
    if stored is None:
        return []
    return list((stored.components or {}).get("missing_students") or [])


async def scores(
    session: AsyncSession, institution_ids: Sequence[uuid.UUID], academic_year: str
) -> dict[uuid.UUID, Reconciliation]:
    """The stored reconciliations of many institutions, for lists."""
    if not institution_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(InstitutionScore).where(
                    InstitutionScore.institution_id.in_(list(institution_ids)),
                    InstitutionScore.academic_year == academic_year,
                )
            )
        )
        .scalars()
        .all()
    )
    return {s.institution_id: _from_components(dict(s.components or {}), s) for s in rows}


# ------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.engine.completeness",
        description="Reconcile colleges' uploads with the state admission authority (D40).",
    )
    parser.add_argument("--academic-year", required=True, help="e.g. 2026-27")
    parser.add_argument("--institution", default=None, help="one AICTE permanent id")
    args = parser.parse_args(argv)
    from app.adapters.factory import build_adapters
    from app.db.session import dispose_engine, session_factory

    async def run() -> dict[str, int]:
        adapters = build_adapters()
        factory = session_factory()
        try:
            ids: list[uuid.UUID] | None = None
            if args.institution:
                async with factory() as session:
                    found = (
                        await session.execute(
                            select(Institution.id).where(
                                Institution.aicte_permanent_id == args.institution
                            )
                        )
                    ).scalar_one_or_none()
                if found is None:
                    raise SystemExit(f"no institution {args.institution}")
                ids = [found]
            return await reconcile_all(factory, adapters, args.academic_year, institution_ids=ids)
        finally:
            await adapters.aclose()
            await dispose_engine()

    totals = asyncio.run(run())
    print(
        f"{totals['institutions']} institutions reconciled; {totals['missing']} students "
        f"missing; {totals['cases_raised']} cases raised, {totals['cases_updated']} updated; "
        f"{totals['unavailable']} with the authority unavailable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
