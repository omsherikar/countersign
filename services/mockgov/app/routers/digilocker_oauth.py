"""Demo DigiLocker sign-in: an OAuth code flow over synthetic accounts (API_CONTRACT C.11, C.12).

    GET  /digilocker/oauth/authorize?response_type=code&client_id&redirect_uri&scope=openid
         &state&nonce[&q]
         a plain page, "Demo DigiLocker. A simulator for the Countersign demo, not the real
         DigiLocker.": the synthetic accounts (the demo accounts first, Ravi Kumar Sharma at
         the top; `q` searches by DigiLocker id, APAAR, its last four digits or name), an OTP
         field and a Cancel link (`&cancel=1`: 302 to redirect_uri?error=access_denied&state)
    POST /digilocker/oauth/authorize (form: those parameters, `account`, `otp`)
         `account` is a DigiLocker id or an APAAR; the OTP is always 123456. A wrong OTP or an
         unknown account shows the page again (200); success stores a one-time code (60
         seconds) and answers 302 to redirect_uri?code&state
    POST /digilocker/oauth/token (form: grant_type, code, redirect_uri, client_id,
         client_secret)
         {access_token, token_type, expires_in, scope, id_token}; OAuth errors
         {error, error_description}

The client id and redirect URI must be DIGILOCKER_CLIENT_ID and one of
DIGILOCKER_REDIRECT_URIS, else a 400 page and no redirect. Not the real DigiLocker and labelled
so on every page; the pages are self-contained (inline CSS, no scripts), escape every value
and let a form go only to this service and the caller's origin. None of these routes is behind
the chaos gate: sign-in works while the "DigiLocker" notices are switched off.
"""

from __future__ import annotations

import re
import secrets
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select

