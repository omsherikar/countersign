"""Category eligibility for the Seat Ledger (D41; API_CONTRACT §A4.4; ENGINES §17.5).

Pure: no database, no clock. A seat type is checked against what the college reported for
the student (`enrolments.eligibility`: `tfw_income_certified`, `nri_sponsored`, `ciwg`,
each true, false or None when not reported):

- an INTERNATIONAL seat is for foreign nationals, OCI and PIO students, and for an Indian
  national only when marked CIWG (rule INTERNATIONAL_CIWG);
- an NRI seat only for a row marked NRI or NRI-sponsored (rule NRI_STATUS);
- a TFW seat only with the family income certificate reported (rule TFW_INCOME); a blank
  marker is NOT_REPORTED, which keeps the Seat row Pending and is never a breach.

Every other seat type fits. The clause each breach cites comes from rules.yaml `eligibility`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.core.rules import Rules
from app.models.enums import AdmissionRoute, SeatType

MARKERS = ("tfw_income_certified", "nri_sponsored", "ciwg")
INTERNATIONAL_CIWG = "INTERNATIONAL_CIWG"
NRI_STATUS = "NRI_STATUS"
TFW_INCOME = "TFW_INCOME"
# copy deck §25 `eligibility.word.*`, and the TFW words of API_CONTRACT §A4.4
NOT_MARKED = "not marked for this category"
WITHOUT_INCOME_CERTIFICATE = "without a family income certificate"

Verdict = Literal["FITS", "BREACH", "NOT_REPORTED"]


@dataclass(frozen=True, slots=True)
class EligibilityVerdict:
    state: Verdict
    rule: str | None = None  # INTERNATIONAL_CIWG, NRI_STATUS, TFW_INCOME
    reported_word: str | None = None
    clause: str | None = None
    allowed_words: str | None = None


FITS = EligibilityVerdict("FITS")


def markers(eligibility: Mapping[str, object] | None) -> dict[str, bool | None]:
    """The three markers, each True, False or None (not reported)."""
    eligibility = eligibility or {}
    out: dict[str, bool | None] = {}
    for key in MARKERS:
        value = eligibility.get(key)
        out[key] = value if isinstance(value, bool) else None
    return out


def is_indian(nationality: str | None) -> bool:
    return (nationality or "IN").upper() == "IN"


def is_ciwg(
    route: AdmissionRoute, nationality: str | None, eligibility: Mapping[str, object] | None
) -> bool:
    """A child of an Indian worker in the Gulf: an International-route row of an Indian
    national that the college marked CIWG. Only these take the CIWG-reserved seats."""
    return (
        route is AdmissionRoute.INTERNATIONAL
        and is_indian(nationality)
        and markers(eligibility)["ciwg"] is True
    )


def _breach(rule: str, word: str, rules: Rules) -> EligibilityVerdict:
    found = rules.eligibility.rule(rule)
    return EligibilityVerdict("BREACH", rule, word, found.clause, found.allowed)


def check(
    seat_type: SeatType,
    nationality: str | None,
    eligibility: Mapping[str, object] | None,
    rules: Rules,
) -> EligibilityVerdict:
    """Whether the student, as reported, may hold a seat of this type."""
    reported = markers(eligibility)
    if seat_type is SeatType.INTERNATIONAL:
        if is_indian(nationality) and reported["ciwg"] is not True:
            return _breach(INTERNATIONAL_CIWG, NOT_MARKED, rules)
        return FITS
    if seat_type is SeatType.NRI:
        if reported["nri_sponsored"] is not True:
            return _breach(NRI_STATUS, NOT_MARKED, rules)
        return FITS
    if seat_type is SeatType.TFW:
        if reported["tfw_income_certified"] is None:
            rule = rules.eligibility.rule(TFW_INCOME)
            return EligibilityVerdict("NOT_REPORTED", TFW_INCOME, None, rule.clause, rule.allowed)
        if reported["tfw_income_certified"] is False:
            return _breach(TFW_INCOME, WITHOUT_INCOME_CERTIFICATE, rules)
        return FITS
    return FITS
