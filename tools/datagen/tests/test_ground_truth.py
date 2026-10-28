"""Ground truth: counts match datagen.yaml, every reference resolves, scenarios are exact."""

from collections import Counter

from datagen.config import load_datagen_config

FLAG_TYPES = {
    "EXCESS_ADMISSION", "QUOTA_BREACH", "LATE_REFILL", "INVALID_APAAR", "NAME_MISMATCH",
    "DUPLICATE_CROSS_INSTITUTION", "DUPLICATE_WITHIN_UPLOAD", "DUAL_ENROLMENT_ALLOWED",
    "NO_ACADEMIC_ACTIVITY", "STUDENT_DENIED", "GHOST_RING", "ANOMALY",
}  # fmt: skip


def by_type(records):
    return Counter(r["anomaly_type"] for r in records)


def test_counts_match_datagen_yaml(small):
    cfg = load_datagen_config()["anomalies"]
    counts = by_type(small.json("ground_truth.json"))
    for key, spec in cfg.items():
        expected = spec["small"] if spec["enabled"] else 0
        if key == "QUOTA_BREACH_NRI":
            continue
        if key == "QUOTA_BREACH_INTERNATIONAL":
            expected = cfg["QUOTA_BREACH_NRI"]["small"] + spec["small"]
            assert counts["QUOTA_BREACH"] == expected
            continue
        assert counts[key] == expected, key


def test_record_shape_and_flag_vocabulary(small):
    for rec in small.json("ground_truth.json"):
        for key in (
            "anomaly_type", "expected_flag", "severity_expected", "institution_aicte_id",
            "institution_aicte_ids", "programme_code", "student_refs", "rows", "note",
        ):  # fmt: skip
            assert key in rec, key
        assert rec["institution_aicte_id"] == rec["institution_aicte_ids"][0]
        assert rec["rows"] and len(rec["student_refs"]) == len(rec["rows"])
        if rec["anomaly_type"] == "CONSENT_REFUSED_NO_APAAR":
            assert rec["expected_flag"] is None and rec["severity_expected"] is None
        else:
            assert rec["expected_flag"] in FLAG_TYPES
            assert rec["severity_expected"] in {"LOW", "MEDIUM", "HIGH"}


def test_every_reference_resolves_to_an_upload_row(small):
    uploads = small.all_uploads()
    for rec in small.json("ground_truth.json"):
        for ref, row in zip(rec["student_refs"], rec["rows"], strict=True):
            file = row["file"]
            aid = row["institution_aicte_id"]
            assert file == f"uploads/{aid}_2026-27.csv"
            assert (small.path / file).is_file()
            assert aid in rec["institution_aicte_ids"]
            csv_row = uploads[aid][row["row_no"] - 1]
            assert csv_row["name"] == row["name"]
            assert csv_row["programme_code"] == row["programme_code"]
            assert int(csv_row["year_of_study"]) == row["year_of_study"]
            assert (csv_row["apaar_id"] or None) == row["apaar_id"]
            if row["apaar_id"]:
                assert ref == row["apaar_id"]
            else:
                assert ref == f"{file}#{row['row_no']}"


def test_abc_cse_132_against_120(small):
    cse = next(
        p for p in small.json("institutions.json")["institutions"][0]["programmes"]
        if p["code"] == "CSE"
    )
    assert {"academic_year": "2026-27", "approved_intake": 120} in cse["approvals"]
    rows = small.upload("1-ABC-0001")
    first_years = [r for r in rows if r["programme_code"] == "CSE" and r["year_of_study"] == "1"]
    assert len(first_years) == 132
    assert all(r["admission_route"] not in {"TFW", "INTERNATIONAL", "LATERAL"} for r in first_years)
    rec = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "abc_cse_132")
    assert rec["approved_intake"] == 120 and rec["admitted"] == 132
    assert len(rec["rows"]) == 12


