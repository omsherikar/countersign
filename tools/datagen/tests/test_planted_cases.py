"""Every planted case is producible by the decision rules in ENGINES.md as written."""

import re
from collections import Counter

from seat_math import ROUTE_POOL, RULES, cohort_rows, intake, pool_counts, usable_capacity

from datagen.matching import match_names, name_key, normalise_name, registry_score
from datagen.students import Pools

APAAR = re.compile(r"[0-9]{12}")


def records(small, anomaly_type: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == anomaly_type]


def programme(small, aid: str, code: str) -> dict:
    return next(p for p in small.institutions()[aid]["programmes"] if p["code"] == code)


def usable_apaar(row: dict) -> bool:
    return bool(APAAR.fullmatch(row["apaar_id"])) and row["consent_status"] == "LINKED"


def latest_in_pool(small, rec: dict, pool: str) -> None:
    """The planted rows are the pool's last admissions, so the ledger leaves them unseated."""
    aid, code = rec["institution_aicte_id"], rec["programme_code"]
    planted = {r["row_no"] for r in rec["rows"]}
    dates = [
        row["admission_date"]
        for i, row in enumerate(small.upload(aid), start=2)
        if i not in planted and row["programme_code"] == code and row["year_of_study"] == "1"
        and ROUTE_POOL[row["admission_route"]] == pool
    ]  # fmt: skip
    for r in rec["rows"]:
        row = small.row(r["file"], r["row_no"])
        assert ROUTE_POOL[row["admission_route"]] == pool
        assert row["admission_date"] > max(dates)


def test_excess_admission_overflows_the_regular_pool(small):
    recs = records(small, "EXCESS_ADMISSION")
    assert recs
    for rec in recs:
        aid, code = rec["institution_aicte_id"], rec["programme_code"]
        prog = programme(small, aid, code)
        counts = pool_counts(small.upload(aid), code, 1)
        cap = usable_capacity(prog, 1)
        admitted = counts["REGULAR"] + counts["NRI"]
        assert rec["approved_intake"] == intake(prog, "2026-27")
        assert admitted == rec["admitted"] > rec["approved_intake"]
        assert counts["NRI"] <= cap["NRI"]
        assert counts["REGULAR"] - cap["REGULAR"] == rec["unseated"] == len(rec["rows"])
        latest_in_pool(small, rec, "REGULAR")


def test_quota_breach_overflows_the_routes_pool(small):
    recs = records(small, "QUOTA_BREACH")
    assert {r["seat_type"] for r in recs} == {"NRI", "INTERNATIONAL"}
    for rec in recs:
        aid, code, pool = rec["institution_aicte_id"], rec["programme_code"], rec["seat_type"]
        prog = programme(small, aid, code)
        counts = pool_counts(small.upload(aid), code, 1)
        cap = usable_capacity(prog, 1)
        full = Pools(RULES, prog, intake(prog, "2026-27"))
        assert rec["capacity"] == (full.nri if pool == "NRI" else full.international)
        assert counts[pool] == rec["admitted"] > rec["capacity"]
        assert counts[pool] - cap[pool] == rec["unseated"] == len(rec["rows"])
        # Only the planted pool overflows: no excess admission rides along.
        assert counts["REGULAR"] <= cap["REGULAR"]
        assert counts["REGULAR"] + counts["NRI"] <= rec["approved_intake"]
        latest_in_pool(small, rec, pool)


def test_renamed_duplicates_block_together_and_share_a_mobile(small):
    recs = records(small, "DUPLICATE_WITHIN_UPLOAD")
    assert {r["variant"] for r in recs} == {"INITIALS", "TRANSLITERATION", "MOHD"}
    for rec in recs:
        a, b = (small.row(r["file"], r["row_no"]) for r in rec["rows"])
        assert rec["rows"][0]["institution_aicte_id"] == rec["rows"][1]["institution_aicte_id"]
        assert a["name"] != b["name"]
        assert a["dob"] == b["dob"] and a["mobile"] == b["mobile"]
        assert name_key(a["name"], a["dob"]) == name_key(b["name"], b["dob"])
        assert match_names(a["name"], b["name"]).score >= 90
        if "devanagari" in rec:
            assert name_key(rec["devanagari"], a["dob"]) == name_key(a["name"], a["dob"])
            assert match_names(rec["devanagari"], a["name"]).score >= 90
        assert [usable_apaar(a), usable_apaar(b)] == [True, False]
        assert b["consent_status"] == "PENDING"
        if rec["variant"] == "MOHD":
            assert normalise_name(a["name"]) == normalise_name(b["name"])


