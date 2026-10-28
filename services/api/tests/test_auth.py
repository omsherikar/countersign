from http.cookies import SimpleCookie

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.ratelimit import limiter
from tests.conftest import PASSWORD, login_as


async def test_login_sets_cookie_and_returns_scoped_user(seeded, client):
    response = await client.post(
        "/auth/login", json={"email": "registrar@abc.edu.demo", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["email"] == "registrar@abc.edu.demo"
    assert user["role"] == "INSTITUTION"
    assert user["name"] == "Registrar, ABC College of Engineering"
    assert set(user["scope"]) == {
        "institution_id",
        "institution_name",
        "region",
        "student_id",
        "university_id",
    }
    assert user["scope"]["institution_name"] == "ABC College of Engineering"
    assert user["scope"]["region"] == "WEST"
    assert user["scope"]["student_id"] is None

    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie["cs_access"]
    assert morsel["httponly"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/"
    assert int(morsel["max-age"]) == 120 * 60
    assert not morsel["secure"]


async def test_me_scope_per_role(seeded):
    expectations = {
        "admin@aicte.demo": (
            "AICTE_ADMIN",
            {
                "institution_id": None,
                "region": None,
                "student_id": None,
                "university_id": None,
                "institution_name": None,
            },
        ),
        "ro.west@aicte.demo": ("RO_OFFICER", {"region": "WEST", "institution_id": None}),
        "student@demo": ("STUDENT", {"region": None, "institution_id": None}),
    }
    for email, (role, scope_bits) in expectations.items():
        c = await login_as(email)
        try:
            me = (await c.get("/me")).json()["user"]
        finally:
            await c.aclose()
        assert me["role"] == role
        for key, value in scope_bits.items():
            assert me["scope"][key] == value, (email, key)
        if role == "STUDENT":
            assert me["scope"]["student_id"]
        assert "university_name" not in me["scope"]

    c = await login_as("coe@univ.demo")
    try:
        me = (await c.get("/me")).json()["user"]
    finally:
        await c.aclose()
    assert me["scope"]["university_name"] == "Maharashtra State Technical University"
    assert me["scope"]["university_id"]


async def test_bad_credentials(seeded, client):
    response = await client.post(
        "/auth/login", json={"email": "admin@aicte.demo", "password": "nope"}
    )
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "INVALID_CREDENTIALS",
            "message": "Email or password is incorrect.",
            "details": {},
        }
    }
    response = await client.post(
        "/auth/login", json={"email": "ghost@aicte.demo", "password": PASSWORD}
    )
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_without_cookie_is_401(client):
    response = await client.get("/me")
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "UNAUTHENTICATED", "message": "Sign in to continue.", "details": {}}
    }
    client.cookies.set("cs_access", "not-a-jwt")
    response = await client.get("/me")
    assert response.status_code == 401


async def test_logout_clears_cookie_even_when_anonymous(seeded, client):
    anonymous = await client.post("/auth/logout")
    assert anonymous.status_code == 204
    c = await login_as("admin@aicte.demo")
    try:
        response = await c.post("/auth/logout")
        assert response.status_code == 204
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        assert cookie["cs_access"].value == ""
        assert cookie["cs_access"]["max-age"] == "0"
        c.cookies.clear()
        assert (await c.get("/me")).status_code == 401
    finally:
        await c.aclose()


async def test_login_rate_limit_10_per_minute(seeded, client):
    limiter.enabled = True
    limiter.reset()
    try:
        statuses = []
        for _ in range(11):
            r = await client.post(
                "/auth/login", json={"email": "admin@aicte.demo", "password": "x"}
            )
            statuses.append(r.status_code)
        assert statuses[:10] == [401] * 10
        assert statuses[10] == 429
        body = r.json()
        assert body["error"]["code"] == "RATE_LIMITED"
        assert isinstance(body["error"]["details"]["retry_after"], int)
        assert r.headers["retry-after"]
    finally:
        limiter.enabled = False
        limiter.reset()


async def test_login_rate_limit_is_configurable(seeded, client, monkeypatch):
    monkeypatch.delenv("LOGIN_RATE_LIMIT", raising=False)
    assert Settings().login_rate_limit == "10/minute"
    with pytest.raises(ValidationError):
        Settings(login_rate_limit="lots")

    monkeypatch.setenv("LOGIN_RATE_LIMIT", "3/minute")
    get_settings.cache_clear()
    limiter.enabled = True
    limiter.reset()
    try:
        statuses = []
        for _ in range(4):
            r = await client.post(
                "/auth/login", json={"email": "admin@aicte.demo", "password": "x"}
            )
            statuses.append(r.status_code)
        assert statuses == [401, 401, 401, 429]
    finally:
        limiter.enabled = False
        limiter.reset()
        monkeypatch.delenv("LOGIN_RATE_LIMIT")
        get_settings.cache_clear()
