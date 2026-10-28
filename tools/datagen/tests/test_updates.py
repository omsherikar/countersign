"""Update files: withdrawals, transfers and late refills (API_CONTRACT A2.24)."""

from collections import Counter

from seat_math import CUTOFF, ROUTE_POOL, pool_counts, usable_capacity

from datagen.config import load_datagen_config

ABC_UPDATE = "uploads/1-ABC-0001_2026-27_update1.csv"
STATUS_FROM, STATUS_TO = "2026-09-16", "2026-10-20"
# Every column an existing student's update row repeats from its initial row.
REPEATED = [
    "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality",
    "passport_no", "programme_code", "academic_year", "year_of_study", "admission_route",
    "counselling_ref", "category", "consent_status", "admission_date",
]  # fmt: skip


def aicte_of(file: str) -> str:
    return file.split("/")[1].split("_")[0]


def records(small, anomaly_type: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == anomaly_type]


def initial_row_no(small, aid: str, row: dict) -> int:
    matches = [
        i for i, r in enumerate(small.upload(aid), start=2)
        if all(r[c] == row[c] for c in REPEATED)
    ]  # fmt: skip
    assert len(matches) == 1, (aid, row["name"])
    return matches[0]


def test_update_files_for_abc_and_the_configured_count(small):
    want = load_datagen_config()["updates"]["colleges"]["small"]
    files = small.update_files()
    assert len(files) == want
    assert ABC_UPDATE in files
    assert len({aicte_of(f) for f in files}) == want


def test_update_rows_change_something_and_repeat_identity(small):
    for file in small.update_files():
        aid = aicte_of(file)
        statuses = Counter()
        for row in small.file(file):
            statuses[row["status"]] += 1
            if row["status"] in {"WITHDRAWN", "TRANSFERRED"}:
                initial_row_no(small, aid, row)
                assert STATUS_FROM <= row["status_date"] <= STATUS_TO
            else:
                assert row["status"] == "ACTIVE" and row["status_date"] == ""
        assert 2 <= statuses["WITHDRAWN"] <= 4, file
        assert 1 <= statuses["TRANSFERRED"] <= 2, file
        assert statuses["ACTIVE"] >= 1, file


def test_updates_leave_planted_rows_and_seat_cases_alone(small):
    gt = small.json("ground_truth.json")
    planted = {
        (r["file"], r["row_no"])
        for rec in gt if rec["anomaly_type"] not in {"WITHDRAWAL", "TRANSFER", "LATE_REFILL"}
        for r in rec["rows"]
    }  # fmt: skip
    seat_cases = {
        (rec["institution_aicte_id"], rec["programme_code"])
        for rec in gt if rec["anomaly_type"] in {"EXCESS_ADMISSION", "QUOTA_BREACH"}
    }  # fmt: skip
    for file in small.update_files():
        aid = aicte_of(file)
        for row in small.file(file):
            if row["year_of_study"] == "1":
                assert (aid, row["programme_code"]) not in seat_cases
            assert row["apaar_id"] != "123456784417"
            if row["status"] != "ACTIVE":
                initial = f"uploads/{aid}_2026-27.csv"
                assert (initial, initial_row_no(small, aid, row)) not in planted


def test_withdrawal_and_transfer_records_are_not_flagged(small):
    for anomaly_type, status in (("WITHDRAWAL", "WITHDRAWN"), ("TRANSFER", "TRANSFERRED")):
        recs = records(small, anomaly_type)
        assert recs
        for rec in recs:
            assert rec["expected_flag"] is None and rec["severity_expected"] is None
            (ref,) = rec["rows"]
            assert ref["file"].endswith("_update1.csv")
            row = small.row(ref["file"], ref["row_no"])
            assert row["status"] == status and row["status_date"] == rec["status_date"]
    statuses = Counter(
        row["status"] for f in small.update_files() for row in small.file(f)
    )  # fmt: skip
    assert statuses["WITHDRAWN"] == len(records(small, "WITHDRAWAL"))
    assert statuses["TRANSFERRED"] == len(records(small, "TRANSFER"))


def test_late_refills_take_seats_released_in_the_same_file(small):
    registry = {r["apaar_id"]: r for r in small.jsonl("apaar_registry.jsonl")}
    counselled = {(c["name"], c["dob"]) for c in small.jsonl("counselling.jsonl")}
    recs = records(small, "LATE_REFILL")
    assert len(recs) == len(small.update_files())
    for rec in recs:
        assert rec["expected_flag"] == "LATE_REFILL" and rec["severity_expected"] == "MEDIUM"
        assert rec["seat_type"] == "REGULAR" and rec["cutoff_date"] == CUTOFF
        aid, code = rec["institution_aicte_id"], rec["programme_code"]
        file = rec["rows"][0]["file"]
        assert file == f"uploads/{aid}_2026-27_update1.csv"
        refills = [small.row(r["file"], r["row_no"]) for r in rec["rows"]]
        released = [small.row(r["file"], r["row_no"]) for r in rec["released_rows"]]
        assert len(refills) == len(released) >= 1
        assert {r["file"] for r in rec["released_rows"]} == {file}
        for row in released:
            assert row["status"] == "WITHDRAWN" and row["programme_code"] == code
            assert row["year_of_study"] == "1"
            assert ROUTE_POOL[row["admission_route"]] == "REGULAR"
        # Every first-year REGULAR-pool withdrawal of the programme frees a seat for a refill.
        withdrawn = [
            r for r in small.file(file)
            if r["status"] == "WITHDRAWN" and r["programme_code"] == code
            and r["year_of_study"] == "1" and ROUTE_POOL[r["admission_route"]] == "REGULAR"
        ]  # fmt: skip
        assert len(withdrawn) == len(released)
        last_release = max(r["status_date"] for r in released)
        for row in refills:
            assert row["status"] == "ACTIVE" and row["programme_code"] == code
            assert row["year_of_study"] == "1"
            assert row["admission_route"] in {"MANAGEMENT", "SPOT"}
            assert CUTOFF < row["admission_date"] <= STATUS_TO
            assert row["admission_date"] > last_release
            assert row["consent_status"] == "LINKED"
            reg = registry[row["apaar_id"]]
            assert reg["name"] == row["name"] and reg["dob"] == row["dob"]
            assert (row["name"], row["dob"]) not in counselled
            assert all(r["apaar_id"] != row["apaar_id"] for r in small.upload(aid))
        # The pool was exactly full, so the released seats are the only free ones.
        prog = next(p for p in small.institutions()[aid]["programmes"] if p["code"] == code)
        counts = pool_counts(small.upload(aid), code, 1)
        assert counts["REGULAR"] == usable_capacity(prog, 1)["REGULAR"]


def test_abc_update_withdraws_from_cse_and_refills_after_the_cutoff(small):
    rec = next(r for r in small.json("ground_truth.json") if r.get("scenario") == "late_refill")
    assert rec["anomaly_type"] == "LATE_REFILL"
    assert rec["institution_aicte_id"] == "1-ABC-0001"
    assert rec["rows"][0]["file"] == ABC_UPDATE
    cse = [r for r in small.file(ABC_UPDATE) if r["programme_code"] == "CSE"]
    assert any(r["status"] == "WITHDRAWN" for r in cse)
    # The 132-against-120 first-year cohort is never touched.
    assert all(r["year_of_study"] != "1" for r in cse)
