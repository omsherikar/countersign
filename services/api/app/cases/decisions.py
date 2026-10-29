"""Officer decisions change the record, the seat and the attestation together (D43;
API_CONTRACT §A4.9, §A4.10; ENGINES §17.7).

UPHOLD: the college's claim stands; the row the case covers keeps its state with `resolved`
(R2), and an EXCESS_ADMISSION or QUOTA_BREACH case needs the approval version that covers
its admissions. CORRECT: named fields of one record are corrected, stored as a DECISION
version, and the record's five rows and the Seat Ledger run again. WITHDRAW: each chosen
record becomes WITHDRAWN "by decision", its seat is released to the pool's backlog and its
attestation revoked. A multi-record case closes only when no record it names is left
outstanding; UPHOLD always decides the whole case.

Everything runs in the caller's transaction and flushes, never commits; the statuses of the
records touched are queued with `status.mark` for the transaction owner to settle. The
`check_*` functions are the field rules and run before anything is written.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import credentials
from app.adapters.base import AdapterSet
from app.core import audit
from app.core.audit import AuditEntry
from app.core.cohort import cohort_year, start_year
from app.core.errors import ApiError
from app.core.rules import get_rules
from app.engine import checks, ledger, matching, status, versions
from app.engine.contracts import CHECK_ORDER, PoolRef
from app.engine.flags import refresh_seat_flags
from app.engine.upload import validate as upload_rules
from app.engine.upload.types import INDIA
from app.models.credential import Credential
from app.models.enums import (
    AdmissionRoute,
    AuditAction,
    CaseActionKind,
    Category,
    CheckStatus,
    CheckType,
    CredentialKind,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    RecordStatus,
    SeatEventKind,
    SeatStatus,
    SeatType,
    VersionSource,
)
from app.models.institution import Approval, ApprovalVersion, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import CaseAction, Check, Flag

Scope = Literal["RECORD", "MULTI_RECORD", "INSTITUTION"]

UPHOLD = CaseActionKind.UPHOLD
CORRECT = CaseActionKind.CORRECT
WITHDRAW = CaseActionKind.WITHDRAW
ESCALATE = CaseActionKind.ESCALATE
REQUEST_DOCS = CaseActionKind.REQUEST_DOCS

# the seat event and enrolment reason of a withdrawal (copy deck case.withdraw_change.status)
RELEASE_REASON = "withdrawn by decision"
CLAIM_WITHDRAWN = "CLAIM_WITHDRAWN"
# the revocation code of a withdrawn claim; FLAG_CONFIRMED (its Week 3 name) until the
# credentials package knows CLAIM_WITHDRAWN. Both hold: the record is never issued again on
# its own.
LEGACY_WITHDRAW_CODE = "FLAG_CONFIRMED"


@dataclass(frozen=True, slots=True)
class CaseRule:
    covers: CheckType | None
    scope: Scope
    correct: bool
    withdraw: bool
    uphold_needs_version: bool  # EXCESS_ADMISSION, QUOTA_BREACH


def _rule(
    covers: CheckType | None,
    scope: Scope = "RECORD",
    *,
    decide: bool = True,
    needs_version: bool = False,
) -> CaseRule:
    return CaseRule(covers, scope, decide, decide, needs_version)


# API_CONTRACT §A4.10
CASE_RULES: Mapping[FlagType, CaseRule] = {
    FlagType.EXCESS_ADMISSION: _rule(CheckType.SEAT, "MULTI_RECORD", needs_version=True),
    FlagType.QUOTA_BREACH: _rule(CheckType.SEAT, "MULTI_RECORD", needs_version=True),
    FlagType.ELIGIBILITY_BREACH: _rule(CheckType.SEAT),
    FlagType.LATE_REFILL: _rule(None),
    FlagType.INVALID_APAAR: _rule(CheckType.IDENTITY),
    FlagType.NAME_MISMATCH: _rule(CheckType.IDENTITY),
    FlagType.NOT_IN_JOINING_RECORD: _rule(CheckType.ADMISSION),
    FlagType.NO_ACADEMIC_ACTIVITY: _rule(CheckType.STUDYING),
    FlagType.STUDENT_DENIED: _rule(CheckType.STUDENT),
    FlagType.DUPLICATE_WITHIN_UPLOAD: _rule(None),
    FlagType.DUPLICATE_CROSS_INSTITUTION: _rule(None),
    FlagType.DUAL_ENROLMENT_ALLOWED: _rule(None),
    FlagType.GHOST_RING: _rule(None, "MULTI_RECORD"),
    FlagType.MISSING_FROM_UPLOAD: _rule(None, "INSTITUTION", decide=False),
    FlagType.ANOMALY: _rule(None, "INSTITUTION", decide=False),
}

# API_CONTRACT §A4.9; the words are copy deck §6 reason.<ACTION>.<CODE>
REASON_CODES: Mapping[CaseActionKind, tuple[str, ...]] = {
    UPHOLD: (
        "DOCUMENTS_SUPPORT_CLAIM",
        "SOURCE_RECORD_WRONG",
        "NAME_VARIANT",
        "PERMITTED_DUAL_PROGRAMME",
        "APPROVAL_VERSION_COVERS",
        "STUDENT_ANSWER_MISTAKEN",
        "MISSING_NOW_UPLOADED",
        "OTHER",
    ),
    CORRECT: ("UPLOAD_ERROR", "DOCUMENTS_SHOW_OTHER_VALUE", "WRONG_SEAT_CATEGORY", "OTHER"),
    WITHDRAW: (
        "STUDENT_NEVER_JOINED",
        "NO_JOINING_EVIDENCE",
        "BEYOND_APPROVED_INTAKE",
        "NOT_ELIGIBLE_FOR_SEAT",
        "DUPLICATE_RECORD",
        "NO_RESPONSE",
        "OTHER",
    ),
    ESCALATE: (
        "NEEDS_AICTE_DECISION",
        "POLICY_QUESTION",
        "SPANS_REGIONS",
        "REPEATED_PATTERN",
        "OTHER",
    ),
}
DOCS_KINDS: tuple[str, ...] = (
    "ADMISSION",
    "JOINING",
    "IDENTITY",
    "ELIGIBILITY",
    "CREDITS",
    "OTHER",
)
# copy deck docs_kind.<KIND>.words, used inside next_step and the document request email
DOCS_WORDS: Mapping[str, str] = {
    "ADMISSION": "admission documents",
    "JOINING": "the joining report",
    "IDENTITY": "identity documents",
    "ELIGIBILITY": "eligibility certificates",
    "CREDITS": "semester results",
    "OTHER": "documents",
}


@dataclass(frozen=True, slots=True)
class FieldSpec:
    word: str  # copy deck field.<key>
    target: Literal["student", "enrolment", "eligibility"]


# API_CONTRACT §A4.9: what an officer may correct
CORRECTABLE: Mapping[str, FieldSpec] = {
    "name": FieldSpec("Name", "student"),
    "dob": FieldSpec("Date of birth", "student"),
    "year_of_study": FieldSpec("Year of study", "enrolment"),
    "admission_route": FieldSpec("Admission route", "enrolment"),
    "category": FieldSpec("Category", "enrolment"),
    "counselling_ref": FieldSpec("Counselling reference", "enrolment"),
    "admission_date": FieldSpec("Admission date", "enrolment"),
    "tfw_income_certified": FieldSpec("TFW income certificate", "eligibility"),
    "nri_sponsored": FieldSpec("NRI sponsored", "eligibility"),
    "ciwg": FieldSpec("CIWG", "eligibility"),
}
# field words of what the upload alone changes, for the refusal message
UPLOAD_ONLY_WORDS: Mapping[str, str] = {
    "apaar_id": "APAAR",
    "apaar_masked": "APAAR",
    "passport_no": "Passport number",
    "mobile": "Mobile",
    "email": "Email",
    "address": "Address",
    "programme_code": "Programme code",
    "status": "Status",
    "status_date": "Status date",
}
COUNSELLING_REF_MAX = 100
YES = {"YES", "Y", "TRUE", "1"}
NO = {"NO", "N", "FALSE", "0"}


@dataclass(slots=True)
class Effects:
    """API_CONTRACT §A4.9 `effects`: every consequence of the action with its real values."""

    case_status: FlagStatus
    records: list[dict[str, Any]] = field(default_factory=list)
    version: int | None = None
    changes: list[dict[str, Any]] = field(default_factory=list)
    rows_resolved: int = 0
    rows_rerun: int = 0
    seats_released: list[dict[str, str]] = field(default_factory=list)
    seats_assigned: list[dict[str, str]] = field(default_factory=list)
    attestations_revoked: list[dict[str, str]] = field(default_factory=list)
    attestations_issued: list[dict[str, str]] = field(default_factory=list)
    approval: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_status": self.case_status.value,
            "records": self.records,
            "version": self.version,
            "changes": self.changes,
            "rows_resolved": self.rows_resolved,
            "rows_rerun": self.rows_rerun,
            "seats_released": self.seats_released,
            "seats_assigned": self.seats_assigned,
            "attestations_revoked": self.attestations_revoked,
            "attestations_issued": self.attestations_issued,
            "approval": self.approval,
        }


@dataclass(slots=True)
class Tracker:
    """What the records an action may touch looked like before it, so the effects can name
    every record whose status, record status or next step changed and every attestation
    revoked or issued, once the statuses are settled."""

    states: dict[uuid.UUID, tuple[EnrolmentStatus, RecordStatus, str | None]] = field(
        default_factory=dict
    )
    live: dict[uuid.UUID, tuple[uuid.UUID, str]] = field(default_factory=dict)

    async def remember(self, session: AsyncSession, ids: Sequence[uuid.UUID | None]) -> None:
        new = [i for i in dict.fromkeys(ids) if i is not None and i not in self.states]
        if not new:
            return
        for enrolment_id, state, record_status, next_step in (
            await session.execute(
                select(
                    Enrolment.id, Enrolment.status, Enrolment.record_status, Enrolment.next_step
                ).where(Enrolment.id.in_(new))
            )
        ).all():
            self.states[enrolment_id] = (state, record_status, next_step)
        for credential_id, enrolment_id, short_id in (
            await session.execute(
                select(Credential.id, Credential.enrolment_id, Credential.short_id).where(
                    Credential.enrolment_id.in_(new),
                    Credential.kind == CredentialKind.ENROLMENT,
                    Credential.revoked.is_(False),
                )
            )
        ).all():
            self.live[credential_id] = (enrolment_id, short_id)

    async def finish(self, session: AsyncSession, effects: Effects, *, decision: bool) -> None:
        """Fill `records`, `attestations_revoked` and `attestations_issued` from the stored
        values; call after the statuses are settled."""
        ids = list(self.states)
        if not ids:
            return
        now = {
            r.id: r
            for r in (
                await session.execute(
                    select(
                        Enrolment.id,
                        Enrolment.status,
                        Enrolment.record_status,
                        Enrolment.status_reason,
                        Enrolment.next_step,
                    )
                    .where(Enrolment.id.in_(ids))
                    .execution_options(populate_existing=True)
                )
            ).all()
        }
        for enrolment_id, (state, record_status, next_step) in self.states.items():
            row = now.get(enrolment_id)
            if row is None:
                continue
            moved = (row.status, row.record_status) != (state, record_status)
            if not moved and (decision or row.next_step == next_step):
                continue
            active = row.status is EnrolmentStatus.ACTIVE
            effects.records.append(
                {
                    "enrolment_id": str(enrolment_id),
                    "status": row.status.value,
                    "record_status": row.record_status.value if active else None,
                    "status_reason": row.status_reason if active else None,
                }
            )
        credentials_now = (
            await session.execute(
                select(
                    Credential.id, Credential.enrolment_id, Credential.short_id, Credential.revoked
                ).where(
                    Credential.enrolment_id.in_(ids), Credential.kind == CredentialKind.ENROLMENT
                )
            )
        ).all()
        for credential_id, enrolment_id, short_id, revoked in credentials_now:
            item = {
                "enrolment_id": str(enrolment_id),
                "credential_id": str(credential_id),
                "short_id": short_id,
            }
            if credential_id in self.live and revoked:
                effects.attestations_revoked.append(item)
            elif credential_id not in self.live and not revoked:
                effects.attestations_issued.append(item)


# ------------------------------------------------------------------------ errors


def invalid(field_name: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{field_name}: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": field_name, "message": message}]},
    )


def not_available(flag: Flag, action: CaseActionKind, allowed: Sequence[str]) -> ApiError:
    from app.cases.service import FLAG_NAMES

    return ApiError(
        409,
        "DECISION_NOT_AVAILABLE",
        f"This decision does not apply to a {FLAG_NAMES.get(flag.type, flag.type.value)} case.",
        {"action": action.value, "type": flag.type.value, "allowed_actions": list(allowed)},
    )


def _not_named(n: int, named: Sequence[uuid.UUID]) -> ApiError:
    return ApiError(
        409,
        "WITHDRAW_NOT_NAMED",
        f"{n} of the selected records are not named by this case.",
        {"n": n, "named_enrolment_ids": [str(i) for i in named]},
    )


def _none_selected() -> ApiError:
    return ApiError(422, "WITHDRAW_NONE_SELECTED", "Select at least one record to withdraw.")


class _Invalid(ValueError):
    pass


# ------------------------------------------------------------------- the case rules


def rule_of(flag: Flag) -> CaseRule:
    return CASE_RULES.get(flag.type, _rule(None))


def available(flag: Flag, action: CaseActionKind) -> bool:
    """Whether the decision applies to the case's type (§A4.10); other actions always do."""
    rule = rule_of(flag)
    if action is CORRECT:
        return rule.correct
    if action is WITHDRAW:
        return rule.withdraw
    return True


