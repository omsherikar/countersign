from httpx import AsyncClient


async def test_credits_for_a_year(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456780003", "academic_year": "2025-26"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "apaar_id_known": True,
        "semesters": [
            {"sem": 1, "credits": 22, "uploaded_at": "2026-01-20T00:00:00Z", "result": "PASS"},
            {"sem": 2, "credits": 24, "uploaded_at": "2026-06-30T00:00:00Z", "result": "PASS"},
        ],
    }


async def test_known_id_with_no_uploads_in_that_year(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456780003", "academic_year": "2026-27"}
    )
    assert response.json() == {"apaar_id_known": True, "semesters": []}


async def test_registered_id_with_no_uploads_at_all(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456784417", "academic_year": "2025-26"}
    )
    assert response.json() == {"apaar_id_known": True, "semesters": []}


async def test_unknown_id(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "000000000000", "academic_year": "2025-26"}
    )
    assert response.json() == {"apaar_id_known": False, "semesters": []}


async def test_fail_result_is_reported(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456780004", "academic_year": "2025-26"}
    )
    assert response.json()["semesters"] == [
        {"sem": 1, "credits": 0, "uploaded_at": "2026-01-20T00:00:00Z", "result": "FAIL"}
    ]


async def test_validation(client: AsyncClient) -> None:
    response = await client.post("/abc/credits", json={"apaar_id": "123", "academic_year": "2025"})
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"apaar_id", "academic_year"}
