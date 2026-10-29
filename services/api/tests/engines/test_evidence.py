"""Every sentence the engines store, against API_CONTRACT A2.14 and A2.17 verbatim."""

from __future__ import annotations

import uuid
from datetime import date

from app.engine import evidence as ev
from app.models.enums import AdmissionRoute, FlagType, ProgrammeMode, SeatType

E1, E2 = uuid.uuid4(), uuid.uuid4()


def test_dates_in_sentences() -> None:
    assert ev.fmt_date(date(2026, 10, 5)) == "5 Oct 2026"
    assert ev.fmt_date(date(2026, 9, 15)) == "15 Sep 2026"


def test_source_unavailable() -> None:
    detail = ev.source_unavailable("APAAR", "HTTP 503")
    assert detail == {
        "summary": (
            "APAAR registry did not respond. "
            "This row is asked again at the next recheck or the next upload."
        ),
        "finding": None,
        "source_line": "APAAR registry did not respond · {date}",
        "basis": "SOURCE_UNAVAILABLE",
        "source_unavailable": True,
        "source_error": "HTTP 503",
    }
    assert ev.source_unavailable("SII", disabled=True)["source_disabled"] is True
    assert ev.source_unavailable("ABC")["summary"].startswith("ABC credits did not respond.")
    assert ev.source_unavailable("ADMISSION_AUTHORITY")["summary"].startswith(
        "State admission authority did not respond."
    )


def _texts(detail: dict) -> tuple:
    return detail["basis"], detail["finding"], detail["source_line"], detail["summary"]


def test_identity_sentences() -> None:
    assert _texts(ev.identity_no_apaar()) == (
        "NO_APAAR",
        None,
        "APAAR not linked; alternative route not used yet",
        "APAAR not linked, and the student has not claimed the record through DigiLocker yet. "
        "Admission is not blocked.",
    )
    assert _texts(ev.identity_malformed("has 11 digits, expected 12")) == (
        "APAAR_MALFORMED",
        "APAAR not valid",
        "College upload · {date}",
        "APAAR as uploaded has 11 digits, expected 12; the record was kept without it.",
    )
    assert _texts(ev.identity_not_found("4417")) == (
        "APAAR_UNKNOWN",
        "APAAR not found",
        "APAAR verification · {date}",
        "APAAR ending 4417 is not in the APAAR registry.",
    )
    assert _texts(ev.identity_dob_mismatch(100, "4417"))[1:] == (
        "date of birth differs",
        "APAAR verification · {date}",
        "Date of birth on upload does not match the APAAR registry.",
    )
    assert _texts(ev.identity_name_differs(62, "4417"))[1:] == (
        "name differs",
        "APAAR verification · {date}",
        "Name on upload differs from the APAAR registry (similarity 62 of 100).",
    )
    review = ev.identity_review(81, "4417")
    assert _texts(review)[1:] == (
        "needs review",
        "APAAR verification · {date}",
        "Name on upload is close to the APAAR registry but not a clear match "
        "(similarity 81 of 100); an officer should review. Name matching supports a decision; "
        "it never makes one.",
    )
    assert (review["needs_review"], review["case_type"]) == (True, "NAME_MISMATCH")
    assert _texts(ev.identity_confirmed(100, "4417")) == (
        "APAAR_MATCH",
        None,
        "APAAR verification · {date}",
        "Name and date of birth match the APAAR registry (similarity 100 of 100).",
    )
    assert _texts(ev.identity_digilocker_claim())[2:] == (
        "Student sign-in via DigiLocker · {date}",
        "The student signed in with DigiLocker on {date} and claimed this record with its "
        "provisional ID; name and date of birth match.",
    )
    assert _texts(ev.identity_sii_confirmed())[2:] == (
        "Study in India · {date}",
        "Study in India confirms the passport holder's identity.",
    )
    assert ev.identity_sii_none()["summary"] == (
        "Study in India has no admission on record for this passport; see the Joining record row."
    )