def test_cross_institution_pairs_share_one_apaar(small):
    insts = small.institutions()
    for anomaly_type, allowed in (
        ("DUPLICATE_CROSS_INSTITUTION", {("PHYSICAL", "PHYSICAL")}),
        ("DUAL_ENROLMENT_ALLOWED", {("PHYSICAL", "ODL"), ("PHYSICAL", "ONLINE")}),
    ):
        recs = records(small, anomaly_type)
        assert recs
        for rec in recs:
            a, b = rec["rows"]
            assert a["institution_aicte_id"] != b["institution_aicte_id"]
            ra, rb = small.row(a["file"], a["row_no"]), small.row(b["file"], b["row_no"])
            assert usable_apaar(ra) and ra["apaar_id"] == rb["apaar_id"]
            for col in ("name", "dob", "consent_status"):
                assert ra[col] == rb[col]
            modes = tuple(
                next(
                    p["mode"] for p in insts[r["institution_aicte_id"]]["programmes"]
                    if p["code"] == r["programme_code"]
                )
                for r in (a, b)
            )  # fmt: skip
            assert modes in allowed


def test_name_mismatch_scores_below_review_with_the_same_dob(small):
    registry = {r["apaar_id"]: r for r in small.jsonl("apaar_registry.jsonl")}
    recs = records(small, "NAME_MISMATCH")
    assert recs
    for rec in recs:
        row = small.row(rec["rows"][0]["file"], rec["rows"][0]["row_no"])
        reg = registry[row["apaar_id"]]
        assert reg["name"] == rec["registry_name"] and reg["dob"] == row["dob"]
        assert registry_score(row["name"], reg["name"]) < 75


def test_invalid_apaar_kinds(small):
    registry = {r["apaar_id"] for r in small.jsonl("apaar_registry.jsonl")}
    abc = {a["apaar_id"] for a in small.jsonl("abc_credits.jsonl")}
    recs = records(small, "INVALID_APAAR")
    assert {r["kind"] for r in recs} == {"UNKNOWN", "SHORT", "LONG", "LETTERS"}
    for rec in recs:
        row = small.row(rec["rows"][0]["file"], rec["rows"][0]["row_no"])
        assert row["consent_status"] == "LINKED"
        apaar = row["apaar_id"]
        if rec["kind"] == "UNKNOWN":
            assert APAAR.fullmatch(apaar) and apaar not in registry and apaar not in abc
        else:
            assert not APAAR.fullmatch(apaar)
            assert len(apaar) == {"SHORT": 11, "LONG": 13, "LETTERS": 12}[rec["kind"]]


def test_no_academic_activity_misses_two_semesters(small):
    registry = {r["apaar_id"] for r in small.jsonl("apaar_registry.jsonl")}
    credited = Counter()
    for a in small.jsonl("abc_credits.jsonl"):
        if a["credits"] > 0:
            credited[a["apaar_id"]] += 1
    recs = records(small, "NO_ACADEMIC_ACTIVITY")
    assert recs
    for rec in recs:
        row = small.row(rec["rows"][0]["file"], rec["rows"][0]["row_no"])
        assert usable_apaar(row) and row["apaar_id"] in registry
        expected = 2 * (int(row["year_of_study"]) - 1)
        assert expected >= 2
        assert credited[row["apaar_id"]] <= expected - 2


def test_programmes_without_a_seat_case_stay_inside_every_pool(small):
    seat_cases = {
        (r["institution_aicte_id"], r["programme_code"]): r.get("seat_type", "REGULAR")
        for r in small.json("ground_truth.json")
        if r["anomaly_type"] in {"EXCESS_ADMISSION", "QUOTA_BREACH"}
    }
    checked = 0
    for aid, inst in small.institutions().items():
        rows = small.upload(aid)
        for prog in inst["programmes"]:
            for year in range(1, prog["duration_years"] + 1):
                cap = usable_capacity(prog, year)
                counts = pool_counts(rows, prog["code"], year)
                if not cap:
                    assert not cohort_rows(rows, prog["code"], year)
                    continue
                breached = seat_cases.get((aid, prog["code"])) if year == 1 else None
                for pool, n in counts.items():
                    if pool != breached:
                        assert n <= cap[pool], (aid, prog["code"], year, pool)
                        checked += 1
    assert checked > 300
