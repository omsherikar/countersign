from httpx import AsyncClient

AISHA = {"passport_no": "N1234567", "name": "Aisha Rahman", "nationality": "BD"}
NOT_ADMITTED = {
    "admitted": False,
    "institution_aicte_id": None,
    "programme": None,
    "academic_year": None,
}


async def test_admitted(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/sii/verify", json=AISHA)
    assert response.status_code == 200
    assert response.json() == {
        "admitted": True,
        "institution_aicte_id": "1-ABC-0001",
        "programme": "CSE",
        "academic_year": "2026-27",
    }


async def test_passport_and_nationality_are_case_insensitive(
    client: AsyncClient, seeded: dict
) -> None:
    response = await client.post(
        "/sii/verify", json={**AISHA, "passport_no": "n1234567", "nationality": "bd"}
    )
    assert response.json()["admitted"] is True


async def test_unknown_passport(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/sii/verify", json={**AISHA, "passport_no": "Z0000000"})
    assert response.json() == NOT_ADMITTED


async def test_wrong_nationality(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/sii/verify", json={**AISHA, "nationality": "NP"})
    assert response.json() == NOT_ADMITTED


async def test_name_mismatch(client: AsyncClient, seeded: dict) -> None:
    response = await client.post("/sii/verify", json={**AISHA, "name": "Someone Else"})
    assert response.json() == NOT_ADMITTED
    assert "Aisha" not in response.text


async def test_validation(client: AsyncClient) -> None:
    response = await client.post("/sii/verify", json={"passport_no": "N1234567"})
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"name", "nationality"}
