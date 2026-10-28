"""The privacy notice and consent texts (D30), mirrored from the copy deck.

A consent row keeps the exact text the student saw and the version it was given under, so
a change of wording is a new version here, never an edit of an old one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from app.models.enums import ConsentPurpose

NOTICE_VERSION = "v1"
EFFECTIVE_FROM = date(2026, 10, 28)

PRIVACY_NOTICE: Mapping[str, Any] = {
    "title": "How Countersign uses your data",
    "sections": (
        {
            "id": "what_we_hold",
            "heading": "What we hold",
            "body": (
                "Your college uploads your enrolment: your name, date of birth, gender, "
                "nationality, email, mobile number and address, your programme, year of "
                "study, admission route and category, and your APAAR id when you allowed it "
                "to be linked. Your APAAR id and passport number are stored encrypted, your "
                "mobile number and address only as keyed fingerprints, and officers see only "
                "the last four digits of your APAAR id. Countersign also holds the results of "
                "the checks on your enrolment, any flags raised about it, the notices sent to "
                "you and your replies, the proofs in your wallet, and a log of who viewed "
                "your record."
            ),
        },
        {
            "id": "why_we_use_it",
            "heading": "Why we use it",
            "body": (
                "AICTE uses your data only to check that your enrolment is genuine: that the "
                "seat was approved, that your admission matches the counselling allotment, "
                "that your identity matches the APAAR registry and that you are studying. "
                "Nothing is decided automatically. When a check does not agree, an officer "
                "reads the evidence and decides, and Countersign never cancels an admission."
            ),
        },
        {
            "id": "where_we_check",
            "heading": "Where we check it",
            "body": (
                "With your consent, AICTE looks up your APAAR id with the APAAR registry, the "
                "state counselling allotment list and the Academic Bank of Credits, and sends "
                "you a notice by email or through DigiLocker so that you can confirm the "
                "enrolment yourself. International students are checked against Study in "
                "India records using their passport."
            ),
        },
        {
            "id": "who_sees_it",
            "heading": "Who sees it",
            "body": (
                "AICTE officers, the regional officer for your college's region, your college "
                "and, once you graduate, your university see your enrolment with your APAAR "
                "masked. Your college sees your reply to a notice only as Confirmed or "
                "Denied; a comment you add is seen only by AICTE officers. When you share a "
                "proof, whoever checks it sees only the fields you chose."
            ),
        },
        {
            "id": "your_rights",
            "heading": "Your rights",
            "body": (
                "On your Privacy page you can read what you agreed to in the exact words you "
                "saw, stop new notices, stop sharing your proofs, see who viewed your record "
                "by role and date, download a copy of everything Countersign holds about you, "
                "and ask for a correction or an erasure. AICTE answers every request in "
                "writing on the same page."
            ),
        },
        {
            "id": "how_long",
            "heading": "How long we keep it",
            "body": (
                "Enrolment records, their checks and flags, and the audit log are kept for "
                "the period the law requires, so they cannot be erased on request. Contact "
                "details and anything not needed for that record can be removed when you ask."
            ),
        },
    ),
}

# copy deck §9: stored verbatim, with {institution_name} filled in, when consent is recorded
CONSENT_TEXTS: Mapping[ConsentPurpose, str] = {
    ConsentPurpose.APAAR_LINK: (
        "I allow AICTE to use my APAAR id to check that my enrolment at {institution_name} is "
        "genuine. AICTE will look up my id with the APAAR registry, the counselling allotment "
        "list and the Academic Bank of Credits. Only the last four digits of my id are shown "
        "to officers. To unlink my APAAR later, I can ask from my Privacy page; my college "
        "then uploads my enrolment again without it. Checks already made stay on record, and "
        "my admission is not affected."
    ),
    ConsentPurpose.NOTICE: (
        "By replying, you let AICTE record your answer with today's date against this "
        "enrolment. Your answer is shown to AICTE officers and to {institution_name} as "
        '"Confirmed" or "Denied", with no other personal detail. If you add a comment, only '
        "AICTE officers see it."
    ),
    ConsentPurpose.CREDENTIAL_SHARE: (
        "I am creating a proof that shows only the fields I ticked. Whoever scans it sees "
        "those fields, who issued the proof and when, and nothing else. The proof works for "
        "10 minutes. AICTE records when it is created and when it is checked, but not who "
        "checks it."
    ),
}

# copy deck consent.withdraw.*: the confirmation shown before a withdrawal
WITHDRAW_TEXTS: Mapping[ConsentPurpose, str] = {
    ConsentPurpose.NOTICE: (
        "Stop new notices? You will get no new notices about your enrolments. Notices already "
        "sent can still be answered, and replies you gave stay on record."
    ),
    ConsentPurpose.CREDENTIAL_SHARE: (
        "Stop sharing? Every QR or link you created that still works stops working now. Your "
        "proofs stay in your wallet, and sharing again asks for your consent again."
    ),
}

UNLINK_APAAR = (
    "To unlink your APAAR, send a correction request. Your college must upload your record "
    "again; your admission is not affected."
)


def consent_text(purpose: ConsentPurpose, **values: str) -> str:
    """The consent text with its placeholders filled; unknown placeholders stay as they are."""
    text = CONSENT_TEXTS[purpose]
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def public_notice() -> dict[str, Any]:
    """The GET /privacy/notice body; consent texts keep their placeholders."""
    return {
        "version": NOTICE_VERSION,
        "effective_from": EFFECTIVE_FROM.isoformat(),
        "title": PRIVACY_NOTICE["title"],
        "sections": [dict(section) for section in PRIVACY_NOTICE["sections"]],
        "consent_texts": {purpose.value: text for purpose, text in CONSENT_TEXTS.items()},
    }
