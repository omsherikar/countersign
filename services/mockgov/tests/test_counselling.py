from httpx import AsyncClient

RAVI = {
    "state": "MH",
    "year": 2026,
    "name": "Ravi Kumar Sharma",
    "dob": "2007-03-21",
    "roll_no": "MHCET-2026-004512",
    "programme": "CSE",
    "institution_aicte_id": "1-ABC-0001",
}
NOT_FOUND = {"found": False, "round": None, "category": None, "allotment_ref": None}


async def test_roll_no_match(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/counselling/verify", json=RAVI)
    assert response.status_code == 200
    assert response.json() == {
        "found": True,
        "round": 1,
        "category": "GENERAL",
        "allotment_ref": "MHCET-2026-R1-004512",
    }


async def test_roll_no_is_exact_even_when_name_differs(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/counselling/verify", json={**RAVI, "name": "R. K. Sharma"})
    assert response.json()["found"] is True


async def test_unknown_roll_no(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/counselling/verify", json={**RAVI, "roll_no": "MHCET-2026-9"})
    assert response.json() == NOT_FOUND


async def test_roll_no_for_another_institution(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/counselling/verify", json={**RAVI, "institution_aicte_id": "1-XYZ-0002"}
    )
    assert response.json() == NOT_FOUND


async def test_roll_no_for_another_programme(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/counselling/verify", json={**RAVI, "programme": "ME"})
    assert response.json() == NOT_FOUND


async def test_fuzzy_match_without_roll_no(client: AsyncClient, seeded: dict) -> None:
    body = {k: v for k, v in RAVI.items() if k not in ("roll_no", "institution_aicte_id")}
    response = await client.post("/counselling/verify", json={**body, "name": "Sharma Ravi Kumar"})
    assert response.json()["found"] is True
    assert response.json()["allotment_ref"] == "MHCET-2026-R1-004512"


async def test_fuzzy_match_needs_score_90(client: AsyncClient, seeded: dict) -> None:
    body = {k: v for k, v in RAVI.items() if k != "roll_no"}
    response = await client.post("/counselling/verify", json={**body, "name": "R. K. Sharma"})
    assert response.json() == NOT_FOUND


async def test_fuzzy_match_needs_same_dob(client: AsyncClient, seeded: dict) -> None:
    body = {k: v for k, v in RAVI.items() if k != "roll_no"}
    response = await client.post("/counselling/verify", json={**body, "dob": "2007-03-22"})
    assert response.json() == NOT_FOUND


async def test_fuzzy_match_folds_mohammed_variants(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/counselling/verify",
        json={
            "state": "mh",
            "year": 2026,
            "name": "Mohd Irfan Khan",
            "dob": "2006-11-02",
            "programme": "ME",
        },
    )
    assert response.json() == {
        "found": True,
        "round": 2,
        "category": "OBC",
        "allotment_ref": "MHCET-2026-R2-004513",
    }


async def test_other_state_or_year(client: AsyncClient, seeded: dict) -> None:
    other_state = await client.post("/counselling/verify", json={**RAVI, "state": "TN"})
    other_year = await client.post("/counselling/verify", json={**RAVI, "year": 2025})
    assert other_state.json() == NOT_FOUND
    assert other_year.json() == NOT_FOUND


async def test_validation(client: AsyncClient) -> None:
    response = await client.post("/counselling/verify", json={"state": "MH"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
