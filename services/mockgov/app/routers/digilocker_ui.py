"""GET /digilocker/ui: a plain HTML window on the mock DigiLocker inbox, for the demo.

Not the real DigiLocker, and it says so in its header: no DigiLocker branding, synthetic
data only. The page is self-contained (inline CSS, no scripts, nothing loaded from
elsewhere), escapes every value it shows, and offers a Respond link only for an http(s)
callback URL. Opening it marks nothing read. It sits outside the chaos gate: chaos simulates
the government API for the Countersign api, while this page is how the demo looks at what was
delivered.
"""

import re
from datetime import UTC, datetime, timedelta, timezone
from html import escape
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.db import SessionDep
from app.models import ApaarRecord, DigiLockerMessage

router = APIRouter(prefix="/digilocker", tags=["digilocker"])

IST = timezone(timedelta(hours=5, minutes=30), "IST")
APAAR_DIGITS = re.compile(r"[0-9]{12}")
SEPARATORS = re.compile(r"[\s-]+")
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}

STYLE = """
:root { --bg: #f4f4f1; --card: #ffffff; --ink: #1f2328; --muted: #5c6168; --line: #d5d6d2;
  --demo: #8a5a00; --demo-bg: #fff4d6; --button: #1f2328; --button-ink: #ffffff; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #17181a; --card: #202225; --ink: #e8e8e6; --muted: #a3a6ab; --line: #35373b;
    --demo: #f2c46b; --demo-bg: #3a2f17; --button: #e8e8e6; --button-ink: #17181a; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
.wrap { max-width: 42rem; margin: 0 auto; padding: 1.25rem 1rem 3rem; }
header { border: 2px dashed var(--demo); background: var(--demo-bg); border-radius: 8px;
  padding: 0.75rem 1rem; }
header h1 { margin: 0; font-size: 1.25rem; }
header .tag { margin: 0.125rem 0 0; color: var(--demo); font-weight: 600; }
header .note { margin: 0.25rem 0 0; color: var(--muted); font-size: 0.875rem; }
form { display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: end; margin: 1.25rem 0; }
label { width: 100%; font-weight: 600; }
input { flex: 1 1 12rem; min-width: 0; padding: 0.5rem 0.625rem; font: inherit;
  border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--ink); }
button, .respond { display: inline-block; padding: 0.5rem 1rem; border: 0; border-radius: 6px;
  background: var(--button); color: var(--button-ink); font: inherit; font-weight: 600;
  text-decoration: none; cursor: pointer; }
h2 { font-size: 1.0625rem; margin: 1.5rem 0 0.25rem; }
.muted { color: var(--muted); margin: 0 0 0.75rem; }
.error { color: #b42318; font-weight: 600; }
ol { list-style: none; margin: 0; padding: 0; }
li { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 0.875rem 1rem; margin: 0 0 0.75rem; }
li time { color: var(--muted); font-size: 0.875rem; }
li .text { margin: 0.375rem 0 0.75rem; white-space: pre-wrap; overflow-wrap: anywhere; }
"""


def _when(received_at: datetime) -> tuple[str, str]:
    """ISO UTC for the datetime attribute and "28 Oct 2026, 15:00 IST" to read."""
    utc = received_at.astimezone(UTC)
    local = utc.astimezone(IST)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{local.day} {local:%b %Y, %H:%M} IST"


def _message(row: DigiLockerMessage) -> str:
    iso, shown = _when(row.received_at)
    url = row.callback_url.strip()
    if url.lower().startswith(("http://", "https://")):
        action = f'<a class="respond" href="{escape(url)}" rel="noreferrer">Respond</a>'
    else:
        action = '<p class="muted">This message has no reply link.</p>'
    return (
        f'<li><time datetime="{iso}">{escape(shown)}</time>'
        f'<p class="text">{escape(row.message)}</p>{action}</li>'
    )


def _page(content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Mock DigiLocker inbox</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<header>
<h1>Mock DigiLocker</h1>
<p class="tag">Demo DigiLocker inbox, synthetic data</p>
<p class="note">Not the real DigiLocker. Notices here come from the Countersign demo and are
addressed to synthetic students.</p>
</header>
<main>
<form method="get">
<label for="apaar_id">APAAR number</label>
<input id="apaar_id" name="apaar_id" inputmode="numeric" autocomplete="off"
  placeholder="12 digits" required>
<button type="submit">Open inbox</button>
</form>
{content}
</main>
</div>
</body>
</html>
"""


def _html(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(_page(content), status_code=status_code, headers=HEADERS)


@router.get("/ui", response_class=HTMLResponse)
async def inbox_page(
    session: SessionDep,
    apaar_id: Annotated[str | None, Query(max_length=64)] = None,
) -> HTMLResponse:
    """The form, and with `apaar_id` that id's messages, newest first."""
    if apaar_id is None or not apaar_id.strip():
        return _html("")
    apaar = SEPARATORS.sub("", apaar_id)
    if not APAAR_DIGITS.fullmatch(apaar):
        return _html('<p class="error">Enter the 12-digit APAAR number.</p>', status_code=422)

    rows = list(
        await session.scalars(
            select(DigiLockerMessage)
            .where(DigiLockerMessage.apaar_id == apaar)
            .order_by(DigiLockerMessage.received_at.desc(), DigiLockerMessage.inbox_id.desc())
        )
    )
    heading = f"<h2>Inbox for APAAR XXXX XXXX {apaar[-4:]}</h2>"
    if not rows:
        if await session.get(ApaarRecord, apaar) is None:
            note = "No DigiLocker account is linked to this APAAR number."
        else:
            note = "No messages yet."
        return _html(f'{heading}<p class="muted">{note}</p>')
    count = "1 message" if len(rows) == 1 else f"{len(rows)} messages"
    items = "\n".join(_message(row) for row in rows)
    return _html(f'{heading}<p class="muted">{count}, newest first</p>\n<ol>\n{items}\n</ol>')
