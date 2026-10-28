import json

from httpx import AsyncClient

from app import seed
from app.config import Settings

MSTU = {"type": "UNIVERSITY", "code": "MSTU", "name": "Maharashtra State Technical University"}
XYZ = {"type": "INSTITUTION", "code": "1-XYZ-0002", "name": "XYZ Institute of Technology"}


async def test_credits_for_a_year(client: AsyncClient, seeded: dict) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456780003", "academic_year": "2025-26"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "apaar_id_known": True,
        "semesters": [
            {
                "sem": 1,
                "credits": 22,
                "uploaded_at": "2026-01-20T00:00:00Z",
                "result": "PASS",
                "issuer": MSTU,
            },
            {
                "sem": 2,
                "credits": 24,
                "uploaded_at": "2026-06-30T00:00:00Z",
                "result": "PASS",
                "issuer": MSTU,
            },
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
        {
            "sem": 1,
            "credits": 0,
            "uploaded_at": "2026-01-20T00:00:00Z",
            "result": "FAIL",
            "issuer": XYZ,
        }
    ]


async def test_an_autonomous_college_issues_its_own_credits(
    client: AsyncClient, seeded: dict
) -> None:
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456780004", "academic_year": "2025-26"}
    )
    assert response.json()["semesters"][0]["issuer"]["type"] == "INSTITUTION"


async def test_a_record_without_an_issuer_reports_null(
    client: AsyncClient, settings: Settings, tmp_path
) -> None:
    folder = tmp_path / "mockgov"
    folder.mkdir()
    line = {
        "apaar_id": "123456780009",
        "academic_year": "2025-26",
        "sem": 1,
        "credits": 20,
        "uploaded_at": "2026-01-20T00:00:00Z",
        "result": "PASS",
    }
    (folder / "abc_credits.jsonl").write_text(json.dumps(line) + "\n")
    await seed.run(folder, reset=False, settings=settings)
    response = await client.post(
        "/abc/credits", json={"apaar_id": "123456780009", "academic_year": "2025-26"}
    )
    assert response.json()["semesters"][0]["issuer"] is None


async def test_validation(client: AsyncClient) -> None:
    response = await client.post("/abc/credits", json={"apaar_id": "123", "academic_year": "2025"})
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"apaar_id", "academic_year"}
