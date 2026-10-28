async def test_healthz_shape_and_status(client):
    response = await client.get("/healthz")
    body = response.json()
    assert set(body) == {"status", "db", "redis", "version"}
    assert body["db"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["redis"] in ("ok", "down")
    if body["redis"] == "ok":
        assert (response.status_code, body["status"]) == (200, "ok")
    else:
        assert (response.status_code, body["status"]) == (503, "degraded")


async def test_healthz_is_public_and_tagged_with_request_id(client):
    response = await client.get("/healthz", headers={"x-request-id": "abc-123"})
    assert response.headers["x-request-id"] == "abc-123"
    assert response.status_code in (200, 503)
