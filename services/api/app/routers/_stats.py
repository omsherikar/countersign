"""Per-institution aggregates shared by the institutions list, detail and dashboard."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.deps import scope_institutions
from app.engine.contracts import UNRESOLVED_FLAG_STATUSES
from app.models.enums import EnrolmentStatus
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.student import Enrolment
from app.models.user import User
from app.models.verification import Flag


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


def enrolment_count_sq(academic_year: str):
    return (
        select(Enrolment.institution_id.label("institution_id"), func.count().label("enrolments"))
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


def institution_stats_stmt(user: User, academic_year: str) -> Select:
    """Institution + state + region + university + (programmes, approved_seats, enrolments,
    admitted, flags_open)."""
    pc = programme_count_sq()
    asq = approved_seats_sq(academic_year)
    ec = enrolment_count_sq(academic_year)
    adm = admitted_count_sq(academic_year)
    fo = flags_open_sq(academic_year)
    uni = aliased(University)
    stmt = (
        select(
            Institution,
            State,
            Region,
            uni,
            func.coalesce(pc.c.programmes, 0).label("programmes"),
            func.coalesce(asq.c.approved_seats, 0).label("approved_seats"),
            func.coalesce(ec.c.enrolments, 0).label("enrolments"),
            func.coalesce(adm.c.admitted, 0).label("admitted"),
            func.coalesce(fo.c.flags_open, 0).label("flags_open"),
        )
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .outerjoin(uni, uni.id == Institution.university_id)
        .outerjoin(pc, pc.c.institution_id == Institution.id)
        .outerjoin(asq, asq.c.institution_id == Institution.id)
        .outerjoin(ec, ec.c.institution_id == Institution.id)
        .outerjoin(adm, adm.c.institution_id == Institution.id)
        .outerjoin(fo, fo.c.institution_id == Institution.id)
    )
    return scope_institutions(stmt, user)


def region_label(region: Region) -> str:
    return f"{region.name} ({region.hq_city})"