def named_ids(flag: Flag) -> list[uuid.UUID]:
    return status.named_enrolments(flag)


async def named_records(session: AsyncSession, flag: Flag) -> list[Enrolment]:
    """The records the case names at its own institution, in the case's order."""
    ids = named_ids(flag)
    if not ids:
        return []
    rows = (
        (
            await session.execute(
                select(Enrolment).where(
                    Enrolment.id.in_(ids), Enrolment.institution_id == flag.institution_id
                )
            )
        )
        .scalars()
        .all()
    )
    order = {i: n for n, i in enumerate(ids)}
    return sorted(rows, key=lambda e: order[e.id])


async def _corrected_by(session: AsyncSession, flag: Flag) -> set[uuid.UUID]:
    """The records this case's CORRECT actions changed."""
    rows = (
        await session.execute(
            select(CaseAction.correction).where(
                CaseAction.flag_id == flag.id, CaseAction.action == CORRECT
            )
        )
    ).scalars()
    out: set[uuid.UUID] = set()
    for correction in rows:
        if isinstance(correction, dict) and correction.get("enrolment_id"):
            out.add(uuid.UUID(str(correction["enrolment_id"])))
    return out


async def outstanding(session: AsyncSession, flag: Flag) -> list[uuid.UUID]:
    """The named records of a multi-record case still to decide (§A4.10): ACTIVE, at the
    case's institution, and with the covered row unresolved-contradicted (for a ring: not
    withdrawn or corrected by this case). `[]` for every other case."""
    rule = rule_of(flag)
    if rule.scope != "MULTI_RECORD":
        return []
    records = [e for e in await named_records(session, flag) if e.status is EnrolmentStatus.ACTIVE]
    if not records:
        return []
    if rule.covers is None:
        corrected = await _corrected_by(session, flag)
        return [e.id for e in records if e.id not in corrected]
    open_rows = set(
        (
            await session.execute(
                select(Check.enrolment_id).where(
                    Check.enrolment_id.in_([e.id for e in records]),
                    Check.type == rule.covers,
                    Check.status == CheckStatus.CONTRADICTED,
                    Check.resolved.is_(None),
                )
            )
        ).scalars()
    )
    return [e.id for e in records if e.id in open_rows]