def test_joining_record_sentences() -> None:
    today = date(2026, 10, 29)
    words = {"state_name": "Maharashtra", "joining_year": "2026-27", "deadline": date(2026, 9, 30)}
    joined = ev.admission_joined(
        programme_code="CSE",
        joined_on=date(2026, 8, 2),
        round_no=1,
        route="COUNSELLING",
        uploaded_route=AdmissionRoute.COUNSELLING,
        today=today,
        **words,
    )
    assert _texts(joined) == (
        "JOINED",
        "joined 2 Aug",
        "State admission authority · {date}",
        "The Maharashtra admission authority records that the student joined CSE at this "
        "college on 2 Aug (round 1).",
    )
    assert joined["route_mismatch"] is False
    assert ev.round_words(None, "NRI") == "NRI admission approved by the state"
    assert _texts(ev.admission_pending(today=date(2026, 9, 1), **words))[1:] == (
        "not in the joining record yet",
        "State admission authority · {date}",
        "Not in the Maharashtra admission authority's joining record yet; the reporting "
        "deadline is 30 Sep.",
    )
    assert _texts(ev.admission_not_yet_due(today=date(2026, 9, 1), **words))[1:] == (
        None,
        "Published by 30 Sep",
        "The Maharashtra admission authority publishes joining records by 30 Sep.",
    )
    assert _texts(ev.admission_unpublished_late(today=today, **words))[1:] == (
        "not published yet",
        "Published by 30 Sep",
        "The Maharashtra admission authority has not published its joining record for "
        "2026-27; it was due by 30 Sep.",
    )
    missing = ev.admission_not_found(programme_code="CSE", today=today, **words)
    assert _texts(missing)[1:] == (
        "not found",
        "State admission authority · {date}",
        "Not found in the Maharashtra admission authority's joining record for CSE (2026-27) "
        "after the reporting deadline of 30 Sep.",
    )
    assert missing["case_type"] == "NOT_IN_JOINING_RECORD"
    assert ev.admission_sii_confirmed("CSE", "2026-27")["summary"] == (
        "Study in India confirms this admission to CSE (2026-27)."
    )
    assert ev.admission_sii_not_admitted()["summary"] == (
        "Study in India has no matching admission for this passport at this institution."
    )
    # a date in another year carries the year
    assert ev.short_date(date(2025, 8, 12), today) == "12 Aug 2025"


def test_seat_sentences() -> None:
    holds = ev.seat_confirmed(
        "CSE-R-001", SeatType.REGULAR, approval_id=None, version=2, cohort_year="2026-27"
    )
    assert _texts(holds) == (
        "FITS",
        "fits approved intake",
        "AICTE approval v2, 2026-27 (Seat Ledger, derived)",
        "Holds seat CSE-R-001 (Regular, AICTE approval v2, 2026-27).",
    )
    missing = ev.seat_missing(
        SeatType.REGULAR, "CSE", "2026-27", FlagType.EXCESS_ADMISSION, "EXCESS_ADMISSION:x"
    )
    assert _texts(missing)[1:] == (
        "beyond approved intake",
        "AICTE approval v1, 2026-27 (Seat Ledger, derived)",
        "No Regular seat is free in CSE (2026-27); see the Excess admission case.",
    )
    assert missing["flag_type"] == missing["case_type"] == "EXCESS_ADMISSION"
    assert missing["flag_dedupe_key"] == "EXCESS_ADMISSION:x"
    no_pool = ev.seat_no_pool(
        AdmissionRoute.NRI, SeatType.NRI, "CSE", "2026-27", FlagType.QUOTA_BREACH, "k"
    )
    assert _texts(no_pool)[1:] == (
        "no NRI seats approved",
        "AICTE approval v1, 2026-27 (Seat Ledger, derived)",
        "NRI admission is not allowed for CSE: approval v1 for 2026-27 has no NRI seats.",
    )


