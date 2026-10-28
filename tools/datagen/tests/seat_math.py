"""Seat arithmetic for the tests, read straight from rules.yaml (as the api's ledger does)."""

from collections import Counter

from datagen.config import load_rules
from datagen.institutions import intake_on
from datagen.students import Pools

RULES = load_rules()
ROUTE_POOL = {route: spec["pool"] for route, spec in RULES["admission_routes"].items()}
CUTOFF = RULES["cutoff_dates"]["2026-27"]


def cohort_label(year_of_study: int, academic_year: str = "2026-27") -> str:
    start = int(academic_year[:4]) - (int(year_of_study) - 1)
    return f"{start}-{(start + 1) % 100:02d}"


def cutoff_of(label: str) -> str:
    return RULES["cutoff_dates"].get(label) or f"{label[:4]}-09-30"


def intake(prog: dict, label: str) -> int | None:
    """The intake the cohort was admitted against: the approval version in force on the
    year's admission cutoff (a later revision, such as ABC College IT's v2, adds seats only
    after the admissions it would otherwise seem to cover)."""
    for a in prog["approvals"]:
        if a["academic_year"] == label:
            if "versions" not in a:
                return a["approved_intake"]
            return intake_on(a, cutoff_of(label))
    return None


def usable_capacity(prog: dict, year_of_study: int) -> dict[str, int]:
    """Seats a non-CIWG student can take in each pool of the cohort's approval."""
    approved = intake(prog, cohort_label(year_of_study))
    if approved is None:
        return {}
    p = Pools(RULES, prog, approved)
    return {
        "REGULAR": p.regular,
        "NRI": p.nri,
        "TFW": p.tfw,
        "LATERAL": p.lateral,
        "INTERNATIONAL": p.international - p.ciwg,
    }


def cohort_rows(rows: list[dict], code: str, year_of_study: int) -> list[dict]:
    return [
        r for r in rows
        if r["programme_code"] == code and int(r["year_of_study"]) == int(year_of_study)
        and r.get("status", "") in {"", "ACTIVE"}
    ]  # fmt: skip


def pool_counts(rows: list[dict], code: str, year_of_study: int) -> Counter:
    return Counter(ROUTE_POOL[r["admission_route"]] for r in cohort_rows(rows, code, year_of_study))
