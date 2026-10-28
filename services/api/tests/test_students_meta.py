async def test_students_me(student, admin, registrar_abc):
    body = (await student.get("/students/me")).json()
    assert body["name"] == "Ravi Kumar Sharma"
    assert body["apaar_masked"] == "XXXX XXXX 4417"
    assert body["consent_status"] == "LINKED" and body["provisional_id"] is None
    assert body["dob"] == "2007-03-21"
    assert body["email"] == "ravi.sharma@example.demo"
    assert body["mobile_masked"] == "XXXXXX4521"
    assert body["notices"] == [] and body["credentials"] == []
    assert len(body["enrolments"]) == 1
    enrolment = body["enrolments"][0]
    assert enrolment["institution_name"] == "ABC College of Engineering"
    assert enrolment["programme_code"] == "CSE"
    assert enrolment["programme_name"] == "B.Tech Computer Science and Engineering"
    assert enrolment["academic_year"] == "2026-27" and enrolment["year_of_study"] == 1
    assert enrolment["status"] == "ACTIVE"
    assert enrolment["countersign"] == {"score": None, "checks": []}
    assert "apaar_id" not in body and "mobile" not in body

    for other in (admin, registrar_abc):
        response = await other.get("/students/me")
        assert response.status_code == 403
        assert response.json()["error"]["details"] == {"required_roles": ["STUDENT"]}

    audit = (await admin.get("/admin/audit", params={"entity_type": "student"})).json()
    assert audit["items"][0]["action"] == "READ"
    assert audit["items"][0]["entity_id"] == body["id"]
    assert audit["items"][0]["actor_email"] == "student@demo"


async def test_meta_for_every_role(student, admin, client):
    regions = (await student.get("/meta/regions")).json()["items"]
    assert {"code": "WEST", "name": "Western", "hq_city": "Mumbai"} in regions
    assert [r["name"] for r in regions] == sorted(r["name"] for r in regions)
    states = (await admin.get("/meta/states")).json()["items"]
    assert {"code": "MH", "name": "Maharashtra", "region": "WEST"} in states
    assert (await client.get("/meta/regions")).status_code == 401