# ------------------------------------------------------------ seat cases and versions


@dataclass(frozen=True, slots=True)
class SeatCase:
    approval: Approval
    programme: Programme
    cohort_year: str
    pools: tuple[SeatType, ...]
    unseated: int

    @property
    def covers(self) -> bool:
        """The current version covers the admissions: the case's pool has no ACTIVE cohort
        enrolment without a seat (the backlog was seated when the version was added)."""
        return self.unseated == 0


async def seat_case(session: AsyncSession, flag: Flag) -> SeatCase | None:
    """The approval behind an EXCESS_ADMISSION or QUOTA_BREACH case, read from its key
    (`<TYPE>:<programme_id>:<cohort_year>:<seat_type>`)."""
    if not rule_of(flag).uphold_needs_version:
        return None
    parts = flag.dedupe_key.split(":")
    if len(parts) < 4:
        return None
    try:
        programme_id = uuid.UUID(parts[1])
        seat_type = SeatType(parts[3])
    except ValueError:
        return None
    cohort = parts[2]
    row = (
        await session.execute(
            select(Approval, Programme)
            .join(Programme, Programme.id == Approval.programme_id)
            .where(Approval.programme_id == programme_id, Approval.academic_year == cohort)
        )
    ).first()
    if row is None:
        return None
    approval, programme = row
    pools: tuple[SeatType, ...] = (
        (SeatType.REGULAR, SeatType.NRI) if flag.type is FlagType.EXCESS_ADMISSION else (seat_type,)
    )
    rules = get_rules()
    routes = [r for r in AdmissionRoute if ledger.target_seat_type(r, rules) in pools]
    unseated = (
        await session.execute(
            select(Enrolment.id).where(
                Enrolment.programme_id == programme_id,
                Enrolment.cohort_year == cohort,
                Enrolment.status == EnrolmentStatus.ACTIVE,
                Enrolment.admission_route.in_(routes),
                Enrolment.seat_id.is_(None),
            )
        )
    ).all()
    return SeatCase(approval, programme, cohort, pools, len(unseated))


