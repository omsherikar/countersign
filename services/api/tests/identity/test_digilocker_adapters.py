"""The DigiLocker adapter's sign-in side: the authorize link, the code exchange and the id
token checks, in the in-memory, mockgov and real implementations (ENGINES §17.6)."""

from __future__ import annotations

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
import respx

from app.adapters import digilocker_oidc
from app.adapters.base import AdapterRequestError, IdTokenInvalid, RealAdapterDisabled
from app.adapters.digilocker_oidc import OAuthClient, mint_id_token, read_id_token
from app.adapters.inmemory import InMemoryDigiLocker
from app.adapters.mockgov import MockGovClient, MockGovDigiLocker
from app.adapters.real import RealDigiLocker

BASE = "http://mockgov.test"
REDIRECT = "http://localhost:3000/api/auth/digilocker/callback"
CLIENT = OAuthClient(
    client_id="countersign-demo",
    client_secret="countersign-demo-digilocker-client-secret",
    authorize_endpoint="http://localhost:8001/digilocker/oauth/authorize",
    issuer="http://localhost:8001/digilocker",
)
RAVI = {"name": "Ravi Kumar Sharma", "dob": date(2007, 3, 21), "apaar_id": "123456784417"}


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def _token(client: OAuthClient = CLIENT, **overrides) -> str:
    values = {
        "sub": "DL-RAVI-4417",
        "name": "Ravi Kumar Sharma",
        "birthdate": date(2007, 3, 21),
        "nonce": "n-1",
        "gender": "M",
        "apaar_id": "123456784417",
    }
    values.update(overrides)
    return mint_id_token(client, **values)


def test_the_authorize_link_carries_the_oauth_request():
    url = digilocker_oidc.authorize_url(CLIENT, state="s-1", nonce="n-1", redirect_uri=REDIRECT)
    assert url.startswith("http://localhost:8001/digilocker/oauth/authorize?")
    assert query_of(url) == {
        "response_type": "code",
        "client_id": "countersign-demo",
        "redirect_uri": REDIRECT,
        "scope": "openid",
        "state": "s-1",
        "nonce": "n-1",
    }


def test_a_good_token_names_the_person():
    identity = read_id_token(_token(), CLIENT, nonce="n-1")
    assert (identity.sub, identity.name, identity.birthdate, identity.gender) == (
        "DL-RAVI-4417",
        "Ravi Kumar Sharma",
        date(2007, 3, 21),
        "M",
    )
    assert identity.apaar_id == "123456784417"
    assert "123456784417" not in repr(identity)  # never in a log line
    assert read_id_token(_token(apaar_id=None), CLIENT, nonce="n-1").apaar_id is None


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(
            _token(
                OAuthClient(
                    "countersign-demo", "another-secret-of-the-same-length-x", "x", CLIENT.issuer
                )
            ),
            id="signed with another secret",
        ),
        pytest.param(
            _token(OAuthClient("someone-else", CLIENT.client_secret, "x", CLIENT.issuer)),
            id="for another client",
        ),
        pytest.param(
            _token(OAuthClient(CLIENT.client_id, CLIENT.client_secret, "x", "http://evil")),
            id="from another issuer",
        ),
        pytest.param(_token(issued_at=1_000_000), id="expired"),
        pytest.param(_token(nonce="n-2"), id="another sign-in's nonce"),
        pytest.param(_token(nonce=None), id="no nonce"),
        pytest.param(_token(apaar_id="1234"), id="not an APAAR"),
        pytest.param(
            jwt.encode({"sub": "x"}, CLIENT.client_secret, algorithm="HS256"),
            id="claims missing",
        ),
        pytest.param("not-a-token", id="not a JWT"),
    ],
)
def test_a_token_that_does_not_hold_is_refused(token):
    with pytest.raises(IdTokenInvalid):
        read_id_token(token, CLIENT, nonce="n-1")


