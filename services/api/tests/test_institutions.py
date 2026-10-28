from tests.conftest import institution_id, login_as

FORBIDDEN = {
    "code": "FORBIDDEN",
    "message": "Your role cannot access this resource.",
    "details": {"required_roles": ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]},
}
NOT_FOUND = {"error": {"code": "NOT_FOUND", "message": "Institution not found.", "details": {}}}


async def test_list_is_scoped_per_role(
    admin, ro_west, ro_south, registrar_abc, university, student
):
    body = (await admin.get("/institutions")).json()
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 25
    assert {i["aicte_permanent_id"] for i in body["items"]} == {
        "1-ABC-0001",
        "1-XYZ-0002",
        "1-PQR-0003",
    }
    row = next(i for i in body["items"] if i["aicte_permanent_id"] == "1-ABC-0001")
    assert row["name"] == "ABC College of Engineering"
    assert row["type"] == "PRIVATE_SELF_FINANCED"
    assert (row["state_code"], row["state_name"], row["region"]) == ("MH", "Maharashtra", "WEST")
    assert row["region_name"] == "Western (Mumbai)"
    assert row["university_name"] == "Maharashtra State Technical University"
    assert (row["programmes"], row["approved_seats"], row["enrolments"]) == (2, 180, 20)
    assert (row["flags_open"], row["integrity_index"]) == (1, None)  # Ananya's ABC side

    west = (await ro_west.get("/institutions")).json()
    assert [i["aicte_permanent_id"] for i in west["items"]] == ["1-ABC-0001"]
    # region query is ignored for RO officers
    west_again = (await ro_west.get("/institutions", params={"region": "SOUTH"})).json()
    assert west_again["total"] == 1 and west_again["items"][0]["region"] == "WEST"

    south = (await ro_south.get("/institutions")).json()
    assert [i["aicte_permanent_id"] for i in south["items"]] == ["1-XYZ-0002"]

    own = (await registrar_abc.get("/institutions")).json()
    assert own["total"] == 1 and own["items"][0]["aicte_permanent_id"] == "1-ABC-0001"

    affiliates = (await university.get("/institutions")).json()
    assert [i["aicte_permanent_id"] for i in affiliates["items"]] == ["1-ABC-0001"]

    response = await student.get("/institutions")
    assert response.status_code == 403
    assert response.json()["error"] == FORBIDDEN


async def test_list_filters_sort_and_pagination(admin):
    by_name = (await admin.get("/institutions", params={"sort": "name_asc"})).json()
    assert [i["name"] for i in by_name["items"]] == [
        "ABC College of Engineering",
        "PQR Polytechnic",
        "XYZ Institute of Technology",
    ]
    default = (await admin.get("/institutions")).json()  # most open flags first
    assert [(i["flags_open"], i["enrolments"]) for i in default["items"]] == [
        (3, 9),
        (1, 20),
        (1, 12),
    ]
    by_seats = (
        await admin.get("/institutions", params={"sort": "approved_seats", "order": "asc"})
    ).json()
    assert [i["approved_seats"] for i in by_seats["items"]] == [40, 90, 180]

    assert (await admin.get("/institutions", params={"state": "tn"})).json()["total"] == 1
    assert (await admin.get("/institutions", params={"region": "SOUTH_WEST"})).json()["total"] == 1
    assert (await admin.get("/institutions", params={"type": "GOVERNMENT"})).json()["total"] == 1
    assert (await admin.get("/institutions", params={"q": "xyz"})).json()["total"] == 1
    assert (await admin.get("/institutions", params={"q": "1-pqr"})).json()["total"] == 1

    page2 = (
        await admin.get("/institutions", params={"page": 2, "page_size": 2, "sort": "name_asc"})
    ).json()
    assert page2["total"] == 3 and page2["page"] == 2 and page2["page_size"] == 2
    assert [i["name"] for i in page2["items"]] == ["XYZ Institute of Technology"]
    assert (await admin.get("/institutions", params={"page_size": 500})).status_code == 422
    assert (await admin.get("/institutions", params={"type": "BOGUS"})).status_code == 422


