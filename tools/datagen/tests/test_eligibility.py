"""Eligibility markers (tfw_income_certified, nri_sponsored, ciwg) and the rows planted on them."""

from seat_math import cohort_label, intake

from datagen.config import load_datagen_config, load_rules
from datagen.students import Pools

CFG = load_datagen_config()["eligibility"]


def records(small, kind: str) -> list[dict]:
    return [r for r in small.json("ground_truth.json") if r["anomaly_type"] == kind]


def planted(small, kind: str) -> dict[tuple[str, int], dict]:
    return {
        (row["file"], row["row_no"]): rec for rec in records(small, kind) for row in rec["rows"]
    }


def every_row(small):
    for aid in small.institutions():
        name = f"uploads/{aid}_2026-27.csv"
        for i, row in enumerate(small.file(name), start=2):
            yield name, i, row


def test_markers_say_yes_on_every_legitimate_row(small):
    breaches = planted(small, "ELIGIBILITY_BREACH")
    blank_tfw = planted(small, "TFW_INCOME_NOT_REPORTED")
    for name, i, row in every_row(small):
        key = (name, i)
        rule = breaches[key]["eligibility_rule"] if key in breaches else None
        route = row["admission_route"]
        for column in ("tfw_income_certified", "nri_sponsored", "ciwg"):
            assert row[column] in {"yes", "no", ""}, (key, column)
        if route == "TFW":
            want = "no" if rule == "TFW_INCOME" else "" if key in blank_tfw else "yes"
            assert row["tfw_income_certified"] == want, key
        else:
            assert row["tfw_income_certified"] == "", key
        if route == "NRI":
            assert row["nri_sponsored"] == ("no" if rule == "NRI_STATUS" else "yes"), key
        else:
            assert row["nri_sponsored"] == "", key
        if route == "INTERNATIONAL" and row["nationality"] == "IN":
            assert row["ciwg"] == ("" if rule == "INTERNATIONAL_CIWG" else "yes"), key
        else:
            assert row["ciwg"] == "", key


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
        ciwg = sum(r["ciwg"] == "yes" for r in cohort)
        assert 1 <= ciwg <= pools.ciwg
        assert len(cohort) - ciwg <= pools.international - pools.ciwg


def test_each_breach_breaks_one_rule(small):
    recs = records(small, "ELIGIBILITY_BREACH")
    by_rule = {}
    for rec in recs:
        by_rule.setdefault(rec["eligibility_rule"], []).append(rec)
        assert rec["expected_flag"] == "ELIGIBILITY_BREACH"
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        assert ref["institution_aicte_id"] != "1-ABC-0001"
        rule = rec["eligibility_rule"]
        if rule == "NRI_STATUS":
            assert row["admission_route"] == "NRI" and row["nri_sponsored"] == "no"
            assert rec["severity_expected"] == "MEDIUM" and rec["source"].endswith("2.8(b)")
        elif rule == "TFW_INCOME":
            assert row["admission_route"] == "TFW" and row["tfw_income_certified"] == "no"
            assert rec["severity_expected"] == "MEDIUM"
        else:
            assert rule == "INTERNATIONAL_CIWG"
            assert row["admission_route"] == "INTERNATIONAL" and row["nationality"] == "IN"
            assert row["ciwg"] == "" and rec["severity_expected"] == "HIGH"
    assert {k: len(v) for k, v in by_rule.items()} == {
        "NRI_STATUS": CFG["nri_status"]["small"],
        "TFW_INCOME": CFG["tfw_income"]["small"],
        "INTERNATIONAL_CIWG": CFG["international_ciwg"]["small"],
    }


def test_a_few_tfw_rows_leave_the_certificate_blank(small):
    recs = records(small, "TFW_INCOME_NOT_REPORTED")
    assert len(recs) == CFG["tfw_not_reported"]["small"]
    for rec in recs:
        assert rec["expected_flag"] is None
        assert rec["expected_check"] == {"type": "SEAT", "status": "PENDING"}
        (ref,) = rec["rows"]
        row = small.row(ref["file"], ref["row_no"])
        assert row["admission_route"] == "TFW" and row["tfw_income_certified"] == ""
