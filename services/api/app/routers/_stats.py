"""Per-institution aggregates shared by the institutions list and detail, the dashboard and the
reports, so every page and every downloaded file counts the same records the same way
(D35, D40, D46; API_CONTRACT §A4.20, §A4.21).

Records are the ACTIVE enrolments of the academic year, counted by `record_status`;
completeness comes from the stored reconciliation in `institution_scores` (never from the
authority); the deadline state is computed when read from the first DONE upload of the year,
the reporting deadline in rules.yaml and today's date in IST.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import Integer, Select, case, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.crypto import mask_apaar
from app.core.deps import scope_institutions
from app.core.rules import get_rules
from app.engine.contracts import UNRESOLVED_FLAG_STATUSES
from app.engine.upload.types import INDIA
from app.models.credential import InstitutionScore
from app.models.enums import EnrolmentStatus, FlagType, RecordStatus, UploadStatus
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.student import Enrolment
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import Flag

# the order the four statuses are listed in wherever they appear together (copy deck §21)
RECORD_STATUSES = (
    RecordStatus.AWAITING_EVIDENCE,
    RecordStatus.COUNTERSIGNED,
    RecordStatus.UNDER_REVIEW,
    RecordStatus.DISPUTED,
)
DEADLINE_STATES = ("NOT_DUE", "ON_TIME", "LATE", "OVERDUE")
FIGURES = (
    "programmes",
    "approved_seats",
    "enrolments",
    "admitted",
    "flags_open",
    "awaiting_evidence",
    "countersigned",
    "under_review",
    "disputed",
    "joined",
    "uploaded_and_joined",
    "missing",
    "uploaded_not_joined",
)
COLUMNS = (*FIGURES, "completeness_pct", "first_upload_at", "deadline_state")


def today_ist() -> date:
    return datetime.now(INDIA).date()


def deadline_for(academic_year: str) -> date:
    return get_rules().reporting.deadline_for(academic_year)


def pct(part: int, whole: int) -> float | None:
    """0 to 100, one decimal; null when there is nothing to count."""
    return round(100 * part / whole, 1) if whole else None


# ------------------------------------------------------------------ subqueries


def programme_count_sq():
    return (
        select(Programme.institution_id.label("institution_id"), func.count().label("programmes"))
        .group_by(Programme.institution_id)
        .subquery("pc")
    )


def approved_seats_sq(academic_year: str):
    return (
        select(
            Programme.institution_id.label("institution_id"),
            func.coalesce(func.sum(Approval.approved_intake), 0).label("approved_seats"),
        )
        .join(Approval, Approval.programme_id == Programme.id)
        .where(Approval.academic_year == academic_year)
        .group_by(Programme.institution_id)
        .subquery("asq")
    )


def record_counts_sq(academic_year: str):
    """ACTIVE enrolments of the year, in total and by record status."""
    status = Enrolment.record_status
    return (
        select(
            Enrolment.institution_id.label("institution_id"),
            func.count().label("enrolments"),
            func.count().filter(status == RecordStatus.AWAITING_EVIDENCE).label("awaiting"),
            func.count().filter(status == RecordStatus.COUNTERSIGNED).label("countersigned"),
            func.count().filter(status == RecordStatus.UNDER_REVIEW).label("under_review"),
            func.count().filter(status == RecordStatus.DISPUTED).label("disputed"),
        )
        .where(Enrolment.academic_year == academic_year, Enrolment.status == EnrolmentStatus.ACTIVE)
        .group_by(Enrolment.institution_id)
        .subquery("ec")
    )


def admitted_count_sq(academic_year: str):
    """ACTIVE enrolments of the cohort `academic_year`, counted in the current roll (A2.18).

    Every route counts, supernumerary pools included (A2 errata 3).
    """
    return (
        select(Enrolment.institution_id.label("institution_id"), func.count().label("admitted"))
        .where(
            Enrolment.academic_year == get_settings().academic_year,
            Enrolment.cohort_year == academic_year,
            Enrolment.status == EnrolmentStatus.ACTIVE,
        )
        .group_by(Enrolment.institution_id)
        .subquery("adm")
    )


def flags_open_sq(academic_year: str):
    """Unresolved flags (OPEN, DOCS_REQUESTED, ESCALATED) of the academic year."""
    return (
        select(Flag.institution_id.label("institution_id"), func.count().label("flags_open"))
        .where(
            Flag.academic_year == academic_year,
            Flag.status.in_(UNRESOLVED_FLAG_STATUSES),
        )
        .group_by(Flag.institution_id)
        .subquery("fo")
    )


def _component(name: str):
    return cast(InstitutionScore.components[name].astext, Integer)


def completeness_sq(academic_year: str):
    """The stored reconciliation of the year (ENGINES §17.10)."""
    return (
        select(
            InstitutionScore.institution_id.label("institution_id"),
            InstitutionScore.completeness_pct.label("completeness_pct"),
            _component("joined").label("joined"),
            _component("uploaded_and_joined").label("uploaded_and_joined"),
            _component("missing").label("missing"),
            _component("uploaded_not_joined").label("uploaded_not_joined"),
        )
        .where(InstitutionScore.academic_year == academic_year)
        .subquery("cq")
    )


def first_upload_sq(academic_year: str):
    """When each institution's first DONE batch of the year was uploaded."""
    return (
        select(
            UploadBatch.institution_id.label("institution_id"),
            func.min(UploadBatch.created_at).label("first_upload_at"),
        )
        .where(UploadBatch.academic_year == academic_year, UploadBatch.status == UploadStatus.DONE)
        .group_by(UploadBatch.institution_id)
        .subquery("fu")
    )


