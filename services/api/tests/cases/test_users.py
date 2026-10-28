"""GET /users, the assignee picker: officers only, scoped by region, never a contact detail."""

from __future__ import annotations

from tests.cases.conftest import new_flag


async def test_aicte_sees_every_active_officer_in_order(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    body = (await admin.get("/users", params={"role": "RO_OFFICER,AICTE_ADMIN"})).json()
    assert [(i["name"], i["role"], i["region"]) for i in body["items"]] == [
        ("AICTE Administrator", "AICTE_ADMIN", None),
        ("Senior AICTE Officer", "AICTE_ADMIN", None),
        ("Deputy Officer, Western", "RO_OFFICER", "WEST"),
        ("Regional Officer, Southern", "RO_OFFICER", "SOUTH"),
        ("Regional Officer, Western", "RO_OFFICER", "WEST"),
    ]
    assert body["total"] == 5 and body["page"] == 1 and body["page_size"] == 25
    assert set(body["items"][0]) == {"id", "name", "role", "region"}
    assert "@" not in str(body)
    only_ro = (await admin.get("/users", params={"role": "RO_OFFICER"})).json()
    assert {i["role"] for i in only_ro["items"]} == {"RO_OFFICER"}
    paged = (await admin.get("/users", params={"role": "AICTE_ADMIN", "page_size": 1})).json()
    assert paged["total"] == 2 and len(paged["items"]) == 1


async def test_a_regional_officer_sees_aicte_and_its_own_region(cw, logins) -> None:
    west = await logins("ro.west@aicte.demo")
    body = (await west.get("/users", params={"role": "AICTE_ADMIN,RO_OFFICER"})).json()
    assert [i["name"] for i in body["items"]] == [
        "AICTE Administrator",
        "Senior AICTE Officer",
        "Deputy Officer, Western",
        "Regional Officer, Western",
    ]


async def test_a_flag_narrows_the_list_to_who_may_take_it(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    south = await logins("ro.south@aicte.demo")
    abc_flag = await new_flag(cw)
    body = (
        await admin.get("/users", params={"role": "RO_OFFICER,AICTE_ADMIN", "flag_id": abc_flag})
    ).json()
    assert "Regional Officer, Southern" not in [i["name"] for i in body["items"]]
    assert body["total"] == 4
    outside = await south.get("/users", params={"role": "RO_OFFICER", "flag_id": abc_flag})
    assert outside.status_code == 404


async def test_roles_and_query_are_checked(cw, logins) -> None:
    admin = await logins("admin@aicte.demo")
    for bad in ("INSTITUTION", "RO_OFFICER,STUDENT", ""):
        response = await admin.get("/users", params={"role": bad})
        assert response.status_code == 422, bad
    assert (await admin.get("/users")).status_code == 422
    for email in ("registrar@abc.edu.demo", "coe@univ.demo", "student@demo"):
        response = await (await logins(email)).get("/users", params={"role": "AICTE_ADMIN"})
        assert response.status_code == 403, email
