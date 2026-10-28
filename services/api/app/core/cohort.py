"""Cohort arithmetic: which approval year an enrolment row belongs to.

Every row in an upload carries the academic year it was uploaded for and the student's
year of study. A student is admitted against the approval of their cohort, the year
they started: academic_year minus (year_of_study - 1). A year-3 row in 2026-27 belongs
to the 2024-25 approval. Lateral entrants join year 2 and so belong to the batch they
join (2025-26 for a year-2 row in 2026-27).

Academic years are labelled "YYYY-YY", e.g. "2026-27".
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, cast, func
from sqlalchemy.sql.elements import ColumnElement

from app.models.enums import AdmissionRoute

if TYPE_CHECKING:
    from app.core.rules import Rules


def start_year(academic_year: str) -> int:
    """The start year of a label: "2026-27" gives 2026."""
    return int(academic_year[:4])


def year_label(start: int) -> str:
    """The label for a start year: 2026 gives "2026-27"."""
    return f"{start}-{(start + 1) % 100:02d}"


def cohort_year(academic_year: str, year_of_study: int) -> str:
    """The approval year a row belongs to: "2024-25" for year 3 in "2026-27"."""
    return year_label(start_year(academic_year) - (year_of_study - 1))


def cohort_year_sql(
    academic_year: ColumnElement[str], year_of_study: ColumnElement[int]
) -> ColumnElement[str]:
    """cohort_year() as a SQL expression, for filtering or joining enrolments to approvals."""
    start = cast(func.substr(academic_year, 1, 4), Integer) - (year_of_study - 1)
    return func.concat(cast(start, String), "-", func.lpad(cast((start + 1) % 100, String), 2, "0"))


def joining_year(academic_year: str, year_of_study: int, route: AdmissionRoute) -> str:
    """The year the student joined this programme, as the admission authority files it:
    the cohort year, or for a lateral entrant the year it entered year 2 ("2026-27" for a
    year-2 lateral in "2026-27", "2025-26" for a year-3 one)."""
    if route is AdmissionRoute.LATERAL:
        return year_label(start_year(academic_year) - (year_of_study - 2))
    return cohort_year(academic_year, year_of_study)


def reporting_deadline(academic_year: str, rules: Rules) -> date:
    """The admission authority's reporting deadline for a joining year (rules.yaml
    `reporting.deadline`; 30 September of the start year when the year is not listed)."""
    return rules.reporting.deadline_for(academic_year)
