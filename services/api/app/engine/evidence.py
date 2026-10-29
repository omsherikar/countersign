"""Evidence row texts and case evidence: copy deck §15 and §5, API_CONTRACT §A4.2, §A4.4.

Officers, colleges and the web read these sentences verbatim and never rebuild them, so
every template lives here and nowhere else. A row `detail` always has `summary`, `finding`,
`source_line` and `basis`; case evidence is `{summary, summary_for_institution?, facts,
related_enrolment_ids, rule_source, data?}` (DATA_MODEL "Migration 0002"). No summary ever
holds a student name or a full id; facts may hold the name as uploaded.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.models.enums import AdmissionRoute, FlagType, ProgrammeMode, SeatType

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# copy deck §3 `source.*`: the words for each source code
SOURCE_NAMES = {
    "APAAR": "APAAR registry",
    "ADMISSION_AUTHORITY": "State admission authority",
    "COUNSELLING": "State admission authority",
    "SEAT_LEDGER": "Seat Ledger",
    "ABC": "ABC credits",
    "SII": "Study in India",
    "STUDENT_NOTICE": "Student sign-in via DigiLocker",
    "DIGILOCKER": "DigiLocker",
}
ROUTE_WORDS = {
    AdmissionRoute.COUNSELLING: "Counselling",
    AdmissionRoute.MANAGEMENT: "Management",
    AdmissionRoute.NRI: "NRI",
    AdmissionRoute.SPOT: "Spot",
    AdmissionRoute.LATERAL: "Lateral",
    AdmissionRoute.INTERNATIONAL: "International",
    AdmissionRoute.TFW: "TFW",
}
SEAT_TYPE_WORDS = {
    SeatType.REGULAR: "Regular",
    SeatType.NRI: "NRI",
    SeatType.TFW: "TFW",
    SeatType.LATERAL: "Lateral",
    SeatType.INTERNATIONAL: "International",
}
FLAG_NAMES = {
    FlagType.EXCESS_ADMISSION: "Excess admission",
    FlagType.QUOTA_BREACH: "Quota breach",
    FlagType.LATE_REFILL: "Late refill",
    FlagType.INVALID_APAAR: "APAAR not verified",
    FlagType.NAME_MISMATCH: "Name or date of birth mismatch",
    FlagType.DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
    FlagType.DUPLICATE_WITHIN_UPLOAD: "Duplicate within institution",
    FlagType.DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
    FlagType.NO_ACADEMIC_ACTIVITY: "No academic activity",
    FlagType.STUDENT_DENIED: "Student dispute",
    FlagType.GHOST_RING: "Shared contact ring",
    FlagType.ANOMALY: "Unusual pattern",
    FlagType.NOT_IN_JOINING_RECORD: "Not in joining record",
    FlagType.ELIGIBILITY_BREACH: "Seat category not eligible",
    FlagType.MISSING_FROM_UPLOAD: "Missing from upload",
}
MODE_WORDS = {
    ProgrammeMode.PHYSICAL: "physical",
    ProgrammeMode.ODL: "open and distance learning",
    ProgrammeMode.ONLINE: "online",
}

# Evidence never names a config file (API_CONTRACT A2 errata 6).
APPROVAL_RULES = "AICTE approval rules"
ADMISSION_SCHEDULE = "AICTE admission schedule"

AUDIENCE_OFFICER = "OFFICER"
AUDIENCE_INSTITUTION = "INSTITUTION"


def fmt_date(value: date) -> str:
    """`5 Oct 2026`: day without a leading zero, three-letter English month, year."""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def fact(label: str, value: object, source: str | None, audience: str | None = None) -> dict:
    out: dict[str, Any] = {"label": label, "value": str(value), "source": source}
    if audience is not None:
        out["audience"] = audience
    return out


def _ids(ids: Iterable[uuid.UUID | str]) -> list[str]:
    out: list[str] = []
    for value in ids:
        text = str(value)
        if text not in out:
            out.append(text)
    return out


def _join_words(parts: Sequence[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _evidence(
    summary: str,
    facts: list[dict],
    related: Iterable[uuid.UUID | str],
    rule_source: str,
    *,
    summary_for_institution: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "summary": summary,
        "facts": facts,
        "related_enrolment_ids": _ids(related),
        "rule_source": rule_source,
    }
    if summary_for_institution is not None:
        out["summary_for_institution"] = summary_for_institution
    if data is not None:
        out["data"] = data
    return out


# ====================================================================== row texts
#
# Copy deck §15. Every row detail carries `summary` (the detail sentence), `finding` (the
# short phrase after the state word, or None), `source_line` (the "Source and date" cell)
# and `basis` (API_CONTRACT §A4.4). `{date}` in a source line or a summary is the row's
# observed_at; the row writer fills it once it knows that time. Every other placeholder is
# filled here.

DATE = "{date}"


def short_date(value: date, today: date) -> str:
    """`12 Aug` in the current calendar year, `12 Aug 2025` otherwise (API_CONTRACT §A4.1)."""
    words = f"{value.day} {MONTHS[value.month - 1]}"
    return words if value.year == today.year else f"{words} {value.year}"


def _row(
    basis: str, summary: str, source_line: str, finding: str | None = None, **extra: Any
) -> dict[str, Any]:
    return {
        "summary": summary,
        "finding": finding,
        "source_line": source_line,
        "basis": basis,
        **extra,
    }


def source_unavailable(
    source: str, error: str | None = None, *, disabled: bool = False
) -> dict[str, Any]:
    name = SOURCE_NAMES[source]
    detail = _row(
        "SOURCE_UNAVAILABLE",
        f"{name} did not respond. This row is asked again at the next recheck or the next upload.",
        f"{name} did not respond · {DATE}",
        source_unavailable=True,
    )
    if disabled:
        detail["source_disabled"] = True
    if error:
        detail["source_error"] = error
    return detail


# ---------------------------------------------------------------------- IDENTITY

APAAR_LINE = f"APAAR verification · {DATE}"
DIGILOCKER_LINE = f"Student sign-in via DigiLocker · {DATE}"
SII_LINE = f"Study in India · {DATE}"


def identity_confirmed(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return _row(
        "APAAR_MATCH",
        f"Name and date of birth match the APAAR registry (similarity {name_score} of 100).",
        APAAR_LINE,
        name_score=name_score,
        dob_match=True,
        apaar_last4=apaar_last4,
    )


def identity_review(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return _row(
        "NAME_REVIEW",
        "Name on upload is close to the APAAR registry but not a clear match "
        f"(similarity {name_score} of 100); an officer should review. Name matching supports "
        "a decision; it never makes one.",
        APAAR_LINE,
        "needs review",
        name_score=name_score,
        dob_match=True,
        needs_review=True,
        apaar_last4=apaar_last4,
        case_type=FlagType.NAME_MISMATCH.value,
    )


def identity_not_found(apaar_last4: str | None) -> dict[str, Any]:
    """The registry has no such id, so it returned no name score and no date check."""
    return _row(
        "APAAR_UNKNOWN",
        f"APAAR ending {apaar_last4} is not in the APAAR registry.",
        APAAR_LINE,
        "APAAR not found",
        apaar_last4=apaar_last4,
        case_type=FlagType.INVALID_APAAR.value,
    )


def identity_malformed(problem: str) -> dict[str, Any]:
    return _row(
        "APAAR_MALFORMED",
        f"APAAR as uploaded {problem}; the record was kept without it.",
        f"College upload · {DATE}",
        "APAAR not valid",
        case_type=FlagType.INVALID_APAAR.value,
    )


def identity_name_differs(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return _row(
        "NAME_MISMATCH",
        f"Name on upload differs from the APAAR registry (similarity {name_score} of 100).",
        APAAR_LINE,
        "name differs",
        name_score=name_score,
        dob_match=True,
        apaar_last4=apaar_last4,
        case_type=FlagType.NAME_MISMATCH.value,
    )


def identity_dob_mismatch(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return _row(
        "DOB_MISMATCH",
        "Date of birth on upload does not match the APAAR registry.",
        APAAR_LINE,
        "date of birth differs",
        name_score=name_score,
        dob_match=False,
        apaar_last4=apaar_last4,
        case_type=FlagType.NAME_MISMATCH.value,
    )


def identity_no_apaar() -> dict[str, Any]:
    return _row(
        "NO_APAAR",
        "APAAR not linked, and the student has not claimed the record through DigiLocker yet. "
        "Admission is not blocked.",
        "APAAR not linked; alternative route not used yet",
    )


def identity_digilocker_claim() -> dict[str, Any]:
    return _row(
        "DIGILOCKER_CLAIM",
        f"The student signed in with DigiLocker on {DATE} and claimed this record with its "
        "provisional ID; name and date of birth match.",
        DIGILOCKER_LINE,
    )


def identity_sii_confirmed() -> dict[str, Any]:
    return _row("SII_MATCH", "Study in India confirms the passport holder's identity.", SII_LINE)


def identity_sii_none() -> dict[str, Any]:
    return _row(
        "SII_NONE",
        "Study in India has no admission on record for this passport; see the Joining record row.",
        SII_LINE,
    )


# -------------------------------------------------------------------------- SEAT


def approval_line(version: int, cohort_year: str) -> str:
    """The Seat row's source: `AICTE approval v2, 2026-27 (Seat Ledger, derived)`."""
    return f"AICTE approval v{version}, {cohort_year} (Seat Ledger, derived)"


