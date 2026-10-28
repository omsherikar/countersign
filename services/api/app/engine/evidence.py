"""Check details and flag evidence, with the sentences of API_CONTRACT A2.14 and A2.17.

Officers and the web read these sentences verbatim and never rebuild them, so every
template lives here and nowhere else. A check `detail` always has a `summary`; flag
evidence is `{summary, summary_for_institution?, facts, related_enrolment_ids,
rule_source, data?}` (DATA_MODEL "Migration 0002"). No summary ever holds a student
name or a full id; facts may hold the name as uploaded.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.models.enums import AdmissionRoute, FlagType, ProgrammeMode, SeatType

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

SOURCE_NAMES = {
    "APAAR": "APAAR registry",
    "COUNSELLING": "Counselling list",
    "SEAT_LEDGER": "Seat ledger",
    "ABC": "ABC credits",
    "SII": "Study in India",
    "STUDENT_NOTICE": "Student reply",
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
    FlagType.STUDENT_DENIED: "Student denied",
    FlagType.GHOST_RING: "Shared contact ring",
    FlagType.ANOMALY: "Unusual pattern",
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


# =================================================================== check details


def source_unavailable(
    source: str, error: str | None = None, *, disabled: bool = False
) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "summary": (
            f"{SOURCE_NAMES[source]} did not respond. "
            "This check stays pending until a recheck or the next upload."
        ),
        "source_unavailable": True,
    }
    if disabled:
        detail["source_disabled"] = True
    if error:
        detail["source_error"] = error
    return detail


# ---------------------------------------------------------------------- IDENTITY


def identity_no_apaar() -> dict[str, Any]:
    return {"summary": "APAAR not linked; admission is not blocked."}


def identity_international() -> dict[str, Any]:
    return {
        "summary": "International student; identity is checked through the passport, not APAAR."
    }


def identity_malformed(problem: str) -> dict[str, Any]:
    return {"summary": f"APAAR as uploaded {problem}; the enrolment was kept without it."}


def identity_not_found(apaar_last4: str | None) -> dict[str, Any]:
    """The registry has no such id, so it returned no name score and no date check."""
    return {
        "summary": f"APAAR ending {apaar_last4} is not in the APAAR registry.",
        "apaar_last4": apaar_last4,
    }


def identity_dob_mismatch(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return {
        "summary": "Date of birth on upload does not match the APAAR registry.",
        "name_score": name_score,
        "dob_match": False,
        "apaar_last4": apaar_last4,
    }


def identity_name_differs(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return {
        "summary": (
            f"Name on upload differs from the APAAR registry (similarity {name_score} of 100)."
        ),
        "name_score": name_score,
        "dob_match": True,
        "apaar_last4": apaar_last4,
    }


def identity_review(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return {
        "summary": (
            "Name on upload is close to the APAAR registry but not a clear match "
            f"(similarity {name_score} of 100); an officer should review."
        ),
        "name_score": name_score,
        "dob_match": True,
        "needs_review": True,
        "apaar_last4": apaar_last4,
    }


def identity_pass(name_score: int, apaar_last4: str | None) -> dict[str, Any]:
    return {
        "summary": (
            f"Name and date of birth match the APAAR registry (similarity {name_score} of 100)."
        ),
        "name_score": name_score,
        "dob_match": True,
        "apaar_last4": apaar_last4,
    }


# --------------------------------------------------------------------- ADMISSION


def admission_counselling_found(
    *,
    state_name: str,
    programme_code: str,
    cohort_start: int,
    round_no: int | None,
    allotment_ref: str | None,
    counselling_ref: str | None,
) -> dict[str, Any]:
    mismatch = bool(counselling_ref) and bool(allotment_ref) and allotment_ref != counselling_ref
    head = (
        f"Found in the {state_name} counselling allotments for {programme_code} "
        f"({cohort_start}), round {round_no}"
    )
    summary = (
        f"{head}, as {allotment_ref}; the upload says {counselling_ref}."
        if mismatch
        else f"{head}."
    )
    return {
        "summary": summary,
        "round": round_no,
        "allotment_ref": allotment_ref,
        "ref_mismatch": mismatch,
    }


def admission_counselling_not_found(
    *, state_name: str, programme_code: str, cohort_start: int
) -> dict[str, Any]:
    return {
        "summary": (
            f"Not found in the {state_name} counselling allotments for {programme_code} "
            f"({cohort_start})."
        )
    }


def admission_seat_rules_pass(
    route: AdmissionRoute, programme_code: str, seat_type: SeatType
) -> dict[str, Any]:
    return {
        "summary": (
            f"{ROUTE_WORDS[route]} admission is allowed for {programme_code} and holds a "
            f"{SEAT_TYPE_WORDS[seat_type]} seat."
        ),
        "seat_type": seat_type.value,
    }


def admission_seat_rules_no_pool(
    route: AdmissionRoute, programme_code: str, cohort_year: str, seat_type: SeatType
) -> dict[str, Any]:
    return {
        "summary": (
            f"{ROUTE_WORDS[route]} admission is not allowed for {programme_code}: the "
            f"{cohort_year} approval has no {SEAT_TYPE_WORDS[seat_type]} seats."
        ),
        "seat_type": seat_type.value,
    }


def admission_seat_rules_no_seat(
    route: AdmissionRoute, programme_code: str, cohort_year: str, seat_type: SeatType
) -> dict[str, Any]:
    return {
        "summary": (
            f"{ROUTE_WORDS[route]} admission has no {SEAT_TYPE_WORDS[seat_type]} seat in "
            f"{programme_code} ({cohort_year})."
        ),
        "seat_type": seat_type.value,
    }


def admission_sii_confirms(programme_code: str, cohort_year: str) -> dict[str, Any]:
    return {
        "summary": f"Study in India confirms this admission to {programme_code} ({cohort_year})."
    }


def admission_sii_no_match() -> dict[str, Any]:
    return {
        "summary": (
            "Study in India has no matching admission for this passport at this institution."
        )
    }


# -------------------------------------------------------------------------- SEAT


def seat_holds(seat_code: str, seat_type: SeatType, cohort_year: str) -> dict[str, Any]:
    return {
        "summary": (
            f"Holds seat {seat_code} ({SEAT_TYPE_WORDS[seat_type]}, {cohort_year} approval)."
        ),
        "seat_code": seat_code,
        "seat_type": seat_type.value,
    }


def seat_missing(
    seat_type: SeatType,
    programme_code: str,
    cohort_year: str,
    flag_type: FlagType,
    flag_dedupe_key: str,
) -> dict[str, Any]:
    return {
        "summary": (
            f"No {SEAT_TYPE_WORDS[seat_type]} seat is free in {programme_code} ({cohort_year}); "
            f"see the {FLAG_NAMES[flag_type]} flag."
        ),
        "seat_code": None,
        "seat_type": seat_type.value,
        "flag_type": flag_type.value,
        "flag_dedupe_key": flag_dedupe_key,
    }


# ---------------------------------------------------------------------- STUDYING


@dataclass(frozen=True, slots=True)
class SemesterCredits:
    academic_year: str
    sem: int
    credits: int

    def wire(self) -> dict[str, Any]:
        return {"academic_year": self.academic_year, "sem": self.sem, "credits": self.credits}


def studying_first_year() -> dict[str, Any]:
    return {"summary": "First year, no result yet."}


def studying_lateral_entry() -> dict[str, Any]:
    return {"summary": "Joined in year 2 as a lateral entrant; no completed year to check yet."}


def studying_no_apaar() -> dict[str, Any]:
    return {"summary": "APAAR not linked; ABC credits cannot be checked."}


def studying_unknown_apaar() -> dict[str, Any]:
    return {"summary": "ABC has no record of this APAAR; see the Identity check."}


def studying_detail(semesters: Sequence[SemesterCredits]) -> dict[str, Any]:
    """PASS, PENDING (one semester missing) or FAIL (two or more), by the missing count."""
    expected = len(semesters)
    missing = [s for s in semesters if s.credits <= 0]
    detail: dict[str, Any] = {
        "expected": expected,
        "missing": len(missing),
        "semesters": [s.wire() for s in semesters],
    }
    if not missing:
        summary = f"Credits recorded in ABC for all {expected} semesters since admission."
    elif len(missing) == 1:
        gap = missing[0]
        summary = (
            f"No credits recorded in ABC for semester {gap.sem} ({gap.academic_year}); "
            "waiting for the next upload."
        )
        detail["awaiting_semester"] = gap.sem
    else:
        summary = (
            f"No credits recorded in ABC for {len(missing)} of {expected} semesters "
            "since admission."
        )
    return {"summary": summary, **detail}


# ----------------------------------------------------------------------- STUDENT


def student_notice_not_sent() -> dict[str, Any]:
    return {"summary": "Notice not sent yet."}


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
