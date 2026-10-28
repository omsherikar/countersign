"""Rows not referenced by ground truth must pass all five countersign checks."""

import re
from collections import Counter

from datagen.config import load_rules
from datagen.students import Pools, round_half_up

APAAR = re.compile(r"^[0-9]{12}$")
MOBILE = re.compile(r"^[789][0-9]{9}$")


def planted_rows(small) -> set[tuple[str, int]]:
    return {
        (row["institution_aicte_id"], row["row_no"])
        for rec in small.json("ground_truth.json")
        for row in rec["rows"]
    }


def planted_programmes(small) -> set[tuple[str, str]]:
    return {
        (rec["institution_aicte_id"], rec["programme_code"])
        for rec in small.json("ground_truth.json")
        if rec["anomaly_type"] in {"EXCESS_ADMISSION", "QUOTA_BREACH"}
    }


def test_clean_rows_match_every_registry(small):
    planted = planted_rows(small)
    registry = {r["apaar_id"]: r for r in small.jsonl("apaar_registry.jsonl")}
    counselling = {c["allotment_ref"]: c for c in small.jsonl("counselling.jsonl")}
    credits = Counter()
    for a in small.jsonl("abc_credits.jsonl"):
        if a["credits"] > 0:
            credits[a["apaar_id"]] += 1
    sii = {s["passport_no"]: s for s in small.jsonl("sii.jsonl")}
    checked = Counter()
    for aid, rows in small.all_uploads().items():
        for i, row in enumerate(rows, start=1):
            if (aid, i) in planted:
                continue
            assert row["academic_year"] == "2026-27"
            assert row["year_of_study"] in {"1", "2", "3"}
            assert row["gender"] in {"M", "F", "O"}
            assert row["category"] in {"GENERAL", "EWS", "OBC", "SC", "ST", "OTHER"}
            assert MOBILE.fullmatch(row["mobile"])
            assert row["dob"] < "2011-01-01"
            # IDENTITY
            if row["consent_status"] == "LINKED":
                assert APAAR.fullmatch(row["apaar_id"])
                reg = registry[row["apaar_id"]]
                assert reg["name"] == row["name"] and reg["dob"] == row["dob"]
                checked["identity"] += 1
            elif row["consent_status"] in {"PENDING", "REFUSED"}:
                assert row["apaar_id"] == "" and row["nationality"] == "IN"
            else:
                assert row["consent_status"] == "INTERNATIONAL"
                assert row["apaar_id"] == "" and row["nationality"] != "IN"
                assert row["admission_route"] == "INTERNATIONAL"
            # ADMISSION
            if row["admission_route"] in {"COUNSELLING", "TFW", "LATERAL"}:
                c = counselling[row["counselling_ref"]]
                assert c["name"] == row["name"] and c["dob"] == row["dob"]
                assert c["institution_aicte_id"] == aid
                assert c["programme"] == row["programme_code"]
                checked["admission"] += 1
            else:
                assert row["counselling_ref"] == ""
            if row["admission_route"] == "LATERAL":
                assert row["year_of_study"] == "2"
            # STUDYING
            if row["year_of_study"] != "1" and row["apaar_id"]:
                assert credits[row["apaar_id"]] >= 2 * (int(row["year_of_study"]) - 1)
                checked["studying"] += 1
            # STUDENT (international): Study in India record
            if row["admission_route"] == "INTERNATIONAL":
                s = sii[row["passport_no"]]
                assert s["name"] == row["name"] and s["institution_aicte_id"] == aid
                assert s["programme"] == row["programme_code"]
                checked["sii"] += 1
    assert checked["identity"] > 5000
    assert checked["admission"] > 3000
    assert checked["studying"] > 2000
    assert checked["sii"] > 50


def test_clean_programmes_stay_inside_seat_pools(small):
    rules = load_rules()
    breached = planted_programmes(small)
    insts = small.json("institutions.json")["institutions"]
    for inst in insts:
        aid = inst["aicte_permanent_id"]
        rows = small.upload(aid)
        for prog in inst["programmes"]:
            if prog["mode"] != "PHYSICAL" or (aid, prog["code"]) in breached:
                continue
            approvals = {a["academic_year"]: a["approved_intake"] for a in prog["approvals"]}
            intake = approvals.get("2026-27")
            if intake is None:
                continue
            pools = Pools(rules, prog, intake)
            first = [
                r for r in rows
                if r["programme_code"] == prog["code"] and r["year_of_study"] == "1"
            ]  # fmt: skip
            routes = Counter(r["admission_route"] for r in first)
            assert len(first) <= intake, (aid, prog["code"])
            assert routes["NRI"] <= pools.nri
            assert routes["TFW"] <= pools.tfw
            assert routes["INTERNATIONAL"] <= pools.international
            regular = routes["COUNSELLING"] + routes["MANAGEMENT"] + routes["SPOT"]
            assert regular + routes["NRI"] <= intake


def test_pool_arithmetic_matches_rules_examples():
    rules = load_rules()
    cse = {"discipline": "ENGINEERING", "level": "UG"}
    p = Pools(rules, cse, 120)
    assert (p.regular, p.nri, p.tfw, p.lateral, p.international) == (114, 6, 6, 12, 18)
    mba = {"discipline": "MANAGEMENT", "level": "PG"}
    assert Pools(rules, mba, 60).international == 15
    assert round_half_up(2.5) == 3 and round_half_up(2.4) == 2


def test_no_real_looking_pii(small):
    rows = small.upload("1-ABC-0001") + small.upload("1-XYZ-0002")
    mobiles = {r["mobile"] for r in rows}
    assert all(m[0] in "789" for m in mobiles)
    # Random, not sequential: distinct numbers rarely share a 6-digit prefix.
    prefixes = Counter(m[:6] for m in mobiles)
    assert max(prefixes.values()) <= 3
    for r in rows:
        domain = r["email"].split("@")[1]
        assert domain in {
            "example.com", "example.net", "example.org", "mail.example", "example.demo",
        }  # fmt: skip
    assert all(r["address"].count(",") >= 3 for r in rows)