def _seat_keys(
    approval_id: uuid.UUID | None, version: int, seat_code: str | None, seat_type: SeatType
) -> dict[str, Any]:
    return {
        "approval_id": str(approval_id) if approval_id else None,
        "approval_version": version,
        "seat_code": seat_code,
        "seat_type": seat_type.value,
    }


def seat_confirmed(
    seat_code: str,
    seat_type: SeatType,
    *,
    approval_id: uuid.UUID | None,
    version: int,
    cohort_year: str,
) -> dict[str, Any]:
    return _row(
        "FITS",
        f"Holds seat {seat_code} ({SEAT_TYPE_WORDS[seat_type]}, AICTE approval v{version}, "
        f"{cohort_year}).",
        approval_line(version, cohort_year),
        "fits approved intake",
        **_seat_keys(approval_id, version, seat_code, seat_type),
    )


def seat_missing(
    seat_type: SeatType,
    programme_code: str,
    cohort_year: str,
    flag_type: FlagType,
    flag_dedupe_key: str,
    *,
    approval_id: uuid.UUID | None = None,
    version: int = 1,
) -> dict[str, Any]:
    return _row(
        "NO_SEAT",
        f"No {SEAT_TYPE_WORDS[seat_type]} seat is free in {programme_code} ({cohort_year}); "
        f"see the {FLAG_NAMES[flag_type]} case.",
        approval_line(version, cohort_year),
        "beyond approved intake",
        **_seat_keys(approval_id, version, None, seat_type),
        flag_type=flag_type.value,
        flag_dedupe_key=flag_dedupe_key,
        case_type=flag_type.value,
    )


