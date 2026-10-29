"""Enrolment rows (API_CONTRACT A2.10, §A4.5), evidence rows, flag references and redaction
shared by routers.

An enrolment's flags are the flags against its own institution that name it as
`enrolment_id` or in `related_enrolment_ids`; the other side of a cross-institution
pair has its own flag, reached through flag detail. Everything that names another
institution is shown only to AICTE_ADMIN and RO_OFFICER (API_CONTRACT A2 errata 5).
Rows are always in the deck's order: Identity, Seat, Joining record, Credits, Student.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Select, exists, literal, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID, array
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import mask_apaar
from app.engine import eligibility
from app.engine import status_text as text
from app.engine.contracts import CHECK_ORDER, UNRESOLVED_FLAG_STATUSES
from app.engine.evidence import AUDIENCE_INSTITUTION, AUDIENCE_OFFICER
from app.models.enums import EnrolmentStatus, Severity, UserRole
from app.models.institution import Institution, Programme
from app.models.seat import Seat
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Check, Flag
from app.schemas.common import FlagRef, IdName
from app.schemas.enrolments import (
    Eligibility,
    EnrolmentRow,
    EvidenceRow,
    EvidenceRowBrief,
    RelatedEnrolmentRow,
    StudentRef,
)

OFFICER_ROLES = (UserRole.AICTE_ADMIN, UserRole.RO_OFFICER)
SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
ROW_ORDER = {t: i for i, t in enumerate(CHECK_ORDER)}
# copy deck §21 `evidence.resolved.UPHELD`
RESOLVED_LINE = {"UPHELD": "Claim upheld by an officer on {date}"}


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value.isoformat()


def is_officer(user: User) -> bool:
    return user.role in OFFICER_ROLES


# ---------------------------------------------------------------------- redaction


def visible_summary(user: User, evidence: dict[str, Any]) -> str:
    summary = evidence.get("summary") or ""
    if is_officer(user):
        return summary
    return evidence.get("summary_for_institution") or summary


def visible_facts(user: User, evidence: dict[str, Any]) -> list[dict[str, Any]]:
    hidden = AUDIENCE_INSTITUTION if is_officer(user) else AUDIENCE_OFFICER
    return [
        {"label": f["label"], "value": f["value"], "source": f.get("source")}
        for f in evidence.get("facts", [])
        if f.get("audience") != hidden
    ]


# -------------------------------------------------------------------------- flags


def names_enrolment(enrolment_id) -> Any:
    """SQL: the flag names the enrolment as its own or as a related one (GIN-friendly)."""
    return or_(
        Flag.enrolment_id == enrolment_id,
        Flag.related_enrolment_ids.op("@>")(array([enrolment_id], type_=UUID(as_uuid=True))),
    )


def unresolved_flag_exists() -> Any:
    """SQL for the `flagged` filter on an enrolment query."""
    return exists(
        select(Flag.id).where(
            Flag.institution_id == Enrolment.institution_id,
            Flag.status.in_(UNRESOLVED_FLAG_STATUSES),
            names_enrolment(Enrolment.id),
        )
    )


async def flags_for(
    session: AsyncSession,
    owners: dict[uuid.UUID, uuid.UUID],
    *,
    unresolved_only: bool,
) -> dict[uuid.UUID, list[Flag]]:
    """{enrolment_id: [Flag]} most severe first, oldest first within a severity."""
    out: dict[uuid.UUID, list[Flag]] = defaultdict(list)
    if not owners:
        return out
    ids = list(owners)
    stmt = select(Flag).where(
        or_(
            Flag.enrolment_id.in_(ids),
            Flag.related_enrolment_ids.op("&&")(literal(ids, type_=ARRAY(UUID(as_uuid=True)))),
        )
    )
    if unresolved_only:
        stmt = stmt.where(Flag.status.in_(UNRESOLVED_FLAG_STATUSES))
    for flag in (await session.execute(stmt)).scalars().all():
        named = {flag.enrolment_id, *flag.related_enrolment_ids} & owners.keys()
        for enrolment_id in named:
            if owners[enrolment_id] == flag.institution_id:
                out[enrolment_id].append(flag)
    for flags in out.values():
        flags.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.created_at, str(f.id)))
    return out


def flag_ref(flag: Flag) -> FlagRef:
    return FlagRef(
        id=str(flag.id),
        type=flag.type.value,
        severity=flag.severity.value,
        status=flag.status.value,
    )


# ------------------------------------------------------------------ evidence rows


def ordered(checks: Iterable[Check]) -> list[Check]:
    """The rows in the deck's order."""
    return sorted(checks, key=lambda c: ROW_ORDER[c.type])


def brief(check: Check) -> EvidenceRowBrief:
    return EvidenceRowBrief(
        type=check.type.value,
        state=check.status.value,
        finding=(check.detail or {}).get("finding"),
        independent=check.independent,
        resolved=check.resolved is not None,
    )


async def brief_rows(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[EvidenceRowBrief]]:
    """{enrolment_id: brief rows in row order}, [] before the first evaluation."""
    out: dict[uuid.UUID, list[Check]] = {i: [] for i in enrolment_ids}
    if enrolment_ids:
        rows = await session.execute(
            select(Check).where(Check.enrolment_id.in_(list(enrolment_ids)))
        )
        for check in rows.scalars().all():
            out[check.enrolment_id].append(check)
    return {i: [brief(c) for c in ordered(checks)] for i, checks in out.items()}


