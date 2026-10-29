import json

from conftest import gt, records, row

from eval import truth


def test_parse_keeps_rows_expectations_and_file_names():
    (parsed,) = records(
        gt(
            "NOT_IN_JOINING_RECORD",
            [row("1-AAA-0001_2026-27.csv", 41)],
            severity_expected="MEDIUM",
            academic_year="2026-27",
            expected_record_status="DISPUTED",
            expected_rows={"ADMISSION": "CONTRADICTED", "STUDENT": "CONTRADICTED"},
        )
    )
    assert parsed.rows[0].key == ("1-AAA-0001_2026-27.csv", 41)
    assert parsed.severity == "MEDIUM"
    assert parsed.expected_record_status == "DISPUTED"
    assert parsed.expected_rows == {"ADMISSION": "CONTRADICTED", "STUDENT": "CONTRADICTED"}
    assert parsed.planted_case and not parsed.is_control


def test_expected_check_becomes_an_expected_row():
    (parsed,) = records(
        gt(
            "TFW_INCOME_NOT_REPORTED",
            [row("f.csv", 2)],
            expected_flag=None,
            severity_expected=None,
            expected_check={"type": "SEAT", "status": "PENDING"},
        )
    )
    assert parsed.expected_rows == {"SEAT": "PENDING"}
    assert parsed.is_control


def test_rings_anomalies_and_withdrawals_are_not_controls():
    ring, anomaly, withdrawal, refused = records(
        gt("GHOST_RING", [row("f.csv", 2)], expected_flag=None, expected_signal="GHOST_RING"),
        gt("ANOMALY", [], expected_flag=None, expected_signal="ANOMALY"),
        gt("WITHDRAWAL", [row("f_update1.csv", 3)], expected_flag=None),
        gt("CONSENT_REFUSED_NO_APAAR", [row("f.csv", 9)], expected_flag=None),
    )
    assert not ring.is_control and not anomaly.is_control and not withdrawal.is_control
    assert refused.is_control


def test_resolve_and_named_enrolments():
    dup, refused = records(
        gt("DUPLICATE_WITHIN_UPLOAD", [row("f.csv", 2), row("f.csv", 122)]),
        gt("CONSENT_REFUSED_NO_APAAR", [row("f.csv", 9)], expected_flag=None),
    )
    resolved = truth.resolve([dup, refused], {("f.csv", 2): "e2", ("f.csv", 9): "e9"})
    assert resolved == {dup.index: ("e2", None), refused.index: ("e9",)}
    assert truth.named_enrolments([dup, refused], resolved) == {"e2", "e9"}


def test_load_reads_ground_truth_and_manifest(tmp_path):
    (tmp_path / "ground_truth.json").write_text(
        json.dumps([gt("INVALID_APAAR", [row("f.csv", 5)])]), encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"size": "small", "seed": 2026, "perf": {"file": "perf/x.csv", "rows": 9}}),
        encoding="utf-8",
    )
    loaded = truth.load(tmp_path)
    assert [r.type for r in loaded.planted()] == ["INVALID_APAAR"]
    assert (loaded.size, loaded.seed, loaded.perf["rows"]) == ("small", 2026, 9)
