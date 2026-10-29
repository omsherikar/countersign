from app.models.enums import FlagType


async def test_national_summary(admin):
    body = (await admin.get("/dashboard/summary")).json()
    assert body["academic_year"] == "2026-27"
    assert body["scope"] == {"kind": "NATIONAL", "label": "All India"}
    kpis = body["kpis"]
    assert {k: kpis[k] for k in ("institutions", "programmes", "approved_seats")} == {
        "institutions": 3,
        "programmes": 5,
        "approved_seats": 310,
    }
    assert (kpis["admitted"], kpis["enrolments"]) == (38, 41)
    # the seed runs the engines: Lokesh's malformed APAAR, Ananya at two colleges (one
    # flag each side) and two refills after the cut-off at PQR
    assert kpis["flags_open"] == 5
    # every active record has one status (D35); the share is the COUNTERSIGNED one
    records = kpis["records"]
    assert list(records) == ["AWAITING_EVIDENCE", "COUNTERSIGNED", "UNDER_REVIEW", "DISPUTED"]
    assert sum(records.values()) == kpis["enrolments"]
    assert kpis["countersigned_pct"] == round(100 * records["COUNTERSIGNED"] / 41, 1)
    assert "clear_pct" not in kpis
    assert [r["status"] for r in body["records_by_status"]] == [
        "COUNTERSIGNED",
        "AWAITING_EVIDENCE",
        "UNDER_REVIEW",
        "DISPUTED",
    ]
    assert {r["status"]: r["count"] for r in body["records_by_status"]} == records
    # no reconciliation has run on the mini seed; its files arrived after the 30 Sep deadline
    assert (kpis["joined"], kpis["missing_from_upload"], kpis["completeness_pct"]) == (0, 0, None)
    assert (kpis["colleges_late"], kpis["colleges_overdue"], kpis["signals_new"]) == (3, 0, 0)
    assert [b["bucket"] for b in body["cases_by_age"]] == [
        "UNDER_7_DAYS",
        "DAYS_7_TO_30",
        "OVER_30_DAYS",
    ]
    assert sum(b["open"] for b in body["cases_by_age"]) == 5
    top = body["top_institutions"]
    assert [t["institution"]["aicte_permanent_id"] for t in top] == [
        "1-PQR-0003",
        "1-ABC-0001",
        "1-XYZ-0002",
    ]
    assert top[0]["flags_open"] == 3 and body["completeness"] is None
    assert [f["type"] for f in body["flags_by_type"]][:3] == [
        "EXCESS_ADMISSION",
        "QUOTA_BREACH",
        "LATE_REFILL",
    ]
    assert len(body["flags_by_type"]) == len(FlagType)
    open_by_type = {f["type"]: f["open"] for f in body["flags_by_type"]}
    assert {t: n for t, n in open_by_type.items() if n} == {
        "LATE_REFILL": 2,
        "INVALID_APAAR": 1,
        "DUPLICATE_CROSS_INSTITUTION": 2,
    }
    assert [s["state_name"] for s in body["by_state"]] == ["Karnataka", "Maharashtra", "Tamil Nadu"]
    mh = body["by_state"][1]
    mh_records = mh.pop("records")
    assert sum(mh_records.values()) == 20
    assert mh.pop("countersigned_pct") == round(100 * mh_records["COUNTERSIGNED"] / 20, 1)
    assert mh == {
        "state_code": "MH",
        "state_name": "Maharashtra",
        "region": "WEST",
        "institutions": 1,
        "programmes": 2,
        "approved_seats": 180,
        "admitted": 19,
        "enrolments": 20,
        "flags_open": 1,
        "completeness_pct": None,
        "missing_from_upload": 0,
    }
    west = next(r for r in body["by_region"] if r["region"] == "WEST")
    assert west.pop("records") == mh_records
    west.pop("countersigned_pct")
    assert west == {
        "region": "WEST",
        "region_name": "Western (Mumbai)",
        "institutions": 1,
        "approved_seats": 180,
        "admitted": 19,
        "enrolments": 20,
        "flags_open": 1,
        "completeness_pct": None,
        "missing_from_upload": 0,
    }
    other_year = (await admin.get("/dashboard/summary", params={"academic_year": "2025-26"})).json()
    # 2025-26 approvals exist for the lateral entrants' cohort; nobody is on that year's roll
    assert other_year["kpis"]["enrolments"] == 0 and other_year["kpis"]["approved_seats"] == 220
    assert other_year["kpis"]["institutions"] == 3


async def test_scoped_summaries(ro_west, registrar_abc, university, student):
    west = (await ro_west.get("/dashboard/summary")).json()
    assert west["scope"] == {"kind": "REGION", "label": "Western Region"}
    assert west["kpis"]["institutions"] == 1 and west["kpis"]["enrolments"] == 20
    assert [s["state_code"] for s in west["by_state"]] == ["MH"]
    assert [r["region"] for r in west["by_region"]] == ["WEST"]

    assert west["kpis"]["signals_new"] == 0

    college = (await registrar_abc.get("/dashboard/summary")).json()
    assert college["scope"] == {"kind": "INSTITUTION", "label": "ABC College of Engineering"}
    assert college["kpis"]["programmes"] == 2 and len(college["by_state"]) == 1
    # a college never sees signals or other colleges; it gets its own completeness
    assert college["kpis"]["signals_new"] is None and college["top_institutions"] == []
    own = college["completeness"]
    assert (own["deadline"], own["deadline_state"], own["missing_students"]) == (
        "2026-09-30",
        "LATE",
        [],
    )
    assert "institution" not in own

    uni = (await university.get("/dashboard/summary")).json()
    assert uni["scope"] == {"kind": "UNIVERSITY", "label": "Maharashtra State Technical University"}
    assert uni["kpis"]["institutions"] == 1

    response = await student.get("/dashboard/summary")
    assert response.status_code == 403
    assert response.json()["error"]["details"]["required_roles"] == [
        "AICTE_ADMIN",
        "RO_OFFICER",
        "INSTITUTION",
        "UNIVERSITY",
    ]
