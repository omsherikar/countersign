"""Identity test wiring: the notices world, synthetic DigiLocker accounts, and helpers that
walk a browser through the sign-in.

`identity_rerun` stands in for the evidence rows' `checks.rerun(types=[IDENTITY])` while
that function is not in place: it writes the Identity row a DigiLocker claim gives
(API_CONTRACT §A4.4, basis DIGILOCKER_CLAIM) and nothing else. Once the real function
exists the stand-in is not installed and the real evaluator runs.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select

from app.auth import digilocker
from app.core.crypto import decrypt
from app.core.security import COOKIE_NAME, create_access_token
from app.db.session import session_factory
from app.engine import checks, status
from app.main import app
from app.models.enums import CheckStatus, CheckType
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Check
from tests.notices.conftest import (  # noqa: F401  (fixtures used by the tests here)
    World,
    clients,
    db,
    gov,
    mailer,
    no_pauses,
    public,
    world,
)

CLAIM_SUPPLIED_BY = "Student via DigiLocker sign-in"


async def _identity_rerun(
    session,
    enrolment_ids: Sequence[uuid.UUID],
    adapters: Any,
    *,
    types: Sequence[CheckType] = (CheckType.IDENTITY,),
    actor_id: uuid.UUID | None = None,
    **_: Any,
) -> None:
    now = datetime.now(UTC)
    for enrolment_id in enrolment_ids:
        enrolment = await session.get(Enrolment, enrolment_id)
        student = await session.get(Student, enrolment.student_id)
        if CheckType.IDENTITY not in types or not await digilocker.is_claimed(session, student):
            continue
        row = (
            await session.execute(
                select(Check).where(
                    Check.enrolment_id == enrolment_id, Check.type == CheckType.IDENTITY
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = Check(enrolment_id=enrolment_id, type=CheckType.IDENTITY, source="DIGILOCKER")
            session.add(row)
        row.status = CheckStatus.CONFIRMED
        row.source = "DIGILOCKER"
        row.detail = {
            "basis": "DIGILOCKER_CLAIM",
            "summary": "Claimed by the student after DigiLocker sign-in.",
            "finding": None,
            "source_line": CLAIM_SUPPLIED_BY,
            "claimed_at": now.isoformat(),
        }
        row.checked_at = now
        row.supplied_by = CLAIM_SUPPLIED_BY
        row.observed_at = now
        row.independent = True
        row.resolved = None
    await session.flush()
    status.mark(session, enrolment_ids)


@pytest.fixture(autouse=True)
def identity_rerun(monkeypatch) -> None:
    if not hasattr(checks, "rerun"):
        monkeypatch.setattr(checks, "rerun", _identity_rerun, raising=False)


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def as_user(user: User) -> httpx.AsyncClient:
    c = client()
    c.cookies.set(COOKIE_NAME, create_access_token(user.id, user.role.value))
    return c


def add_account(
    adapters, digilocker_id: str, name: str, dob: date, apaar_id: str | None = None
) -> str:
    """A synthetic account of the in-memory DigiLocker, as datagen writes them."""
    adapters.digilocker.accounts[digilocker_id] = {
        "name": name,
        "dob": dob,
        "gender": "F",
        "apaar_id": apaar_id,
    }
    return digilocker_id


def query_of(location: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}


async def start(c: httpx.AsyncClient, next_path: str | None = None) -> dict[str, str]:
    params = {"next": next_path} if next_path is not None else {}
    response = await c.get("/auth/digilocker/start", params=params)
    assert response.status_code == 302, response.text
    return query_of(response.headers["location"])


async def sign_in(
    c: httpx.AsyncClient, adapters, account: str, next_path: str | None = None
) -> httpx.Response:
    """Start, choose the account on the demo page (OTP 123456), come back with the code."""
    sent = await start(c, next_path)
    code = adapters.digilocker.sign_in(
        account, redirect_uri=sent["redirect_uri"], nonce=sent["nonce"]
    )
    return await c.get("/auth/digilocker/callback", params={"code": code, "state": sent["state"]})


def pending_client(name: str, dob: date, *, sub: str | None = None, next_path: str = "/student"):
    """A browser holding a pending claim, as the callback leaves one."""
    c = client()
    identity = digilocker.DigiLockerIdentity(
        sub=sub or f"DL-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}",
        name=name,
        birthdate=dob,
    )
    c.cookies.set(digilocker.CLAIM_COOKIE, digilocker.claim_cookie(identity, next_path))
    return c


async def write_rows(enrolment_id: uuid.UUID, rows: dict[CheckType, tuple[str, str, bool]]) -> None:
    """Rows as the engine writes them: {type: (state, supplied_by, independent)}, then the
    record's status."""
    now = datetime.now(UTC)
    async with session_factory()() as s:
        for check_type, (state, supplied_by, independent) in rows.items():
            s.add(
                Check(
                    enrolment_id=enrolment_id,
                    type=check_type,
                    status=CheckStatus(state),
                    source="TEST",
                    detail={"summary": "Set by a test.", "finding": None, "source_line": ""},
                    checked_at=now,
                    supplied_by=supplied_by,
                    observed_at=now if supplied_by else None,
                    independent=independent,
                )
            )
        await s.flush()
        await status.refresh(s, [enrolment_id], issue=False)
        await s.commit()


# a record without APAAR whose seat fits and whose joining record was found: only the
# alternative identity route is missing (D36)
UNCLAIMED_ROWS = {
    CheckType.IDENTITY: ("NOT_APPLICABLE", "", False),
    CheckType.SEAT: ("CONFIRMED", "AICTE approval v1, 2026-27 (Seat Ledger, derived)", False),
    CheckType.ADMISSION: ("CONFIRMED", "State admission authority", True),
}
# a linked record confirmed by the registry, its seat and the joining record
COUNTERSIGNED_ROWS = {
    CheckType.IDENTITY: ("CONFIRMED", "APAAR registry", True),
    CheckType.SEAT: ("CONFIRMED", "AICTE approval v1, 2026-27 (Seat Ledger, derived)", False),
    CheckType.ADMISSION: ("CONFIRMED", "State admission authority", True),
}


async def student_of(enrolment: Enrolment) -> Student:
    async with session_factory()() as s:
        return await s.get(Student, enrolment.student_id)


async def apaar_of(enrolment: Enrolment) -> str:
    """The student's APAAR, decrypted (as only the registry and the token carry it)."""
    student = await student_of(enrolment)
    assert student.apaar_encrypted is not None
    return decrypt(student.apaar_encrypted)


async def user_of(student_id: uuid.UUID) -> User | None:
    async with session_factory()() as s:
        return (
            await s.execute(select(User).where(User.student_id == student_id))
        ).scalar_one_or_none()


@pytest.fixture
async def clients_closed() -> AsyncIterator[list[httpx.AsyncClient]]:
    """Clients a test opens, closed at the end."""
    opened: list[httpx.AsyncClient] = []
    yield opened
    for c in opened:
        await c.aclose()