def seat_no_pool(
    route: AdmissionRoute,
    seat_type: SeatType,
    programme_code: str,
    cohort_year: str,
    flag_type: FlagType,
    flag_dedupe_key: str,
    *,
    approval_id: uuid.UUID | None = None,
    version: int = 1,
) -> dict[str, Any]:
    word = SEAT_TYPE_WORDS[seat_type]
    return _row(
        "NO_POOL",
        f"{ROUTE_WORDS[route]} admission is not allowed for {programme_code}: approval "
        f"v{version} for {cohort_year} has no {word} seats.",
        approval_line(version, cohort_year),
        f"no {word} seats approved",
        **_seat_keys(approval_id, version, None, seat_type),
        flag_type=flag_type.value,
        flag_dedupe_key=flag_dedupe_key,
        case_type=flag_type.value,
    )


def seat_not_eligible(
    seat_code: str,
    seat_type: SeatType,
    *,
    rule: str,
    reported_word: str,
    clause: str,
    reported: dict[str, bool | None],
    approval_id: uuid.UUID | None,
    version: int,
    cohort_year: str,
) -> dict[str, Any]:
    return _row(
        "NOT_ELIGIBLE",
        f"{SEAT_TYPE_WORDS[seat_type]} seat held by a student reported as {reported_word}; "
        f"{clause} does not allow it.",
        approval_line(version, cohort_year),
        "not eligible for this seat",
        **_seat_keys(approval_id, version, seat_code, seat_type),
        eligibility_rule=rule,
        reported=reported,
        case_type=FlagType.ELIGIBILITY_BREACH.value,
    )


def seat_tfw_not_reported(
    seat_code: str,
    seat_type: SeatType,
    *,
    reported: dict[str, bool | None],
    approval_id: uuid.UUID | None,
    version: int,
    cohort_year: str,
) -> dict[str, Any]:
    return _row(
        "TFW_NOT_REPORTED",
        "TFW income certificate not reported; the seat is held until the college reports it.",
        approval_line(version, cohort_year),
        "TFW income certificate not reported",
        **_seat_keys(approval_id, version, seat_code, seat_type),
        eligibility_rule="TFW_INCOME",
        reported=reported,
    )


