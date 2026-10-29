"""rules.yaml for Week 4 and the joining-year arithmetic (API_CONTRACT §A4.1, ENGINES §17.4)."""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from app.core.cohort import joining_year, reporting_deadline
from app.core.config import get_settings
from app.core.rules import get_rules
from app.models.enums import AdmissionRoute


@pytest.mark.parametrize(
    ("academic_year", "year_of_study", "route", "expected"),
    [
        ("2026-27", 1, AdmissionRoute.COUNSELLING, "2026-27"),
        ("2026-27", 3, AdmissionRoute.MANAGEMENT, "2024-25"),
        ("2026-27", 2, AdmissionRoute.LATERAL, "2026-27"),
        ("2026-27", 3, AdmissionRoute.LATERAL, "2025-26"),
        ("2026-27", 2, AdmissionRoute.NRI, "2025-26"),
    ],
)
def test_the_joining_year_is_the_cohort_or_the_lateral_entry_year(
    academic_year, year_of_study, route, expected
) -> None:
    assert joining_year(academic_year, year_of_study, route) == expected


def test_the_reporting_deadline_comes_from_rules_or_30_september() -> None:
    rules = get_rules()
    assert reporting_deadline("2026-27", rules) == date(2026, 9, 30)
    assert reporting_deadline("2023-24", rules) == date(2023, 9, 30)


def test_every_route_but_international_reads_the_joining_record() -> None:
    routes = get_rules().admission_routes
    assert {name: r.admission_check for name, r in routes.items()} == {
        **{r.value: "JOINING_RECORD" for r in AdmissionRoute},
        "INTERNATIONAL": "STUDY_IN_INDIA",
    }


def test_eligibility_clauses_and_the_anomaly_model_are_in_rules() -> None:
    rules = get_rules()
    assert rules.eligibility.rule("INTERNATIONAL_CIWG").clause == "APH 2024-27 cl. 2.9"
    assert rules.eligibility.rule("NRI_STATUS").clause == "APH 2024-27 cl. 2.8(b)"
    assert rules.eligibility.rule("TFW_INCOME").clause == "APH 2024-27 cl. 6.42(d)"
    assert rules.signals is not None
    anomaly = rules.signals.anomaly
    assert (anomaly.contamination, anomaly.n_estimators, anomaly.random_state) == (0.1, 200, 0)
    assert anomaly.min_records == 20 and anomaly.source


def test_the_integrity_index_is_gone_from_rules() -> None:
    with open(get_settings().resolved_rules_path(), encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    assert "integrity_index" not in raw
    assert raw["ghost_ring"]["min_colleges"] == 2