from app.config import Settings
from app.db import SessionDep
from app.digilocker_signin import (
    DEMO_OTP,
    INVALID_CLIENT,
    OAuthError,
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

router = APIRouter(prefix="/digilocker/oauth", tags=["digilocker sign-in (simulated)"])

HEADING = "Demo DigiLocker. A simulator for the Countersign demo, not the real DigiLocker."
UNKNOWN_CLIENT = "Unknown client or redirect address."
MAX_RESULTS = 20
LAST4 = re.compile(r"[0-9]{4}")
APAAR12 = re.compile(r"[0-9]{12}")
SAFE_ORIGIN = re.compile(r"https?://[A-Za-z0-9.\-:\[\]]+")
PARAMS = ("response_type", "client_id", "redirect_uri", "scope", "state", "nonce")
LIMITS = {"redirect_uri": 2000, "state": 500, "nonce": 500, "q": 100, "account": 40, "otp": 20}
SIGNIN_STYLE = """
.who { margin: 1rem 0 0; color: var(--muted); }
.accounts label { display: flex; gap: 0.625rem; align-items: baseline; width: auto;
  font-weight: 400; cursor: pointer; }
.accounts input { flex: 0 0 auto; }
.accounts .meta { color: var(--muted); font-size: 0.875rem; }
.otp-hint { color: var(--demo); font-weight: 600; }
.cancel { display: inline-block; margin-top: 0.75rem; color: inherit; }
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
<h1>{escape(HEADING)}</h1>
<p class="note">Every account here is synthetic, made for the Countersign demo, and no message
or OTP is ever sent.</p>
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


def _hidden(params: dict[str, str]) -> str:
    return "".join(
        f'<input type="hidden" name="{escape(k)}" value="{escape(v)}">'
        for k, v in params.items()
        if v
    )


def _clip(values: dict[str, str]) -> dict[str, str]:
    return {k: v[: LIMITS.get(k, 200)] for k, v in values.items()}


def _request_problem(settings: Settings, params: dict[str, str]) -> str | None:
    if not client_ok(settings, params["client_id"]):
        return UNKNOWN_CLIENT
    if not redirect_allowed(settings, params["redirect_uri"]):
        return UNKNOWN_CLIENT
    if params["response_type"] not in {"", "code"}:
        return "Only response_type=code is supported."
    return None


def _error_page(reason: str) -> HTMLResponse:
    return _html(
        f'<h2>This sign-in request cannot continue</h2><p class="error">{escape(reason)}</p>'
        '<p class="muted">Go back to the service you came from and start again.</p>',
        status_code=400,
    )


def _apaar_label(account: DigiLockerAccount) -> str:
    if account.apaar_id:
        return f"APAAR XXXX XXXX {account.apaar_id[-4:]}"
    return "No APAAR linked"


async def _find(session, account: str) -> DigiLockerAccount | None:
    """An account by DigiLocker id or by APAAR."""
    value = account.strip()
    if APAAR12.fullmatch(value):
        return await session.scalar(
            select(DigiLockerAccount).where(DigiLockerAccount.apaar_id == value)
        )
    return await session.get(DigiLockerAccount, value.upper()) if value else None


async def _list(session, q: str) -> list[DigiLockerAccount]:
    stmt = select(DigiLockerAccount)
    q = q.strip()
    if not q:
        pass
    elif APAAR12.fullmatch(q):
        stmt = stmt.where(DigiLockerAccount.apaar_id == q)
    elif LAST4.fullmatch(q):
        stmt = stmt.where(DigiLockerAccount.apaar_last4 == q)
    elif q.upper().startswith("DL-"):
        stmt = stmt.where(DigiLockerAccount.digilocker_id == q.upper())
    else:
        tokens = normalize_name(q).split()
        if not tokens:
            return []
        for token in tokens:  # letters and digits only after normalising
            stmt = stmt.where(DigiLockerAccount.name_normalized.contains(token))
    stmt = stmt.order_by(DigiLockerAccount.position, DigiLockerAccount.digilocker_id)
    return list(await session.scalars(stmt.limit(MAX_RESULTS + 1)))


def _account_item(account: DigiLockerAccount, checked: bool) -> str:
    value = escape(account.digilocker_id)
    meta = f"{value} · {escape(_apaar_label(account))}"
    return (
        f'<li><label><input type="radio" name="account" value="{value}"'
        f"{' checked' if checked else ''}><span><strong>{escape(account.name)}</strong> "
        f'<span class="meta">{meta}</span></span></label></li>'
    )


def _signin_page(
    params: dict[str, str],
    accounts: list[DigiLockerAccount],
    q: str = "",
    chosen: str = "",
    error: str = "",
) -> str:
    cancel = with_query("authorize", **params, cancel="1")
    message = f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    if accounts:
        shown = accounts[:MAX_RESULTS]
        more = (
            f'<p class="muted">Showing the first {MAX_RESULTS}; search to narrow the list.</p>'
            if len(accounts) > MAX_RESULTS
            else ""
        )
        first = chosen or shown[0].digilocker_id
        items = "\n".join(_account_item(a, a.digilocker_id == first) for a in shown)
        listing = f'{more}<ol class="accounts">\n{items}\n</ol>'
    else:
        listing = '<p class="muted">No synthetic account matches.</p>'
    client = escape(params["client_id"])
    return f"""<p class="who">Countersign (client <code>{client}</code>) asks for your name, date
of birth, gender and APAAR id.</p>
<form method="get" action="authorize">
{_hidden(params)}
<label for="q">Find an account by DigiLocker id or APAAR</label>
<input id="q" name="q" value="{escape(q)}" maxlength="100" autocomplete="off">
<button type="submit">Search</button>
</form>
{message}
<form method="post" action="authorize">
{_hidden(params)}{_hidden({"q": q})}
<h2>Synthetic accounts</h2>
{listing}
<label for="otp">One-time password</label>
<input id="otp" name="otp" inputmode="numeric" autocomplete="one-time-code" maxlength="6"
  required>
<button type="submit">Sign in</button>
</form>
<p class="otp-hint">Demo OTP: {DEMO_OTP}. No message is sent.</p>
<a class="cancel" href="{escape(cancel)}">Cancel</a>"""


@router.get("/authorize", response_class=HTMLResponse)
async def authorize_page(request: Request, session: SessionDep):
    """The sign-in page; with `cancel=1`, back to the caller with error=access_denied."""
    query = request.query_params
    params = _clip({k: query.get(k, "") for k in PARAMS})
    problem = _request_problem(_settings(request), params)
    if problem:
        return _error_page(problem)
    if query.get("cancel"):
        return RedirectResponse(
            with_query(params["redirect_uri"], error="access_denied", state=params["state"]),
            status_code=302,
            headers={"Cache-Control": "no-store"},
        )
    q = query.get("q", "")[: LIMITS["q"]]
    content = _signin_page(params, await _list(session, q), q=q)
    return _html(content, form_origin=origin_of(params["redirect_uri"]))


@router.post("/authorize", response_class=HTMLResponse)
async def authorize_submit(request: Request, session: SessionDep):
    """Checks the account and the demo OTP; on success sends the browser back with a code."""
    settings = _settings(request)
    form = await request.form()
    fields = _clip({k: str(form.get(k) or "") for k in (*PARAMS, "q", "account", "otp")})
    params = {k: fields[k] for k in PARAMS}
    problem = _request_problem(settings, params)
    if problem:
        return _error_page(problem)
    origin = origin_of(params["redirect_uri"])
    found = await _find(session, fields["account"])
    q = fields["q"]
    if found is None:
        content = _signin_page(params, await _list(session, q), q=q, error="No such account.")
        return _html(content, form_origin=origin)
    if not secrets.compare_digest(fields["otp"].strip().encode(), DEMO_OTP.encode()):
        accounts = await _list(session, q)
        if all(a.digilocker_id != found.digilocker_id for a in accounts[:MAX_RESULTS]):
            accounts = [found, *accounts]
        content = _signin_page(
            params, accounts, q=q, chosen=found.digilocker_id, error="Wrong OTP."
        )
        return _html(content, form_origin=origin)
    code = await issue_code(
        session,
        settings,
        account=found,
        client_id=params["client_id"],
        redirect_uri=params["redirect_uri"],
        nonce=params["nonce"],
    )
    return RedirectResponse(
        with_query(params["redirect_uri"], code=code, state=params["state"]),
        status_code=302,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def _oauth_error(status_code: int, error: str, description: str) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@router.post(
    "/token",
    responses={
        400: {"description": "invalid_grant: the code is unknown, expired or used."},
        401: {"description": "invalid_client: unknown client or wrong secret."},
    },
)
async def token(request: Request, session: SessionDep) -> JSONResponse:
    """Exchanges a one-time code (form-encoded request) for an id token signed HS256 with the
    client secret: `iss`, `sub` (the DigiLocker id), `aud`, `iat`, `exp`, `nonce`, `name`,
    `birthdate`, `gender` and `apaar_id` (null when none is linked). A code works once."""
    settings = _settings(request)
    form = await request.form()
    field = {k: str(form.get(k) or "") for k in (
        "grant_type", "code", "redirect_uri", "client_id", "client_secret",
    )}  # fmt: skip
    if not client_ok(settings, field["client_id"], field["client_secret"]):
        return _oauth_error(*INVALID_CLIENT)
    if field["grant_type"] != "authorization_code":
        return _oauth_error(400, "unsupported_grant_type", "Use grant_type=authorization_code.")
    if not field["code"] or not field["redirect_uri"]:
        return _oauth_error(400, "invalid_request", "code and redirect_uri are required.")
    try:
        row, account = await redeem_code(
            session, field["code"][:256], field["client_id"], field["redirect_uri"]
        )
    except OAuthError as exc:
        return _oauth_error(exc.status_code, exc.error, exc.description)
    return JSONResponse(
        {
            "access_token": f"dl_at_{secrets.token_urlsafe(32)}",
            "token_type": "Bearer",
            "expires_in": settings.digilocker_token_ttl_seconds,
            "scope": "openid",
            "id_token": id_token(settings, account, field["client_id"], row.nonce),
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )
