"""The simulated state admission authority: one joining verified, one college's joinings listed."""

from httpx import AsyncClient

RAVI = {
    "state": "MH",
    "academic_year": "2026-27",
    "name": "Ravi Kumar Sharma",
    "dob": "2007-03-21",
    "institution_code": "1-ABC-0001",
    "programme": "CSE",
}


async def joining(client: AsyncClient, **overrides) -> dict:
    response = await client.post("/admission-authority/joining", json={**RAVI, **overrides})
    assert response.status_code == 200, response.text
    return response.json()


async def test_found_by_name_and_dob(client: AsyncClient, seeded: dict) -> None:
    assert await joining(client) == {
        "found": True,
        "joined_on": "2026-07-24",
        "round": 1,
        "route": "COUNSELLING",
        "category": "GENERAL",
        "roll_no": "MHCET-2026-004512",
    }


async def test_never_returns_the_stored_name(client: AsyncClient, seeded: dict) -> None:
    body = await joining(client, name="Ravi K Sharma")
    assert body["found"] is True
    assert "name" not in body and "Ravi" not in str(body)


async def test_found_by_roll_number_even_with_another_spelling(
    client: AsyncClient, seeded: dict
) -> None:
    body = await joining(client, name="R. K. Sharma", roll_no=" MHCET-2026-004512 ")
    assert body["found"] is True and body["roll_no"] == "MHCET-2026-004512"


async def test_management_admission_has_no_round(client: AsyncClient, seeded: dict) -> None:
    body = await joining(client, name="Mohd Irfan Khan", dob="2006-11-02")
    assert body == {
        "found": True,
        "joined_on": "2026-08-03",
        "round": None,
        "route": "MANAGEMENT",
        "category": "OBC",
        "roll_no": "MHAA-2026-000001",
    }


async def test_not_found_answers(client: AsyncClient, seeded: dict) -> None:
    not_found = {
        "found": False,
        "joined_on": None,
        "round": None,
        "route": None,
        "category": None,
        "roll_no": None,
    }
    assert await joining(client, name="Someone Else Entirely") == not_found
    assert await joining(client, dob="2007-03-22") == not_found
    assert await joining(client, academic_year="2025-26") == not_found
    assert await joining(client, state="TN") == not_found
    assert await joining(client, programme="IT") == not_found
    assert await joining(client, institution_code="1-XYZ-0002") == not_found
    assert await joining(client, roll_no="MHCET-2026-999999") == not_found


async def test_state_is_case_insensitive(client: AsyncClient, seeded: dict) -> None:
    assert (await joining(client, state="mh"))["found"] is True


async def test_validation(client: AsyncClient) -> None:
    response = await client.post(
        "/admission-authority/joining", json={**RAVI, "academic_year": "2026", "state": "MAH"}
    )
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"academic_year", "state"}


async def test_joinings_list_names_every_joining(client: AsyncClient, seeded: dict) -> None:
    response = await client.get(
        "/admission-authority/joinings",
        params={"institution_code": "1-ABC-0001", "academic_year": "2026-27"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "roll_no": "MHAA-2026-000001",
                "name": "Mohammed Irfan Khan",
                "joined_on": "2026-08-03",
                "programme": "CSE",
                "route": "MANAGEMENT",
            },
            {
                "roll_no": "MHCET-2026-004512",
                "name": "Ravi Kumar Sharma",
                "joined_on": "2026-07-24",
                "programme": "CSE",
                "route": "COUNSELLING",
            },
            {
                "roll_no": "MHAA-2026-000002",
                "name": "Sneha Patil",
                "joined_on": "2026-10-04",
                "programme": "IT",
                "route": "NRI",
            },
        ],
        "total": 3,
    }


async def test_joinings_list_is_per_college_and_year(client: AsyncClient, seeded: dict) -> None:
    older = await client.get(
        "/admission-authority/joinings",
        params={"institution_code": "1-ABC-0001", "academic_year": "2025-26"},
    )
    assert [i["roll_no"] for i in older.json()["items"]] == ["MHCET-2025-000310"]
    none = await client.get(
        "/admission-authority/joinings",
        params={"institution_code": "1-NOPE-0000", "academic_year": "2026-27"},
    )
    assert none.json() == {"items": [], "total": 0}


async def test_joinings_list_needs_both_parameters(client: AsyncClient) -> None:
    response = await client.get("/admission-authority/joinings", params={"academic_year": "x"})
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"institution_code", "academic_year"}


async def test_openapi_says_it_is_simulated(client: AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    assert "simulated" in spec["info"]["description"]
    post = spec["paths"]["/admission-authority/joining"]["post"]
    assert post["description"] == (
        "One state's joining-record format, simulated, served for every state."
    )
