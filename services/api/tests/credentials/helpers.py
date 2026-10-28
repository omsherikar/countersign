"""Shared steps for the credential API tests."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import select

from app.credentials import issuer
from app.db.session import session_factory
from app.main import app
from app.models.credential import Credential
from tests.conftest import login_as
from tests.credentials.conftest import make_countersigned, ravi_enrolment


def b64json(part: str):
    """A base64url JSON segment of a JWT or a disclosure, decoded."""
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def b64(value) -> str:
    """The base64url JSON form of a value, as a disclosure carries it."""
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


@asynccontextmanager
async def signed_in(email: str) -> AsyncIterator[httpx.AsyncClient]:
    client = await login_as(email)
    try:
        yield client
    finally:
        await client.aclose()


@asynccontextmanager
async def public() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def issue_for(enrolment_id: uuid.UUID) -> Credential:
    """Countersign the enrolment and issue its proof, committed."""
    async with session_factory()() as session:
        await make_countersigned(session, enrolment_id)
        credential = await issuer.issue_if_eligible(session, enrolment_id)
        assert credential is not None
        await session.commit()
        return credential


async def ravis_proof() -> Credential:
    async with session_factory()() as session:
        enrolment = await ravi_enrolment(session)
    return await issue_for(enrolment.id)


async def stored_presentation(presentation_id: str):
    from app.models.credential import CredentialPresentation

    async with session_factory()() as session:
        return await session.get(CredentialPresentation, uuid.UUID(presentation_id))


async def credential_row(credential_id: uuid.UUID) -> Credential:
    async with session_factory()() as session:
        return (
            await session.execute(select(Credential).where(Credential.id == credential_id))
        ).scalar_one()
