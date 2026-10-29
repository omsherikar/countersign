"""A student signs in through DigiLocker (D37, API_CONTRACT §A4.12): the round trip against
the in-memory and the mockgov DigiLocker, the failures that sign nobody in, binding by
APAAR, and the end of the student password."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import date
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

import httpx
import pytest
import respx
from sqlalchemy import select

from app.adapters import digilocker_oidc
from app.adapters.mockgov import MockGovClient, MockGovDigiLocker
from app.auth import UNUSABLE_PREFIX, digilocker
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import AuditAction, ConsentStatus, UserRole
from app.models.user import User
from app.seed.importer import import_directory
from tests.conftest import FIXTURE_DIR, PASSWORD, truncate_all
from tests.identity.conftest import (
    add_account,
    apaar_of,
    client,
    query_of,
    sign_in,
    start,
    student_of,
    user_of,
)

RAVI_APAAR = "123456784417"
RETURN = "/auth/digilocker/return"


def cookies_set(response: httpx.Response) -> dict[str, SimpleCookie]:
    out = {}
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        for name, morsel in cookie.items():
            out[name] = morsel
    return out


async def audit_entries(entity_type: str, action: AuditAction) -> list[AuditLog]:
    async with session_factory()() as s:
        return list(
            (
                await s.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type == entity_type, AuditLog.action == action)
                    .order_by(AuditLog.seq)
                )
            ).scalars()
        )


@pytest.fixture
async def mini(gov) -> AsyncIterator[None]:
    """The mini datagen fixture imported fresh (student@demo is Ravi), emptied afterwards."""
    await truncate_all()
    await import_directory(session_factory(), FIXTURE_DIR)
    yield
    await truncate_all()


async def test_start_sends_the_browser_to_digilocker_with_state_and_nonce(world):
    async with client() as c:
        response = await c.get(
            "/auth/digilocker/start", params={"next": "/student/notices/" + "A" * 43}
        )
    assert response.status_code == 302
    location = response.headers["location"]
    sent = query_of(location)
    assert location.startswith("http://localhost:8001/digilocker/oauth/authorize?")
    assert sent["response_type"] == "code" and sent["scope"] == "openid"
    assert sent["client_id"] == "countersign-demo"
    assert sent["redirect_uri"] == "http://localhost:3000/api/auth/digilocker/callback"
    assert len(sent["state"]) >= 43 and len(sent["nonce"]) >= 43
    assert sent["state"] != sent["nonce"]
    morsel = cookies_set(response)[digilocker.STATE_COOKIE]
    assert morsel["httponly"] and morsel["samesite"].lower() == "lax" and morsel["path"] == "/"
    assert int(morsel["max-age"]) == 600


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        (None, "/student"),
        ("/student", "/student"),
        ("/student/notices/" + "A" * 43, "/student/notices/" + "A" * 43),
        ("/student/claim?next=/student", "/student/claim?next=/student"),
        ("https://evil.example/student", "/student"),
        ("//evil.example/student", "/student"),
        ("/students-elsewhere", "/student"),
        ("/student/../aicte", "/student"),
        ("/aicte/enrolments", "/student"),
        ("/student/%2e%2e/aicte", "/student"),
    ],
)
def test_next_stays_under_student(raw, kept):
    assert digilocker.safe_next(raw) == kept


async def test_the_round_trip_against_the_in_memory_digilocker(world, gov):
    enrolment = await world.enrolment("Asha Patil")
    student = await student_of(enrolment)
    apaar = await apaar_of(enrolment)
    add_account(gov, "DL-ASHA-0001", "Asha Patil", date(2007, 1, 1), apaar)
    async with client() as c:
        response = await sign_in(c, gov, "DL-ASHA-0001", "/student")
        assert response.status_code == 302
        assert response.headers["location"] == f"{RETURN}?next=/student"
        set_now = cookies_set(response)
        assert set_now["cs_access"].value and set_now[digilocker.STATE_COOKIE].value == ""
        me = (await c.get("/me")).json()["user"]
    assert me["role"] == "STUDENT" and me["scope"]["student_id"] == str(student.id)

    # the account was made at first sign-in, bound by the APAAR, with no usable password
    user = await user_of(student.id)
    assert user.digilocker_sub == "DL-ASHA-0001"
    assert user.email == "dl-asha-0001@digilocker.invalid" and user.name == "Asha Patil"
    assert user.password_hash.startswith(UNUSABLE_PREFIX)
    [created] = [
        e for e in await audit_entries("user", AuditAction.CREATE) if e.entity_id == user.id
    ]
    assert created.after == {"role": "STUDENT", "via": "digilocker"}
    [login] = await audit_entries("user", AuditAction.LOGIN)
    assert (login.actor_id, login.after) == (user.id, {"via": "digilocker"})
    async with session_factory()() as s:
        chain = json.dumps([e.after for e in (await s.execute(select(AuditLog))).scalars()])
    assert apaar not in chain  # the APAAR on the token is never logged

    # a second sign-in finds the account by its DigiLocker subject
    async with client() as c:
        again = await sign_in(c, gov, "DL-ASHA-0001", "/student/notices/" + "B" * 43)
        assert again.headers["location"] == f"{RETURN}?next=/student/notices/{'B' * 43}"
    assert len(await audit_entries("user", AuditAction.CREATE)) == 1
    assert len(await audit_entries("user", AuditAction.LOGIN)) == 2
    # and the student still has no password
    async with client() as c:
        refused = await c.post("/auth/login", json={"email": user.email, "password": PASSWORD})
    assert refused.status_code == 401


async def test_the_round_trip_against_the_mockgov_digilocker(world, monkeypatch):
    """The token call goes to mockgov's simulator (API_CONTRACT C.12), answered here as it
    answers: an id token signed HS256 with the shared client secret."""
    enrolment = await world.enrolment("Meena Iyer")
    student = await student_of(enrolment)
    apaar = await apaar_of(enrolment)
    mockgov = MockGovDigiLocker(MockGovClient("http://mockgov.test"))
    monkeypatch.setattr(world.gov, "digilocker", mockgov)
    issued: dict[str, str] = {}

    def token_endpoint(request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        if form.get("code") != issued.get("code"):
            return httpx.Response(400, json={"error": "invalid_grant"})
        token = digilocker_oidc.mint_id_token(
            digilocker_oidc.OAuthClient.from_settings(),
            sub="DL-MEEN-0001",
            name="Meena Iyer",
            birthdate=date(2007, 1, 1),
            apaar_id=apaar,
            nonce=issued["nonce"],
        )
        issued.pop("code")
        return httpx.Response(200, json={"id_token": token, "token_type": "Bearer"})

    async with respx.mock(base_url="http://mockgov.test", assert_all_called=False) as mock:
        mock.post("/digilocker/oauth/token").mock(side_effect=token_endpoint)
        async with client() as c:
            sent = await start(c, "/student")
            issued.update(code="code-from-the-demo-page", nonce=sent["nonce"])
            response = await c.get(
                "/auth/digilocker/callback",
                params={"code": "code-from-the-demo-page", "state": sent["state"]},
            )
            assert response.headers["location"] == f"{RETURN}?next=/student"
            assert (await c.get("/me")).json()["user"]["scope"]["student_id"] == str(student.id)
            # the same code again is refused by DigiLocker, and nobody is signed in
            sent = await start(c, "/student")
            c.cookies.delete("cs_access")
            replay = await c.get(
                "/auth/digilocker/callback",
                params={"code": "code-from-the-demo-page", "state": sent["state"]},
            )
            assert replay.headers["location"] == f"{RETURN}?error=DIGILOCKER_FAILED&next=/student"
            assert "cs_access" not in cookies_set(replay)
    await mockgov.client.aclose()


async def _failed(response: httpx.Response, code: str, next_path: str = "/student") -> None:
    assert response.status_code == 302
    assert response.headers["location"] == f"{RETURN}?error={code}&next={next_path}"
    set_now = cookies_set(response)
    assert "cs_access" not in set_now and digilocker.CLAIM_COOKIE not in set_now
    assert set_now[digilocker.STATE_COOKIE].value == ""


async def test_a_state_mismatch_a_cancel_and_a_bad_token_sign_nobody_in(world, gov):
    enrolment = await world.enrolment("Kavya Nair")
    apaar = await apaar_of(enrolment)
    add_account(gov, "DL-KAVY-0001", "Kavya Nair", date(2007, 1, 1), apaar)
    page = "/student/notices/" + "C" * 43
    async with client() as c:
        # the state sent back is not the one this browser started with
        sent = await start(c, page)
        code = gov.digilocker.sign_in(
            "DL-KAVY-0001", redirect_uri=sent["redirect_uri"], nonce=sent["nonce"]
        )
        mismatch = await c.get(
            "/auth/digilocker/callback", params={"code": code, "state": "not-the-state"}
        )
        await _failed(mismatch, "DIGILOCKER_STATE_INVALID", page)
        # the person cancelled on the DigiLocker page
        sent = await start(c, page)
        cancelled = await c.get(
            "/auth/digilocker/callback", params={"error": "access_denied", "state": sent["state"]}
        )
        await _failed(cancelled, "DIGILOCKER_CANCELLED", page)
        # a token for another sign-in's nonce
        sent = await start(c, page)
        other = gov.digilocker.sign_in(
            "DL-KAVY-0001", redirect_uri=sent["redirect_uri"], nonce="another-nonce"
        )
        bad = await c.get(
            "/auth/digilocker/callback", params={"code": other, "state": sent["state"]}
        )
        await _failed(bad, "DIGILOCKER_FAILED", page)
        # a code DigiLocker never gave
        sent = await start(c, page)
        forged = await c.get(
            "/auth/digilocker/callback", params={"code": "forged", "state": sent["state"]}
        )
        await _failed(forged, "DIGILOCKER_FAILED", page)
        assert (await c.get("/me")).status_code == 401
    # a browser with no state cookie at all (started elsewhere, or expired)
    async with client() as c:
        stray = await c.get("/auth/digilocker/callback", params={"code": "x", "state": "y"})
        await _failed(stray, "DIGILOCKER_STATE_INVALID")
    assert await user_of(enrolment.student_id) is None
    assert await audit_entries("user", AuditAction.LOGIN) == []


async def test_a_person_with_no_linked_record_gets_a_pending_claim(world, gov):
    add_account(gov, "DL-ASHA-7777", "Asha Patil", date(2008, 1, 14), "999988887777")
    async with client() as c:
        response = await sign_in(c, gov, "DL-ASHA-7777", "/student")
        assert response.headers["location"] == "/student/claim?next=/student"
        morsel = cookies_set(response)[digilocker.CLAIM_COOKIE]
        assert int(morsel["max-age"]) == 900 and morsel["httponly"]
        assert "cs_access" not in cookies_set(response)
        pending = await c.get("/auth/digilocker/claim")
        assert pending.json() == {
            "name": "Asha Patil",
            "birthdate": "2008-01-14",
            "next": "/student",
        }
        # the claim cookie never carries the APAAR, and it is not a session
        assert "999988887777" not in morsel.value + json.dumps(pending.json())
        assert (await c.get("/me")).status_code == 401
        # from a notice link, the browser goes back to the notice page
        page = "/student/notices/" + "D" * 43
        from_notice = await sign_in(c, gov, "DL-ASHA-7777", page)
        assert from_notice.headers["location"] == page
    async with client() as c:
        none = await c.get("/auth/digilocker/claim")
    assert none.status_code == 401
    assert none.json()["error"] == {
        "code": "DIGILOCKER_STATE_INVALID",
        "message": "This sign-in has expired or was started in another browser.",
        "details": {},
    }


async def test_an_apaar_without_consent_does_not_bind(world, gov):
    """The token's APAAR finds only a student who holds it with consent LINKED (D36)."""
    enrolment = await world.enrolment("Rahul Verma")
    student = await student_of(enrolment)
    apaar = await apaar_of(enrolment)
    async with session_factory()() as s:
        row = await s.get(type(student), student.id)
        row.consent_status = ConsentStatus.PENDING
        await s.commit()
    add_account(gov, "DL-RAHU-0001", "Rahul Verma", date(2007, 1, 1), apaar)
    async with client() as c:
        response = await sign_in(c, gov, "DL-RAHU-0001")
    assert response.headers["location"] == "/student/claim?next=/student"
    assert await user_of(student.id) is None


