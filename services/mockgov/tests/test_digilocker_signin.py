"""The DigiLocker sign-in simulator: pages, one-time codes, signed id tokens."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.digilocker_signin import SigningKey
from app.main import create_app, startup
from app.models import DigiLockerAccount, DigiLockerAuthCode

CALLBACK = "http://localhost:8000/auth/digilocker/callback"
CLIENT = {
    "client_id": "countersign-demo",
    "redirect_uri": CALLBACK,
    "state": "st-1",
    "nonce": "n-1",
}
SECRET = "countersign-demo-secret"
ISSUER = "http://localhost:8001/digilocker"


async def page(client: AsyncClient, **params):
    return await client.get("/digilocker/oauth/authorize", params={**CLIENT, **params})


async def sign_in(client: AsyncClient, account: str = "DL-RAVI-4417", otp: str = "123456", **kw):
    data = {**CLIENT, "account": account, "otp": otp, **kw}
    return await client.post("/digilocker/oauth/authorize", data=data)


def code_of(response) -> tuple[str, str]:
    assert response.status_code == 303, response.text
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == CALLBACK
    query = parse_qs(location.query)
    return query["code"][0], query["state"][0]


async def exchange(client: AsyncClient, code: str, **overrides):
    body = {"code": code, "client_id": "countersign-demo", "client_secret": SECRET}
    body["redirect_uri"] = CALLBACK
    return await client.post("/digilocker/oauth/token", json={**body, **overrides})


async def claims_of(client: AsyncClient, token: str) -> dict:
    keys = (await client.get("/digilocker/oauth/jwks")).json()["keys"]
    assert len(keys) == 1 and keys[0]["alg"] == "ES256" and keys[0]["kty"] == "EC"
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "ES256" and header["kid"] == keys[0]["kid"]
    return jwt.decode(
        token,
        jwt.PyJWK(keys[0]).key,
        algorithms=["ES256"],
        audience="countersign-demo",
        issuer=ISSUER,
    )


async def test_the_page_is_labelled_and_finds_accounts_by_apaar_last_four(
    client: AsyncClient, seeded: dict
) -> None:
    response = await page(client, q="4417")
    assert response.status_code == 200
    html = response.text
    assert "Demo DigiLocker, synthetic data" in html and "Not the real DigiLocker" in html
    assert "Ravi Kumar Sharma" in html and "Rahul Desai" in html
    assert "Priya Nair" not in html
    assert "APAAR XXXX XXXX 4417" in html and "123456784417" not in html
    assert response.headers["cache-control"] == "no-store"
    assert "script-src" not in response.headers["content-security-policy"]
    assert "<script" not in html


async def test_search_by_name_and_by_typed_id(client: AsyncClient, seeded: dict) -> None:
    by_name = (await page(client, q="meena")).text
    assert "Meena Iyer" in by_name and "No APAAR linked" in by_name
    assert "No synthetic account matches." in (await page(client, q="nobody here")).text
    typed = await page(client, account="dl-7k2m-9qrt")
    assert typed.status_code == 200
    assert "Signing in as Priya Nair" in typed.text and "Demo OTP: 123456" in typed.text
    assert "form-action 'self' http://localhost:8000" in typed.headers["content-security-policy"]
    unknown = await page(client, account="DL-NOPE-0000")
    assert unknown.status_code == 404 and "No synthetic account has that" in unknown.text


async def test_full_code_flow(client: AsyncClient, seeded: dict) -> None:
    code, state = code_of(await sign_in(client))
    assert state == "st-1" and len(code) >= 40
    response = await exchange(client, code)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 600 and body["access_token"]
    claims = await claims_of(client, body["id_token"])
    assert claims["sub"] == "DL-RAVI-4417"
    assert claims["name"] == "Ravi Kumar Sharma" and claims["dob"] == "2007-03-21"
    assert claims["apaar_id"] == "123456784417" and claims["gender"] == "M"
    assert claims["nonce"] == "n-1" and claims["aud"] == "countersign-demo"
    assert claims["iss"] == ISSUER and claims["exp"] - claims["iat"] == 600


async def test_an_account_without_apaar_signs_in_without_the_claim(
    client: AsyncClient, seeded: dict
) -> None:
    code, _ = code_of(await sign_in(client, account="DL-4HXP-2WZA"))
    claims = await claims_of(client, (await exchange(client, code)).json()["id_token"])
    assert claims["sub"] == "DL-4HXP-2WZA" and claims["name"] == "Meena Iyer"
    assert "apaar_id" not in claims


async def test_the_redirect_keeps_the_callers_query(client: AsyncClient, seeded: dict) -> None:
    response = await sign_in(client, redirect_uri=CALLBACK + "?next=%2Fstudent")
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["next"] == ["/student"] and query["state"] == ["st-1"] and query["code"]


async def test_a_code_works_once(client: AsyncClient, seeded: dict) -> None:
    code, _ = code_of(await sign_in(client))
    assert (await exchange(client, code)).status_code == 200
    again = await exchange(client, code)
    assert again.status_code == 400
    assert again.json()["error"] == {
        "code": "INVALID_GRANT",
        "message": "The code was already used.",
        "details": {},
    }


async def test_wrong_otp_shows_the_form_again_and_issues_no_code(
    client: AsyncClient, seeded: dict, session: AsyncSession
) -> None:
    response = await sign_in(client, otp="000000")
    assert response.status_code == 401
    assert "location" not in response.headers
    assert "That OTP is not right. The demo OTP is 123456." in response.text
    assert await session.scalar(select(func.count()).select_from(DigiLockerAuthCode)) == 0


async def test_an_expired_code_is_refused(
    client: AsyncClient, seeded: dict, session: AsyncSession
) -> None:
    code, _ = code_of(await sign_in(client))
    row = await session.get(DigiLockerAuthCode, code)
    assert row.expires_at - row.created_at == timedelta(minutes=5)
    await session.execute(
        update(DigiLockerAuthCode)
        .where(DigiLockerAuthCode.code == code)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    response = await exchange(client, code)
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "The code has expired."


async def test_unknown_and_misdirected_codes(client: AsyncClient, seeded: dict) -> None:
    unknown = await exchange(client, "not-a-code")
    assert unknown.status_code == 400
    assert unknown.json()["error"]["message"] == "The code is not known."
    code, _ = code_of(await sign_in(client))
    other = await exchange(client, code, redirect_uri="http://localhost:8000/elsewhere")
    assert other.status_code == 400
    assert other.json()["error"]["message"] == (
        "The code was issued to another client or redirect URI."
    )


async def test_the_client_secret_is_checked(client: AsyncClient, seeded: dict) -> None:
    code, _ = code_of(await sign_in(client))
    response = await exchange(client, code, client_secret="wrong")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CLIENT"
    # A refused client does not spend the code.
    assert (await exchange(client, code)).status_code == 200


async def test_a_bad_request_gets_an_error_page_and_no_redirect(
    client: AsyncClient, seeded: dict
) -> None:
    for params in (
        {"client_id": "someone-else"},
        {"redirect_uri": "https://evil.example/cb"},
        {"redirect_uri": "javascript:alert(1)"},
        {"redirect_uri": "http://localhost:8000/cb#frag"},
        {"response_type": "token"},
    ):
        response = await page(client, **params)
        assert response.status_code == 400, params
        assert "This sign-in request cannot continue" in response.text
        if "response_type" in params:
            continue  # checked on the page; the OTP form never carries it
        posted = await sign_in(client, **params)
        assert posted.status_code == 400 and "location" not in posted.headers, params


async def test_the_page_escapes_every_value(
    client: AsyncClient, seeded: dict, session: AsyncSession
) -> None:
    session.add(
        DigiLockerAccount(
            digilocker_id="DL-EVIL-0001",
            name='<script>alert("x")</script> Kumar',
            name_normalized="script alert x script kumar",
            dob=datetime(2007, 1, 1).date(),
            gender="M",
            apaar_id=None,
            apaar_last4=None,
        )
    )
    await session.commit()
    hostile = '"><img src=x onerror=alert(1)>'
    for response in (
        await page(client, q="kumar", state=hostile, nonce=hostile),
        await page(client, account="DL-EVIL-0001", state=hostile),
        await sign_in(client, account="DL-EVIL-0001", otp="1", state=hostile),
        await page(client, q='<b>"bold"</b>'),
    ):
        html = response.text
        assert "<script>" not in html and "<img" not in html and "<b>" not in html
    listed = (await page(client, q="kumar", state=hostile)).text
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; Kumar" in listed
    assert 'value="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"' in listed


async def test_the_token_route_honours_digilocker_chaos(client: AsyncClient, seeded: dict) -> None:
    code, _ = code_of(await sign_in(client))
    await client.post("/admin/chaos", json={"source": "digilocker", "down": True})
    response = await exchange(client, code)
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "DigiLocker unavailable."
    # The sign-in page stays up, like the inbox page.
    assert (await page(client)).status_code == 200


async def test_the_signing_key_survives_a_restart(
    client: AsyncClient, app: FastAPI, settings: Settings
) -> None:
    kid = (await client.get("/digilocker/oauth/jwks")).json()["keys"][0]["kid"]
    restarted = create_app(settings)
    await startup(restarted)
    try:
        async with AsyncClient(transport=ASGITransport(app=restarted), base_url="http://m") as c:
            assert (await c.get("/digilocker/oauth/jwks")).json()["keys"][0]["kid"] == kid
    finally:
        await restarted.state.db.dispose()


async def test_a_configured_key_is_used(settings: Settings) -> None:
    pem = (
        ec.generate_private_key(ec.SECP256R1())
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    custom = settings.model_copy(update={"mockgov_digilocker_signing_key": pem})
    application = create_app(custom)
    await startup(application)
    try:
        assert application.state.digilocker_key.kid == SigningKey.from_pem(pem).kid
    finally:
        await application.state.db.dispose()