def test_credits_sentences() -> None:
    S = ev.SemesterCredits
    assert _texts(ev.studying_not_yet_due("Maharashtra State Technical University"))[1:] == (
        None,
        "First semester not complete",
        "First year; no semester result is due yet.",
    )
    assert _texts(ev.studying_not_yet_due_lateral(None))[2:] == (
        "Lateral entry; first semester here not complete",
        "Lateral entry into year 2; no semester result here is due yet.",
    )
    assert _texts(ev.studying_no_apaar())[2:] == (
        "APAAR not linked; ABC cannot be checked",
        "APAAR not linked; ABC credits cannot be checked.",
    )
    assert _texts(ev.studying_unknown_apaar())[2:] == (
        "ABC has no record of this APAAR",
        "ABC has no record of this APAAR; see the Identity row.",
    )
    mstu = ("MSTU", "Maharashtra State Technical University")
    sems = [S("2025-26", 1, 22, *mstu), S("2025-26", 2, 24, *mstu)]
    issuers = ev.credit_issuers(sems, "1-ABC-0001", "ABC College of Engineering")
    assert (issuers.supplied_by, issuers.self_issued) == (
        "ABC, issued by Maharashtra State Technical University",
        False,
    )
    assert _texts(ev.studying_detail(sems, issuers)) == (
        "CREDITS",
        "credits for 2 semesters",
        "ABC, issued by Maharashtra State Technical University · {date}",
        "Credits recorded in ABC for all 2 semesters since admission, issued by Maharashtra "
        "State Technical University.",
    )
    own = [S("2025-26", 1, 22, "1-ABC-0001", "ABC"), S("2025-26", 2, 24, "1-ABC-0001", "ABC")]
    self_issued = ev.credit_issuers(own, "1-ABC-0001", "ABC College of Engineering")
    assert (
        self_issued.supplied_by == "ABC, issued by ABC College of Engineering (the college itself)"
    )
    assert _texts(ev.studying_detail(own, self_issued)) == (
        "CREDITS_SELF_ISSUED",
        "credits for 2 semesters",
        "ABC, issued by ABC College of Engineering itself · {date}",
        "Credits recorded in ABC for all 2 semesters, issued by the college itself. They do "
        "not count as evidence independent of the college.",
    )
    one = ev.studying_detail([S("2025-26", 1, 22, *mstu), S("2025-26", 2, 0)], issuers)
    assert _texts(one)[1:] == (
        "waiting for semester 2",
        "ABC, issued by Maharashtra State Technical University · {date}",
        "No credits recorded in ABC for semester 2 (2025-26); waiting for the next results.",
    )
    assert one["awaiting_semester"] == 2
    two = ev.studying_detail([S("2025-26", 1, 0), S("2025-26", 2, 0)])
    assert _texts(two)[1:] == (
        "no credits for 2 semesters",
        "ABC credits · {date}",
        "No credits recorded in ABC for 2 of 2 semesters since admission.",
    )
    assert two["semesters"] == [
        {"academic_year": "2025-26", "sem": 1, "credits": 0},
        {"academic_year": "2025-26", "sem": 2, "credits": 0},
    ]


def test_new_case_evidence() -> None:
    joining = ev.not_in_joining_record(
        state_name="Maharashtra",
        programme_code="CSE",
        joining_year="2026-27",
        deadline=date(2026, 9, 30),
        checked_on=date(2026, 10, 29),
        related=[E1],
    )
    assert joining["summary"] == (
        "Not found in the Maharashtra admission authority's joining record for CSE (2026-27) "
        "after the reporting deadline of 30 Sep 2026."
    )
    assert _facts(joining) == {
        "Programme and year": "CSE (2026-27)",
        "Joining record": "Not found",
        "Checked on": "29 Oct 2026",
        "Reporting deadline": "30 Sep 2026",
    }
    breach = ev.eligibility_breach(
        seat_code="CSE-N-001",
        seat_type=SeatType.NRI,
        programme_code="CSE",
        cohort_year="2026-27",
        reported_word="not marked for this category",
        allowed_words="NRI or NRI-sponsored students",
        clause="APH 2024-27 cl. 2.8(b)",
        related=[E1],
    )
    assert breach["summary"] == (
        "NRI seat in CSE (2026-27) held by a student reported as not marked for this category."
    )
    assert breach["rule_source"] == "APH 2024-27 cl. 2.8(b)"
    assert _facts(breach) == {
        "Seat": "CSE-N-001 (NRI)",
        "Reported as": "not marked for this category",
        "Allowed for this seat": "NRI or NRI-sponsored students",
    }


