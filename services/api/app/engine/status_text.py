"""The sentences of a record's status: copy deck §21 `status_reason.*` and `next_step.*`.

`app.engine.status.decide` fills them; nothing else writes them. Dates inside them follow
API_CONTRACT §A4.1: `12 Aug` in the current calendar year (IST), `12 Aug 2025` otherwise.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from app.models.enums import CheckType, FlagType

IST = timezone(timedelta(hours=5, minutes=30), "IST")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# the deck's row labels (`check.*`)
ROW_LABELS = {
    CheckType.IDENTITY: "Identity",
    CheckType.SEAT: "Seat",
    CheckType.ADMISSION: "Joining record",
    CheckType.STUDYING: "Credits",
    CheckType.STUDENT: "Student",
}
# copy deck §5 `flag.<TYPE>.name`
CASE_NAMES = {
    FlagType.EXCESS_ADMISSION: "Excess admission",
    FlagType.QUOTA_BREACH: "Quota breach",
    FlagType.LATE_REFILL: "Late refill",
    FlagType.INVALID_APAAR: "APAAR not verified",
    FlagType.NAME_MISMATCH: "Name or date of birth mismatch",
    FlagType.DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
    FlagType.DUPLICATE_WITHIN_UPLOAD: "Duplicate within institution",
    FlagType.DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
    FlagType.NO_ACADEMIC_ACTIVITY: "No academic activity",
    FlagType.NOT_IN_JOINING_RECORD: "Not in joining record",
    FlagType.ELIGIBILITY_BREACH: "Seat category not eligible",
    FlagType.MISSING_FROM_UPLOAD: "Missing from upload",
    FlagType.STUDENT_DENIED: "Student dispute",
    FlagType.GHOST_RING: "Shared contact ring",
    FlagType.ANOMALY: "Unusual pattern",
}
# copy deck §6 `docs_kind.<KIND>.words`
DOCS_WORDS = {
    "ADMISSION": "admission documents",
    "JOINING": "the joining report",
    "IDENTITY": "identity documents",
    "ELIGIBILITY": "eligibility certificates",
    "CREDITS": "semester results",
    "OTHER": "documents",
}

# status_reason.*
DISPUTED = "The student said they never joined, after signing in with DigiLocker on {reply_date}."
DISPUTED_UNDATED = "The student said they never joined."
UNDER_REVIEW_ROW = "{check} is contradicted: {finding}."
UNDER_REVIEW_ROW_PLAIN = "{check} is contradicted."
UNDER_REVIEW_CASE = "An open {case_name} case names this record."
COUNTERSIGNED = (
    "Identity, seat and {independent_rows} confirm the record, and nothing is unresolved."
)
NOT_CONFIRMED = "{check} is not confirmed yet: {finding}."
NOT_CONFIRMED_PLAIN = "{check} is not confirmed yet."
UPHELD = (
    "An officer upheld the claim on {date}, but no evidence independent of the college "
    "confirms the record yet."
)
ONLY_SELF = "The only enrolment evidence so far comes from the college itself."
NO_INDEPENDENT = "No enrolment evidence independent of the college yet."

# next_step.*
DOCS_REQUESTED = "College asked for {docs_words} by {due_date}."
DOCS_REQUESTED_NO_DATE = "College asked for {docs_words}; no reply date set."
DOCS_OVERDUE = "College was asked for {docs_words} by {due_date}; no response yet."
RESPONDED = "College responded on {date}; waiting for an officer's decision."
RESPONDED_UNDATED = "College responded; waiting for an officer's decision."
ESCALATED = "Escalated to AICTE on {date}; waiting for a decision."
ESCALATED_UNDATED = "Escalated to AICTE; waiting for a decision."
DISPUTE_OPEN = "Waiting for an officer to review the student's dispute."
CASE_OPEN = "Waiting for an officer to review the {case_name} case."
CASE_REOPEN = "Waiting for an officer to reopen the {case_name} case."
CONTRADICTION_OPEN = "Waiting for an officer to review the contradiction."
JOINING_RECORD = "Waiting for the joining record from the state admission authority."
JOINING_DEADLINE = (
    "Waiting for the joining record; the state admission authority publishes it by {deadline_date}."
)
IDENTITY_CLAIM = (
    "Waiting for the student to sign in with DigiLocker and claim this record with its "
    "provisional ID."
)
SOURCE_UNAVAILABLE = (
    "Waiting for {source_name}, which did not respond; it is asked again at the next recheck."
)
SEAT_TFW = "Waiting for the college to report the TFW income certificate."
CREDITS = "Waiting for credits from {issuer_name} after the semester {sem} result."
CREDITS_UNNUMBERED = "Waiting for credits from {issuer_name}."
STUDENT = (
    "Waiting for evidence independent of the college; the student's notice was sent on {sent_date}."
)
STUDENT_NOT_SENT = (
    "Waiting for evidence independent of the college; no notice has reached the student yet."
)
NO_ROUTE = "Waiting for evidence independent of the college."
NONE = "None. The evidence is complete."
WITHDRAWN = "None. The record was withdrawn by an officer's decision on {date}."


def ist_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(IST).date()
    return value


def day(value: date | datetime, today: date) -> str:
    """`12 Aug` in the current calendar year, `12 Aug 2025` otherwise."""
    on = ist_date(value)
    words = f"{on.day} {MONTHS[on.month - 1]}"
    return words if on.year == today.year else f"{words} {on.year}"


def join_words(parts: list[str]) -> str:
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def evidence_words(row_type: CheckType, issuer_name: str | None) -> str:
    """How `{independent_rows}` names one confirmed independent row."""
    if row_type is CheckType.ADMISSION:
        return "the joining record"
    if row_type is CheckType.STUDYING:
        return f"credits from {issuer_name or 'ABC'}"
    return "the student's own answer"
