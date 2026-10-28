"""mockgov/admission_joinings.jsonl and the cases planted against it."""

import re
import unicodedata
from collections import defaultdict

from rapidfuzz import fuzz

from datagen.config import Config, load_datagen_config
from datagen.joining import JOINING_FIELDS

CFG = load_datagen_config()["joining"]
ABC_FILE = "uploads/1-ABC-0001_2026-27.csv"
DEADLINE = Config.build("small").reporting_deadline
HONORIFICS = {"mr", "ms", "mrs", "dr", "shri", "smt", "kumari", "km", "sri"}
MOHAMMED = {"mohd", "mohammed", "md", "mohammad", "muhammad", "mohamed", "muhammed"}


def mockgov_name(name: str) -> str:
    """services/mockgov/app/names.py normalize_name, as the simulator compares names."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]+", " ", text.lower())
    words = [w for w in text.split() if w not in HONORIFICS]
    return " ".join("mohammed" if w in MOHAMMED else w for w in words)


def records(small) -> list[dict]:
    return small.jsonl("admission_joinings.jsonl")


def joining_year(row: dict) -> str:
    """The year the student joined: the cohort's, or year 2's for a lateral entrant."""
    start = 2026 - (int(row["year_of_study"]) - 1)
    if row["admission_route"] == "LATERAL":
        start += 1
    return f"{start}-{(start + 1) % 100:02d}"


def unpublished(small) -> set[tuple[str, str]]:
    return {
        (r["unpublished"]["state"], r["unpublished"]["academic_year"])
        for r in small.json("ground_truth.json") if r["anomaly_type"] == "SELF_ISSUED_ONLY"
    }  # fmt: skip


def planted(small, kind: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == kind]


def lookup(small):
    """mockgov's POST /admission-authority/joining without a roll number."""
    index = defaultdict(list)
    for rec in records(small):
        key = (rec["institution_code"], rec["academic_year"], rec["programme"], rec["dob"])
        index[key].append(rec)

    def find(aid: str, row: dict) -> dict | None:
        key = (aid, joining_year(row), row["programme_code"], row["dob"])
        best, score = None, 89
        for rec in index.get(key, []):
            s = round(fuzz.token_set_ratio(mockgov_name(row["name"]), mockgov_name(rec["name"])))
            if s > score:
                best, score = rec, s
        return best

    return find


def test_record_shape_and_numbers(small):
    recs = records(small)
    insts = small.institutions()
    assert recs and all(list(r) == JOINING_FIELDS for r in recs)
    assert len({r["roll_no"] for r in recs}) == len(recs)
    rolls = {c["roll_no"] for c in small.jsonl("counselling.jsonl")}
    for rec in recs:
        assert rec["state"] == insts[rec["institution_code"]]["state_code"]
        assert rec["route"] != "INTERNATIONAL"
        if rec["route"] in {"COUNSELLING", "TFW", "LATERAL"}:
            assert rec["roll_no"] in rolls and rec["round"] in {1, 2, 3}
        else:
            assert re.fullmatch(r"[A-Z]{2}AA-\d{4}-\d{6}", rec["roll_no"]), rec["roll_no"]
            assert rec["roll_no"][5:9] == rec["academic_year"][:4] and rec["round"] is None
        assert rec["apaar_id"] is None or re.fullmatch(r"\d{12}", rec["apaar_id"])
    counts = small.json("manifest.json")["counts"]
    assert counts["admission_joinings"] == len(recs)
    late = [r for r in recs if r["joined_on"] > DEADLINE(r["academic_year"])]
    assert counts["admission_joinings_late"] == len(late) >= CFG["late_joiners"]["small"]


def test_one_state_has_not_published_last_year(small):
    ((state, year),) = unpublished(small)
    assert year == "2025-26"
    published = {(r["state"], r["academic_year"]) for r in records(small)}
    assert (state, year) not in published and (state, "2026-27") in published


def test_every_uploaded_student_who_joined_has_their_own_record(small):
    find = lookup(small)
    never = {(r["file"], r["row_no"]) for g in planted(small, "NOT_IN_JOINING_RECORD")
             for r in g["rows"]}  # fmt: skip
    renamed = {
        (g["rows"][1]["file"], g["rows"][1]["row_no"])
        for g in planted(small, "DUPLICATE_WITHIN_UPLOAD")
    }
    files = [f"uploads/{aid}_2026-27.csv" for aid in small.institutions()] + small.update_files()
    insts = small.institutions()
    held_back = unpublished(small)
    registry = {r["apaar_id"]: r["name"] for r in small.jsonl("apaar_registry.jsonl")}
    used = defaultdict(int)
    checked = 0
    for name in files:
        aid = name.split("/")[1].split("_")[0]
        for i, row in enumerate(small.file(name), start=2):
            if row["admission_route"] == "INTERNATIONAL" or (name, i) in renamed:
                continue
            if row["status"] in {"WITHDRAWN", "TRANSFERRED"}:
                continue  # the initial row of the same student was checked
            rec = find(aid, row)
            if (name, i) in never or (insts[aid]["state_code"], joining_year(row)) in held_back:
                assert rec is None, (name, i)
                continue
            assert rec is not None and rec["name"] == row["name"], (name, i)
            own = row["consent_status"] == "LINKED" and registry.get(row["apaar_id"]) == row["name"]
            assert rec["apaar_id"] == (row["apaar_id"] if own else None), (name, i)
            assert rec["route"] == row["admission_route"]
            assert rec["category"] == row["category"]
            assert rec["joined_on"] >= row["admission_date"]
            used[rec["roll_no"]] += 1
            checked += 1
    assert checked > 8500 and max(used.values()) == 1