def deadline_state_expr(first_upload_at: Any, deadline: date, today: date) -> Any:
    """API_CONTRACT §A4.18: ON_TIME or LATE by the first upload's IST date; with no DONE upload,
    OVERDUE once the deadline has passed, else NOT_DUE."""
    uploaded_on = func.date(func.timezone("Asia/Kolkata", first_upload_at))
    return case(
        (first_upload_at.is_(None) & literal(today > deadline), "OVERDUE"),
        (first_upload_at.is_(None), "NOT_DUE"),
        (uploaded_on <= literal(deadline), "ON_TIME"),
        else_="LATE",
    )


def deadline_state(deadline: date, first_upload_at: datetime | None, today: date) -> str:
    """The same rule in Python."""
    if first_upload_at is None:
        return "OVERDUE" if today > deadline else "NOT_DUE"
    return "ON_TIME" if first_upload_at.astimezone(INDIA).date() <= deadline else "LATE"


def figures_sq(academic_year: str, *, today: date | None = None):
    """One row per institution: every figure the pages and reports count, zeros filled in."""
    pc = programme_count_sq()
    asq = approved_seats_sq(academic_year)
    ec = record_counts_sq(academic_year)
    adm = admitted_count_sq(academic_year)
    fo = flags_open_sq(academic_year)
    cq = completeness_sq(academic_year)
    fu = first_upload_sq(academic_year)
    zero = func.coalesce
    return (
        select(
            Institution.id.label("institution_id"),
            zero(pc.c.programmes, 0).label("programmes"),
            zero(asq.c.approved_seats, 0).label("approved_seats"),
            zero(ec.c.enrolments, 0).label("enrolments"),
            zero(adm.c.admitted, 0).label("admitted"),
            zero(fo.c.flags_open, 0).label("flags_open"),
            zero(ec.c.awaiting, 0).label("awaiting_evidence"),
            zero(ec.c.countersigned, 0).label("countersigned"),
            zero(ec.c.under_review, 0).label("under_review"),
            zero(ec.c.disputed, 0).label("disputed"),
            zero(cq.c.joined, 0).label("joined"),
            zero(cq.c.uploaded_and_joined, 0).label("uploaded_and_joined"),
            zero(cq.c.missing, 0).label("missing"),
            zero(cq.c.uploaded_not_joined, 0).label("uploaded_not_joined"),
            cq.c.completeness_pct.label("completeness_pct"),
            fu.c.first_upload_at.label("first_upload_at"),
            deadline_state_expr(
                fu.c.first_upload_at, deadline_for(academic_year), today or today_ist()
            ).label("deadline_state"),
        )
        .outerjoin(pc, pc.c.institution_id == Institution.id)
        .outerjoin(asq, asq.c.institution_id == Institution.id)
        .outerjoin(ec, ec.c.institution_id == Institution.id)
        .outerjoin(adm, adm.c.institution_id == Institution.id)
        .outerjoin(fo, fo.c.institution_id == Institution.id)
        .outerjoin(cq, cq.c.institution_id == Institution.id)
        .outerjoin(fu, fu.c.institution_id == Institution.id)
        .subquery("fig")
    )


# ------------------------------------------------------------- institution rows


