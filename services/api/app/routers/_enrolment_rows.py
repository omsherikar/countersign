"""Enrolment rows (API_CONTRACT A2.10), flag references and redaction shared by routers.

An enrolment's flags are the flags against its own institution that name it as
`enrolment_id` or in `related_enrolment_ids`; the other side of a cross-institution
pair has its own flag, reached through flag detail. Everything that names another
institution is shown only to AICTE_ADMIN and RO_OFFICER (API_CONTRACT A2 errata 5).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, and_, exists, literal, or_, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID, array
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import mask_apaar
from app.engine.contracts import UNRESOLVED_FLAG_STATUSES
from app.engine.evidence import AUDIENCE_INSTITUTION, AUDIENCE_OFFICER
from app.engine.score import countersign_from_pairs
from app.models.enums import Severity, UserRole
from app.models.institution import Institution, Programme
from app.models.seat import Seat
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Check, Flag
from app.schemas.common import Countersign, FlagRef, IdName
from app.schemas.institutions import EnrolmentRow, RelatedEnrolmentRow, StudentRef

OFFICER_ROLES = (UserRole.AICTE_ADMIN, UserRole.RO_OFFICER)
SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


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


# ---------------------------------------------------------------------- countersign


async def countersigns(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, Countersign]:
    pairs: dict[uuid.UUID, list[tuple[Any, Any]]] = defaultdict(list)
    if enrolment_ids:
        rows = await session.execute(
            select(Check.enrolment_id, Check.type, Check.status).where(
                Check.enrolment_id.in_(list(enrolment_ids))
            )
        )
        for enrolment_id, check_type, status in rows.all():
            pairs[enrolment_id].append((check_type, status))
    return {i: Countersign.model_validate(countersign_from_pairs(pairs[i])) for i in enrolment_ids}


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


def check_filter(check_status: Any, check_type: Any) -> Any:
    """Enrolments with at least one check in the status (that check, with a type)."""
    conditions = [Check.enrolment_id == Enrolment.id, Check.status == check_status]
    if check_type is not None:
        conditions.append(Check.type == check_type)
    return exists(select(Check.id).where(and_(*conditions)))


async def build_rows(session: AsyncSession, rows: Iterable[Any]) -> list[RelatedEnrolmentRow]:
    """EnrolmentRows (with their institution) for rows of `row_stmt()`, in order."""
    rows = list(rows)
    ids = [r[0].id for r in rows]
    signs = await countersigns(session, ids)
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
                seat_code=seat_code,
                status=enrolment.status.value,
                admission_date=iso(enrolment.admission_date) or "",
                status_date=iso(enrolment.status_date) or "",
                uploaded_at=iso(enrolment.uploaded_at) or "",
                upload_batch_id=str(enrolment.upload_batch_id)
                if enrolment.upload_batch_id
                else None,
                source_row_no=enrolment.source_row_no,
                countersign=signs[enrolment.id],
                flags=[flag_ref(f) for f in flags.get(enrolment.id, [])],
                institution=IdName(id=str(institution_id), name=institution_name),
            )
        )
    return out


def plain_row(row: RelatedEnrolmentRow) -> EnrolmentRow:
    return EnrolmentRow.model_validate(row.model_dump(exclude={"institution"}))
