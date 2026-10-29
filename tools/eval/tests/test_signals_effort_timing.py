from datetime import UTC, datetime, timedelta

from conftest import case, gt, records, row

from eval import effort, signals, timing
from eval.views import BatchView, SignalView


def test_a_ring_is_found_by_a_signal_holding_80_percent_of_it():
    ring = frozenset(f"m{i}" for i in range(10))
    assert signals.holds(frozenset(f"m{i}" for i in range(8)), ring)
    assert not signals.holds(frozenset(f"m{i}" for i in range(7)), ring)
    result = signals.score_rings(
        [ring, frozenset({"x1", "x2", "x3"})],
        [frozenset(f"m{i}" for i in range(9)) | {"stranger"}, frozenset({"y1", "y2", "y3"})],
    )
    assert (result["found"], result["recall"]) == (1, 0.5)
    assert (result["correct"], result["precision"]) == (1, 0.5)


def test_anomalies_by_institution():
    result = signals.score_anomalies(
        {"1-A", "1-B"}, [frozenset({"1-A"}), frozenset({"1-C"}), frozenset({"1-A"})]
    )
    assert (result["found"], result["planted"], result["recall"]) == (1, 2, 0.5)
    assert (result["correct"], result["signals"]) == (2, 3)


def test_score_signals_from_ground_truth_and_no_run():
    ring, anomaly = records(
        gt("GHOST_RING", [row("f.csv", n) for n in (2, 3, 4)], expected_flag=None,
           expected_signal="GHOST_RING"),
        gt("ANOMALY", [], expected_flag=None, expected_signal="ANOMALY",
           institution_aicte_id="1-A", programme_code=None),
    )  # fmt: skip
    resolved = {ring.index: ("e2", "e3", "e4"), anomaly.index: ()}
    none = signals.score_signals([ring, anomaly], resolved, [])
    assert none["signals_run"] is False and none["recall"] == 0.0 and none["precision"] is None
    found = signals.score_signals(
        [ring, anomaly],
        resolved,
        [
            SignalView("s1", "GHOST_RING", frozenset({"1-X"}), frozenset({"e2", "e3", "e4"})),
            SignalView("s2", "ANOMALY", frozenset({"1-A"})),
        ],
    )
    assert found["recall"] == 1.0 and found["precision"] == 1.0


def test_review_effort_counts_unresolved_cases_only():
    cases = [
        case("a", "NAME_MISMATCH", ("e1",), facts=4),
        case("b", "EXCESS_ADMISSION", ("e2", "e3", "e4"), facts=6, status="DOCS_REQUESTED"),
        case("c", "STUDENT_DENIED", ("e5",), facts=3, status="UPHELD"),
        case("d", "MISSING_FROM_UPLOAD", (), facts=2, status="ESCALATED"),
        case("e", "NAME_MISMATCH", ("p1",), facts=9, institution="9-PERF-0001"),
    ]
    result = effort.review_effort(cases, 2000, {"9-PERF-0001"})
    assert result["unresolved_cases"] == 3
    assert result["cases_per_1000"] == 1.5
    assert result["facts_per_case"] == 4.0
    assert result["records_per_case"] == 1.33
    assert result["by_type"] == {
        "EXCESS_ADMISSION": 1,
        "MISSING_FROM_UPLOAD": 1,
        "NAME_MISMATCH": 1,
    }


def test_review_effort_with_nothing_open():
    result = effort.review_effort([], 0)
    assert result["cases_per_1000"] is None and result["facts_per_case"] is None


def batch(inst, ms, rows=100, status="DONE"):
    start = datetime(2026, 10, 29, tzinfo=UTC)
    return BatchView(f"{inst}.csv", inst, rows, status, start, start + timedelta(milliseconds=ms))


def test_percentile_is_nearest_rank():
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert timing.percentile(values, 0.5) == 50
    assert timing.percentile(values, 0.95) == 100
    assert timing.percentile([], 0.5) is None


def test_upload_timing_skips_failed_and_excluded_batches():
    batches = [
        batch("1-A", 1000),
        batch("1-B", 3000),
        batch("1-C", 2000),
        batch("1-D", 9999, status="FAILED"),
        batch("9-PERF-0001", 60000, rows=50000),
    ]
    result = timing.upload_timing(batches, {"9-PERF-0001"})
    assert result["count"] == 3
    assert (result["median_ms"], result["p95_ms"], result["max_ms"]) == (2000, 3000, 3000)
    assert result["rows_per_second"] == 50.0


def test_throughput_needs_a_fresh_done_run_under_two_minutes():
    def perf(seconds, fresh=True, status="DONE"):
        return timing.perf_result(
            file="perf/x.csv", rows=50000, seconds=seconds, stages_ms={}, status=status,
            fresh=fresh,
        )  # fmt: skip

    assert timing.throughput_met(None) is None
    assert timing.throughput_met(perf(119.9)) is True
    assert timing.throughput_met(perf(120.0)) is False
    assert timing.throughput_met(perf(30, fresh=False)) is False
    assert timing.throughput_met(perf(30, status="FAILED")) is False
    assert perf(100)["rows_per_second"] == 500.0
