"""graduates.jsonl: 2025-26 final-year students who have finished, for the degree proof."""

import datetime as dt
import re
from collections import Counter

FIELDS = [
    "institution_aicte_id", "programme_code", "academic_year", "year_of_study", "name", "dob",
    "gender", "apaar_id", "consent_status", "provisional_id", "email", "mobile", "nationality",
    "year_of_award", "admission_route", "category", "admission_date", "status_date",
]  # fmt: skip
ABC = "1-ABC-0001"
APAAR = re.compile(r"[1-9][0-9]{11}")
PROVISIONAL = re.compile(r"PRV-[A-Z2-7]{8}")


def graduates(gen) -> list[dict]:
    return gen.lines("graduates.jsonl")


def roll_rows(gen) -> list[dict]:
    rows = [r for rows in gen.all_uploads().values() for r in rows]
    return rows + [r for name in gen.update_files() for r in gen.file(name)]


def test_final_year_of_2025_26_at_affiliated_colleges(small):
    grads = graduates(small)
    assert len(grads) == 40
    insts = small.institutions()
    for g in grads:
        assert list(g) == FIELDS
        assert (g["academic_year"], g["year_of_award"], g["nationality"]) == ("2025-26", 2026, "IN")
        inst = insts[g["institution_aicte_id"]]
        prog = next(p for p in inst["programmes"] if p["code"] == g["programme_code"])
        assert prog["mode"] == "PHYSICAL"
        assert g["year_of_study"] == prog["duration_years"]
        assert any(a["academic_year"] == "2025-26" for a in prog["approvals"])
        assert g["gender"] in {"M", "F"}
        assert g["admission_route"] in {"COUNSELLING", "MANAGEMENT"}
        assert g["category"] in {"GENERAL", "OBC", "SC", "ST", "EWS", "OTHER"}
        start = 2025 - (g["year_of_study"] - 1)
        admitted = dt.date.fromisoformat(g["admission_date"])
        assert dt.date(start, 7, 1) <= admitted <= dt.date(start, 9, 30)
        assert "2026-06-15" <= g["status_date"] <= "2026-07-31"
        age = start - dt.date.fromisoformat(g["dob"]).year
        assert 16 <= age <= 26, g
    universities = Counter(insts[g["institution_aicte_id"]]["university_code"] for g in grads)
    assert universities["MSTU"] == 24
    assert len(universities) >= 3
    assert len(universities) <= 4
    at_abc = [g for g in grads if g["institution_aicte_id"] == ABC]
    assert len(at_abc) == 12
    abc_cse = [g for g in at_abc if g["programme_code"] == "CSE"]
    assert len(abc_cse) >= 4 and all(g["consent_status"] == "LINKED" for g in abc_cse)


def test_most_linked_a_few_provisional(small):
    grads = graduates(small)
    provisional = [g for g in grads if g["provisional_id"] is not None]
    assert 3 <= len(provisional) <= 5
    assert sum(g["institution_aicte_id"] == ABC for g in provisional) == 1
    for g in grads:
        if g["provisional_id"] is None:
            assert g["consent_status"] == "LINKED" and APAAR.fullmatch(g["apaar_id"])
        else:
            assert g["apaar_id"] is None and PROVISIONAL.fullmatch(g["provisional_id"])
            assert g["consent_status"] in {"PENDING", "REFUSED"}
    for key in ("apaar_id", "provisional_id", "email", "mobile"):
        values = [g[key] for g in grads if g[key] is not None]
        assert len(values) == len(set(values)), key


def test_graduate_apaars_are_in_the_registry(small):
    registry = {r["apaar_id"]: r for r in small.jsonl("apaar_registry.jsonl")}
    linked = [g for g in graduates(small) if g["apaar_id"]]
    assert len(linked) >= 35
    for g in linked:
        rec = registry[g["apaar_id"]]
        assert (rec["name"], rec["dob"], rec["gender"]) == (g["name"], g["dob"], g["gender"])
    assert small.json("manifest.json")["counts"]["apaar_registry"] == len(registry)


def test_graduates_are_not_on_the_2026_27_roll(small):
    roll = roll_rows(small)
    grads = graduates(small)
    for key in ("apaar_id", "email", "mobile"):
        taken = {r[key] for r in roll if r[key]}
        assert not taken & {g[key] for g in grads if g[key]}, key
    assert small.json("manifest.json")["counts"]["graduates"] == len(grads)
    assert small.summary["counts"]["graduates"] == len(grads)