async def test_detail_scope_and_shape(
    admin, ro_west, ro_south, registrar_abc, registrar_xyz, university, student
):
    abc = await institution_id("1-ABC-0001")
    xyz = await institution_id("1-XYZ-0002")

    detail = (await admin.get(f"/institutions/{abc}")).json()
    assert detail["aicte_permanent_id"] == "1-ABC-0001"
    assert detail["address_city"] == "Pune" and detail["established_year"] == 2004
    assert detail["region_name"] == "Western (Mumbai)"
    assert detail["integrity_index"] is None and detail["integrity_components"] is None
    assert detail["flags_open"] == 1
    last = detail["last_upload"]  # the seeded file is the college's latest upload (A2.20)
    assert (last["rows"], last["errors"], last["status"]) == (20, 0, "DONE")
    assert detail["admitted"] == 19 and detail["enrolments"] == 20
    assert [p["code"] for p in detail["programmes"]] == ["CSE", "MBA"]
    cse = detail["programmes"][0]
    assert cse["name"] == "B.Tech Computer Science and Engineering"
    assert (cse["level"], cse["discipline"], cse["shift"]) == ("UG", "ENGINEERING", "FIRST")
    assert cse["approval"] == {
        "academic_year": "2026-27",
        "approved_intake": 120,
        "cutoff_date": "2026-09-15",
    }
    # 15 first-years; the year-2 lateral entrant belongs to the 2025-26 batch
    assert cse["enrolments"] == 15 and cse["unseated"] == 0
    pools = {p["seat_type"]: p for p in cse["pools"]}
    assert [p["seat_type"] for p in cse["pools"]] == [
        "REGULAR",
        "NRI",
        "TFW",
        "LATERAL",
        "INTERNATIONAL",
    ]
    assert {k: v["capacity"] for k, v in pools.items()} == {
        "REGULAR": 114,
        "NRI": 6,
        "TFW": 6,
        "LATERAL": 12,
        "INTERNATIONAL": 18,
    }
    assert {k: v["assigned"] for k, v in pools.items()} == {
        "REGULAR": 12,
        "NRI": 1,
        "TFW": 1,
        "LATERAL": 0,
        "INTERNATIONAL": 1,
    }
    assert all(p["assigned"] + p["free"] == p["capacity"] for p in cse["pools"])
    assert pools["INTERNATIONAL"]["reserved_for"] == "FN_OCI_PIO_CIWG"
    assert pools["REGULAR"]["reserved_for"] is None
    assert "6.42" in pools["TFW"]["rule_source"]
    assert pools["TFW"]["is_supernumerary"] is True and pools["NRI"]["is_supernumerary"] is False
    mba = detail["programmes"][1]
    assert {p["seat_type"]: p["capacity"] for p in mba["pools"]}["INTERNATIONAL"] == 15

    assert (await registrar_abc.get(f"/institutions/{abc}")).status_code == 200
    assert (await ro_west.get(f"/institutions/{abc}")).status_code == 200
    assert (await university.get(f"/institutions/{abc}")).status_code == 200
    for other in (registrar_abc, ro_west, university):
        response = await other.get(f"/institutions/{xyz}")
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    assert (await registrar_xyz.get(f"/institutions/{xyz}")).status_code == 200
    assert (await ro_south.get(f"/institutions/{xyz}")).status_code == 200
    assert (await student.get(f"/institutions/{abc}")).status_code == 403
    assert (
        await admin.get("/institutions/00000000-0000-4000-8000-000000000000")
    ).json() == NOT_FOUND
    assert (await admin.get("/institutions/not-a-uuid")).status_code == 422


