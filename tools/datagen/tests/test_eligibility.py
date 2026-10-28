"""Eligibility markers (tfw_income_certified, nri_sponsored, ciwg) and the cases planted on them."""

from collections import Counter

from seat_math import cohort_label, intake

from datagen.config import load_datagen_config, load_rules
from datagen.students import Pools

CFG = load_datagen_config()["eligibility"]


def records(small, kind: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == kind]


def planted(small, kind: str) -> set[tuple[str, int]]:
    return {(row["file"], row["row_no"]) for rec in records(small, kind) for row in rec["rows"]}


def every_row(small):
    for aid in small.institutions():
        name = f"uploads/{aid}_2026-27.csv"
        for i, row in enumerate(small.file(name), start=2):
            yield name, i, row


def test_markers_follow_the_route(small):
    no_tfw = planted(small, "TFW_INCOME_NOT_REPORTED")
    breach = planted(small, "ELIGIBILITY_BREACH")
    nri = Counter()
    for name, i, row in every_row(small):
        route = row["admission_route"]
        if route == "TFW" and (name, i) not in no_tfw:
            assert row["tfw_income_certified"] == "yes", (name, i)
        else:
            assert row["tfw_income_certified"] == "", (name, i)
        if route == "NRI":
            want = {"NO"} if (name, i) in breach else {"NRI", "NRI_SPONSORED"}
            assert row["nri_sponsored"] in want, (name, i)
            nri[row["nri_sponsored"]] += 1
        else:
            assert row["nri_sponsored"] == "", (name, i)
        ciwg = route == "INTERNATIONAL" and row["nationality"] == "IN"
        assert row["ciwg"] == ("yes" if ciwg else ""), (name, i)
    sponsored = nri["NRI_SPONSORED"] / (nri["NRI"] + nri["NRI_SPONSORED"])
    assert 0.2 <= sponsored <= 0.4, sponsored


def test_ciwg_students_take_reserved_seats_with_a_study_in_india_record(small):
    recs = records(small, "CIWG_ADMISSION")
    assert len(recs) == CFG["ciwg_rows"]["small"]
    sii = {s["passport_no"]: s for s in small.jsonl("sii.jsonl")}
    rules = load_rules()
    insts = small.institutions()
    for rec in recs:
        assert rec["expected_flag"] is None and rec["severity_expected"] is None
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        assert row["admission_route"] == "INTERNATIONAL" and row["nationality"] == "IN"
        assert row["consent_status"] == "INTERNATIONAL" and row["apaar_id"] == ""
        assert row["ciwg"] == "yes" and row["year_of_study"] == "1"
        record = sii[row["passport_no"]]
        assert record["nationality"] == "IN" and record["name"] == row["name"]
        assert record["institution_aicte_id"] == ref["institution_aicte_id"]
        prog = next(
            p for p in insts[ref["institution_aicte_id"]]["programmes"]
            if p["code"] == row["programme_code"]
        )  # fmt: skip
        pools = Pools(rules, prog, intake(prog, cohort_label(1)))
        cohort = [
            r for r in small.upload(ref["institution_aicte_id"])
            if r["programme_code"] == row["programme_code"] and r["year_of_study"] == "1"
            and r["admission_route"] == "INTERNATIONAL"
        ]  # fmt: skip
        ciwg = sum(r["nationality"] == "IN" for r in cohort)
        assert 1 <= ciwg <= pools.ciwg
        assert len(cohort) - ciwg <= pools.international - pools.ciwg


def test_one_nri_route_row_is_not_eligible(small):
    recs = records(small, "ELIGIBILITY_BREACH")
    assert len(recs) == CFG["nri_breach"]["small"]
    for rec in recs:
        assert rec["expected_flag"] == "ELIGIBILITY_BREACH"
        assert rec["severity_expected"] == "MEDIUM"
        assert rec["seat_type"] == "NRI" and rec["marker"] == {"nri_sponsored": "NO"}
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        assert row["admission_route"] == "NRI" and row["nri_sponsored"] == "NO"
        assert ref["institution_aicte_id"] != "1-ABC-0001"


def test_one_tfw_row_has_no_income_certificate(small):
    recs = records(small, "TFW_INCOME_NOT_REPORTED")
    assert len(recs) == CFG["tfw_not_reported"]["small"]
    for rec in recs:
        assert rec["expected_flag"] is None
        assert rec["expected_check"] == {"type": "SEAT", "status": "PENDING"}
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        assert row["admission_route"] == "TFW" and row["tfw_income_certified"] == ""


def test_update_rows_repeat_the_markers_of_their_initial_row(small):
    for name in small.update_files():
        for row in small.file(name):
            if row["status"] in {"WITHDRAWN", "TRANSFERRED"}:
                if row["admission_route"] == "TFW":
                    assert row["tfw_income_certified"] in {"yes", ""}
            if row["admission_route"] != "NRI":
                assert row["nri_sponsored"] == ""