async def approval_view(session: AsyncSession, flag: Flag) -> dict[str, Any] | None:
    """FlagDetail `approval` (§A4.11) for EXCESS_ADMISSION and QUOTA_BREACH, else None."""
    found = await seat_case(session, flag)
    if found is None:
        return None
    return {
        "id": str(found.approval.id),
        "current_version": found.approval.current_version,
        "approved_intake": found.approval.approved_intake,
        "covers": found.covers,
    }


async def check_uphold(
    session: AsyncSession, flag: Flag, approval_version: int | None
) -> dict[str, Any] | None:
    """For a case that needs one, the covering approval version (`effects.approval`):
    422 without a version, 409 UPHOLD_NEEDS_VERSION when it does not cover."""
    if not rule_of(flag).uphold_needs_version:
        return None
    if approval_version is None:
        raise invalid(
            "approval_version", "Choose the approval version that covers these admissions."
        )
    found = await seat_case(session, flag)
    current = found.approval.current_version if found else None
    if found is None or approval_version != current or not found.covers:
        raise ApiError(
            409,
            "UPHOLD_NEEDS_VERSION",
            "This case can be upheld only when an approval version covers these admissions.",
            {"current_version": current, "covers": False},
        )
    intake = (
        await session.execute(
            select(ApprovalVersion.approved_intake).where(
                ApprovalVersion.approval_id == found.approval.id,
                ApprovalVersion.version == approval_version,
            )
        )
    ).scalar_one_or_none()
    return {
        "version": approval_version,
        "approved_intake": intake if intake is not None else found.approval.approved_intake,
        "cohort_year": found.cohort_year,
        "programme_code": found.programme.code,
    }


# --------------------------------------------------------------------- withdrawals


async def check_withdraw(
    session: AsyncSession, flag: Flag, enrolment_ids: Sequence[uuid.UUID] | None
) -> list[uuid.UUID]:
    """The records to withdraw: each named by the case, at its institution and ACTIVE."""
    records = await named_records(session, flag)
    multi = rule_of(flag).scope == "MULTI_RECORD"
    if enrolment_ids is None:
        if multi:
            raise _none_selected()
        if flag.enrolment_id is not None and any(e.id == flag.enrolment_id for e in records):
            enrolment_ids = [flag.enrolment_id]
        elif len(records) == 1:
            enrolment_ids = [records[0].id]
        else:
            raise _none_selected()
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        raise _none_selected()
    active = [e.id for e in records if e.status is EnrolmentStatus.ACTIVE]
    wrong = [i for i in ids if i not in active]
    if wrong:
        raise _not_named(len(wrong), active)
    return ids


