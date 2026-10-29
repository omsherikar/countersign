import json
from datetime import UTC, datetime

from eval import access, report, timing


def attempt(status, path="/institutions/{id}", requester="1-A", target="1-B"):
    return access.Attempt(requester, target, path, status)


def test_access_summary_separates_refusals_leaks_and_errors():
    result = access.summarise(
        [attempt(404), attempt(403, "/flags/{id}"), attempt(200, "/uploads/{id}"), attempt(500)],
        [attempt(200, requester="1-A", target="1-A")],
        skipped=["/enrolments/{id}/history"],
    )
    assert (result["attempts"], result["refused"], result["error_count"]) == (4, 2, 1)
    assert result["leaks"] == [
        {"requester": "1-A", "target": "1-B", "path": "/uploads/{id}", "status": 200}
    ]
    assert result["by_path"]["/institutions/{id}"] == {"attempts": 2, "refused": 1}
    assert result["controls"] == {"attempts": 1, "ok": 1}
    assert result["skipped_paths"] == ["/enrolments/{id}/history"]
    assert not access.all_refused(result)
    assert access.all_refused(access.summarise([attempt(404), attempt(403)], []))
    assert not access.all_refused(access.summarise([], []))


def result(*, recall=0.97, rate=0.01, seconds=95.0, fresh=True, refused=10, attempts=10):
    perf = timing.perf_result(
        file="perf/9-PERF-0001_2026-27.csv", rows=50000, seconds=seconds,
        stages_ms={"UPSERT": 20000, "CHECKS": 60000}, status="DONE", fresh=fresh,
    )  # fmt: skip
    return report.assemble(
        dataset={"size": "small", "seed": 2026, "institutions": 50, "records": 10500},
        detection={
            "overall_recall": recall, "planted": 100, "found": round(100 * recall),
            "severity_match": 1.0,
            "by_type": {"INVALID_APAAR": {"planted": 15, "found": 15, "recall": 1.0,
                                          "severity_match": 1.0, "severity_matched": 15}},
            "misses": [{"type": "NAME_MISMATCH", "institution": "1-A", "programme_code": "CSE",
                        "rows": 1, "rows_without_enrolment": 0, "note": "planted"}],
            "severity_mismatches": [],
        },
        record_status={"checked": 10, "matched": 9, "rate": 0.9, "rows_checked": 7,
                       "rows_matched": 7, "mismatches": []},
        deadlines={"checked": 3, "matched": None, "available": False, "items": []},
        false_alarms={"clean_records": 9800, "flagged": round(9800 * rate), "rate": rate,
                      "causes": {"case NAME_MISMATCH": 3}, "examples": []},
        controls={"records": 30, "flagged": 0, "by_type": {}, "flagged_items": []},
        uploads={"count": 52, "rows": 10600, "median_ms": 2100, "p95_ms": 9000,
                 "max_ms": 12000, "rows_per_second": 400.0},
        perf=perf,
        effort={"unresolved_cases": 120, "active_records": 10500, "cases_per_1000": 11.43,
                "facts_per_case": 4.1, "records_per_case": 1.6, "by_type": {}},
        signals={"rings": {"planted": 3, "found": 3, "recall": 1.0, "signals": 3, "correct": 3,
                           "precision": 1.0},
                 "anomalies": {"planted": 2, "found": 1, "recall": 0.5, "signals": 2,
                               "correct": 1, "precision": 0.5},
                 "signals_run": True, "recall": 0.8, "precision": 0.8},
        access=access.summarise(
            [attempt(404)] * refused + [attempt(200)] * (attempts - refused), []
        ),
        generated_at=datetime(2026, 10, 29, 6, 0, tzinfo=UTC),
    )  # fmt: skip


def test_targets_pass_and_fail():
    assert report.passed(result()) == {
        "recall": True,
        "false_alarms": True,
        "throughput": True,
        "access": True,
    }
    assert report.failed(result()) == []
    missed = result(recall=0.94, rate=0.05, seconds=121, refused=9)
    assert report.failed(missed) == ["recall", "false_alarms", "throughput", "access"]
    assert report.passed(result(fresh=False))["throughput"] is False


def test_skipped_runs_are_not_failures():
    skipped = result()
    skipped["timing"]["perf_50k"] = None
    skipped["access"] = None
    skipped["passed"] = report.passed(skipped)
    assert skipped["passed"]["throughput"] is None and skipped["passed"]["access"] is None
    assert report.failed(skipped) == []
    text = report.render(skipped)
    assert "| Time to process 50,000 rows | not run | Under 2 minutes | Not run |" in text


def test_every_number_is_labelled_synthetic(tmp_path):
    md_path, json_path = report.write(tmp_path, result())
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["synthetic"] is True
    assert data["generated_at"] == "2026-10-29T06:00:00Z"
    assert set(data) >= {
        "dataset", "targets", "detection", "record_status", "deadlines", "false_alarms",
        "timing", "effort", "signals", "access", "passed",
    }  # fmt: skip
    text = md_path.read_text(encoding="utf-8")
    assert text.startswith("# Evaluation\n\n**Synthetic data.**")
    assert "| Measure | Result (synthetic) | Target | Met |" in text
    assert "| Seeded inconsistencies caught | 97.0% (97 of 100) | 95% or more | Met |" in text
    assert "| Time to process 50,000 rows | 95.0 s (50,000 rows) | Under 2 minutes | Met |" in text
    assert "| INVALID_APAAR | 15 | 15 | 100.0% | 100.0% |" in text
    assert "Run 2026-10-29 06:00 UTC · seed 2026 · 50 colleges · 10,500 records" in text
    assert "a student who colludes cannot always be caught" in text
    assert "—" not in text


def test_not_met_reads_as_plainly_as_met():
    text = report.render(result(rate=0.2))
    assert (
        "| Cases raised on legitimate records | 20.0% (1,960 of 9,800 known-clean records) "
        "| Under 5% | Not met |" in text
    )