@dataclass(slots=True)
class InstitutionStats:
    institution: Institution
    state: State
    region: Region
    university: University | None
    programmes: int
    approved_seats: int
    enrolments: int
    admitted: int
    flags_open: int
    awaiting_evidence: int
    countersigned: int
    under_review: int
    disputed: int
    joined: int
    uploaded_and_joined: int
    missing: int
    uploaded_not_joined: int
    completeness_pct: float | None
    first_upload_at: datetime | None
    deadline_state: str

    @property
    def records(self) -> dict[str, int]:
        return {
            "AWAITING_EVIDENCE": self.awaiting_evidence,
            "COUNTERSIGNED": self.countersigned,
            "UNDER_REVIEW": self.under_review,
            "DISPUTED": self.disputed,
        }

    @property
    def countersigned_pct(self) -> float | None:
        return pct(self.countersigned, self.enrolments)


def institution_stats_stmt(user: User, academic_year: str) -> Select:
    """Institution, state, region, university and the figures of `figures_sq`, in the user's
    scope. Read rows with `stats_of`."""
    fig = figures_sq(academic_year)
    uni = aliased(University)
    stmt = (
        select(Institution, State, Region, uni, *[fig.c[name] for name in COLUMNS])
        .join(fig, fig.c.institution_id == Institution.id)
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .outerjoin(uni, uni.id == Institution.university_id)
    )
    return scope_institutions(stmt, user)


def stats_of(row: Any) -> InstitutionStats:
    institution, state, region, university, *rest = row
    values = dict(zip(COLUMNS, rest, strict=True))
    if values["completeness_pct"] is not None:
        values["completeness_pct"] = round(float(values["completeness_pct"]), 1)
    return InstitutionStats(
        institution=institution, state=state, region=region, university=university, **values
    )


def region_label(region: Region) -> str:
    return f"{region.name} ({region.hq_city})"


def institution_ref(stats: InstitutionStats) -> dict[str, str]:
    return {
        "id": str(stats.institution.id),
        "name": stats.institution.name,
        "aicte_permanent_id": stats.institution.aicte_permanent_id,
        "state_code": stats.state.code,
        "state_name": stats.state.name,
        "region": stats.region.code,
    }


# ------------------------------------------------------------------ completeness


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


async def completeness_body(
    session: AsyncSession,
    institution_id: uuid.UUID,
    academic_year: str,
    *,
    with_students: bool,
) -> dict[str, Any]:
    """The §A4.18 body of one institution and year, without `institution`; the missing
    students only `with_students`."""
    score = (
        await session.execute(
            select(InstitutionScore).where(
                InstitutionScore.institution_id == institution_id,
                InstitutionScore.academic_year == academic_year,
            )
        )
    ).scalar_one_or_none()
    components: dict[str, Any] = (score.components or {}) if score is not None else {}
    first_upload_at = (
        await session.execute(
            select(func.min(UploadBatch.created_at)).where(
                UploadBatch.institution_id == institution_id,
                UploadBatch.academic_year == academic_year,
                UploadBatch.status == UploadStatus.DONE,
            )
        )
    ).scalar_one_or_none()
    case = (
        await session.execute(
            select(Flag.id, Flag.status).where(
                Flag.type == FlagType.MISSING_FROM_UPLOAD,
                Flag.dedupe_key == f"MISSING_FROM_UPLOAD:{institution_id}:{academic_year}",
            )
        )
    ).first()
    deadline = deadline_for(academic_year)
    pct_value = None
    if score is not None and score.completeness_pct is not None:
        pct_value = round(float(score.completeness_pct), 1)
    body: dict[str, Any] = {
        "academic_year": academic_year,
        "joined": int(components.get("joined") or 0),
        "uploaded_and_joined": int(components.get("uploaded_and_joined") or 0),
        "missing": int(components.get("missing") or 0),
        "uploaded_not_joined": int(components.get("uploaded_not_joined") or 0),
        "completeness_pct": pct_value,
        "published": bool(components.get("published", False)),
        "deadline": deadline.isoformat(),
        "first_upload_at": _iso(first_upload_at),
        "deadline_state": deadline_state(deadline, first_upload_at, today_ist()),
        "computed_at": _iso(score.computed_at) if score is not None else None,
        "source_unavailable": bool(components.get("source_unavailable", False)),
        "case": {"id": str(case[0]), "status": case[1].value} if case else None,
    }
    if with_students:
        body["missing_students"] = [
            {
                "name": s.get("name"),
                "roll_no": s.get("roll_no"),
                "programme_code": s.get("programme_code"),
                "joined_on": s.get("joined_on"),
                "round": s.get("round"),
                "route": s.get("route"),
                "apaar_masked": s.get("apaar_masked") or mask_apaar(s.get("apaar_last4")),
            }
            for s in components.get("missing_students") or []
        ]
    return body
