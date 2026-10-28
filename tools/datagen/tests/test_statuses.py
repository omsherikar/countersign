"""Records planted to check the record status rule: CLEAN_INDEPENDENT, SELF_ISSUED_ONLY and
PROVISIONAL_UNCLAIMED, each answering no notice."""

from datagen.config import load_datagen_config

CFG = load_datagen_config()["statuses"]


def records(small, kind: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == kind]


def replies(small) -> dict[tuple[str, int], dict]:
    return {(r["file"], r["row_no"]): r for r in small.lines("notice_replies.jsonl")}


def joining_lines(small) -> set[tuple[str, str, str, str]]:
    return {
        (j["institution_code"], j["programme"], j["name"], j["dob"])
        for j in small.jsonl("admission_joinings.jsonl")
    }


def test_clean_records_countersigned_by_their_joining_line(small):
    recs = records(small, "CLEAN_INDEPENDENT")
    assert len(recs) == CFG["clean_independent"]["small"]
    registry = {r["apaar_id"]: r for r in small.jsonl("apaar_registry.jsonl")}
    lines = joining_lines(small)
    answers = replies(small)
    others = {
        (row["file"], row["row_no"]) for rec in small.json("ground_truth.json")
        if rec["anomaly_type"] != "CLEAN_INDEPENDENT" for row in rec["rows"]
    }  # fmt: skip
    for rec in recs:
        assert rec["expected_flag"] is None
        assert rec["expected_record_status"] == "COUNTERSIGNED"
        (ref,) = rec["rows"]
        key = (ref["file"], ref["row_no"])
        assert key not in others
        row = small.row(*key)
        assert row["consent_status"] == "LINKED"
        assert registry[row["apaar_id"]]["name"] == row["name"]
        aid = ref["institution_aicte_id"]
        assert (aid, row["programme_code"], row["name"], row["dob"]) in lines
        assert answers[key]["reply"] == "NONE"


def test_second_years_with_only_self_issued_credits(small):
    recs = records(small, "SELF_ISSUED_ONLY")
    assert len(recs) == CFG["self_issued_only"]["small"]
    insts = small.institutions()
    lines = small.jsonl("admission_joinings.jsonl")
    answers = replies(small)
    for rec in recs:
        assert rec["expected_flag"] is None
        assert rec["expected_record_status"] == "AWAITING_EVIDENCE"
        state, year = rec["unpublished"]["state"], rec["unpublished"]["academic_year"]
        assert year == "2025-26"
        assert not any(j["state"] == state and j["academic_year"] == year for j in lines)
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        inst = insts[ref["institution_aicte_id"]]
        assert inst["state_code"] == state and inst["autonomous"]
        assert row["year_of_study"] == "2" and row["admission_route"] != "LATERAL"
        credits = [c for c in small.jsonl("abc_credits.jsonl") if c["apaar_id"] == row["apaar_id"]]
        assert len(credits) == 2 and all(c["credits"] > 0 for c in credits)
        assert {c["issuer"] for c in credits} == {inst["aicte_permanent_id"]}
        assert answers[(ref["file"], ref["row_no"])]["reply"] == "NONE"


def test_the_provisional_claim_waits_for_the_student(small):
    (rec,) = records(small, "PROVISIONAL_UNCLAIMED")
    assert rec["expected_record_status"] == "AWAITING_EVIDENCE"
    assert rec["expected_record_status_after_claim"] == "COUNTERSIGNED"
    (ref,) = rec["rows"]
    row = small.row(ref["file"], ref["row_no"])
    assert row["consent_status"] == "REFUSED" and row["apaar_id"] == "" and row["email"]
    assert ("1-ABC-0001", "CSE", row["name"], row["dob"]) in joining_lines(small)
    assert replies(small)[(ref["file"], ref["row_no"])]["reply"] == "NONE"
    demo = small.json("manifest.json")["demo_digilocker_accounts"]
    claim = next(d for d in demo if d["role"] == "PROVISIONAL_CLAIM")
    assert (claim["file"], claim["row_no"]) == (ref["file"], ref["row_no"])
