import pytest
from sqlalchemy import literal, select

from app.core.cohort import cohort_year, cohort_year_sql
from app.db.session import session_factory
from tests.conftest import institution_id, login_as

CASES = [
    ("2026-27", 1, "2026-27"),
    ("2026-27", 2, "2025-26"),
    ("2026-27", 3, "2024-25"),
    ("2000-01", 2, "1999-00"),
    ("2099-00", 1, "2099-00"),
    ("2100-01", 2, "2099-00"),
]


@pytest.mark.parametrize(("academic_year", "year_of_study", "expected"), CASES)
def test_cohort_year(academic_year, year_of_study, expected):
    assert cohort_year(academic_year, year_of_study) == expected


async def test_cohort_year_sql_matches_python():
    async with session_factory()() as session:
        for academic_year, year_of_study, expected in CASES:
            stmt = select(cohort_year_sql(literal(academic_year), literal(year_of_study)))
            assert (await session.execute(stmt)).scalar_one() == expected


async def test_programme_admitted_counts_its_own_cohort(three_cohorts):
    admin = await login_as("admin@aicte.demo")
    try:
        abc = await institution_id("1-ABC-0001")

        # ABC CSE 2026-27: 120 approved, 132 active first-years uploaded. The 86 second
        # years (laterals included) and 50 third years belong to earlier approvals.
        cse = (await admin.get(f"/institutions/{abc}")).json()["programmes"][0]
        assert cse["approval"]["academic_year"] == "2026-27"
        assert cse["approval"]["approved_intake"] == 120
        # the 114 REGULAR seats went to the first 114 of the 133 uploaded; the last one was
        # withdrawn afterwards, so 18 active first-years are without a seat
        assert (cse["enrolments"], cse["unseated"]) == (132, 18)

        for year, intake, admitted in (("2025-26", 90, 86), ("2024-25", 60, 50)):
            detail = await admin.get(f"/institutions/{abc}", params={"academic_year": year})
            cse = detail.json()["programmes"][0]
            assert cse["approval"]["academic_year"] == year
            assert cse["approval"]["approved_intake"] == intake
            assert (cse["enrolments"], cse["unseated"]) == (admitted, 0)  # within intake

        # Institution rows and dashboard KPIs keep counting every active enrolment in the year.
        row = (await admin.get("/institutions")).json()["items"][0]
        assert row["enrolments"] == 132 + 86 + 50
        kpis = (await admin.get("/dashboard/summary")).json()["kpis"]
        assert kpis["enrolments"] == 132 + 86 + 50

        # The detail carries the same totals as its list row, so a tab badge never
        # mistakes one cohort's admissions for the whole roll.
        detail = (await admin.get(f"/institutions/{abc}")).json()
        assert detail["enrolments"] == row["enrolments"] == 132 + 86 + 50
        assert detail["approved_seats"] == row["approved_seats"] == 120
    finally:
        await admin.aclose()