async def test_seats(admin, registrar_abc, registrar_xyz):
    abc = await institution_id("1-ABC-0001")
    body = (await registrar_abc.get(f"/institutions/{abc}/seats")).json()
    assert body["total"] == 156 + 84
    first = body["items"][0]
    assert first["seat_code"] == "CSE-I-001"
    assert first["academic_year"] == "2026-27"
    assert first["programme_code"] == "CSE"
    assert first["seat_type"] == "INTERNATIONAL"
    assert first["status"] == "FREE" and first["reserved_for"] == "CIWG"
    assert (
        first["enrolment_id"] is None
        and first["student_name"] is None
        and first["assigned_at"] is None
    )
    assert (
        await admin.get(
            f"/institutions/{abc}/seats", params={"seat_type": "REGULAR", "page_size": 200}
        )
    ).json()["total"] == 114 + 57
    assert (await admin.get(f"/institutions/{abc}/seats", params={"q": "CSE-I"})).json()[
        "total"
    ] == 18
    # the seed's ledger seated all 19 ABC enrolments of the 2026-27 cohort
    assert (await admin.get(f"/institutions/{abc}/seats", params={"status": "ASSIGNED"})).json()[
        "total"
    ] == 19
    ciwg = (
        await admin.get(f"/institutions/{abc}/seats", params={"q": "CSE-I", "page_size": 50})
    ).json()
    assert sum(1 for s in ciwg["items"] if s["reserved_for"] == "CIWG") == 6
    detail = (await admin.get(f"/institutions/{abc}")).json()
    cse_id = detail["programmes"][0]["id"]
    assert (await admin.get(f"/institutions/{abc}/seats", params={"programme_id": cse_id})).json()[
        "total"
    ] == 156
    assert (await registrar_xyz.get(f"/institutions/{abc}/seats")).json() == NOT_FOUND


async def test_seats_are_per_approval_year(three_cohorts):
    registrar = await login_as("registrar@abc.edu.demo")
    try:
        abc = await institution_id("1-ABC-0001")
        totals = {}
        for params in ({}, {"academic_year": "2025-26"}, {"academic_year": "2024-25"}):
            year = params.get("academic_year", "2026-27")
            detail = (await registrar.get(f"/institutions/{abc}", params=params)).json()
            capacity = sum(p["capacity"] for p in detail["programmes"][0]["pools"])
            seats = (
                await registrar.get(
                    f"/institutions/{abc}/seats", params={**params, "page_size": 200}
                )
            ).json()
            assert seats["total"] == capacity == len(seats["items"])
            codes = [s["seat_code"] for s in seats["items"]]
            assert len(codes) == len(set(codes))
            assert {s["academic_year"] for s in seats["items"]} == {year}
            totals[year] = seats["total"]
        # 120 approved for 2026-27: 114 regular + 6 NRI + 6 TFW + 12 lateral + 18 international
        assert totals["2026-27"] == 156
        assert totals["2026-27"] > totals["2025-26"] > totals["2024-25"]
        response = await registrar.get(
            f"/institutions/{abc}/seats", params={"academic_year": "2026"}
        )
        assert response.status_code == 422
    finally:
        await registrar.aclose()