async def _lock(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[tuple[Enrolment, Student]]:
    rows = (
        await session.execute(
            select(Enrolment, Student)
            .join(Student, Student.id == Enrolment.student_id)
            .where(Enrolment.id.in_(list(ids)))
            .order_by(Enrolment.id)
            .with_for_update(of=Enrolment)
            .execution_options(populate_existing=True)
        )
    ).all()
    order = {i: n for n, i in enumerate(ids)}
    return sorted(((e, s) for e, s in rows), key=lambda pair: order[pair[0].id])


async def _pool_of(session: AsyncSession, enrolment: Enrolment) -> PoolRef | None:
    """The pool the enrolment's route targets in its cohort approval."""
    approval_id = (
        await session.execute(
            select(Approval.id).where(
                Approval.programme_id == enrolment.programme_id,
                Approval.academic_year == enrolment.cohort_year,
            )
        )
    ).scalar_one_or_none()
    if approval_id is None:
        return None
    return PoolRef(
        approval_id=approval_id, seat_type=ledger.target_seat_type(enrolment.admission_route)
    )


async def _release(
    session: AsyncSession,
    enrolment: Enrolment,
    actor_id: uuid.UUID,
    on: date,
    entries: list[AuditEntry],
) -> tuple[str, SeatPool] | None:
    """Free the enrolment's seat with the reason "withdrawn by decision"; the seat code and
    its pool, or None when it held none."""
    if enrolment.seat_id is None:
        return None
    row = (
        await session.execute(
            select(Seat, SeatPool)
            .join(SeatPool, SeatPool.id == Seat.pool_id)
            .where(Seat.id == enrolment.seat_id)
            .with_for_update(of=Seat)
        )
    ).first()
    if row is None:
        return None
    seat, pool = row
    before_status, before_holder = seat.status, seat.enrolment_id
    seat.status = SeatStatus.FREE
    seat.enrolment_id = None
    enrolment.seat_id = None
    session.add(
        SeatEvent(
            seat_id=seat.id,
            enrolment_id=enrolment.id,
            kind=SeatEventKind.RELEASE,
            actor_id=actor_id,
            reason=RELEASE_REASON,
            effective_date=on,
        )
    )
    entries.append(
        ledger._seat_entry(
            seat, before_status, before_holder, SeatEventKind.RELEASE, RELEASE_REASON, on, actor_id
        )
    )
    return seat.seat_code, pool


async def _backlog(session: AsyncSession, pool: SeatPool) -> list[uuid.UUID]:
    """The ACTIVE cohort enrolments of the pool still without a seat."""
    approval = await session.get(Approval, pool.approval_id)
    if approval is None:
        return []
    rules = get_rules()
    routes = [r for r in AdmissionRoute if ledger.target_seat_type(r, rules) is pool.seat_type]
    return list(
        (
            await session.execute(
                select(Enrolment.id).where(
                    Enrolment.programme_id == approval.programme_id,
                    Enrolment.cohort_year == approval.academic_year,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                    Enrolment.admission_route.in_(routes),
                    Enrolment.seat_id.is_(None),
                )
            )
        ).scalars()
    )


async def _seat_codes(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Enrolment.id, Seat.seat_code)
        .join(Seat, Seat.id == Enrolment.seat_id)
        .where(Enrolment.id.in_(list(ids)))
    )
    return dict(rows.all())


def withdraw_code() -> str:
    codes = getattr(credentials, "SYSTEM_REASON_CODES", ())
    return CLAIM_WITHDRAWN if CLAIM_WITHDRAWN in codes else LEGACY_WITHDRAW_CODE


async def _rerun(
    session: AsyncSession,
    enrolment_ids: Sequence[uuid.UUID],
    adapters: AdapterSet | None,
    *,
    types: Sequence[CheckType],
    actor_id: uuid.UUID,
) -> int:
    """Evaluate the chosen rows of the ACTIVE records again (`checks.rerun`); returns how
    many rows were evaluated."""
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return 0
    rerun = getattr(checks, "rerun", None)
    if rerun is not None:
        result = await rerun(session, ids, adapters, types=list(types), actor_id=actor_id)
        return result.enrolments * len(types)
    if set(types) == set(CHECK_ORDER) and adapters is not None:
        result = await checks.run_checks(session, ids, adapters, actor_id=actor_id)
        return result.enrolments * len(types)
    # rows that call no source (SEAT): the writer of run_checks, without the adapters
    subjects = await checks.load_subjects(session, ids)
    if not subjects:
        return 0
    existing = await checks._existing_checks(
        session, [s.enrolment_id for s in subjects], list(types)
    )
    gate = asyncio.Semaphore(1)
    writer = checks._Writer(session, existing, actor_id)
    for subject in subjects:
        outcomes = await checks.evaluate_subject(subject, adapters, gate, list(types))  # type: ignore[arg-type]
        await writer.write(subject, outcomes)
    await writer.finish()
    return len(subjects) * len(types)


def today_ist() -> date:
    return datetime.now(INDIA).date()