def test_demo_student_and_initials_duplicate(small):
    rows = small.upload("1-ABC-0001")
    ravi = rows[0]
    assert ravi["apaar_id"] == "123456784417"
    assert ravi["name"] == "Ravi Kumar Sharma"
    assert ravi["dob"] == "2007-03-21"
    assert ravi["email"] == "ravi.sharma@example.demo"
    assert ravi["mobile"].endswith("4521")
    assert ravi["counselling_ref"] == "MHCET-2026-R1-004512"
    assert ravi["consent_status"] == "LINKED" and ravi["admission_route"] == "COUNSELLING"
    dup = [r for r in rows if r["name"] == "R. K. Sharma"]
    assert len(dup) == 1
    assert dup[0]["dob"] == "2007-03-21" and dup[0]["programme_code"] == "CSE"
    assert dup[0]["apaar_id"] == "" and dup[0]["consent_status"] == "PENDING"
    rec = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "demo_student")
    assert rec["variant"] == "INITIALS"
    assert rec["student_refs"][0] == "123456784417"


def test_ghost_ring_40_students_3_colleges_4_mobiles(small):
    rec = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "ghost_ring_40")
    assert len(rec["rows"]) == 40
    assert len(rec["institution_aicte_ids"]) == 3
    assert "1-ABC-0001" in rec["institution_aicte_ids"]
    assert len(rec["shared_mobiles"]) == 4
    uploads = small.all_uploads()
    mobiles = Counter(
        uploads[r["institution_aicte_id"]][r["row_no"] - 1]["mobile"] for r in rec["rows"]
    )
    assert set(mobiles) == set(rec["shared_mobiles"])
    assert all(n == 10 for n in mobiles.values())
    assert Counter(r["institution_aicte_id"] for r in rec["rows"]) == {
        i: 40 // 3 + (1 if k < 40 % 3 else 0) for k, i in enumerate(rec["institution_aicte_ids"])
    }


def test_xyz_second_year_with_zero_credits(small):
    gt = small.json("ground_truth.json")
    rec = next(r for r in gt if r.get("scenario") == "xyz_zero_credits")
    assert rec["institution_aicte_id"] == "1-XYZ-0002"
    row = rec["rows"][0]
    assert row["year_of_study"] == 2
    credits = [a for a in small.jsonl("abc_credits.jsonl") if a["apaar_id"] == row["apaar_id"]]
    assert len(credits) == 2
    assert all(c["credits"] == 0 and c["academic_year"] == "2025-26" for c in credits)
    assert sorted(c["sem"] for c in credits) == [1, 2]


def test_not_me_student_flagged_will_deny(small):
    rec = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "not_me")
    assert rec["will_deny"] is True
    assert rec["institution_aicte_id"] == "1-ABC-0001"
    assert rec["expected_flag"] == "STUDENT_DENIED"
    deniers = [r for r in small.json("ground_truth.json") if r["anomaly_type"] == "STUDENT_DENIED"]
    assert all(r["will_deny"] for r in deniers)


def test_legal_dual_enrolment_abc_plus_odl(small):
    rec = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "legal_dual_abc")
    assert rec["institution_aicte_ids"][0] == "1-ABC-0001"
    assert rec["modes"][0] == "PHYSICAL" and rec["modes"][1] in {"ODL", "ONLINE"}
    a, b = rec["rows"]
    assert a["apaar_id"] == b["apaar_id"]
    assert b["programme_code"] in {"BCA-ODL", "MCA-ONLINE"}
    insts = {i["aicte_permanent_id"]: i for i in small.json("institutions.json")["institutions"]}
    programmes = insts[b["institution_aicte_id"]]["programmes"]
    prog = next(p for p in programmes if p["code"] == b["programme_code"])
    assert prog["mode"] in {"ODL", "ONLINE"}


def test_scenarios_can_be_switched_off(small_no_scenarios):
    gt = small_no_scenarios.json("ground_truth.json")
    assert not any(r.get("scenario") for r in gt)
    rows = small_no_scenarios.upload("1-ABC-0001")
    assert not any(r["apaar_id"] == "123456784417" for r in rows)
    assert small_no_scenarios.summary["xlsx_written"] is False
    assert small_no_scenarios.summary["xlsx_note"]
    assert not list((small_no_scenarios.path / "uploads").glob("*.xlsx"))
