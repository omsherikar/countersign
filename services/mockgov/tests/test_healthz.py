from httpx import AsyncClient

from app.chaos import SOURCES


async def test_healthz_reports_db_and_chaos(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert set(body["chaos"]) == set(SOURCES)
    assert body["chaos"]["apaar"] == {"latency_ms": 0, "fail_rate": 0.0, "down": False}


async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not found.", "details": {}}
    }


async def test_validation_error_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.post(
        "/apaar/verify", json={"apaar_id": "12345", "name": "Ravi", "dob": "2007-03-21"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "apaar_id must be 12 digits."
    assert body["error"]["details"]["fields"] == [
        {"field": "apaar_id", "message": "apaar_id must be 12 digits."}
    ]


async def test_missing_field_lists_the_field(client: AsyncClient) -> None:
    response = await client.post("/apaar/verify", json={"apaar_id": "123456784417"})
    assert response.status_code == 422
    fields = {f["field"] for f in response.json()["error"]["details"]["fields"]}
    assert fields == {"name", "dob"}