def test_joined_on_respects_the_reporting_deadline(small):
    recs = records(small)
    deadline = DEADLINE("2026-27")
    assert deadline == "2026-09-30"
    late = [r for r in recs if r["joined_on"] > DEADLINE(r["academic_year"])]
    on_time = len(recs) - len(late)
    assert on_time / len(recs) > 0.99
    assert all(r["academic_year"] == "2026-27" for r in late)


def test_students_who_never_joined(small):
    recs = planted(small, "NOT_IN_JOINING_RECORD")
    assert len(recs) == CFG["never_joined"]["small"]
    registry = {r["apaar_id"]: r for r in small.jsonl("apaar_registry.jsonl")}
    allotments = {c["allotment_ref"] for c in small.jsonl("counselling.jsonl")}
    for rec in recs:
        assert rec["expected_flag"] == "NOT_IN_JOINING_RECORD"
        assert rec["severity_expected"] == "MEDIUM"
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        assert rec["academic_year"] == joining_year(row)
        assert rec["reporting_deadline"] == DEADLINE(rec["academic_year"])
        # Identity verifies, so the joining record is the only thing missing.
        assert registry[row["apaar_id"]]["name"] == row["name"]
        if row["counselling_ref"]:
            assert row["counselling_ref"] in allotments
    card = [r for r in recs if r.get("scenario") == "sample_card"]
    assert len(card) == 1 and card[0]["rows"][0]["file"] == ABC_FILE


def test_the_sample_card(small):
    card = small.json("manifest.json")["sample_card"]
    gt = small.json("ground_truth.json")
    not_me = next(r for r in gt if r.get("scenario") == "not_me")["rows"][0]
    assert card == {"file": not_me["file"], "row_no": not_me["row_no"]}
    rec = next(r for r in gt if r.get("scenario") == "sample_card")
    assert rec["expected_record_status"] == "DISPUTED"
    assert rec["expected_rows"] == {
        "IDENTITY": "CONFIRMED", "SEAT": "CONFIRMED", "ADMISSION": "CONTRADICTED",
        "STUDYING": "NOT_YET_DUE", "STUDENT": "CONTRADICTED",
    }  # fmt: skip
    row = small.row(card["file"], card["row_no"])
    assert row["programme_code"] == "CSE" and row["year_of_study"] == "1"
    assert row["consent_status"] == "LINKED" and row["admission_route"] == "COUNSELLING"
    # The seat fits: it is not one of the twelve ABC CSE admissions left without a seat.
    excess = next(r for r in gt if r.get("scenario") == "abc_cse_132")
    assert card["row_no"] not in {r["row_no"] for r in excess["rows"]}
    tagged = [r["anomaly_type"] for r in gt for x in r["rows"]
              if (x["file"], x["row_no"]) == (card["file"], card["row_no"])]  # fmt: skip
    assert sorted(tagged) == ["NOT_IN_JOINING_RECORD", "STUDENT_DENIED"]
    reply = next(r for r in small.lines("notice_replies.jsonl")
                 if (r["file"], r["row_no"]) == (card["file"], card["row_no"]))  # fmt: skip
    assert (reply["reply"], reply["comment"]) == ("NO", "I never joined this college.")


def test_colleges_that_left_students_out(small):
    recs = planted(small, "MISSING_FROM_UPLOAD")
    assert len(recs) == CFG["omitted_colleges"]["small"]
    assert any(r["institution_aicte_id"] == "1-XYZ-0002" and r["scenario"] == "xyz_missing"
               for r in recs)  # fmt: skip
    recs = [r for r in recs if r.get("scenario") != "overdue"]
    by_roll = {r["roll_no"]: r for r in records(small)}
    registry = {r["apaar_id"] for r in small.jsonl("apaar_registry.jsonl")}
    counselling = {c["roll_no"]: c for c in small.jsonl("counselling.jsonl")}
    lo, hi = CFG["omitted_per_college"]
    total = 0
    for rec in recs:
        aid = rec["institution_aicte_id"]
        assert rec["expected_flag"] == "MISSING_FROM_UPLOAD"
        assert rec["severity_expected"] == "MEDIUM" and rec["rows"] == []
        assert rec["academic_year"] == "2026-27"
        assert lo <= rec["missing"] == len(rec["missing_students"]) <= hi
        uploaded = {(r["name"], r["dob"]) for r in small.upload(aid)}
        joined = [r for r in records(small)
                  if r["institution_code"] == aid and r["academic_year"] == "2026-27"]  # fmt: skip
        assert rec["joined"] == len(joined)
        assert rec["uploaded_and_joined"] == len(joined) - rec["missing"]
        assert rec["completeness_pct"] == round(100 * rec["uploaded_and_joined"] / len(joined), 1)
        for student in rec["missing_students"]:
            joining = by_roll[student["roll_no"]]
            assert joining["institution_code"] == aid and joining["name"] == student["name"]
            assert joining["joined_on"] == student["joined_on"]
            assert (student["name"], student["dob"]) not in uploaded
            if student["apaar_id"]:
                assert student["apaar_id"] in registry
            if student["route"] == "COUNSELLING":
                assert counselling[student["roll_no"]]["institution_aicte_id"] == aid
        total += rec["missing"]
    assert small.json("manifest.json")["counts"]["missing_from_upload"] == total