def _facts(evidence: dict) -> dict[str, str]:
    return {f["label"]: f["value"] for f in evidence["facts"] if f.get("audience") != "OFFICER"}


def test_excess_admission_evidence() -> None:
    evidence = ev.excess_admission(
        programme_code="CSE",
        cohort_year="2026-27",
        approved=120,
        admitted=132,
        seated=120,
        peak_unseated=12,
        rule_source="AICTE approved intake",
        related=[E1, E2],
    )
    assert evidence["summary"] == (
        "132 admitted against 120 approved seats in CSE (2026-27); 12 without a seat."
    )
    assert evidence["facts"] == [
        {"label": "Approved intake", "value": "120", "source": "AICTE approval 2026-27"},
        {
            "label": "Admitted (active)",
            "value": "132",
            "source": "College uploads, Regular and NRI routes",
        },
        {"label": "Seated", "value": "120", "source": "Seat ledger"},
        {"label": "Unseated", "value": "12", "source": "Seat ledger"},
    ]
    assert evidence["related_enrolment_ids"] == [str(E1), str(E2)]
    assert evidence["data"] == {
        "approved": 120,
        "admitted": 132,
        "seated": 120,
        "unseated": 12,
        "peak_unseated": 12,
    }
    peaked = ev.excess_admission(
        programme_code="CSE",
        cohort_year="2026-27",
        approved=120,
        admitted=125,
        seated=120,
        peak_unseated=12,
        rule_source="r",
        related=[],
    )
    assert _facts(peaked)["Most unseated at once"] == "12"


def test_quota_breach_evidence() -> None:
    evidence = ev.quota_breach(
        seat_type=SeatType.NRI,
        programme_code="CSE",
        cohort_year="2026-27",
        capacity=6,
        admitted=9,
        seated=6,
        unseated=3,
        peak_unseated=3,
        routes=[AdmissionRoute.NRI],
        share=0.05,
        approved=120,
        rule_source="APH 2024-27 cl. 2.8(b)",
        related=[E1],
    )
    assert evidence["summary"] == "9 NRI admissions against 6 NRI seats in CSE (2026-27)."
    assert _facts(evidence) == {
        "Pool": "NRI",
        "Capacity": "6",
        "Admitted via route": "9 (NRI)",
        "Unseated": "3",
        "Rule percentage": "5% of approved intake 120",
    }
    assert evidence["rule_source"] == "APH 2024-27 cl. 2.8(b)"
    sources = {f["label"]: f["source"] for f in evidence["facts"]}
    assert sources["Capacity"] == sources["Rule percentage"] == "AICTE approval rules"
    assert not any("rules.yaml" in (f["source"] or "") for f in evidence["facts"])


def test_late_refill_evidence() -> None:
    evidence = ev.late_refill(
        seat_code="CSE-R-087",
        released_on=date(2026, 9, 20),
        assigned_on=date(2026, 10, 5),
        cutoff=date(2026, 9, 15),
        cohort_year="2026-27",
        filename="1-ABC-0001_2026-27_update1.csv",
        row_no=4,
        related=[E1],
    )
    assert evidence["summary"] == (
        "Seat CSE-R-087 assigned on 5 Oct 2026, after the last admission date 15 Sep 2026."
    )
    assert evidence["facts"][2] == {
        "label": "Assigned on",
        "value": "5 Oct 2026",
        "source": "College upload 1-ABC-0001_2026-27_update1.csv, row 4",
    }
    assert evidence["rule_source"] == "Last admission date for 2026-27 (AICTE admission schedule)"
    assert evidence["facts"][3] == {
        "label": "Last admission date",
        "value": "15 Sep 2026",
        "source": "AICTE admission schedule",
    }