async def test_enrolments(admin, registrar_abc, registrar_xyz, student):
    abc = await institution_id("1-ABC-0001")
    roll = {"academic_year": "2026-27"}  # the fixture also holds 2025-26 graduates (D28)
    body = (
        await registrar_abc.get(f"/institutions/{abc}/enrolments", params={"page_size": 50, **roll})
    ).json()
    assert body["total"] == 20
    names = [e["student"]["name"] for e in body["items"]]
    assert names == sorted(names)
    ravi = next(e for e in body["items"] if e["student"]["name"] == "Ravi Kumar Sharma")
    assert ravi["student"]["apaar_masked"] == "XXXX XXXX 4417"
    assert ravi["student"]["consent_status"] == "LINKED"
    assert ravi["student"]["provisional_id"] is None
    assert ravi["student"]["nationality"] == "IN"
    assert ravi["programme_code"] == "CSE" and ravi["academic_year"] == "2026-27"
    assert ravi["year_of_study"] == 1 and ravi["admission_route"] == "COUNSELLING"
    assert ravi["counselling_ref"] == "MHCET-2026-R1-004512" and ravi["category"] == "GENERAL"
    assert ravi["seat_code"].startswith("CSE-R-") and ravi["status"] == "ACTIVE"
    assert ravi["uploaded_at"].endswith("Z")
    assert ravi["countersign"]["score"] == {"passes": 3, "applicable": 4}
    assert [c["status"] for c in ravi["countersign"]["checks"]] == [
        "CONFIRMED",
        "CONFIRMED",
        "CONFIRMED",
        "NOT_APPLICABLE",
        "PENDING",
    ]
    assert ravi["flags"] == []
    assert ravi["upload_batch_id"] is not None and ravi["source_row_no"] == 2
    assert "email" not in ravi["student"] and "apaar_id" not in ravi["student"]

    refused = next(e for e in body["items"] if e["student"]["name"] == "Suresh Pawar")
    assert refused["student"]["apaar_masked"] is None
    assert refused["student"]["consent_status"] == "REFUSED"
    assert (
        refused["student"]["provisional_id"].startswith("PRV-")
        and len(refused["student"]["provisional_id"]) == 12
    )
    intl = next(e for e in body["items"] if e["student"]["name"] == "Aisha Rahman")
    assert (
        intl["student"]["nationality"] == "BD"
        and intl["student"]["consent_status"] == "INTERNATIONAL"
    )

    params = {"q": "4417"}
    assert (await admin.get(f"/institutions/{abc}/enrolments", params=params)).json()["total"] == 1
    assert (await admin.get(f"/institutions/{abc}/enrolments", params={"q": "sharma"})).json()[
        "total"
    ] == 1
    assert (await admin.get(f"/institutions/{abc}/enrolments", params={"year_of_study": 2})).json()[
        "total"
    ] == 1
    assert (
        await admin.get(f"/institutions/{abc}/enrolments", params={"admission_route": "MANAGEMENT"})
    ).json()["total"] == 5
    assert (
        await admin.get(f"/institutions/{abc}/enrolments", params={"academic_year": "2025-26"})
    ).json()["total"] == 3  # the graduates, all GRADUATED
    assert (
        await admin.get(f"/institutions/{abc}/enrolments", params={"status": "WITHDRAWN"})
    ).json()["total"] == 0
    mba_id = (await admin.get(f"/institutions/{abc}")).json()["programmes"][1]["id"]
    assert (
        await admin.get(f"/institutions/{abc}/enrolments", params={"programme_id": mba_id})
    ).json()["total"] == 4

    by_year = (
        await admin.get(f"/institutions/{abc}/enrolments", params={"sort": "year_desc", **roll})
    ).json()
    assert by_year["items"][0]["year_of_study"] == 2
    by_route = (
        await admin.get(
            f"/institutions/{abc}/enrolments", params={"sort": "route_asc", "page_size": 50}
        )
    ).json()
    routes = [e["admission_route"] for e in by_route["items"]]
    assert routes == sorted(routes)

    assert (await registrar_xyz.get(f"/institutions/{abc}/enrolments")).json() == NOT_FOUND
    assert (await student.get(f"/institutions/{abc}/enrolments")).status_code == 403


async def test_student_reads_are_audited(admin):
    abc = await institution_id("1-ABC-0001")
    before = (await admin.get("/admin/audit", params={"entity_type": "student"})).json()["total"]
    await admin.get(f"/institutions/{abc}/enrolments", params={"page_size": 5})
    after = (await admin.get("/admin/audit", params={"entity_type": "student"})).json()
    assert after["total"] == before + 5
    assert after["items"][0]["action"] == "READ"
    assert after["items"][0]["actor_email"] == "admin@aicte.demo"
