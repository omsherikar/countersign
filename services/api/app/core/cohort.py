"""Cohort arithmetic: which approval year an enrolment row belongs to.

Every row in an upload carries the academic year it was uploaded for and the student's
year of study. A student is admitted against the approval of their cohort, the year
they started: academic_year minus (year_of_study - 1). A year-3 row in 2026-27 belongs
to the 2024-25 approval. Lateral entrants join year 2 and so belong to the batch they
join (2025-26 for a year-2 row in 2026-27).

Academic years are labelled "YYYY-YY", e.g. "2026-27".
"""

from __future__ import annotations

from sqlalchemy import Integer, String, cast, func
from sqlalchemy.sql.elements import ColumnElement


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
