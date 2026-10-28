"""Signals the detectors should raise (GHOST_RING, ANOMALY) and history.json."""

import statistics

from datagen.config import load_datagen_config

CFG = load_datagen_config()["signals"]


def anomalies(small, feature: str | None = None) -> list[dict]:
    return [
        r for r in small.json("ground_truth.json")
        if r["anomaly_type"] == "ANOMALY" and (feature is None or feature in r["features"])
    ]  # fmt: skip


def model_features(small, aid: str) -> dict[str, float]:
    """ENGINES 17.11: first-years over second-years, and route shares of the first-years."""
    rows = small.upload(aid)
    first = [r for r in rows if r["year_of_study"] == "1"]
    second = sum(r["year_of_study"] == "2" for r in rows)
    routes = [r["admission_route"] for r in first]
    return {
        "admission_growth": len(first) / second if second else 0.0,
        "nri_share": routes.count("NRI") / len(first),
        "management_share": (routes.count("MANAGEMENT") + routes.count("SPOT")) / len(first),
    }


def first_years(small, aid: str) -> list[dict]:
    return [r for r in small.upload(aid) if r["year_of_study"] == "1"]


def growth(small, history: dict, aid: str) -> float:
    ran = {code: n for code, n in history[aid]["programmes"].items() if n > 0}
    if not ran:
        return 0.0
    now = sum(r["programme_code"] in ran for r in first_years(small, aid))
    return now / sum(ran.values())


def share(small, aid: str) -> float:
    rows = first_years(small, aid)
    return sum(r["admission_route"] in {"NRI", "MANAGEMENT"} for r in rows) / len(rows)


def test_history_lists_last_years_admissions_per_college(small):
    history = small.json("history.json")
    assert history["academic_year"] == "2025-26" and "Synthetic" in history["note"]
    insts = small.json("institutions.json")["institutions"]
    entries = history["institutions"]
    assert [e["institution_aicte_id"] for e in entries] == [i["aicte_permanent_id"] for i in insts]
    for inst, entry in zip(insts, entries, strict=True):
        assert set(entry) == {"institution_aicte_id", "admitted", "programmes"}
        ran = [
            p["code"] for p in inst["programmes"]
            if any(a["academic_year"] == "2025-26" for a in p["approvals"])
        ]  # fmt: skip
        assert list(entry["programmes"]) == ran
        assert entry["admitted"] == sum(entry["programmes"].values())
        second = {}
        for row in small.upload(inst["aicte_permanent_id"]):
            if row["year_of_study"] == "2" and row["admission_route"] != "LATERAL":
                second[row["programme_code"]] = second.get(row["programme_code"], 0) + 1
        for code, n in entry["programmes"].items():
            # Last year's admissions cover the second-years still on the roll.
            assert n >= second.get(code, 0), (inst["aicte_permanent_id"], code)
    assert small.json("manifest.json")["counts"]["history_institutions"] == len(insts)


def test_the_spike_college_grows_far_above_its_peers(small):
    recs = anomalies(small, "admission_growth")
    assert len(recs) == CFG["admission_spike"]["small"]
    history = {e["institution_aicte_id"]: e for e in small.json("history.json")["institutions"]}
    values = {aid: growth(small, history, aid) for aid in history}
    for rec in recs:
        aid = rec["institution_aicte_id"]
        assert rec["expected_flag"] is None and rec["severity_expected"] is None
        assert rec["expected_signal"] == "ANOMALY" and rec["rows"] == []
        assert rec["features"] == ["admission_growth"]
        assert abs(rec["growth_like_for_like"] - values[aid]) < 0.01
        assert values[aid] == max(values.values())
        assert values[aid] >= 2.5 * statistics.median(values.values())
        assert rec["admitted_last_year"] == history[aid]["admitted"]
        assert rec["added_rows"] > 0
        model = model_features(small, aid)
        assert abs(rec["values"]["admission_growth"] - model["admission_growth"]) < 0.001
        assert model["admission_growth"] >= 2 * rec["peer_medians"]["admission_growth"]


def test_the_share_college_admits_far_more_nri_and_management(small):
    recs = anomalies(small, "management_share")
    assert len(recs) == CFG["nri_management_share"]["small"]
    values = {aid: share(small, aid) for aid in small.institutions()}
    for rec in recs:
        aid = rec["institution_aicte_id"]
        assert rec["expected_signal"] == "ANOMALY" and rec["rows"] == []
        assert rec["features"] == ["management_share", "nri_share"]
        assert values[aid] == max(values.values())
        assert values[aid] >= 2.5 * statistics.median(values.values())
        model = model_features(small, aid)
        for name in rec["features"]:
            assert abs(rec["values"][name] - model[name]) < 0.001
            assert model[name] >= 2 * rec["peer_medians"][name], name


def test_anomaly_colleges_carry_no_other_named_plant(small):
    gt = small.json("ground_truth.json")
    colleges = {r["institution_aicte_id"] for r in anomalies(small)}
    assert len(colleges) == len(anomalies(small))
    assert not colleges & {"1-ABC-0001", "1-XYZ-0002"}
    for rec in gt:
        if rec["anomaly_type"] in {"GHOST_RING", "EXCESS_ADMISSION", "QUOTA_BREACH",
                                   "LATE_REFILL", "CIWG_ADMISSION"}:  # fmt: skip
            assert not colleges & set(rec["institution_aicte_ids"]), rec["anomaly_type"]


def test_every_ghost_ring_is_an_expected_signal(small):
    rings = [r for r in small.json("ground_truth.json") if r["anomaly_type"] == "GHOST_RING"]
    assert rings and all(r["expected_signal"] == "GHOST_RING" for r in rings)
    assert all(r["expected_flag"] is None and r["severity_expected"] is None for r in rings)
    named = next(r for r in rings if r.get("scenario") == "ghost_ring_40")
    assert len(named["rows"]) == 40 and len(named["institution_aicte_ids"]) == 3