async def full_rows(session: AsyncSession, enrolment_id: uuid.UUID) -> list[EvidenceRow]:
    """The record card's five rows (API_CONTRACT §A4.2), with each resolution's officer."""
    checks = ordered(
        (await session.execute(select(Check).where(Check.enrolment_id == enrolment_id)))
        .scalars()
        .all()
    )
    officer_ids = {
        uuid.UUID(str(c.resolved["by_id"]))
        for c in checks
        if c.resolved and c.resolved.get("by_id")
    }
    officers: dict[str, User] = {}
    if officer_ids:
        for officer in (
            await session.execute(select(User).where(User.id.in_(officer_ids)))
        ).scalars():
            officers[str(officer.id)] = officer
    return [
        EvidenceRow(
            type=c.type.value,
            state=c.status.value,
            finding=(c.detail or {}).get("finding"),
            source_line=str((c.detail or {}).get("source_line") or ""),
            summary=str((c.detail or {}).get("summary") or ""),
            supplied_by=c.supplied_by,
            observed_at=iso(c.observed_at),
            independent=c.independent,
            resolved=resolution(c.resolved, officers),
            source=c.source,
            checked_at=iso(c.checked_at),
            attempts=c.attempts,
            detail=c.detail or {},
        )
        for c in checks
    ]


def resolution(resolved: dict[str, Any] | None, officers: dict[str, User]) -> dict[str, Any] | None:
    """The stored resolution with the officer and the line the card prints."""
    if not resolved:
        return None
    by_id = str(resolved.get("by_id") or "")
    officer = officers.get(by_id)
    at = resolved.get("at")
    line = None
    template = RESOLVED_LINE.get(str(resolved.get("outcome")))
    if template and isinstance(at, str):
        try:
            when = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            when = None
        if when is not None:
            line = template.format(date=text.day(when, text.ist_date(datetime.now(UTC))))
    return {
        "outcome": resolved.get("outcome"),
        "case_id": resolved.get("case_id"),
        "case_action_seq": resolved.get("case_action_seq"),
        "reason_code": resolved.get("reason_code"),
        "at": at,
        "by": {
            "id": by_id or None,
            "name": officer.name if officer else None,
            "role": officer.role.value if officer else None,
        },
        "line": line,
    }


def record_fields(enrolment: Enrolment) -> dict[str, Any]:
    """record_status, status_reason, next_step, record_status_at as the wire carries them:
    a record that is not ACTIVE has no status, only the next step a withdrawal leaves
    (API_CONTRACT §A4.3)."""
    if enrolment.status is not EnrolmentStatus.ACTIVE:
        return {
            "record_status": None,
            "status_reason": None,
            "next_step": enrolment.next_step,
            "record_status_at": None,
        }
    return {
        "record_status": enrolment.record_status.value,
        "status_reason": enrolment.status_reason,
        "next_step": enrolment.next_step,
        "record_status_at": iso(enrolment.record_status_at),
    }


def eligibility_of(enrolment: Enrolment) -> Eligibility:
    return Eligibility(**eligibility.markers(enrolment.eligibility))


# ---------------------------------------------------------------------------- rows


def row_stmt() -> Select:
    """Enrolment, student, programme code, held seat code, institution id and name."""
    return (
        select(Enrolment, Student, Programme.code, Seat.seat_code, Institution.id, Institution.name)
        .join(Student, Student.id == Enrolment.student_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .outerjoin(Seat, Seat.id == Enrolment.seat_id)
    )


async def build_rows(session: AsyncSession, rows: Iterable[Any]) -> list[RelatedEnrolmentRow]:
    """EnrolmentRows (with their institution) for rows of `row_stmt()`, in order."""
    rows = list(rows)
    ids = [r[0].id for r in rows]
    rows_by_id = await brief_rows(session, ids)
    flags = await flags_for(
        session, {r[0].id: r[0].institution_id for r in rows}, unresolved_only=True
    )
    out = []
    for enrolment, student, programme_code, seat_code, institution_id, institution_name in rows:
        out.append(
            RelatedEnrolmentRow(
                id=str(enrolment.id),
                student=StudentRef(
                    id=str(student.id),
                    name=student.name,
                    apaar_masked=mask_apaar(student.apaar_last4),
                    consent_status=student.consent_status.value,
                    provisional_id=student.provisional_id,
                    nationality=student.nationality,
                ),
                programme_id=str(enrolment.programme_id),
                programme_code=programme_code,
                academic_year=enrolment.academic_year,
                cohort_year=enrolment.cohort_year,
                year_of_study=enrolment.year_of_study,
                admission_route=enrolment.admission_route.value,
                counselling_ref=enrolment.counselling_ref,
                category=enrolment.category.value,
                eligibility=eligibility_of(enrolment),
                seat_code=seat_code,
                status=enrolment.status.value,
                admission_date=iso(enrolment.admission_date) or "",
                status_date=iso(enrolment.status_date) or "",
                uploaded_at=iso(enrolment.uploaded_at) or "",
                upload_batch_id=str(enrolment.upload_batch_id)
                if enrolment.upload_batch_id
                else None,
                source_row_no=enrolment.source_row_no,
                checks=rows_by_id[enrolment.id],
                flags=[flag_ref(f) for f in flags.get(enrolment.id, [])],
                institution=IdName(id=str(institution_id), name=institution_name),
                **record_fields(enrolment),
            )
        )
    return out


def plain_row(row: RelatedEnrolmentRow) -> EnrolmentRow:
    return EnrolmentRow.model_validate(row.model_dump(exclude={"institution"}))
