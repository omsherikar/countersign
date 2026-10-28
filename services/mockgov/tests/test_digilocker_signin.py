"""The DigiLocker sign-in simulator (API_CONTRACT C.11, C.12): page, one-time codes, id tokens."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import jwt
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DigiLockerAccount, DigiLockerAuthCode

CALLBACK = "http://localhost:3000/api/auth/digilocker/callback"
SECRET = "countersign-demo-digilocker-client-secret"
ISSUER = "http://localhost:8001/digilocker"
CLIENT = {
    "response_type": "code",
    "client_id": "countersign-demo",
    "redirect_uri": CALLBACK,
    "scope": "openid",
    "state": "st-1",
    "nonce": "n-1",
}
HEADING = "Demo DigiLocker. A simulator for the Countersign demo, not the real DigiLocker."


async def page(client: AsyncClient, **params):
    return await client.get("/digilocker/oauth/authorize", params={**CLIENT, **params})


async def sign_in(client: AsyncClient, account: str = "DL-RAVI-4417", otp: str = "123456", **kw):
    data = {**CLIENT, "account": account, "otp": otp, **kw}
    return await client.post("/digilocker/oauth/authorize", data=data)


def query_of(response) -> dict[str, list[str]]:
    assert response.status_code == 302, response.text
    location = urlsplit(response.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == CALLBACK
    return parse_qs(location.query)


def code_of(response) -> str:
    query = query_of(response)
    assert query["state"] == ["st-1"]
    return query["code"][0]


async def exchange(client: AsyncClient, code: str, **overrides):
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": CALLBACK,
        "client_id": "countersign-demo",
        "client_secret": SECRET,
        **overrides,
    }
    return await client.post("/digilocker/oauth/token", data=form)


def claims_of(token: str) -> dict:
    assert jwt.get_unverified_header(token) == {"alg": "HS256", "typ": "JWT"}
    return jwt.decode(
        token, SECRET, algorithms=["HS256"], audience="countersign-demo", issuer=ISSUER
    )


async def test_the_page_is_labelled_and_lists_the_demo_accounts_first(
    client: AsyncClient, seeded: dict
) -> None:
    response = await page(client)
    assert response.status_code == 200
    html = response.text
    assert HEADING in html and "<script" not in html
    assert html.index("Ravi Kumar Sharma") < html.index("Priya Nair") < html.index("Meena Iyer")
    assert 'value="DL-RAVI-4417" checked' in html
    assert "APAAR XXXX XXXX 4417" in html and "123456784417" not in html
    assert 'name="otp"' in html and ">Cancel</a>" in html
    assert response.headers["cache-control"] == "no-store"
    csp = response.headers["content-security-policy"]
    assert "script-src" not in csp and "form-action 'self' http://localhost:3000" in csp


async def test_search_by_digilocker_id_or_apaar(client: AsyncClient, seeded: dict) -> None:
    by_id = (await page(client, q="dl-7k2m-9qrt")).text
    assert "Priya Nair" in by_id and "Ravi Kumar Sharma" not in by_id
    by_apaar = (await page(client, q="987654324417")).text
    assert "Rahul Desai" in by_apaar and "Ravi Kumar Sharma" not in by_apaar
    last4 = (await page(client, q="4417")).text
    assert "Ravi Kumar Sharma" in last4 and "Rahul Desai" in last4
    assert "No synthetic account matches." in (await page(client, q="DL-NOPE-0000")).text


async def test_full_code_flow(client: AsyncClient, seeded: dict) -> None:
    code = code_of(await sign_in(client))
    response = await exchange(client, code)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "scope", "id_token"}
    assert body["access_token"].startswith("dl_at_")
    assert (body["token_type"], body["expires_in"], body["scope"]) == ("Bearer", 600, "openid")
    claims = claims_of(body["id_token"])
    assert claims == {
        "iss": ISSUER,
        "sub": "DL-RAVI-4417",
        "aud": "countersign-demo",
        "iat": claims["iat"],
        "exp": claims["iat"] + 600,
        "nonce": "n-1",
        "name": "Ravi Kumar Sharma",
        "birthdate": "2007-03-21",
        "gender": "M",
        "apaar_id": "123456784417",
    }


async def test_the_account_can_be_named_by_apaar(client: AsyncClient, seeded: dict) -> None:
    code = code_of(await sign_in(client, account="123456780003"))
    assert claims_of((await exchange(client, code)).json()["id_token"])["sub"] == "DL-7K2M-9QRT"


async def test_an_account_without_apaar_carries_a_null_apaar(
    client: AsyncClient, seeded: dict
) -> None:
    code = code_of(await sign_in(client, account="DL-4HXP-2WZA"))
    claims = claims_of((await exchange(client, code)).json()["id_token"])
    assert claims["sub"] == "DL-4HXP-2WZA" and claims["name"] == "Meena Iyer"
    assert claims["apaar_id"] is None


async def test_cancel_goes_back_with_access_denied(client: AsyncClient, seeded: dict) -> None:
    query = query_of(await page(client, cancel="1"))
    assert query == {"error": ["access_denied"], "state": ["st-1"]}


async def test_a_code_works_once(client: AsyncClient, seeded: dict) -> None:
    code = code_of(await sign_in(client))
    assert (await exchange(client, code)).status_code == 200
    again = await exchange(client, code)
    assert again.status_code == 400
    assert again.json() == {
        "error": "invalid_grant",
        "error_description": "The code is unknown, expired or used.",
    }


async def test_wrong_otp_or_account_shows_the_page_again_and_issues_no_code(
    client: AsyncClient, seeded: dict, session: AsyncSession
) -> None:
    wrong = await sign_in(client, otp="000000")
    assert wrong.status_code == 200 and "location" not in wrong.headers
    assert "Wrong OTP." in wrong.text and 'value="DL-RAVI-4417" checked' in wrong.text
    unknown = await sign_in(client, account="DL-NOPE-0000")
    assert unknown.status_code == 200 and "No such account." in unknown.text
    assert await session.scalar(select(func.count()).select_from(DigiLockerAuthCode)) == 0


async def test_an_expired_code_is_refused(
    client: AsyncClient, seeded: dict, session: AsyncSession
) -> None:
    code = code_of(await sign_in(client))
    row = await session.get(DigiLockerAuthCode, code)
    assert timedelta(seconds=55) < row.expires_at - datetime.now(UTC) <= timedelta(seconds=60)
    await session.execute(
        update(DigiLockerAuthCode)
        .where(DigiLockerAuthCode.code == code)
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()
    response = await exchange(client, code)
    assert response.status_code == 400 and response.json()["error"] == "invalid_grant"


async def test_unknown_and_misdirected_codes(client: AsyncClient, seeded: dict) -> None:
    assert (await exchange(client, "not-a-code")).json()["error"] == "invalid_grant"
    code = code_of(await sign_in(client))
    other = await exchange(client, code, redirect_uri="http://localhost:3000/elsewhere")
    assert other.status_code == 400 and other.json()["error"] == "invalid_grant"


async def test_the_client_secret_is_checked(client: AsyncClient, seeded: dict) -> None:
    code = code_of(await sign_in(client))
    response = await exchange(client, code, client_secret="wrong")
    assert response.status_code == 401
    assert response.json() == {
        "error": "invalid_client",
        "error_description": "Unknown client or wrong secret.",
    }
    # A refused client does not spend the code.
    assert (await exchange(client, code)).status_code == 200
    bad_grant = await exchange(client, "x", grant_type="password")
    assert bad_grant.status_code == 400 and bad_grant.json()["error"] == "unsupported_grant_type"


async def test_an_unknown_client_or_redirect_gets_an_error_page_and_no_redirect(
    client: AsyncClient, seeded: dict
) -> None:
    for params in (
        {"client_id": "someone-else"},
        {"redirect_uri": "https://evil.example/cb"},
        {"redirect_uri": "javascript:alert(1)"},
        {"redirect_uri": CALLBACK + "/more"},
    ):
        response = await page(client, **params)
        assert response.status_code == 400, params
        assert "Unknown client or redirect address." in response.text
        cancel = await page(client, cancel="1", **params)
        assert cancel.status_code == 400 and "location" not in cancel.headers
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
            position=99,
        )
    )
    await session.commit()
    hostile = '"><img src=x onerror=alert(1)>'
    for response in (
        await page(client, q="kumar", state=hostile, nonce=hostile),
        await page(client, q='<b>"bold"</b>'),
        await sign_in(client, account="DL-EVIL-0001", otp="1", state=hostile),
        await sign_in(client, account="<i>x</i>", q="<u>y</u>"),
    ):
        html = response.text
        assert response.status_code == 200
        for tag in ("<script>", "<img", "<b>", "<i>", "<u>"):
            assert tag not in html, tag
    listed = (await page(client, q="kumar", state=hostile)).text
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; Kumar" in listed
    assert 'value="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"' in listed


async def test_sign_in_stays_up_while_digilocker_notices_are_down(
    client: AsyncClient, seeded: dict
) -> None:
    await client.post("/admin/chaos", json={"source": "digilocker", "down": True})
    code = code_of(await sign_in(client))
    assert (await page(client)).status_code == 200
    assert (await exchange(client, code)).status_code == 200