def test_apaar_and_name_evidence() -> None:
    on = date(2026, 10, 28)
    missing = ev.invalid_apaar_not_found("4417", on, [E1])
    assert missing["summary"] == "APAAR ending 4417 is not in the APAAR registry."
    assert _facts(missing) == {
        "APAAR (masked)": "XXXX XXXX 4417",
        "Registry reply": "Not found",
        "Checked at": "28 Oct 2026",
    }
    malformed = ev.invalid_apaar_malformed("has 11 digits, expected 12", "<11 characters>", on, [])
    assert malformed["summary"] == (
        "APAAR as uploaded has 11 digits, expected 12, so it could not be checked."
    )
    assert _facts(malformed)["Registry reply"] == "Not checked"
    name = ev.name_mismatch(
        name="R Sharma", name_score=62, dob_match=True, checked_on=on, related=[]
    )
    assert name["summary"] == (
        "Name on upload differs from the APAAR registry (similarity 62 of 100)."
    )
    dob = ev.name_mismatch(
        name="R Sharma", name_score=95, dob_match=False, checked_on=on, related=[]
    )
    assert dob["summary"] == "Date of birth on upload differs from the APAAR registry."
    assert _facts(dob)["Date of birth match"] == "No"


def test_no_academic_activity_evidence() -> None:
    S = ev.SemesterCredits
    evidence = ev.no_academic_activity(
        year_of_study=2,
        semesters=[S("2025-26", 1, 0), S("2025-26", 2, 0)],
        last_entry=date(2026, 6, 30),
        related=[E1],
    )
    assert evidence["summary"] == (
        "No credits recorded in ABC for 2 semesters while enrolled in year 2."
    )
    assert _facts(evidence) == {
        "Semesters checked": "2 (2025-26 to 2025-26)",
        "Credits found": "Sem 1: 0, Sem 2: 0",
        "Last ABC entry": "30 Jun 2026",
    }


def _side(name: str, inst: str, state: str, mode=ProgrammeMode.PHYSICAL, **kw) -> ev.DuplicateSide:
    defaults = dict(
        enrolment_id=uuid.uuid4(),
        institution_name=inst,
        state_name=state,
        programme_name="B.Tech CSE",
        mode=mode,
        name=name,
        filename="1-ABC-0001_2026-27.csv",
        row_no=2,
        uploaded_on=date(2026, 10, 28),
    )
    defaults.update(kw)
    return ev.DuplicateSide(**defaults)