def _version_entry(version: Any, actor_id: uuid.UUID, changed: Sequence[str]) -> AuditEntry:
    return AuditEntry(
        action=AuditAction.UPDATE,
        entity_type="enrolment",
        entity_id=version.enrolment_id,
        actor_id=actor_id,
        after={
            "version": version.version,
            "source": VersionSource.DECISION.value,
            "changed": list(changed),
        },
    )


async def withdraw(
    session: AsyncSession,
    flag: Flag,
    user: User,
    row: CaseAction,
    *,
    enrolment_ids: Sequence[uuid.UUID],
    adapters: AdapterSet | None = None,
    tracker: Tracker | None = None,
) -> Effects:
    """Each record: a DECISION version, WITHDRAWN with today's status date, its seat freed
    to the backlog, its attestation revoked. Then the backlog's Seat rows run again and the
    seat cases of the touched pools are refreshed. `ids` come from `check_withdraw`."""
    effects = Effects(case_status=flag.status)
    on = today_ist()
    entries: list[AuditEntry] = []
    pairs = await _lock(session, enrolment_ids)
    if tracker is not None:
        await tracker.remember(session, [e.id for e, _ in pairs])
    pools: set[PoolRef] = set()
    released_pools: list[SeatPool] = []
    code = withdraw_code()
    for enrolment, student in pairs:
        before = versions.snapshot(enrolment, student)
        target = await _pool_of(session, enrolment)
        if target is not None:
            pools.add(target)
        released = await _release(session, enrolment, user.id, on, entries)
        if released is not None:
            seat_code, pool = released
            effects.seats_released.append(
                {"enrolment_id": str(enrolment.id), "seat_code": seat_code}
            )
            pools.add(PoolRef(approval_id=pool.approval_id, seat_type=pool.seat_type))
            released_pools.append(pool)
        previous = enrolment.status
        enrolment.status = EnrolmentStatus.WITHDRAWN
        enrolment.status_date = on
        changes = versions.diff(before, versions.snapshot(enrolment, student))
        written = await versions.record(
            session,
            versions.VersionWrite(
                enrolment_id=enrolment.id,
                changes=changes,
                source=VersionSource.DECISION,
                case_action_seq=row.seq,
                actor_id=user.id,
            ),
        )
        if written is not None:
            if effects.version is None:
                effects.version = written.version
            entries.append(_version_entry(written, user.id, list(changes)))
        entries.append(
            AuditEntry(
                action=AuditAction.UPDATE,
                entity_type="enrolment",
                entity_id=enrolment.id,
                actor_id=user.id,
                before={"status": previous.value, "record_status": enrolment.record_status.value},
                after={
                    "status": EnrolmentStatus.WITHDRAWN.value,
                    "record_status": enrolment.record_status.value,
                },
            )
        )
        await credentials.revoke_for_enrolment(
            session, enrolment.id, code, user.id, audit_sink=entries
        )
    await session.flush()

    backlog: list[uuid.UUID] = []
    for pool in released_pools:
        backlog.extend(await _backlog(session, pool))
    if tracker is not None:
        await tracker.remember(session, backlog)
    seated: list[uuid.UUID] = []
    if backlog:
        result = await ledger.assign_seats(session, backlog, actor_id=user.id)
        seated = list(dict.fromkeys(result.seated))
        pools |= result.touched_pools
    codes = await _seat_codes(session, seated)
    effects.seats_assigned = [
        {"enrolment_id": str(i), "seat_code": codes[i]} for i in seated if i in codes
    ]
    await audit.record_many(session, entries)
    effects.rows_rerun = await _rerun(
        session, seated, adapters, types=[CheckType.SEAT], actor_id=user.id
    )
    if pools:
        await refresh_seat_flags(session, sorted(pools, key=_pool_key), actor_id=user.id)
    status.mark(session, [*(e.id for e, _ in pairs), *seated, *named_ids(flag)])
    return effects


def _pool_key(ref: PoolRef) -> tuple[str, str]:
    return (str(ref.approval_id), SeatType(ref.seat_type).value)


# --------------------------------------------------------------------- corrections


@dataclass(frozen=True, slots=True)
class CorrectionPlan:
    enrolment_id: uuid.UUID
    values: dict[str, Any]  # field -> parsed value
    changes: dict[str, list[Any]]  # versioned field -> [before, after]


def _correction_invalid(key: str, message: str) -> ApiError:
    spec = CORRECTABLE.get(key)
    word = spec.word if spec else UPLOAD_ONLY_WORDS.get(key, key)
    return ApiError(422, "CORRECTION_INVALID", f"{word}: {message}", {"field": key})


def _iso_date(raw: Any, word: str) -> date:
    text = raw.isoformat() if isinstance(raw, date) else str(raw if raw is not None else "")
    parsed = upload_rules.parse_iso_date(text.strip())
    if parsed is None:
        raise _Invalid(f"{word} must be YYYY-MM-DD")
    return parsed


def _marker(raw: Any, word: str) -> bool | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().upper()
    if text in YES:
        return True
    if text in NO:
        return False
    raise _Invalid(f"{word} must be yes or no")


def _enum(raw: Any, enum_cls: Any, key: str) -> Any:
    if isinstance(raw, str) and raw.strip():
        try:
            return enum_cls(upload_rules.enum_key(raw))
        except ValueError:
            pass
    raise _Invalid(upload_rules.BAD_ENUM_MESSAGES[key])


