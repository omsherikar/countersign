from conftest import case, gt, record, records, row

from eval import false_alarms


def views(*items):
    return {v.id: v for v in items}


def test_known_clean_leaves_out_named_inactive_graduate_and_throughput_records():
    all_views = views(
        record("a"),
        record("named"),
        record("gone", status="WITHDRAWN"),
        record("graduate", status="GRADUATED", from_upload=False),
        record("perf", institution="9-PERF-0001"),
    )
    clean = false_alarms.known_clean(all_views, {"named"}, {"9-PERF-0001"})
    assert clean == {"a"}


def test_a_clean_record_is_flagged_by_any_case_or_a_review_status():
    all_views = views(
        record("a"),
        record("b"),
        record("c", record_status="UNDER_REVIEW"),
        record("d", record_status="DISPUTED"),
        record("e", record_status="COUNTERSIGNED"),
    )
    cases = [case("c1", "DUPLICATE_CROSS_INSTITUTION", ("b", "elsewhere"), status="UPHELD")]
    result = false_alarms.score_false_alarms(set(all_views), all_views, cases)
    assert (result["clean_records"], result["flagged"]) == (5, 3)
    assert result["rate"] == 0.6
    assert result["causes"] == {
        "case DUPLICATE_CROSS_INSTITUTION": 1,
        "status DISPUTED": 1,
        "status UNDER_REVIEW": 1,
    }


def test_no_clean_records_gives_no_rate():
    result = false_alarms.score_false_alarms(set(), {}, [])
    assert result["rate"] is None and result["flagged"] == 0


def test_controls_skip_records_a_planted_case_also_names():
    refused, also_dup, dup, ciwg = records(
        gt("CONSENT_REFUSED_NO_APAAR", [row("f.csv", 3)], expected_flag=None),
        gt("CONSENT_REFUSED_NO_APAAR", [row("f.csv", 4)], expected_flag=None),
        gt("DUPLICATE_WITHIN_UPLOAD", [row("f.csv", 4), row("f.csv", 5)]),
        gt("CIWG_ADMISSION", [row("f.csv", 6)], expected_flag=None),
    )
    resolved = {
        refused.index: ("e3",),
        also_dup.index: ("e4",),
        dup.index: ("e4", "e5"),
        ciwg.index: ("e6",),
    }
    all_views = views(record("e3"), record("e4"), record("e5"), record("e6"))
    cases = [
        case("c1", "DUPLICATE_WITHIN_UPLOAD", ("e4", "e5")),
        case("c2", "QUOTA_BREACH", ("e6",)),
    ]
    result = false_alarms.score_controls([refused, also_dup, dup, ciwg], resolved, all_views, cases)
    assert result["records"] == 2
    assert result["flagged"] == 1
    assert result["by_type"] == {
        "CIWG_ADMISSION": {"records": 1, "flagged": 1},
        "CONSENT_REFUSED_NO_APAAR": {"records": 1, "flagged": 0},
    }
