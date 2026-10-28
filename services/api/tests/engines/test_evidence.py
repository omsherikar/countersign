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
            "This check stays pending until a recheck or the next upload."
        ),
        "source_unavailable": True,
        "source_error": "HTTP 503",
    }
    assert ev.source_unavailable("SII", disabled=True)["source_disabled"] is True
    assert ev.source_unavailable("ABC")["summary"].startswith("ABC credits did not respond.")
    assert ev.source_unavailable("COUNSELLING")["summary"].startswith("Counselling list ")


def test_identity_sentences() -> None:
    assert ev.identity_no_apaar()["summary"] == "APAAR not linked; admission is not blocked."
    assert ev.identity_international()["summary"] == (
        "International student; identity is checked through the passport, not APAAR."
    )
    assert ev.identity_malformed("has 11 digits, expected 12")["summary"] == (
        "APAAR as uploaded has 11 digits, expected 12; the enrolment was kept without it."
    )
    assert ev.identity_not_found("4417") == {
        "summary": "APAAR ending 4417 is not in the APAAR registry.",
        "apaar_last4": "4417",
    }
    assert ev.identity_dob_mismatch(100, "4417")["summary"] == (
        "Date of birth on upload does not match the APAAR registry."
    )
    assert ev.identity_name_differs(62, "4417")["summary"] == (
        "Name on upload differs from the APAAR registry (similarity 62 of 100)."
    )
    review = ev.identity_review(81, "4417")
    assert review["summary"] == (
        "Name on upload is close to the APAAR registry but not a clear match "
        "(similarity 81 of 100); an officer should review."
    )
    assert review["needs_review"] is True
    assert ev.identity_pass(100, "4417") == {
        "summary": "Name and date of birth match the APAAR registry (similarity 100 of 100).",
        "name_score": 100,
        "dob_match": True,
        "apaar_last4": "4417",
    }


def test_admission_sentences() -> None:
    found = ev.admission_counselling_found(
        state_name="Maharashtra",
        programme_code="CSE",
        cohort_start=2026,
        round_no=1,
        allotment_ref="MHCET-2026-R1-004512",
        counselling_ref="MHCET-2026-R1-004512",
    )
    assert found == {
        "summary": "Found in the Maharashtra counselling allotments for CSE (2026), round 1.",
        "round": 1,
        "allotment_ref": "MHCET-2026-R1-004512",
        "ref_mismatch": False,
    }
    differs = ev.admission_counselling_found(
        state_name="Maharashtra",
        programme_code="CSE",
        cohort_start=2026,
        round_no=2,
        allotment_ref="MHCET-2026-R2-000101",
        counselling_ref="MHCET-2026-R1-004512",
    )
    assert differs["summary"] == (
        "Found in the Maharashtra counselling allotments for CSE (2026), round 2, as "
        "MHCET-2026-R2-000101; the upload says MHCET-2026-R1-004512."
    )
    assert differs["ref_mismatch"] is True
    assert (
        ev.admission_counselling_not_found(
            state_name="Maharashtra", programme_code="CSE", cohort_start=2026
        )["summary"]
        == "Not found in the Maharashtra counselling allotments for CSE (2026)."
    )
    assert (
        ev.admission_seat_rules_pass(AdmissionRoute.MANAGEMENT, "CSE", SeatType.REGULAR)["summary"]
        == "Management admission is allowed for CSE and holds a Regular seat."
    )
    assert (
        ev.admission_seat_rules_no_pool(AdmissionRoute.NRI, "CSE", "2026-27", SeatType.NRI)[
            "summary"
        ]
        == "NRI admission is not allowed for CSE: the 2026-27 approval has no NRI seats."
    )
    assert (
        ev.admission_seat_rules_no_seat(AdmissionRoute.SPOT, "CSE", "2026-27", SeatType.REGULAR)[
            "summary"
        ]
        == "Spot admission has no Regular seat in CSE (2026-27)."
    )
    assert ev.admission_sii_confirms("CSE", "2026-27")["summary"] == (
        "Study in India confirms this admission to CSE (2026-27)."
    )
    assert ev.admission_sii_no_match()["summary"] == (
        "Study in India has no matching admission for this passport at this institution."
    )


def test_seat_sentences() -> None:
    assert ev.seat_holds("CSE-R-001", SeatType.REGULAR, "2026-27")["summary"] == (
        "Holds seat CSE-R-001 (Regular, 2026-27 approval)."
    )
    missing = ev.seat_missing(
        SeatType.REGULAR, "CSE", "2026-27", FlagType.EXCESS_ADMISSION, "EXCESS_ADMISSION:x"
    )
    assert missing["summary"] == (
        "No Regular seat is free in CSE (2026-27); see the Excess admission flag."
    )
    assert missing["flag_type"] == "EXCESS_ADMISSION"
    assert missing["flag_dedupe_key"] == "EXCESS_ADMISSION:x"
    nri = ev.seat_missing(SeatType.NRI, "CSE", "2026-27", FlagType.QUOTA_BREACH, "k")
    assert nri["summary"] == "No NRI seat is free in CSE (2026-27); see the Quota breach flag."


def test_studying_sentences() -> None:
    S = ev.SemesterCredits
    assert ev.studying_first_year()["summary"] == "First year, no result yet."
    assert ev.studying_no_apaar()["summary"] == "APAAR not linked; ABC credits cannot be checked."
    assert ev.studying_unknown_apaar()["summary"] == (
        "ABC has no record of this APAAR; see the Identity check."
    )
    ok = ev.studying_detail([S("2025-26", 1, 22), S("2025-26", 2, 24)])
    assert ok["summary"] == "Credits recorded in ABC for all 2 semesters since admission."
    assert ok["missing"] == 0
    one = ev.studying_detail([S("2025-26", 1, 22), S("2025-26", 2, 0)])
    assert one["summary"] == (
        "No credits recorded in ABC for semester 2 (2025-26); waiting for the next upload."
    )
    assert one["awaiting_semester"] == 2
    two = ev.studying_detail([S("2025-26", 1, 0), S("2025-26", 2, 0)])
    assert two["summary"] == "No credits recorded in ABC for 2 of 2 semesters since admission."
    assert two["semesters"] == [
        {"academic_year": "2025-26", "sem": 1, "credits": 0},
        {"academic_year": "2025-26", "sem": 2, "credits": 0},
    ]
    assert ev.student_notice_not_sent() == {"summary": "Notice not sent yet."}


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
        rule_source="Approval record (approved_intake)",
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