def test_duplicate_evidence() -> None:
    a = _side("Ravi Kumar Sharma", "ABC College", "Maharashtra", row_no=2)
    b = _side("R. K. Sharma", "ABC College", "Maharashtra", row_no=133)
    words = ev.match_words(same_apaar=False, same_passport=False, name_score=96, mobile=True)
    assert words == "Name (96 of 100), date of birth and mobile"
    within = ev.duplicate_within_upload(original=a, copy=b, words=words)
    assert (
        within["summary"] == "Rows 2 and 133 of 1-ABC-0001_2026-27.csv describe the same student."
    )
    assert _facts(within)["Names as uploaded"] == "Ravi Kumar Sharma / R. K. Sharma"
    later = _side("R. K. Sharma", "ABC College", "Maharashtra", filename="u1.csv", row_no=5)
    two_files = ev.duplicate_within_upload(original=a, copy=later, words=words)
    assert two_files["summary"] == (
        "Row 5 of u1.csv describes the same student as row 2 of 1-ABC-0001_2026-27.csv."
    )

    own = _side("Ravi", "ABC College", "Maharashtra")
    other = _side("Ravi", "XYZ Institute", "Tamil Nadu", mode=ProgrammeMode.ODL)
    same = ev.match_words(same_apaar=True, same_passport=False, name_score=None, mobile=False)
    cross = ev.duplicate_cross_institution(
        own=own, other=other, words=same, academic_year="2026-27"
    )
    assert cross["summary"] == (
        "The same student appears as active at ABC College and XYZ Institute (2026-27)."
    )
    assert cross["summary_for_institution"] == (
        "The same student appears as active here and at another institution in Tamil Nadu "
        "(2026-27)."
    )
    officer = [f for f in cross["facts"] if f.get("audience") == "OFFICER"]
    institution = [f for f in cross["facts"] if f.get("audience") == "INSTITUTION"]
    assert officer[0]["value"] == "XYZ Institute: B.Tech CSE"
    assert institution[0]["value"] == "Another institution in Tamil Nadu: B.Tech CSE"
    assert all("XYZ" not in f["value"] for f in cross["facts"] if f.get("audience") != "OFFICER")

    dual = ev.dual_enrolment_allowed(own=own, other=other)
    assert dual["summary"] == (
        "The student holds two enrolments; one is distance or online, which is permitted."
    )
    assert _facts(dual)["Enrolment B mode"] == (
        "Another institution in Tamil Nadu: B.Tech CSE, open and distance learning"
    )
    assert dual["rule_source"] == "UGC dual-degree guidelines 2022"


def test_match_words() -> None:
    assert ev.match_words(same_apaar=False, same_passport=True, name_score=None, mobile=False) == (
        "Same passport"
    )
    assert ev.match_words(same_apaar=False, same_passport=False, name_score=93, mobile=False) == (
        "Name (93 of 100) and date of birth"
    )
    assert ev.match_words(same_apaar=False, same_passport=False, name_score=None, mobile=True) == (
        "Date of birth and mobile"
    )


def test_every_flag_evidence_passes_the_schema_check() -> None:
    from app.engine.flags import validate_evidence

    S = ev.SemesterCredits
    on = date(2026, 10, 28)
    own = _side("Ravi", "ABC College", "Maharashtra")
    other = _side("Ravi", "XYZ Institute", "Tamil Nadu", mode=ProgrammeMode.ONLINE)
    samples = [
        ev.excess_admission(
            programme_code="CSE",
            cohort_year="2026-27",
            approved=120,
            admitted=132,
            seated=120,
            peak_unseated=12,
            rule_source="r",
            related=[E1],
        ),
        ev.quota_breach(
            seat_type=SeatType.INTERNATIONAL,
            programme_code="CSE",
            cohort_year="2026-27",
            capacity=18,
            admitted=20,
            seated=18,
            unseated=2,
            peak_unseated=2,
            routes=[AdmissionRoute.INTERNATIONAL],
            share=0.15,
            approved=120,
            rule_source="r",
            related=[E1],
        ),
        ev.late_refill(
            seat_code="CSE-R-001",
            released_on=None,
            assigned_on=on,
            cutoff=date(2026, 9, 15),
            cohort_year="2026-27",
            filename=None,
            row_no=None,
            related=[E1],
        ),
        ev.invalid_apaar_not_found("4417", on, [E1]),
        ev.invalid_apaar_malformed("has 11 digits, expected 12", "<11 characters>", on, [E1]),
        ev.name_mismatch(name="R", name_score=60, dob_match=True, checked_on=on, related=[E1]),
        ev.no_academic_activity(
            year_of_study=2, semesters=[S("2025-26", 1, 0)], last_entry=None, related=[E1]
        ),
        ev.duplicate_within_upload(original=own, copy=other, words="Date of birth and mobile"),
        ev.duplicate_cross_institution(own=own, other=other, words="Same APAAR", academic_year="x"),
        ev.dual_enrolment_allowed(own=own, other=other),
    ]
    for evidence in samples:
        validate_evidence(evidence)
        assert "rules.yaml" not in str(evidence)
