from conftest import case, gt, record, records, row

from eval import detection, truth


def test_a_record_case_is_found_only_when_every_row_is_named():
    pair, single = records(
        gt(
            "DUPLICATE_WITHIN_UPLOAD",
            [row("f.csv", 2), row("f.csv", 3)],
            severity_expected="MEDIUM",
        ),
        gt("STUDENT_DENIED", [row("f.csv", 7)]),
    )
    resolved = {pair.index: ("e2", "e3"), single.index: ("e7",)}
    cases = [
        case("c1", "DUPLICATE_WITHIN_UPLOAD", ("e2",), severity="MEDIUM"),
        case("c2", "STUDENT_DENIED", ("e7",)),
    ]
    result = detection.score_detection([pair, single], resolved, cases)
    assert result.by_type["DUPLICATE_WITHIN_UPLOAD"].found == 0
    assert result.by_type["STUDENT_DENIED"].found == 1
    assert result.overall_recall == 0.5
    assert result.misses[0]["type"] == "DUPLICATE_WITHIN_UPLOAD"

    both = cases + [case("c3", "DUPLICATE_WITHIN_UPLOAD", ("e2", "e3"), severity="MEDIUM")]
    assert detection.score_detection([pair, single], resolved, both).overall_recall == 1.0


def test_a_case_of_another_type_does_not_count():
    (planted,) = records(gt("NAME_MISMATCH", [row("f.csv", 4)], severity_expected="MEDIUM"))
    result = detection.score_detection(
        [planted], {planted.index: ("e4",)}, [case("c1", "INVALID_APAAR", ("e4",))]
    )
    assert result.found == 0 and result.planted == 1


def test_rows_without_an_enrolment_are_reported_as_a_miss():
    (planted,) = records(gt("INVALID_APAAR", [row("f.csv", 4)]))
    result = detection.score_detection([planted], {planted.index: (None,)}, [])
    assert result.misses[0]["rows_without_enrolment"] == 1


def test_pool_cases_match_programme_and_seat_type():
    excess, quota = records(
        gt("EXCESS_ADMISSION", [row("f.csv", n) for n in range(130, 134)], programme_code="CSE"),
        gt("QUOTA_BREACH", [row("f.csv", 60)], programme_code="IT", seat_type="NRI"),
    )
    resolved = {excess.index: ("x",) * 4, quota.index: ("y",)}
    cases = [
        case("c1", "EXCESS_ADMISSION", (), programme_code="CSE", pool="REGULAR"),
        case("c2", "QUOTA_BREACH", (), programme_code="IT", pool="INTERNATIONAL"),
    ]
    result = detection.score_detection([excess, quota], resolved, cases)
    assert result.by_type["EXCESS_ADMISSION"].found == 1
    assert result.by_type["QUOTA_BREACH"].found == 0

    cases.append(case("c3", "QUOTA_BREACH", (), programme_code="IT", pool="NRI"))
    assert detection.score_detection([excess, quota], resolved, cases).overall_recall == 1.0


def test_pool_cases_at_another_college_do_not_count():
    (excess,) = records(gt("EXCESS_ADMISSION", [row("f.csv", 9)], programme_code="CSE"))
    other = case("c1", "EXCESS_ADMISSION", (), programme_code="CSE", institution="1-BBB-0002")
    assert detection.score_detection([excess], {excess.index: ("x",)}, [other]).found == 0


def test_missing_from_upload_matches_institution_and_year():
    (missing,) = records(
        gt(
            "MISSING_FROM_UPLOAD",
            [],
            institution_aicte_id="1-XYZ-0002",
            severity_expected="MEDIUM",
            academic_year="2026-27",
            programme_code=None,
        )
    )
    old_year = case(
        "c1", "MISSING_FROM_UPLOAD", institution="1-XYZ-0002", academic_year="2025-26",
        severity="MEDIUM",
    )  # fmt: skip
    assert detection.score_detection([missing], {missing.index: ()}, [old_year]).found == 0
    this_year = case(
        "c2", "MISSING_FROM_UPLOAD", institution="1-XYZ-0002", academic_year="2026-27",
        severity="MEDIUM",
    )  # fmt: skip
    found = detection.score_detection([missing], {missing.index: ()}, [old_year, this_year])
    assert found.found == 1 and found.severity_matched == 1


def test_severity_match_needs_every_covering_case_at_the_planted_severity():
    (refill,) = records(
        gt("LATE_REFILL", [row("u.csv", 7), row("u.csv", 8)], severity_expected="MEDIUM")
    )
    resolved = {refill.index: ("e7", "e8")}
    cases = [
        case("c1", "LATE_REFILL", ("e7",), severity="MEDIUM"),
        case("c2", "LATE_REFILL", ("e8",), severity="LOW"),
    ]
    result = detection.score_detection([refill], resolved, cases)
    assert result.found == 1 and result.severity_matched == 0
    assert result.severity_mismatches[0]["found"] == ["LOW", "MEDIUM"]
    assert result.as_dict()["by_type"]["LATE_REFILL"]["severity_match"] == 0.0


def test_unplanted_records_are_not_scored():
    (control,) = records(gt("CONSENT_REFUSED_NO_APAAR", [row("f.csv", 3)], expected_flag=None))
    result = detection.score_detection([control], {control.index: ("e3",)}, [])
    assert result.planted == 0 and result.overall_recall is None


def test_record_status_and_expected_rows():
    card, clean, self_issued = records(
        gt(
            "NOT_IN_JOINING_RECORD",
            [row("f.csv", 41)],
            expected_record_status="DISPUTED",
            expected_rows={"ADMISSION": "CONTRADICTED", "STUDENT": "CONTRADICTED"},
        ),
        gt("CLEAN_INDEPENDENT", [row("f.csv", 64)], expected_flag=None,
           expected_record_status="COUNTERSIGNED"),
        gt("SELF_ISSUED_ONLY", [row("f.csv", 106)], expected_flag=None,
           expected_record_status="AWAITING_EVIDENCE"),
    )  # fmt: skip
    resolved = {card.index: ("e41",), clean.index: ("e64",), self_issued.index: (None,)}
    views = {
        "e41": record(
            "e41",
            record_status="DISPUTED",
            rows={"ADMISSION": "CONTRADICTED", "STUDENT": "PENDING"},
        ),
        "e64": record("e64", record_status="COUNTERSIGNED"),
    }
    result = detection.score_record_status([card, clean, self_issued], resolved, views)
    assert (result["checked"], result["matched"]) == (3, 2)
    assert (result["rows_checked"], result["rows_matched"]) == (2, 1)
    assert {m.get("row") for m in result["mismatches"]} == {"STUDENT", None}


def test_deadlines_without_and_with_the_route():
    late, overdue = records(
        gt("LATE_UPLOAD", [], expected_flag=None, institution_aicte_id="1-L",
           expected_deadline_state="LATE", programme_code=None),
        gt("OVERDUE_UPLOAD", [], expected_flag=None, institution_aicte_id="1-O",
           expected_deadline_state="OVERDUE", programme_code=None),
    )  # fmt: skip
    unavailable = detection.score_deadlines([late, overdue], None)
    assert unavailable["available"] is False and unavailable["matched"] is None
    scored = detection.score_deadlines([late, overdue], {"1-L": "LATE", "1-O": "ON_TIME"})
    assert (scored["checked"], scored["matched"]) == (2, 1)


def test_pool_and_institution_types_are_the_contract_ones():
    assert truth.POOL_TYPES == {"EXCESS_ADMISSION", "QUOTA_BREACH"}
    assert truth.INSTITUTION_TYPES == {"MISSING_FROM_UPLOAD"}
