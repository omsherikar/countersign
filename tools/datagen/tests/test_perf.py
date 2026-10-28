"""`--perf N`: one college with exactly N legitimate rows and its mockgov lines, under perf/."""

import csv
import json
from collections import Counter

import pytest
from seat_math import usable_capacity

from datagen.cli import generate
from datagen.students import UPLOAD_COLUMNS

N = 400


@pytest.fixture(scope="module")
def perf(tmp_path_factory):
    out = tmp_path_factory.mktemp("perf")
    generate("small", 42, out, xlsx=False, perf=N)
    return out


def lines(path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_manifest_names_the_perf_files(perf):
    manifest = json.loads((perf / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["perf"] == {
        "institutions_file": "perf/institutions.json",
        "file": "perf/9-PERF-0001_2026-27.csv",
        "rows": N,
    }
    assert not list((perf / "uploads").glob("9-PERF-*"))


def test_one_college_that_seats_every_row(perf):
    data = json.loads((perf / "perf" / "institutions.json").read_text(encoding="utf-8"))
    (inst,) = data["institutions"]
    assert inst["aicte_permanent_id"] == "9-PERF-0001"
    assert inst["name"] == "Countersign Throughput Test College"
    assert inst["state_code"] in {s["code"] for s in data["states"]}
    with open(perf / "perf" / "9-PERF-0001_2026-27.csv", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == UPLOAD_COLUMNS
        rows = list(reader)
    assert len(rows) == N
    programmes = {p["code"]: p for p in inst["programmes"]}
    cohorts = Counter((r["programme_code"], int(r["year_of_study"])) for r in rows)
    assert {year for _, year in cohorts} == {1, 2}
    for (code, year), n in cohorts.items():
        assert n <= usable_capacity(programmes[code], year)["REGULAR"], (code, year)


def test_every_row_is_legitimate_with_its_mockgov_lines(perf):
    with open(perf / "perf" / "9-PERF-0001_2026-27.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    folder = perf / "perf" / "mockgov"
    registry = {r["apaar_id"]: r for r in lines(folder / "apaar_registry.jsonl")}
    joinings = {(j["programme"], j["name"], j["dob"]): j
                for j in lines(folder / "admission_joinings.jsonl")}  # fmt: skip
    credits = Counter(c["apaar_id"] for c in lines(folder / "abc_credits.jsonl"))
    accounts = {a["apaar_id"] for a in lines(folder / "digilocker_accounts.jsonl")}
    assert len({r["apaar_id"] for r in rows}) == N
    assert len({r["mobile"] for r in rows}) == N and len({r["email"] for r in rows}) == N
    for row in rows:
        assert row["consent_status"] == "LINKED" and row["status"] == ""
        assert row["admission_route"] in {"COUNSELLING", "MANAGEMENT", "SPOT"}
        reg = registry[row["apaar_id"]]
        assert (reg["name"], reg["dob"]) == (row["name"], row["dob"])
        joining = joinings[(row["programme_code"], row["name"], row["dob"])]
        cohort = 2026 - (int(row["year_of_study"]) - 1)
        assert joining["academic_year"] == f"{cohort}-{(cohort + 1) % 100:02d}"
        assert (
            joining["institution_code"] == "9-PERF-0001"
            and joining["route"] == row["admission_route"]
        )
        assert credits[row["apaar_id"]] == (2 if row["year_of_study"] == "2" else 0)
        assert row["apaar_id"] in accounts
    assert len(joinings) == N


def test_perf_ids_never_repeat_the_main_dataset(perf):
    main = {r["apaar_id"] for r in lines(perf / "mockgov" / "apaar_registry.jsonl")}
    perf_ids = {r["apaar_id"] for r in lines(perf / "perf" / "mockgov" / "apaar_registry.jsonl")}
    assert not main & perf_ids