# ---------------------------------------------------------------- Joining record

AUTHORITY_LINE = f"State admission authority · {DATE}"


def round_words(round_no: int | None, route: str | None) -> str:
    """`round 1` for a counselling joining, else `Management admission approved by the state`."""
    if round_no is not None:
        return f"round {round_no}"
    try:
        word = ROUTE_WORDS[AdmissionRoute(route or "")]
    except ValueError:
        word = (route or "State").title()
    return f"{word} admission approved by the state"


def _joining_keys(joining_year: str, deadline: date, published: bool) -> dict[str, Any]:
    return {"joining_year": joining_year, "deadline": deadline.isoformat(), "published": published}


def admission_joined(
    *,
    state_name: str,
    programme_code: str,
    joining_year: str,
    deadline: date,
    joined_on: date,
    round_no: int | None,
    route: str | None,
    uploaded_route: AdmissionRoute,
    today: date,
) -> dict[str, Any]:
    joined = short_date(joined_on, today)
    return _row(
        "JOINED",
        f"The {state_name} admission authority records that the student joined "
        f"{programme_code} at this college on {joined} ({round_words(round_no, route)}).",
        AUTHORITY_LINE,
        f"joined {joined}",
        **_joining_keys(joining_year, deadline, True),
        joined_on=joined_on.isoformat(),
        round=round_no,
        route=route,
        route_mismatch=route is not None and route != uploaded_route.value,
    )


def admission_pending(
    *, state_name: str, joining_year: str, deadline: date, today: date
) -> dict[str, Any]:
    return _row(
        "NOT_YET_IN_RECORD",
        f"Not in the {state_name} admission authority's joining record yet; the reporting "
        f"deadline is {short_date(deadline, today)}.",
        AUTHORITY_LINE,
        "not in the joining record yet",
        **_joining_keys(joining_year, deadline, True),
    )


def admission_not_yet_due(
    *, state_name: str, joining_year: str, deadline: date, today: date
) -> dict[str, Any]:
    due = short_date(deadline, today)
    return _row(
        "NOT_PUBLISHED",
        f"The {state_name} admission authority publishes joining records by {due}.",
        f"Published by {due}",
        **_joining_keys(joining_year, deadline, False),
    )


def admission_unpublished_late(
    *, state_name: str, joining_year: str, deadline: date, today: date
) -> dict[str, Any]:
    due = short_date(deadline, today)
    return _row(
        "NOT_PUBLISHED_LATE",
        f"The {state_name} admission authority has not published its joining record for "
        f"{joining_year}; it was due by {due}.",
        f"Published by {due}",
        "not published yet",
        **_joining_keys(joining_year, deadline, False),
    )


def admission_not_found(
    *, state_name: str, programme_code: str, joining_year: str, deadline: date, today: date
) -> dict[str, Any]:
    return _row(
        "NOT_IN_JOINING_RECORD",
        f"Not found in the {state_name} admission authority's joining record for "
        f"{programme_code} ({joining_year}) after the reporting deadline of "
        f"{short_date(deadline, today)}.",
        AUTHORITY_LINE,
        "not found",
        **_joining_keys(joining_year, deadline, True),
        case_type=FlagType.NOT_IN_JOINING_RECORD.value,
    )


def admission_sii_confirmed(programme_code: str, cohort_year: str) -> dict[str, Any]:
    return _row(
        "SII_ADMITTED",
        f"Study in India confirms this admission to {programme_code} ({cohort_year}).",
        SII_LINE,
    )


def admission_sii_not_admitted() -> dict[str, Any]:
    return _row(
        "SII_NOT_ADMITTED",
        "Study in India has no matching admission for this passport at this institution.",
        SII_LINE,
        "not found",
        case_type=FlagType.NOT_IN_JOINING_RECORD.value,
    )


# ----------------------------------------------------------------------- Credits


@dataclass(frozen=True, slots=True)
class SemesterCredits:
    academic_year: str
    sem: int
    credits: int
    issuer: str | None = None
    issuer_name: str | None = None

    def wire(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "academic_year": self.academic_year,
            "sem": self.sem,
            "credits": self.credits,
        }
        if self.issuer:
            out["issuer"] = self.issuer
        return out


