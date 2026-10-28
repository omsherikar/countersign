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
    accounts_by_person = {(a["name"], a["dob"]): a["digilocker_id"] for a in accounts(small)}
    international = set()
    without = 0
    for aid, rows in small.all_uploads().items():
        file = f"uploads/{aid}_2026-27.csv"
        for i, row in enumerate(rows, start=2):
            if row["admission_route"] == "INTERNATIONAL":
                international.add((row["name"], row["dob"]))
            elif (file, i) in renamed:
                # A renamed duplicate is the same person: no account of its own.
                assert (row["name"], row["dob"]) not in accounts_by_person
            elif row["consent_status"] in {"REFUSED", "PENDING"}:
                assert (row["name"], row["dob"]) in people, row["name"]
                without += 1
    assert without > 300
    assert not international & people


def test_left_out_students_and_graduates_have_accounts(small):
    held = {a["apaar_id"] for a in accounts(small) if a["apaar_id"]}
    people = {(a["name"], a["dob"]) for a in accounts(small)}
    for rec in small.json("ground_truth.json"):
        for student in rec.get("missing_students", []):
            if student["apaar_id"]:
                assert student["apaar_id"] in held
            assert (student["name"], student["dob"]) in people
    for grad in small.lines("graduates.jsonl"):
        assert (grad["name"], grad["dob"]) in people


def test_the_demo_accounts_come_first(small):
    demo = small.json("manifest.json")["demo_digilocker_accounts"]
    assert [d["role"] for d in demo] == [
        "DEMO_STUDENT", "SECOND_DEMO_NOTICE", "PROVISIONAL_CLAIM", "SOMEONE_ELSE", "SAMPLE_CARD",
    ]  # fmt: skip
    rows = accounts(small)
    assert [a["digilocker_id"] for a in rows[: len(demo)]] == [d["digilocker_id"] for d in demo]
    for d, account in zip(demo, rows, strict=False):
        assert set(d) == {"role", "digilocker_id", "name", "dob", "apaar_id", "file", "row_no"}
        assert (d["name"], d["dob"], d["apaar_id"]) == (
            account["name"], account["dob"], account["apaar_id"],
        )  # fmt: skip
        row = small.row(d["file"], d["row_no"])
        assert (row["name"], row["dob"]) == (d["name"], d["dob"])
    by_role = {d["role"]: d for d in demo}
    assert by_role["DEMO_STUDENT"]["digilocker_id"] == "DL-RAVI-4417"
    unanswered = {u["role"]: u for u in small.json("manifest.json")["demo_unanswered_notices"]}
    second = unanswered["SECOND_DEMO_NOTICE"]
    assert (by_role["SECOND_DEMO_NOTICE"]["file"], by_role["SECOND_DEMO_NOTICE"]["row_no"]) == (
        second["file"], second["row_no"],
    )  # fmt: skip
    card = small.json("manifest.json")["sample_card"]
    assert (by_role["SAMPLE_CARD"]["file"], by_role["SAMPLE_CARD"]["row_no"]) == (
        card["file"], card["row_no"],
    )  # fmt: skip
    claim = by_role["PROVISIONAL_CLAIM"]
    row = small.row(claim["file"], claim["row_no"])
    assert claim["apaar_id"] is None and row["consent_status"] == "REFUSED"
    assert claim["file"] == "uploads/1-ABC-0001_2026-27.csv"
    assert (row["programme_code"], row["year_of_study"]) == ("CSE", "1") and row["email"]
    assert not by_role["SOMEONE_ELSE"]["file"].startswith("uploads/1-ABC-0001")
