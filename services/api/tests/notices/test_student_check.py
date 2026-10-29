"""The STUDENT row: every row of API_CONTRACT §A3.8 and §A4.4, derived from notice facts alone."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, date, datetime, timedelta

from app.engine.checks.base import CheckSubject
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    CheckType,
    ConsentStatus,
    EnrolmentStatus,
    FlagType,
    NoticeChannel,
    NoticeDelivery,
    NoticeResponse,
    ProgrammeLevel,
    ProgrammeMode,
    SeatType,
    Severity,
)
from app.notices.student_check import NoticeFact, derive

NOW = datetime(2026, 11, 2, 6, 0, tzinfo=UTC)
SENT = datetime(2026, 10, 28, 4, 35, tzinfo=UTC)  # 28 Oct 2026, 10:05 IST
E_ID = uuid.UUID("e1e1e1e1-5555-4666-8777-888899990000")
EMAIL, DIGILOCKER = NoticeChannel.EMAIL, NoticeChannel.DIGILOCKER
YES, NO = NoticeResponse.YES, NoticeResponse.NO


def subject(*notices: NoticeFact, **overrides) -> CheckSubject:
    base = CheckSubject(
        enrolment_id=E_ID,
        student_id=uuid.uuid4(),
        institution_id=uuid.uuid4(),
        institution_aicte_id="1-ABC-0001",
        institution_name="ABC College of Engineering",
        state_code="MH",
        state_name="Maharashtra",
        programme_id=uuid.uuid4(),
        programme_code="CSE",
        programme_mode=ProgrammeMode.PHYSICAL,
        programme_level=ProgrammeLevel.UG,
        academic_year="2026-27",
        cohort_year="2026-27",
        year_of_study=1,
        admission_route=AdmissionRoute.COUNSELLING,
        counselling_ref=None,
        status=EnrolmentStatus.ACTIVE,
        seat_code=None,
        seat_type=None,
        seat_in_cohort_approval=False,
        target_seat_type=SeatType.REGULAR,
        target_capacity=120,
        name="Ravi Kumar Sharma",
        name_normalised="ravi kumar sharma",
        dob=date(2007, 3, 21),
        nationality="IN",
        consent_status=ConsentStatus.LINKED,
        apaar_last4="4417",
        apaar_problem=None,
        apaar_problem_masked=None,
        checked_on=date(2026, 10, 28),
        notices=tuple(notices),
        has_email=True,
    )
    return dataclasses.replace(base, **overrides)


def notice(
    channel: NoticeChannel = EMAIL,
    *,
    delivery: NoticeDelivery = NoticeDelivery.SENT,
    sent_at: datetime | None = SENT,
    expires_at: datetime | None = None,
    response: NoticeResponse | None = None,
    responded_at: datetime | None = None,
    previous: NoticeResponse | None = None,
    changed_at: datetime | None = None,
    comment: str | None = None,
) -> NoticeFact:
    if delivery is not NoticeDelivery.SENT and sent_at is SENT:
        sent_at = None
    return NoticeFact(
        id=uuid.uuid4(),
        channel=channel,
        delivery_status=delivery,
        sent_at=sent_at,
        expires_at=expires_at or SENT + timedelta(days=30),
        response=response,
        responded_at=responded_at,
        previous_response=previous,
        changed_at=changed_at,
        comment=comment,
    )


def test_row_1_a_no_on_one_channel_beats_a_yes_on_the_other():
    yes = notice(EMAIL, response=YES, responded_at=datetime(2026, 10, 29, 6, 0, tzinfo=UTC))
    no = notice(
        DIGILOCKER,
        response=NO,
        responded_at=datetime(2026, 10, 30, 6, 0, tzinfo=UTC),
        comment="I did not join this college.",
    )
    out = derive(subject(yes, no), now=NOW)
    assert (out.type, out.status, out.source) == (
        CheckType.STUDENT,
        CheckStatus.CONTRADICTED,
        "STUDENT_NOTICE",
    )
    assert out.detail == {
        "summary": "The student signed in with DigiLocker on 30 Oct and said they never joined.",
        "finding": '"I never joined"',
        "source_line": "Student sign-in via DigiLocker · {date}",
        "basis": "DENIED",
        "case_type": "STUDENT_DENIED",
        "notice_state": "DENIED",
        "channel": "DIGILOCKER",
        "sent_at": "2026-10-28T04:35:00Z",
        "responded_at": "2026-10-30T06:00:00Z",
        "changed": False,
    }
    [flag] = out.flags
    assert (flag.type, flag.severity) == (FlagType.STUDENT_DENIED, Severity.HIGH)
    assert flag.dedupe_key == f"STUDENT_DENIED:{E_ID}" and flag.enrolment_id == E_ID
    via = "Student sign-in via DigiLocker"
    assert flag.evidence == {
        "summary": (
            "The student said they never joined, after signing in with DigiLocker on 30 Oct 2026."
        ),
        "facts": [
            {"label": "Signed in with", "value": "DigiLocker", "source": via},
            {"label": "Notice sent", "value": "28 Oct 2026", "source": "Countersign"},
            {"label": "Answered on", "value": "30 Oct 2026", "source": via},
            {
                "label": "Comment from the student",
                "value": "I did not join this college.",
                "source": via,
                "audience": "OFFICER",
            },
        ],
        "related_enrolment_ids": [str(E_ID)],
        "rule_source": "Student's answer after DigiLocker sign-in",
    }


def test_row_1_takes_the_earliest_no_and_a_missing_comment_reads_none():
    late = notice(EMAIL, response=NO, responded_at=datetime(2026, 10, 31, 6, tzinfo=UTC))
    early = notice(DIGILOCKER, response=NO, responded_at=datetime(2026, 10, 29, 6, tzinfo=UTC))
    out = derive(subject(late, early), now=NOW)
    assert out.detail["summary"] == (
        "The student signed in with DigiLocker on 29 Oct and said they never joined."
    )
    assert out.flags[0].evidence["facts"][-1]["value"] == "None"
    # the answer that decides is the student's own, independent of the college
    assert (out.supplied_by, out.observed_at, out.independent) == (
        "Student via DigiLocker sign-in",
        datetime(2026, 10, 29, 6, tzinfo=UTC),
        True,
    )


def test_row_2_a_yes_passes_with_the_reply_date_in_india():
    # 21:00 UTC on 29 Oct is 30 Oct in India
    yes = notice(EMAIL, response=YES, responded_at=datetime(2026, 10, 29, 21, 0, tzinfo=UTC))
    out = derive(subject(yes, notice(DIGILOCKER)), now=NOW)
    assert out.status is CheckStatus.CONFIRMED and out.flags == ()
    assert (out.supplied_by, out.independent) == ("Student via DigiLocker sign-in", True)
    assert out.observed_at == datetime(2026, 10, 29, 21, 0, tzinfo=UTC)
    assert out.detail == {
        "summary": "The student signed in with DigiLocker on 30 Oct and said they joined.",
        "finding": '"I joined"',
        "source_line": "Student sign-in via DigiLocker · {date}",
        "basis": "CONFIRMED",
        "notice_state": "CONFIRMED",
        "channel": "EMAIL",
        "sent_at": "2026-10-28T04:35:00Z",
        "responded_at": "2026-10-29T21:00:00Z",
        "changed": False,
    }


def test_a_no_changed_to_yes_passes_and_keeps_the_flag_with_changed_evidence():
    changed = notice(
        DIGILOCKER,
        response=YES,
        responded_at=datetime(2026, 10, 29, 6, tzinfo=UTC),
        previous=NO,
        changed_at=datetime(2026, 10, 31, 6, tzinfo=UTC),
        comment="Pressed the wrong button.",
    )
    out = derive(subject(changed), now=NOW)
    assert out.status is CheckStatus.CONFIRMED
    assert out.detail["summary"] == (
        "The student said they never joined on 29 Oct, then changed the answer to Yes on 31 Oct."
    )
    assert out.detail["basis"] == "CONFIRMED_CHANGED"
    assert out.detail["changed"] is True
    assert out.detail["responded_at"] == "2026-10-31T06:00:00Z"
    [flag] = out.flags
    assert flag.evidence["summary"] == (
        "The student said they never joined on 29 Oct 2026, "
        "then changed the answer to Yes on 31 Oct 2026."
    )
    facts = {f["label"]: f["value"] for f in flag.evidence["facts"]}
    assert facts["Answered on"] == "29 Oct 2026"
    assert facts["Answer changed"] == "Yes on 31 Oct 2026"
    assert facts["Comment from the student"] == "Pressed the wrong button."


def test_a_yes_changed_to_no_fails_with_the_date_of_the_no():
    changed = notice(
        EMAIL,
        response=NO,
        responded_at=datetime(2026, 10, 29, 6, tzinfo=UTC),
        previous=YES,
        changed_at=datetime(2026, 10, 30, 6, tzinfo=UTC),
    )
    out = derive(subject(changed), now=NOW)
    assert out.status is CheckStatus.CONTRADICTED
    assert out.detail["summary"] == (
        "The student signed in with DigiLocker on 30 Oct and said they never joined."
    )
    assert out.detail["changed"] is True
    labels = [f["label"] for f in out.flags[0].evidence["facts"]]
    assert "Answer changed" not in labels
    assert out.flags[0].evidence["facts"][2]["value"] == "30 Oct 2026"


def test_row_3_unreachable_without_email_or_linked_apaar():
    for unlinked in (
        {"apaar_last4": None, "consent_status": ConsentStatus.PENDING},
        {"apaar_last4": "4417", "consent_status": ConsentStatus.REFUSED},
    ):
        out = derive(subject(has_email=False, **unlinked), now=NOW)
        assert out.status is CheckStatus.PENDING and out.flags == ()
        assert out.detail == {
            "summary": "Notice not sent yet.",
            "finding": "notice not sent yet",
            "source_line": "No notice sent yet",
            "basis": "UNREACHABLE",
            "notice_state": "UNREACHABLE",
        }
    # a notice that failed does not make a student without channels reachable
    failed = notice(EMAIL, delivery=NoticeDelivery.FAILED)
    out = derive(subject(failed, has_email=False, apaar_last4=None), now=NOW)
    assert out.detail["notice_state"] == "UNREACHABLE"


def test_row_4_not_sent_with_failed_delivery_and_withdrawn_consent():
    assert derive(subject(), now=NOW).detail == {
        "summary": "Notice not sent yet.",
        "finding": "notice not sent yet",
        "source_line": "No notice sent yet",
        "basis": "NOT_SENT",
        "notice_state": "NOT_SENT",
    }
    queued = notice(EMAIL, delivery=NoticeDelivery.QUEUED)
    assert derive(subject(queued), now=NOW).detail["notice_state"] == "NOT_SENT"
    failed = notice(DIGILOCKER, delivery=NoticeDelivery.FAILED)
    out = derive(subject(failed, notice_consent_withdrawn=True), now=NOW)
    assert out.status is CheckStatus.PENDING
    assert out.detail == {
        "summary": "Notice not sent yet.",
        "finding": "notice not sent yet",
        "source_line": "No notice sent yet",
        "basis": "NOT_SENT",
        "notice_state": "NOT_SENT",
        "delivery_failed": True,
        "consent_withdrawn": True,
    }


def test_row_5_sent_and_waiting_names_the_latest_live_notice():
    older = notice(EMAIL)
    newer = notice(DIGILOCKER, sent_at=SENT + timedelta(days=1))
    out = derive(subject(older, newer), now=NOW)
    assert out.status is CheckStatus.PENDING and out.flags == ()
    assert out.detail == {
        "summary": "Notice sent on 29 Oct; no answer yet.",
        "finding": "no answer yet",
        "source_line": "Notice sent 29 Oct",
        "basis": "SENT",
        "notice_state": "SENT",
        "channel": "DIGILOCKER",
        "sent_at": "2026-10-29T04:35:00Z",
    }


def test_row_6_every_delivered_notice_expired_is_pending_never_fail():
    expired = notice(EMAIL, expires_at=NOW - timedelta(hours=1))
    out = derive(subject(expired, notice(DIGILOCKER, delivery=NoticeDelivery.FAILED)), now=NOW)
    assert out.status is CheckStatus.PENDING and out.flags == ()
    assert out.detail == {
        "summary": (
            "No answer before the notice expired on 2 Nov. Silence never counts against the record."
        ),
        "finding": "no answer",
        "source_line": "Notice expired 2 Nov",
        "basis": "EXPIRED",
        "notice_state": "EXPIRED",
        "channel": "EMAIL",
        "sent_at": "2026-10-28T04:35:00Z",
    }
    # one live notice keeps it waiting
    live = notice(DIGILOCKER, sent_at=SENT + timedelta(days=2))
    assert derive(subject(expired, live), now=NOW).detail["notice_state"] == "SENT"