@dataclass(frozen=True, slots=True)
class CreditIssuers:
    """Who issued the credits read for one record (D38)."""

    self_issued: bool  # any semester read was issued by the claiming institution
    issuer: str | None  # the issuing body's code (several joined with ", ")
    issuer_name: str | None  # its name (several joined with "and")
    institution_name: str

    @property
    def supplied_by(self) -> str:
        if self.self_issued:
            return f"ABC, issued by {self.institution_name} (the college itself)"
        if self.issuer_name:
            return f"ABC, issued by {self.issuer_name}"
        return SOURCE_NAMES["ABC"]

    @property
    def source_line(self) -> str:
        if self.self_issued:
            return f"ABC, issued by {self.institution_name} itself · {DATE}"
        if self.issuer_name:
            return f"ABC, issued by {self.issuer_name} · {DATE}"
        return f"{SOURCE_NAMES['ABC']} · {DATE}"


def credit_issuers(
    semesters: Sequence[SemesterCredits], institution_code: str, institution_name: str
) -> CreditIssuers:
    """The issuers of the semesters that carry credits, in the order they first appear."""
    issuers: dict[str, str] = {}
    for s in semesters:
        if s.credits > 0 and s.issuer:
            issuers.setdefault(s.issuer, s.issuer_name or s.issuer)
    self_issued = institution_code in issuers
    return CreditIssuers(
        self_issued=self_issued,
        issuer=", ".join(issuers) or None,
        issuer_name=institution_name
        if self_issued
        else (_join_words(list(issuers.values())) or None),
        institution_name=institution_name,
    )


def studying_not_yet_due(expected_issuer: str | None) -> dict[str, Any]:
    return _row(
        "FIRST_YEAR",
        "First year; no semester result is due yet.",
        "First semester not complete",
        issuer_name=expected_issuer,
    )


def studying_not_yet_due_lateral(expected_issuer: str | None) -> dict[str, Any]:
    return _row(
        "LATERAL_FIRST_YEAR",
        "Lateral entry into year 2; no semester result here is due yet.",
        "Lateral entry; first semester here not complete",
        issuer_name=expected_issuer,
    )


def studying_no_apaar() -> dict[str, Any]:
    return _row(
        "NO_APAAR",
        "APAAR not linked; ABC credits cannot be checked.",
        "APAAR not linked; ABC cannot be checked",
    )


def studying_unknown_apaar() -> dict[str, Any]:
    return _row(
        "ABC_UNKNOWN",
        "ABC has no record of this APAAR; see the Identity row.",
        "ABC has no record of this APAAR",
    )


def studying_detail(
    semesters: Sequence[SemesterCredits], issuers: CreditIssuers | None = None
) -> dict[str, Any]:
    """CONFIRMED, PENDING (one semester missing) or CONTRADICTED (two or more), by `missing`."""
    issuers = issuers or credit_issuers(semesters, "", "")
    expected = len(semesters)
    missing = [s for s in semesters if s.credits <= 0]
    keys: dict[str, Any] = {
        "expected": expected,
        "missing": len(missing),
        "semesters": [s.wire() for s in semesters],
        "issuer": issuers.issuer,
        "issuer_name": issuers.issuer_name,
        "self_issued": issuers.self_issued,
    }
    line = issuers.source_line
    if not missing:
        finding = f"credits for {expected} semesters"
        if issuers.self_issued:
            return _row(
                "CREDITS_SELF_ISSUED",
                f"Credits recorded in ABC for all {expected} semesters, issued by the college "
                "itself. They do not count as evidence independent of the college.",
                line,
                finding,
                **keys,
            )
        by = f", issued by {issuers.issuer_name}" if issuers.issuer_name else ""
        return _row(
            "CREDITS",
            f"Credits recorded in ABC for all {expected} semesters since admission{by}.",
            line,
            finding,
            **keys,
        )
    if len(missing) == 1:
        gap = missing[0]
        return _row(
            "ONE_SEMESTER_MISSING",
            f"No credits recorded in ABC for semester {gap.sem} ({gap.academic_year}); waiting "
            "for the next results.",
            line,
            f"waiting for semester {gap.sem}",
            **keys,
            awaiting_semester=gap.sem,
        )
    return _row(
        "NO_ACADEMIC_ACTIVITY",
        f"No credits recorded in ABC for {len(missing)} of {expected} semesters since admission.",
        line,
        f"no credits for {len(missing)} semesters",
        **keys,
        case_type=FlagType.NO_ACADEMIC_ACTIVITY.value,
    )