async def test_the_seeded_demo_student_binds_by_apaar_and_has_no_password(mini, gov):
    async with session_factory()() as s:
        demo = (await s.execute(select(User).where(User.email == "student@demo"))).scalar_one()
    assert demo.role is UserRole.STUDENT and demo.digilocker_sub is None
    assert demo.password_hash.startswith(UNUSABLE_PREFIX)
    async with client() as c:
        password = await c.post("/auth/login", json={"email": "student@demo", "password": PASSWORD})
        wrong = await c.post("/auth/login", json={"email": "student@demo", "password": "nope"})
        officer = await c.post(
            "/auth/login", json={"email": "admin@aicte.demo", "password": PASSWORD}
        )
    # the same answer as a wrong password; other roles keep their passwords
    assert password.status_code == wrong.status_code == 401
    assert password.json() == wrong.json()
    assert password.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert officer.status_code == 200

    add_account(gov, "DL-RAVI-4417", "Ravi Kumar Sharma", date(2007, 3, 21), RAVI_APAAR)
    async with client() as c:
        response = await sign_in(c, gov, "DL-RAVI-4417")
        assert response.headers["location"] == f"{RETURN}?next=/student"
        me = (await c.get("/me")).json()["user"]
    assert me["email"] == "student@demo"
    async with session_factory()() as s:
        bound = await s.get(User, demo.id)
    assert bound.digilocker_sub == "DL-RAVI-4417"
    [update] = [
        e for e in await audit_entries("user", AuditAction.UPDATE) if e.entity_id == demo.id
    ]
    assert update.after == {"digilocker_bound": True}
    assert await audit_entries("user", AuditAction.CREATE) == []


async def test_the_sign_in_routes_are_rate_limited(world):
    from app.core.ratelimit import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        async with client() as c:
            statuses = [(await c.get("/auth/digilocker/start")).status_code for _ in range(31)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert statuses[:30] == [302] * 30 and statuses[30] == 429
