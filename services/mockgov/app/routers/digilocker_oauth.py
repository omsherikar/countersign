"""Demo DigiLocker sign-in: an OAuth code flow over synthetic accounts.

    GET  /digilocker/oauth/authorize?client_id&redirect_uri&state&nonce
         a plain page headed "Demo DigiLocker, synthetic data": search the synthetic accounts
         by name or the last four digits of an APAAR, or type a DigiLocker id, then enter the
         demo OTP 123456
    POST /digilocker/oauth/authorize
         checks the OTP; on success 303 to redirect_uri with `code` and `state`
    POST /digilocker/oauth/token {code, client_id, client_secret, redirect_uri}
         {id_token, access_token, token_type, expires_in}; the code is spent
    GET  /digilocker/oauth/jwks
         the public key that signs id tokens (ES256)

Not the real DigiLocker and labelled so on every page. The pages are self-contained (inline
CSS, no scripts), escape every value, and send a Content-Security-Policy that lets a form go
only to this service and the caller's own origin. The token route sits behind the
`digilocker` chaos gate; the pages and the key set do not, like the inbox page.
"""

from __future__ import annotations

import re
import secrets
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from app.chaos import chaos_gate
from app.config import Settings
from app.db import SessionDep
from app.digilocker_signin import (
    DEMO_OTP,
    InvalidClient,
    client_ok,
    id_token,
    issue_code,
    origin_of,
    redeem_code,
    redirect_allowed,
    with_query,
)
from app.models import DigiLockerAccount
from app.names import normalize_name
from app.routers.digilocker_ui import STYLE
from app.schemas import DigiLockerJwks, DigiLockerTokenRequest, DigiLockerTokenResponse

router = APIRouter(prefix="/digilocker/oauth", tags=["digilocker sign-in (simulated)"])

MAX_RESULTS = 20
LAST4 = re.compile(r"[0-9]{4}")
APAAR12 = re.compile(r"[0-9]{12}")
SAFE_ORIGIN = re.compile(r"https?://[A-Za-z0-9.\-:\[\]]+")
SIGNIN_STYLE = """
.who { margin: 1rem 0 0; color: var(--muted); }
.accounts form { margin: 0; display: block; }
.accounts .meta { color: var(--muted); font-size: 0.875rem; margin: 0.125rem 0 0.5rem; }
.otp-hint { color: var(--demo); font-weight: 600; }
a { color: inherit; }
"""


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _headers(form_origin: str | None = None) -> dict[str, str]:
    targets = "'self'"
    if form_origin and SAFE_ORIGIN.fullmatch(form_origin):
        targets += f" {form_origin}"
    return {
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": (
            f"default-src 'none'; style-src 'unsafe-inline'; form-action {targets}; "
            "base-uri 'none'; frame-ancestors 'none'"
        ),
    }