# ================================================================== flag evidence

APAAR_RULE = "APAAR verification"


def invalid_apaar_not_found(
    apaar_last4: str | None, checked_on: date, related: Iterable[uuid.UUID | str]
) -> dict[str, Any]:
    return _evidence(
        f"APAAR ending {apaar_last4} is not in the APAAR registry.",
        [
            fact("APAAR (masked)", f"XXXX XXXX {apaar_last4}", "College upload"),
            fact("Registry reply", "Not found", "APAAR registry"),
            fact("Checked at", fmt_date(checked_on), "APAAR registry"),
        ],
        related,
        APAAR_RULE,
    )


def invalid_apaar_malformed(
    problem: str, value_masked: str, checked_on: date, related: Iterable[uuid.UUID | str]
) -> dict[str, Any]:
    return _evidence(
        f"APAAR as uploaded {problem}, so it could not be checked.",
        [
            fact("APAAR (masked)", value_masked, "College upload"),
            fact("Registry reply", "Not checked", "APAAR registry"),
            fact("Checked at", fmt_date(checked_on), "Countersign"),
        ],
        related,
        APAAR_RULE,
    )


def name_mismatch(
    *,
    name: str,
    name_score: int,
    dob_match: bool,
    checked_on: date,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    summary = (
        f"Name on upload differs from the APAAR registry (similarity {name_score} of 100)."
        if dob_match
        else "Date of birth on upload differs from the APAAR registry."
    )
    return _evidence(
        summary,
        [
            fact("Name on upload", name, "College upload"),
            fact("Similarity", f"{name_score} of 100", "APAAR registry"),
            fact("Date of birth match", "Yes" if dob_match else "No", "APAAR registry"),
            fact("Checked at", fmt_date(checked_on), "APAAR registry"),
        ],
        related,
        APAAR_RULE,
    )


def no_academic_activity(
    *,
    year_of_study: int,
    semesters: Sequence[SemesterCredits],
    last_entry: date | None,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    missing = sum(1 for s in semesters if s.credits <= 0)
    span = f"{semesters[0].academic_year} to {semesters[-1].academic_year}"
    return _evidence(
        f"No credits recorded in ABC for {missing} semesters while enrolled in year "
        f"{year_of_study}.",
        [
            fact("Semesters checked", f"{len(semesters)} ({span})", "ABC"),
            fact("Credits found", ", ".join(f"Sem {s.sem}: {s.credits}" for s in semesters), "ABC"),
            fact("Last ABC entry", fmt_date(last_entry) if last_entry else "None", "ABC"),
        ],
        related,
        "ABC credit record",
    )


def not_in_joining_record(
    *,
    state_name: str,
    programme_code: str,
    joining_year: str,
    deadline: date,
    checked_on: date,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    """The Joining record row is Contradicted after the reporting deadline (D39)."""
    return _evidence(
        f"Not found in the {state_name} admission authority's joining record for "
        f"{programme_code} ({joining_year}) after the reporting deadline of {fmt_date(deadline)}.",
        [
            fact("Programme and year", f"{programme_code} ({joining_year})", "College upload"),
            fact("Joining record", "Not found", SOURCE_NAMES["ADMISSION_AUTHORITY"]),
            fact("Checked on", fmt_date(checked_on), SOURCE_NAMES["ADMISSION_AUTHORITY"]),
            fact("Reporting deadline", fmt_date(deadline), "AICTE reporting schedule"),
        ],
        related,
        "State admission authority joining record",
    )


def not_in_study_in_india(
    *,
    programme_code: str,
    cohort_year: str,
    checked_on: date,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    """An international admission Study in India does not hold (API_CONTRACT §A4.11)."""
    return _evidence(
        "Study in India has no matching admission for this passport at this institution.",
        [
            fact("Programme and year", f"{programme_code} ({cohort_year})", "College upload"),
            fact("Study in India", "Not found", "Study in India"),
            fact("Checked on", fmt_date(checked_on), "Study in India"),
        ],
        related,
        "Study in India",
    )


def eligibility_breach(
    *,
    seat_code: str,
    seat_type: SeatType,
    programme_code: str,
    cohort_year: str,
    reported_word: str,
    allowed_words: str,
    clause: str,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    """A seat's category does not allow the student as reported (D41)."""
    word = SEAT_TYPE_WORDS[seat_type]
    return _evidence(
        f"{word} seat in {programme_code} ({cohort_year}) held by a student reported as "
        f"{reported_word}.",
        [
            fact("Seat", f"{seat_code} ({word})", "Seat Ledger"),
            fact("Reported as", reported_word, "College upload"),
            fact("Allowed for this seat", allowed_words, APPROVAL_RULES),
        ],
        related,
        clause,
    )


def late_refill(
    *,
    seat_code: str,
    released_on: date | None,
    assigned_on: date,
    cutoff: date,
    cohort_year: str,
    filename: str | None,
    row_no: int | None,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    return _evidence(
        f"Seat {seat_code} assigned on {fmt_date(assigned_on)}, after the last admission date "
        f"{fmt_date(cutoff)}.",
        [
            fact("Seat", seat_code, "Seat ledger"),
            fact("Released on", fmt_date(released_on) if released_on else "Unknown", "Seat ledger"),
            fact("Assigned on", fmt_date(assigned_on), upload_source(filename, row_no)),
            fact("Last admission date", fmt_date(cutoff), ADMISSION_SCHEDULE),
        ],
        related,
        f"Last admission date for {cohort_year} ({ADMISSION_SCHEDULE})",
    )


def upload_source(filename: str | None, row_no: int | None) -> str:
    if filename is None:
        return "College upload"
    if row_no is None:
        return f"College upload {filename}"
    return f"College upload {filename}, row {row_no}"


def excess_admission(
    *,
    programme_code: str,
    cohort_year: str,
    approved: int,
    admitted: int,
    seated: int,
    peak_unseated: int,
    rule_source: str,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    unseated = admitted - seated
    facts = [
        fact("Approved intake", approved, f"AICTE approval {cohort_year}"),
        fact("Admitted (active)", admitted, "College uploads, Regular and NRI routes"),
        fact("Seated", seated, "Seat ledger"),
        fact("Unseated", unseated, "Seat ledger"),
    ]
    if peak_unseated > unseated:
        facts.append(fact("Most unseated at once", peak_unseated, "Seat ledger"))
    return _evidence(
        f"{admitted} admitted against {approved} approved seats in {programme_code} "
        f"({cohort_year}); {unseated} without a seat.",
        facts,
        related,
        rule_source,
        data={
            "approved": approved,
            "admitted": admitted,
            "seated": seated,
            "unseated": unseated,
            "peak_unseated": peak_unseated,
        },
    )


def _share_words(share: float) -> str:
    pct = share * 100
    return f"{int(pct)}%" if float(pct).is_integer() else f"{round(pct, 2):g}%"


def quota_breach(
    *,
    seat_type: SeatType,
    programme_code: str,
    cohort_year: str,
    capacity: int,
    admitted: int,
    seated: int,
    unseated: int,
    peak_unseated: int,
    routes: Sequence[AdmissionRoute],
    share: float | None,
    approved: int,
    rule_source: str,
    related: Iterable[uuid.UUID | str],
) -> dict[str, Any]:
    word = SEAT_TYPE_WORDS[seat_type]
    route_words = "; ".join(ROUTE_WORDS[r] for r in routes)
    facts = [
        fact("Pool", word, "Seat ledger"),
        fact("Capacity", capacity, APPROVAL_RULES),
        fact("Admitted via route", f"{admitted} ({route_words})", "College uploads"),
        fact("Unseated", unseated, "Seat ledger"),
    ]
    if share is not None:
        facts.append(
            fact(
                "Rule percentage",
                f"{_share_words(share)} of approved intake {approved}",
                APPROVAL_RULES,
            )
        )
    return _evidence(
        f"{admitted} {word} admissions against {capacity} {word} seats in {programme_code} "
        f"({cohort_year}).",
        facts,
        related,
        rule_source,
        data={
            "capacity": capacity,
            "admitted": admitted,
            "seated": seated,
            "unseated": unseated,
            "peak_unseated": peak_unseated,
        },
    )


# ------------------------------------------------------------------- duplicates


@dataclass(frozen=True, slots=True)
class DuplicateSide:
    """One enrolment of a duplicate pair, as the evidence describes it."""

    enrolment_id: uuid.UUID
    institution_name: str
    state_name: str
    programme_name: str
    mode: ProgrammeMode
    name: str
    filename: str | None
    row_no: int | None
    uploaded_on: date


def match_words(*, same_apaar: bool, same_passport: bool, name_score: int | None, mobile: bool):
    """`Same APAAR`, `Same passport`, or `Name (96 of 100), date of birth and mobile`."""
    parts: list[str] = []
    if same_apaar:
        parts.append("Same APAAR")
    if same_passport:
        parts.append("Same passport" if not parts else "same passport")
    if not parts:
        words = []
        if name_score is not None:
            words.append(f"Name ({name_score} of 100)")
        words.append("date of birth")
        if mobile:
            words.append("mobile")
        joined = _join_words(words)
        return joined[:1].upper() + joined[1:]
    return _join_words(parts)


def _row_words(side: DuplicateSide) -> str:
    return f"{side.filename or 'College upload'}, row {side.row_no if side.row_no else '?'}"


def duplicate_within_upload(
    *, original: DuplicateSide, copy: DuplicateSide, words: str
) -> dict[str, Any]:
    """A is the original enrolment, B the suspected copy (the flag's enrolment)."""
    a, b = original, copy
    if a.filename is not None and a.filename == b.filename:
        low, high = sorted([a.row_no or 0, b.row_no or 0])
        summary = f"Rows {low} and {high} of {a.filename} describe the same student."
    else:
        summary = (
            f"Row {b.row_no or '?'} of {b.filename or 'a college upload'} describes the same "
            f"student as row {a.row_no or '?'} of {a.filename or 'a college upload'}."
        )
    return _evidence(
        summary,
        [
            fact("Match on", words, "Duplicate detection"),
            fact("Row A", _row_words(a), "College upload"),
            fact("Row B", _row_words(b), "College upload"),
            fact("Names as uploaded", f"{a.name} / {b.name}", "College upload"),
        ],
        [a.enrolment_id, b.enrolment_id],
        "Upload validation",
    )


def duplicate_cross_institution(
    *, own: DuplicateSide, other: DuplicateSide, words: str, academic_year: str
) -> dict[str, Any]:
    """A is the flag's own institution, B the other one."""
    a, b = own, other
    return _evidence(
        f"The same student appears as active at {a.institution_name} and "
        f"{b.institution_name} ({academic_year}).",
        [
            fact("Match on", words, "Duplicate detection"),
            fact(
                "Institution A programme",
                f"{a.institution_name}: {a.programme_name}",
                f"College upload {fmt_date(a.uploaded_on)}",
            ),
            fact(
                "Institution B programme",
                f"{b.institution_name}: {b.programme_name}",
                f"College upload {fmt_date(b.uploaded_on)}",
                AUDIENCE_OFFICER,
            ),
            fact(
                "Institution B programme",
                f"Another institution in {b.state_name}: {b.programme_name}",
                f"College upload {fmt_date(b.uploaded_on)}",
                AUDIENCE_INSTITUTION,
            ),
            fact(
                "Uploaded on",
                f"{fmt_date(a.uploaded_on)} and {fmt_date(b.uploaded_on)}",
                "College uploads",
            ),
        ],
        [a.enrolment_id, b.enrolment_id],
        "One active full-time enrolment per student",
        summary_for_institution=(
            "The same student appears as active here and at another institution in "
            f"{b.state_name} ({academic_year})."
        ),
    )


def dual_enrolment_allowed(*, own: DuplicateSide, other: DuplicateSide) -> dict[str, Any]:
    a, b = own, other
    return _evidence(
        "The student holds two enrolments; one is distance or online, which is permitted.",
        [
            fact(
                "Enrolment A mode",
                f"{a.institution_name}: {a.programme_name}, {MODE_WORDS[a.mode]}",
                "College upload",
            ),
            fact(
                "Enrolment B mode",
                f"{b.institution_name}: {b.programme_name}, {MODE_WORDS[b.mode]}",
                "College upload",
                AUDIENCE_OFFICER,
            ),
            fact(
                "Enrolment B mode",
                f"Another institution in {b.state_name}: {b.programme_name}, {MODE_WORDS[b.mode]}",
                "College upload",
                AUDIENCE_INSTITUTION,
            ),
            fact(
                "UGC notification", "Pursuing two academic programmes simultaneously, 2022", "UGC"
            ),
        ],
        [a.enrolment_id, b.enrolment_id],
        "UGC dual-degree guidelines 2022",
    )
