"""mockgov/digilocker_accounts.jsonl: one synthetic account per person, international excluded."""

import re
from collections import Counter

FIELDS = ["digilocker_id", "name", "dob", "gender", "apaar_id"]


def accounts(small) -> list[dict]:
    return small.jsonl("digilocker_accounts.jsonl")


def test_shape_and_ids(small):
    rows = accounts(small)
    assert all(list(a) == FIELDS for a in rows)
    ids = [a["digilocker_id"] for a in rows]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"DL-[A-Z0-9]{4}-[A-Z0-9]{4}", i) for i in ids)
    ravi = next(a for a in rows if a["apaar_id"] == "123456784417")
    assert ravi == {
        "digilocker_id": "DL-RAVI-4417",
        "name": "Ravi Kumar Sharma",
        "dob": "2007-03-21",
        "gender": "M",
        "apaar_id": "123456784417",
    }
    assert small.json("manifest.json")["counts"]["digilocker_accounts"] == len(rows)


def test_every_registry_apaar_has_one_account(small):
    by_apaar = Counter(a["apaar_id"] for a in accounts(small) if a["apaar_id"])
    registry = small.jsonl("apaar_registry.jsonl")
    assert set(by_apaar) == {r["apaar_id"] for r in registry}
    assert max(by_apaar.values()) == 1
    held = {a["apaar_id"]: a for a in accounts(small) if a["apaar_id"]}
    for rec in registry:
        account = held[rec["apaar_id"]]
        assert (account["name"], account["dob"], account["gender"]) == (
            rec["name"], rec["dob"], rec["gender"],
        )  # fmt: skip


def test_students_without_apaar_have_accounts_but_international_students_do_not(small):
    people = {(a["name"], a["dob"]) for a in accounts(small) if a["apaar_id"] is None}
    renamed = {
        (rec["rows"][1]["file"], rec["rows"][1]["row_no"]): rec["rows"][0]
        for rec in small.json("ground_truth.json")
        if rec["anomaly_type"] == "DUPLICATE_WITHIN_UPLOAD"
    }
    replies = {(r["file"], r["row_no"]): r for r in small.lines("notice_replies.jsonl")}
    international = set()
    without = 0
    for aid, rows in small.all_uploads().items():
        file = f"uploads/{aid}_2026-27.csv"
        for i, row in enumerate(rows, start=2):
            if row["admission_route"] == "INTERNATIONAL":
                international.add((row["name"], row["dob"]))
            elif (file, i) in renamed:
                # A renamed duplicate is the same person: the original's account.
                original = renamed[(file, i)]
                key = (original["file"], original["row_no"])
                assert replies[(file, i)]["digilocker_id"] == replies[key]["digilocker_id"]
            elif row["consent_status"] in {"REFUSED", "PENDING"}:
                assert (row["name"], row["dob"]) in people, row["name"]
                without += 1
    assert without > 300
    assert not international & people


def test_left_out_students_and_graduates_have_accounts(small):
    held = {a["apaar_id"] for a in accounts(small) if a["apaar_id"]}
    people = {(a["name"], a["dob"]) for a in accounts(small)}
    for rec in small.json("ground_truth.json"):
        for student in rec.get("missing", []):
            if student["apaar_id"]:
                assert student["apaar_id"] in held
            assert (student["name"], student["dob"]) in people
    for grad in small.lines("graduates.jsonl"):
        assert (grad["name"], grad["dob"]) in people