async def check_correct(
    session: AsyncSession, flag: Flag, correction: Mapping[str, Any] | None
) -> CorrectionPlan:
    """The record to correct and the parsed new values (§A4.9 field rules)."""
    if not isinstance(correction, Mapping) or not isinstance(correction.get("fields"), Mapping):
        raise invalid("correction", "Choose a record and the fields to correct.")
    records = await named_records(session, flag)
    active = [e for e in records if e.status is EnrolmentStatus.ACTIVE]
    raw_id = correction.get("enrolment_id")
    if raw_id is None:
        if rule_of(flag).scope == "MULTI_RECORD" or len(records) != 1:
            if flag.enrolment_id is not None and any(e.id == flag.enrolment_id for e in records):
                raw_id = flag.enrolment_id
            else:
                raise invalid("correction.enrolment_id", "Choose the record to correct.")
        else:
            raw_id = records[0].id
    try:
        enrolment_id = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
    except ValueError:
        raise _not_named(1, [e.id for e in active]) from None
    if enrolment_id not in {e.id for e in active}:
        raise _not_named(1, [e.id for e in active])
    fields_in: Mapping[str, Any] = correction["fields"]
    if not fields_in:
        raise ApiError(
            422, "CORRECTION_EMPTY", "Change at least one field, or choose another decision."
        )
    for key in fields_in:
        if key not in CORRECTABLE:
            raise _correction_invalid(
                key, "This field is not corrected by a decision; the college uploads the row again."
            )

    enrolment, student = (await _lock(session, [enrolment_id]))[0]
    programme = await session.get(Programme, enrolment.programme_id)
    assert programme is not None
    approval_years = set(
        (
            await session.execute(
                select(Approval.academic_year).where(Approval.programme_id == programme.id)
            )
        ).scalars()
    )
    today = today_ist()
    values: dict[str, Any] = {}
    # year of study first: the date of birth is judged against the cohort it gives
    order = sorted(fields_in, key=lambda k: (k != "year_of_study", list(CORRECTABLE).index(k)))
    year = enrolment.year_of_study
    for key in order:
        raw = fields_in[key]
        try:
            if key == "name":
                if not isinstance(raw, str) or not raw.strip():
                    raise _Invalid("Name is required")
                if len(raw.strip()) > upload_rules.NAME_MAX:
                    raise _Invalid(f"Name must be at most {upload_rules.NAME_MAX} characters")
                values[key] = " ".join(raw.split())
            elif key == "year_of_study":
                limit = programme.duration_years
                text = str(raw).strip() if not isinstance(raw, bool) and raw is not None else ""
                if not text.isdigit() or not 1 <= int(text) <= limit:
                    raise _Invalid(f"Year of study must be a whole number between 1 and {limit}")
                year = int(text)
                cohort = cohort_year(enrolment.academic_year, year)
                if cohort not in approval_years:
                    raise _Invalid(
                        f"{programme.code} has no approval for {cohort}, the intake of a year "
                        f"{year} student in {enrolment.academic_year}"
                    )
                values[key] = year
            elif key == "dob":
                dob = _iso_date(raw, "Date of birth")
                intake = start_year(cohort_year(enrolment.academic_year, year))
                age = upload_rules.age_on(dob, date(intake, 7, 1))
                if dob > today or not upload_rules.MIN_AGE <= age <= upload_rules.MAX_AGE:
                    raise _Invalid(
                        f"Date of birth {dob.isoformat()} gives an age of {age} at admission; "
                        f"expected {upload_rules.MIN_AGE} to {upload_rules.MAX_AGE}"
                    )
                values[key] = dob
            elif key == "admission_route":
                values[key] = _enum(raw, AdmissionRoute, key)
            elif key == "category":
                values[key] = _enum(raw, Category, key)
            elif key == "counselling_ref":
                text = "" if raw is None else str(raw).strip()
                if len(text) > COUNSELLING_REF_MAX:
                    raise _Invalid(
                        f"Counselling reference must be at most {COUNSELLING_REF_MAX} characters"
                    )
                values[key] = text or None
            elif key == "admission_date":
                admitted = _iso_date(raw, "Admission date")
                if admitted > today:
                    raise _Invalid(f"Admission date {admitted.isoformat()} is after today")
                values[key] = admitted
            else:
                values[key] = _marker(raw, CORRECTABLE[key].word)
        except _Invalid as exc:
            raise _correction_invalid(key, str(exc)) from None

    before = versions.snapshot(enrolment, student)
    after = dict(before)
    for key, value in values.items():
        after[key] = versions._json(value)
    changes = versions.diff(before, after)
    if not changes:
        raise ApiError(
            422, "CORRECTION_EMPTY", "Change at least one field, or choose another decision."
        )
    return CorrectionPlan(enrolment_id=enrolment_id, values=values, changes=changes)


