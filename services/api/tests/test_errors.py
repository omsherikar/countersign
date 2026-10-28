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
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "email: must be an email address"
    assert error["details"]["fields"] == [
        {"field": "email", "message": "must be an email address"},
        {"field": "password", "message": "Field required"},
    ]


async def test_validation_message_names_the_first_field(client, admin):
    response = await client.post("/auth/login", json={})
    assert response.json()["error"]["message"] == "email: field required"

    response = await admin.get("/institutions", params={"page_size": 500})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["message"] == "page_size: input should be less than or equal to 200"
    assert error["details"]["fields"] == [
        {"field": "page_size", "message": "Input should be less than or equal to 200"}
    ]


async def test_malformed_json_is_a_validation_error(client):
    response = await client.post(
        "/auth/login", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "body: not valid JSON"
    assert error["details"]["fields"] == [{"field": "body", "message": "Not valid JSON"}]


async def test_method_not_allowed_uses_envelope(client):
    response = await client.delete("/healthz")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
