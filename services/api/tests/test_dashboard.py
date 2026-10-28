async def test_national_summary(admin):
    body = (await admin.get("/dashboard/summary")).json()
    assert body["academic_year"] == "2026-27"
    assert body["scope"] == {"kind": "NATIONAL", "label": "All India"}
    assert body["kpis"] == {
        "institutions": 3,
        "programmes": 5,
        "approved_seats": 310,
        "enrolments": 41,
        "flags_open": 0,
        "countersigned_pct": None,
    }
    assert [s["state_name"] for s in body["by_state"]] == ["Karnataka", "Maharashtra", "Tamil Nadu"]
    mh = body["by_state"][1]
    assert mh == {
        "state_code": "MH",
        "state_name": "Maharashtra",
        "region": "WEST",
        "institutions": 1,
        "programmes": 2,
        "approved_seats": 180,
        "enrolments": 20,
        "flags_open": 0,
    }
    west = next(r for r in body["by_region"] if r["region"] == "WEST")
    assert west == {
        "region": "WEST",
        "region_name": "Western (Mumbai)",
        "institutions": 1,
        "approved_seats": 180,
        "enrolments": 20,
        "flags_open": 0,
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

    college = (await registrar_abc.get("/dashboard/summary")).json()
    assert college["scope"] == {"kind": "INSTITUTION", "label": "ABC College of Engineering"}
    assert college["kpis"]["programmes"] == 2 and len(college["by_state"]) == 1

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
