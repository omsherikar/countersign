"""Per-institution aggregates shared by the institutions list, detail and dashboard."""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased

from app.core.deps import scope_institutions
from app.models.enums import EnrolmentStatus
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.student import Enrolment
from app.models.user import User


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


def institution_stats_stmt(user: User, academic_year: str) -> Select:
    """Institution + state + region + university + (programmes, approved_seats, enrolments)."""
    pc = programme_count_sq()
    asq = approved_seats_sq(academic_year)
    ec = enrolment_count_sq(academic_year)
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
        )
        .join(State, State.id == Institution.state_id)
        .join(Region, Region.id == Institution.region_id)
        .outerjoin(uni, uni.id == Institution.university_id)
        .outerjoin(pc, pc.c.institution_id == Institution.id)
        .outerjoin(asq, asq.c.institution_id == Institution.id)
        .outerjoin(ec, ec.c.institution_id == Institution.id)
    )
    return scope_institutions(stmt, user)


def region_label(region: Region) -> str:
    return f"{region.name} ({region.hq_city})"