async def test_the_in_memory_digilocker_accepts_only_its_own_codes_once():
    dl = InMemoryDigiLocker(accounts={"DL-RAVI-4417": RAVI}, oauth=CLIENT)
    code = dl.sign_in("DL-RAVI-4417", redirect_uri=REDIRECT, nonce="n-1")
    identity = await dl.exchange_code(code=code, redirect_uri=REDIRECT, nonce="n-1")
    assert (identity.sub, identity.apaar_id) == ("DL-RAVI-4417", "123456784417")
    with pytest.raises(AdapterRequestError):  # a code works once
        await dl.exchange_code(code=code, redirect_uri=REDIRECT, nonce="n-1")
    with pytest.raises(AdapterRequestError):  # a code it never minted
        await dl.exchange_code(code="forged", redirect_uri=REDIRECT, nonce="n-1")
    other = dl.sign_in("DL-RAVI-4417", redirect_uri=REDIRECT, nonce="n-1")
    with pytest.raises(AdapterRequestError):  # sent back somewhere else
        await dl.exchange_code(code=other, redirect_uri="http://evil/cb", nonce="n-1")
    third = dl.sign_in("DL-RAVI-4417", redirect_uri=REDIRECT, nonce="n-1")
    with pytest.raises(IdTokenInvalid):  # the token names another sign-in's nonce
        await dl.exchange_code(code=third, redirect_uri=REDIRECT, nonce="n-2")
    # sign-in works while the notices are switched off, as in mockgov
    dl.down = True
    fourth = dl.sign_in("DL-RAVI-4417", redirect_uri=REDIRECT, nonce="n-1")
    assert (await dl.exchange_code(code=fourth, redirect_uri=REDIRECT, nonce="n-1")).sub


async def test_the_mockgov_exchange_posts_a_form_and_verifies_the_answer():
    sent: list[dict[str, list[str]]] = []

    def token_endpoint(request: httpx.Request) -> httpx.Response:
        sent.append(parse_qs(request.content.decode()))
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        return httpx.Response(
            200,
            json={
                "access_token": "dl_at_x",
                "token_type": "Bearer",
                "expires_in": 600,
                "scope": "openid",
                "id_token": _token(),
            },
        )

    async with respx.mock(base_url=BASE) as mock:
        mock.post("/digilocker/oauth/token").mock(side_effect=token_endpoint)
        dl = MockGovDigiLocker(MockGovClient(BASE), oauth=CLIENT)
        identity = await dl.exchange_code(code="c-1", redirect_uri=REDIRECT, nonce="n-1")
        await dl.client.aclose()
    assert identity.sub == "DL-RAVI-4417"
    assert sent == [
        {
            "grant_type": ["authorization_code"],
            "code": ["c-1"],
            "redirect_uri": [REDIRECT],
            "client_id": ["countersign-demo"],
            "client_secret": ["countersign-demo-digilocker-client-secret"],
        }
    ]
    assert dl.authorize_url(state="s", nonce="n", redirect_uri=REDIRECT).startswith(
        CLIENT.authorize_endpoint
    )


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        (
            httpx.Response(400, json={"error": "invalid_grant", "error_description": "used"}),
            AdapterRequestError,
        ),
        (
            httpx.Response(401, json={"error": "invalid_client", "error_description": "no"}),
            AdapterRequestError,
        ),
        (httpx.Response(200, json={"access_token": "x"}), IdTokenInvalid),
        (httpx.Response(200, json={"id_token": "garbage"}), IdTokenInvalid),
    ],
)
async def test_mockgov_refusals_never_sign_anyone_in(answer, error):
    async with respx.mock(base_url=BASE) as mock:
        mock.post("/digilocker/oauth/token").mock(return_value=answer)
        dl = MockGovDigiLocker(MockGovClient(BASE), oauth=CLIENT)
        with pytest.raises(error):
            await dl.exchange_code(code="c-1", redirect_uri=REDIRECT, nonce="n-1")
        await dl.client.aclose()


async def test_the_real_digilocker_is_never_called():
    real = RealDigiLocker(enabled=False)
    with pytest.raises(RealAdapterDisabled):
        real.authorize_url(state="s", nonce="n", redirect_uri=REDIRECT)
    with pytest.raises(RealAdapterDisabled):
        await real.exchange_code(code="c", redirect_uri=REDIRECT, nonce="n")


def test_the_settings_client_matches_mockgovs_defaults():
    client = OAuthClient.from_settings()
    assert client.client_id and client.client_secret and client.issuer
    assert json.dumps(repr(client)).count(client.client_secret) == 0  # the secret stays out