def _apply(enrolment: Enrolment, student: Student, values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        target = CORRECTABLE[key].target
        if key == "name":
            student.name = value
            student.name_normalized = matching.normalise_name(value)
            student.name_key = matching.name_key(value, student.dob)
        elif key == "dob":
            student.dob = value
            student.name_key = matching.name_key(student.name, value)
        elif key == "year_of_study":
            enrolment.year_of_study = value
            enrolment.cohort_year = cohort_year(enrolment.academic_year, value)
        elif target == "eligibility":
            enrolment.eligibility = {**(enrolment.eligibility or {}), key: value}
        else:
            setattr(enrolment, key, value)


async def correct(
    session: AsyncSession,
    flag: Flag,
    user: User,
    row: CaseAction,
    *,
    plan: CorrectionPlan,
    adapters: AdapterSet | None,
    tracker: Tracker | None = None,
) -> Effects:
    """Apply the correction, store it as a DECISION version, run the Seat Ledger for the
    record and evaluate its five rows again (the sources are called inside the request)."""
    effects = Effects(case_status=flag.status)
    entries: list[AuditEntry] = []
    enrolment, student = (await _lock(session, [plan.enrolment_id]))[0]
    if tracker is not None:
        await tracker.remember(session, [enrolment.id])
    held = await _seat_codes(session, [enrolment.id])
    old_pool = await _pool_of(session, enrolment)
    _apply(enrolment, student, plan.values)
    await session.flush()
    written = await versions.record(
        session,
        versions.VersionWrite(
            enrolment_id=enrolment.id,
            changes=plan.changes,
            source=VersionSource.DECISION,
            case_action_seq=row.seq,
            actor_id=user.id,
        ),
    )
    if written is not None:
        effects.version = written.version
        entries.append(_version_entry(written, user.id, list(plan.changes)))
    effects.changes = [
        {"field": key, "before": pair[0], "after": pair[1]} for key, pair in plan.changes.items()
    ]
    row.correction = {
        "enrolment_id": str(enrolment.id),
        "fields": {key: versions._json(value) for key, value in plan.values.items()},
    }

    result = await ledger.assign_seats(session, [enrolment.id], actor_id=user.id)
    pools = set(result.touched_pools)
    new_pool = await _pool_of(session, enrolment)
    pools |= {p for p in (old_pool, new_pool) if p is not None}
    if enrolment.id in result.released and enrolment.id in held:
        effects.seats_released.append(
            {"enrolment_id": str(enrolment.id), "seat_code": held[enrolment.id]}
        )
    seated = list(dict.fromkeys(result.seated))
    if tracker is not None:
        await tracker.remember(session, seated)
    codes = await _seat_codes(session, seated)
    effects.seats_assigned = [
        {"enrolment_id": str(i), "seat_code": codes[i]} for i in seated if i in codes
    ]
    await audit.record_many(session, entries)
    effects.rows_rerun = await _rerun(
        session, [enrolment.id], adapters, types=CHECK_ORDER, actor_id=user.id
    )
    others = [i for i in seated if i != enrolment.id]
    effects.rows_rerun += await _rerun(
        session, others, adapters, types=[CheckType.SEAT], actor_id=user.id
    )
    if pools:
        await refresh_seat_flags(session, sorted(pools, key=_pool_key), actor_id=user.id)
    status.mark(session, [enrolment.id, *seated, *named_ids(flag)])
    return effects


# ------------------------------------------------------------------------- uphold


async def uphold(
    session: AsyncSession,
    flag: Flag,
    user: User,
    row: CaseAction,
    *,
    approval: dict[str, Any] | None,
    tracker: Tracker | None = None,
) -> Effects:
    """The college's claim stands: the covered rows of the named ACTIVE records keep their
    state and carry `resolved` (R2). `approval` comes from `check_uphold`."""
    effects = Effects(case_status=flag.status, approval=approval)
    named = named_ids(flag)
    if tracker is not None:
        await tracker.remember(session, named)
    if approval is not None:
        row.correction = {"approval_version": approval["version"]}
    await status.mark_resolved(
        session,
        flag,
        FlagStatus.UPHELD,
        actor_id=user.id,
        at=row.at,
        case_action_seq=row.seq,
        reason_code=row.reason_code,
    )
    resolved = (
        await session.execute(
            select(Check.id, Check.type).where(
                Check.resolved["case_action_seq"].astext == str(row.seq)
            )
        )
    ).all()
    effects.rows_resolved = len(resolved)
    await audit.record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.UPDATE,
                entity_type="check",
                entity_id=check_id,
                actor_id=user.id,
                after={"type": check_type.value, "resolved": True},
            )
            for check_id, check_type in resolved
        ],
    )
    status.mark(session, named)
    return effects


async def clear_resolutions(session: AsyncSession, flag: Flag, actor_id: uuid.UUID) -> int:
    """REOPEN: the rows this case's decision resolved count as unresolved again."""
    named = named_ids(flag)
    if not named:
        return 0
    cleared = (
        await session.execute(
            select(Check.id, Check.type).where(
                Check.enrolment_id.in_(named),
                Check.resolved["case_id"].astext == str(flag.id),
            )
        )
    ).all()
    await status.clear_resolved(session, flag)
    await audit.record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.UPDATE,
                entity_type="check",
                entity_id=check_id,
                actor_id=actor_id,
                after={"type": check_type.value, "resolved": False},
            )
            for check_id, check_type in cleared
        ],
    )
    status.mark(session, named)
    return len(cleared)
