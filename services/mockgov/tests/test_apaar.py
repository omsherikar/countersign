from httpx import AsyncClient

RAVI = {"apaar_id": "123456784417", "name": "Ravi Kumar Sharma", "dob": "2007-03-21"}


async def test_exact_match(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/apaar/verify", json=RAVI)
    assert response.status_code == 200
    assert response.json() == {"exists": True, "name_score": 100, "dob_match": True}


async def test_wrong_dob(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/apaar/verify", json={**RAVI, "dob": "2007-03-22"})
    assert response.json() == {"exists": True, "name_score": 100, "dob_match": False}


async def test_initials_score_partially(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/apaar/verify", json={**RAVI, "name": "R. K. Sharma"})
    body = response.json()
    assert body["exists"] is True
    assert body["dob_match"] is True
    assert 0 < body["name_score"] < 90


async def test_honorific_and_case_do_not_matter(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/apaar/verify", json={**RAVI, "name": "MR. ravi kumar SHARMA"})
    assert response.json()["name_score"] == 100


async def test_mohammed_spelling_variants_match(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/apaar/verify",
        json={"apaar_id": "123456780002", "name": "Mohammad Irfan Khan", "dob": "2006-11-02"},
    )
    assert response.json() == {"exists": True, "name_score": 100, "dob_match": True}


async def test_unknown_id_scores_zero(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/apaar/verify", json={**RAVI, "apaar_id": "000000000000"})
    assert response.status_code == 200
    assert response.json() == {"exists": False, "name_score": 0, "dob_match": False}


async def test_stored_name_never_leaves(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/apaar/verify", json={**RAVI, "name": "Someone Else"})
    assert "Ravi" not in response.text
    assert set(response.json()) == {"exists", "name_score", "dob_match"}


async def test_apaar_id_must_be_12_digits(client: AsyncClient) -> None:
    for bad in ("1234", "12345678901234", "12345678abcd"):
        response = await client.post("/apaar/verify", json={**RAVI, "apaar_id": bad})
        assert response.status_code == 422
        assert response.json()["error"]["message"] == "apaar_id must be 12 digits."


async def test_dob_must_be_a_date(client: AsyncClient) -> None:
    response = await client.post("/apaar/verify", json={**RAVI, "dob": "21-03-2007"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
