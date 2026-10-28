"""How colleges submit: manifest `uploads`, late and overdue colleges, their own headers."""

import csv

from datagen.config import load_datagen_config
from datagen.students import UPLOAD_COLUMNS
from datagen.submissions import normalise_header

CFG = load_datagen_config()["submissions"]
REQUIRED = {"name", "dob", "programme_code", "year_of_study", "admission_route", "category"}


def manifest(small) -> dict:
    return small.json("manifest.json")


def records(small, kind: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == kind]


def test_every_file_has_its_submission_time(small):
    m = manifest(small)
    uploads = m["uploads"]
    initial = sorted(f"uploads/{aid}_2026-27.csv" for aid in small.all_uploads())
    assert [u["file"] for u in uploads] == initial + small.update_files()
    late = set(m["late_colleges"])
    deadline = "2026-09-30T18:30:00Z"  # the end of 30 September, IST
    for u in uploads:
        assert set(u) == {"file", "aicte_id", "academic_year", "submitted_at"}
        assert u["file"].startswith(f"uploads/{u['aicte_id']}_2026-27")
        assert u["academic_year"] == "2026-27" and u["submitted_at"].endswith("Z")
        rows = small.file(u["file"])
        dates = [r[c] for r in rows for c in ("admission_date", "status_date") if r[c]]
        assert max(dates) < u["submitted_at"][:10], u["file"]
        if "_update" in u["file"]:
            assert u["submitted_at"] > deadline
        elif u["aicte_id"] in late:
            assert u["submitted_at"] > deadline
        else:
            assert u["submitted_at"] < deadline
    first = {u["aicte_id"]: u["submitted_at"] for u in uploads if "_update" not in u["file"]}
    for u in uploads:
        if "_update" in u["file"]:
            assert u["submitted_at"] > first[u["aicte_id"]]


def test_late_and_overdue_colleges(small):
    m = manifest(small)
    assert len(m["late_colleges"]) == CFG["late_colleges"]["small"]
    assert len(m["overdue_colleges"]) == CFG["overdue_colleges"]["small"]
    assert not set(m["late_colleges"]) & set(m["overdue_colleges"])
    late = {r["institution_aicte_id"]: r for r in records(small, "LATE_UPLOAD")}
    overdue = {r["institution_aicte_id"]: r for r in records(small, "OVERDUE_UPLOAD")}
    assert sorted(late) == m["late_colleges"] and sorted(overdue) == m["overdue_colleges"]
    for rec in [*late.values(), *overdue.values()]:
        assert rec["expected_flag"] is None and rec["rows"] == []
    assert {r["expected_deadline_state"] for r in late.values()} == {"LATE"}
    assert {r["expected_deadline_state"] for r in overdue.values()} == {"OVERDUE"}


def test_an_overdue_college_sent_nothing_but_its_students_joined(small):
    gt = small.json("ground_truth.json")
    joinings = small.jsonl("admission_joinings.jsonl")
    for aid in manifest(small)["overdue_colleges"]:
        assert not list((small.path / "uploads").glob(f"{aid}_*"))
        assert not any(aid in r["institution_aicte_ids"] for r in gt if r["anomaly_type"] not in {
            "OVERDUE_UPLOAD", "MISSING_FROM_UPLOAD"})  # fmt: skip
        assert not any(aid in r["file"] for r in small.lines("notice_replies.jsonl"))
        joined = [j for j in joinings if j["institution_code"] == aid
                  and j["academic_year"] == "2026-27"]  # fmt: skip
        (missing,) = [r for r in records(small, "MISSING_FROM_UPLOAD")
                      if r["institution_aicte_id"] == aid]  # fmt: skip
        assert missing["overdue"] is True and joined
        assert missing["missing"] == missing["joined"] == len(joined)
        assert missing["uploaded_and_joined"] == 0 and missing["completeness_pct"] == 0.0
        rolls = {s["roll_no"] for s in missing["missing_students"]}
        assert rolls == {j["roll_no"] for j in joined}


def test_colleges_with_their_own_headers(small):
    mappings = small.json("column_mappings.json")
    assert len(mappings) == CFG["mapped_colleges"]["small"] and "1-XYZ-0002" in mappings
    assert not set(mappings) & set(manifest(small)["overdue_colleges"])
    for aid, mapping in mappings.items():
        assert 0 < len(mapping) <= 60
        assert set(mapping.values()) <= set(UPLOAD_COLUMNS)
        assert len(set(mapping.values())) == len(mapping)
        normalised = [normalise_header(h) for h in mapping]
        assert len(set(normalised)) == len(normalised)
        assert not set(normalised) & set(UPLOAD_COLUMNS)
        files = [f for f in [f"uploads/{aid}_2026-27.csv", *small.update_files()] if aid in f]
        for name in files:
            with open(small.path / name, encoding="utf-8") as fh:
                header = next(csv.reader(fh))
            assert set(mapping) <= set(header), name
            # Every required column is reached once the mapping is applied.
            assert REQUIRED <= {mapping.get(h, h) for h in header}
            assert {mapping.get(h, h) for h in header} == set(UPLOAD_COLUMNS)
        assert small.upload(aid)[0]["name"]
