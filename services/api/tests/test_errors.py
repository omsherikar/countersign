async def test_unknown_route_uses_envelope(client):
    response = await client.get("/uploads")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not found.", "details": {}}
    }


async def test_form_body_on_mutating_route_is_415(client):
    response = await client.post("/auth/login", data={"email": "a@b", "password": "x"})
    assert response.status_code == 415
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert body["error"]["details"]["content_type"].startswith("application/x-www-form-urlencoded")


async def test_validation_error_lists_fields(client):
    response = await client.post("/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    fields = {f["field"] for f in body["error"]["details"]["fields"]}
    assert fields == {"email", "password"}


async def test_malformed_json_is_a_validation_error(client):
    response = await client.post(
        "/auth/login", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_method_not_allowed_uses_envelope(client):
    response = await client.delete("/healthz")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