def _page(content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Demo DigiLocker sign-in</title>
<style>{STYLE}{SIGNIN_STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Demo DigiLocker, synthetic data</h1>
<p class="tag">Sign-in simulator</p>
<p class="note">Not the real DigiLocker. Every account here is synthetic, made for the
Countersign demo, and no message or OTP is ever sent.</p>
</header>
<main>
{content}
</main>
</div>
</body>
</html>
"""


def _html(content: str, status_code: int = 200, form_origin: str | None = None) -> HTMLResponse:
    return HTMLResponse(_page(content), status_code=status_code, headers=_headers(form_origin))


def _hidden(**fields: str | None) -> str:
    return "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(v)}">'
        for k, v in fields.items()
        if v
    )


def _error_page(reason: str) -> HTMLResponse:
    return _html(
        f'<h2>This sign-in request cannot continue</h2><p class="error">{escape(reason)}</p>'
        '<p class="muted">Go back to the service you came from and start again.</p>',
        status_code=400,
    )


def _request_problem(
    settings: Settings, client_id: str, redirect_uri: str, response_type: str
) -> str | None:
    if not client_id or not client_ok(settings, client_id):
        return "The client id is not registered with this simulator."
    if not redirect_uri or not redirect_allowed(settings, redirect_uri):
        return "The redirect URI is not allowed for this client."
    if response_type != "code":
        return "Only response_type=code is supported."
    return None


def _apaar_label(account: DigiLockerAccount) -> str:
    if account.apaar_id:
        return f"APAAR XXXX XXXX {account.apaar_id[-4:]}"
    return "No APAAR linked"


async def _search(session, q: str) -> list[DigiLockerAccount]:
    stmt = select(DigiLockerAccount)
    if LAST4.fullmatch(q):
        stmt = stmt.where(DigiLockerAccount.apaar_last4 == q)
    elif APAAR12.fullmatch(q):
        stmt = stmt.where(DigiLockerAccount.apaar_id == q)
    elif q.upper().startswith("DL-"):
        stmt = stmt.where(DigiLockerAccount.digilocker_id == q.upper())
    else:
        tokens = normalize_name(q).split()
        if not tokens:
            return []
        for token in tokens:  # letters and digits only after normalising
            stmt = stmt.where(DigiLockerAccount.name_normalized.contains(token))
    stmt = stmt.order_by(DigiLockerAccount.name, DigiLockerAccount.digilocker_id)
    return list(await session.scalars(stmt.limit(MAX_RESULTS + 1)))


def _search_forms(params: dict[str, str], q: str = "", error: str = "") -> str:
    message = f'<p class="error">{escape(error)}</p>' if error else ""
    return f"""<p class="who">Countersign (client <code>{escape(params["client_id"])}</code>)
asks for your name, date of birth and APAAR id.</p>
{message}
<form method="get" action="authorize">
{_hidden(**params)}
<label for="q">Find your account by name or the last four digits of your APAAR</label>
<input id="q" name="q" value="{escape(q)}" maxlength="100" autocomplete="off" required>
<button type="submit">Search</button>
</form>
<form method="get" action="authorize">
{_hidden(**params)}
<label for="account">Or type your DigiLocker id</label>
<input id="account" name="account" maxlength="32" autocomplete="off" placeholder="DL-XXXX-XXXX"
  required>
<button type="submit">Continue</button>
</form>"""


def _results(params: dict[str, str], accounts: list[DigiLockerAccount]) -> str:
    if not accounts:
        return '<p class="muted">No synthetic account matches.</p>'
    shown = accounts[:MAX_RESULTS]
    more = (
        f'<p class="muted">Showing the first {MAX_RESULTS}; narrow the search.</p>'
        if len(accounts) > MAX_RESULTS
        else ""
    )
    items = "\n".join(
        f"""<li><form method="get" action="authorize">{_hidden(**params)}
<input type="hidden" name="account" value="{escape(a.digilocker_id)}">
<strong>{escape(a.name)}</strong>
<p class="meta">DigiLocker id {escape(a.digilocker_id)} · {escape(_apaar_label(a))}</p>
<button type="submit">Continue as {escape(a.name)}</button></form></li>"""
        for a in shown
    )
    return f'<h2>Synthetic accounts</h2>{more}<ol class="accounts">\n{items}\n</ol>'


def _otp_form(params: dict[str, str], account: DigiLockerAccount, error: str = "") -> str:
    message = f'<p class="error">{escape(error)}</p>' if error else ""
    back = with_query("authorize", **params)
    return f"""<h2>Signing in as {escape(account.name)}</h2>
<p class="muted">DigiLocker id {escape(account.digilocker_id)} · {escape(_apaar_label(account))}</p>
{message}
<form method="post" action="authorize">
{_hidden(**params)}
<input type="hidden" name="account" value="{escape(account.digilocker_id)}">
<label for="otp">One-time password</label>
<input id="otp" name="otp" inputmode="numeric" autocomplete="one-time-code" maxlength="6"
  required>
<button type="submit">Verify and continue</button>
</form>
<p class="otp-hint">Demo OTP: {DEMO_OTP}. No message is sent.</p>
<p><a href="{escape(back)}">Choose another account</a></p>"""


@router.get("/authorize", response_class=HTMLResponse)
async def authorize_page(
    request: Request,
    session: SessionDep,
    client_id: Annotated[str, Query(max_length=200)] = "",
    redirect_uri: Annotated[str, Query(max_length=2000)] = "",
    state: Annotated[str, Query(max_length=500)] = "",
    nonce: Annotated[str, Query(max_length=500)] = "",
    response_type: Annotated[str, Query(max_length=20)] = "code",
    q: Annotated[str, Query(max_length=100)] = "",
    account: Annotated[str, Query(max_length=32)] = "",
) -> HTMLResponse:
    """The sign-in page: account search, then the OTP form for the chosen account."""
    settings = _settings(request)
    problem = _request_problem(settings, client_id, redirect_uri, response_type)
    if problem:
        return _error_page(problem)
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce}

    if account.strip():
        found = await session.get(DigiLockerAccount, account.strip().upper())
        if found is None:
            return _html(
                _search_forms(params, error="No synthetic account has that DigiLocker id."),
                status_code=404,
            )
        return _html(_otp_form(params, found), form_origin=origin_of(redirect_uri))

    q = q.strip()
    if not q:
        return _html(_search_forms(params))
    return _html(_search_forms(params, q=q) + _results(params, await _search(session, q)))


@router.post("/authorize", response_class=HTMLResponse)
async def authorize_submit(
    request: Request,
    session: SessionDep,
    client_id: Annotated[str, Form(max_length=200)] = "",
    redirect_uri: Annotated[str, Form(max_length=2000)] = "",
    state: Annotated[str, Form(max_length=500)] = "",
    nonce: Annotated[str, Form(max_length=500)] = "",
    account: Annotated[str, Form(max_length=32)] = "",
    otp: Annotated[str, Form(max_length=20)] = "",
):
    """Checks the demo OTP; on success sends the browser back with a one-time code."""
    settings = _settings(request)
    problem = _request_problem(settings, client_id, redirect_uri, "code")
    if problem:
        return _error_page(problem)
    params = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state, "nonce": nonce}
    found = await session.get(DigiLockerAccount, account.strip().upper()) if account else None
    if found is None:
        return _html(
            _search_forms(params, error="Choose a synthetic account first."), status_code=404
        )
    if not secrets.compare_digest(otp.strip().encode(), DEMO_OTP.encode()):
        return _html(
            _otp_form(params, found, error=f"That OTP is not right. The demo OTP is {DEMO_OTP}."),
            status_code=401,
            form_origin=origin_of(redirect_uri),
        )
    code = await issue_code(
        session,
        settings,
        account=found,
        client_id=client_id,
        redirect_uri=redirect_uri,
        nonce=nonce,
    )
    return RedirectResponse(
        with_query(redirect_uri, code=code, state=state),
        status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.post(
    "/token",
    response_model=DigiLockerTokenResponse,
    dependencies=[Depends(chaos_gate("digilocker"))],
    responses={
        400: {"description": "INVALID_GRANT: unknown, used, expired or misdirected code."},
        401: {"description": "INVALID_CLIENT: unknown client or wrong secret."},
    },
)
async def token(
    body: DigiLockerTokenRequest, request: Request, session: SessionDep
) -> DigiLockerTokenResponse:
    """Exchanges a one-time code for an id token (ES256, key at /digilocker/oauth/jwks) with
    `sub` (the DigiLocker id), `name`, `dob`, `gender`, `apaar_id` when one is linked, `nonce`,
    `iss`, `aud`, `iat` and `exp`. A code works once and for five minutes."""
    settings = _settings(request)
    if not client_ok(settings, body.client_id, body.client_secret):
        raise InvalidClient()
    row, account = await redeem_code(session, body.code, body.client_id, body.redirect_uri)
    return DigiLockerTokenResponse(
        id_token=id_token(
            request.app.state.digilocker_key, settings, account, body.client_id, row.nonce
        ),
        access_token=secrets.token_urlsafe(32),
        token_type="Bearer",
        expires_in=settings.mockgov_digilocker_token_ttl_seconds,
    )


@router.get("/jwks", response_model=DigiLockerJwks)
async def jwks(request: Request) -> DigiLockerJwks:
    """The public key set for verifying id tokens."""
    return DigiLockerJwks(keys=[request.app.state.digilocker_key.jwk()])
