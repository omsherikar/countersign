"""Decision test fixtures: small worlds built with the ORM per test, signed-in clients, a
stand-in state admission authority, and helpers for rows, cases and attestations.

ABC College of Engineering (Maharashtra, Western region) has B.Tech CSE with an intake of 20
for 2026-27 (19 Regular seats and 1 NRI seat); XYZ Institute (Tamil Nadu, Southern region)
has IT. Every test starts and ends with empty tables.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update

from app.adapters.base import SourceUnavailable
from app.core.security import hash_password
from app.db.session import session_factory
from app.engine import checks
from app.engine.contracts import PoolRef
from app.engine.flags import raise_flag, refresh_seat_flags
from app.engine.ledger import assign_seats
from app.models.credential import Credential
from app.models.enums import (
    AdmissionRoute,
    CheckStatus,
    CheckType,
    CredentialKind,
    FlagType,
    SeatType,
    Severity,
    UserRole,
)
from app.models.geo import University
from app.models.institution import Approval, Programme
from app.models.seat import SeatPool
from app.models.student import Enrolment
from app.models.user import User
from app.models.verification import Check, Flag
from tests.conftest import PASSWORD, login_as, truncate_all
from tests.engines.conftest import World, adapters

_serial = itertools.count(1)

USERS = [
    ("admin@aicte.demo", UserRole.AICTE_ADMIN, "AICTE Administrator", None),
    ("ro.west@aicte.demo", UserRole.RO_OFFICER, "Regional Officer, Western", "WEST"),
    ("ro.south@aicte.demo", UserRole.RO_OFFICER, "Regional Officer, Southern", "SOUTH"),
    ("registrar@abc.edu.demo", UserRole.INSTITUTION, "Registrar, ABC College", "abc"),
    ("registrar@xyz.edu.demo", UserRole.INSTITUTION, "Registrar, XYZ Institute", "xyz"),
    ("coe@univ.demo", UserRole.UNIVERSITY, "Controller of Examinations, MSTU", "mstu"),
]


@dataclass
class DecisionWorld:
    abc: uuid.UUID
    xyz: uuid.UUID
    cse: uuid.UUID
    approval: uuid.UUID
    users: dict[str, uuid.UUID] = field(default_factory=dict)
    clients: dict[str, httpx.AsyncClient] = field(default_factory=dict)

    async def login(self, email: str) -> httpx.AsyncClient:
        if email not in self.clients:
            self.clients[email] = await login_as(email)
        return self.clients[email]


@pytest.fixture
async def dw() -> AsyncIterator[DecisionWorld]:
    await truncate_all()
    async with session_factory()() as session:
        world = World(session)
        mh = await world.state("MH", "Maharashtra", "WEST")
        mstu = University(
            code="MSTU", name="Maharashtra State Technical University", state_id=mh.id
        )
        session.add(mstu)
        await session.flush()
        abc = await world.institution("ABC College of Engineering", "1-ABC-0001", university=mstu)
        xyz = await world.institution(
            "XYZ Institute of Technology", "1-XYZ-0002", "TN", "Tamil Nadu", "SOUTH"
        )
        cse = await world.programme(abc, "CSE", intakes={"2026-27": 20})
        await world.programme(xyz, "IT", name="B.Tech Information Technology")
        approval = (
            await session.execute(select(Approval.id).where(Approval.programme_id == cse.id))
        ).scalar_one()
        scopes = {
            "WEST": {"region_id": world.regions["WEST"].id},
            "SOUTH": {"region_id": world.regions["SOUTH"].id},
            "abc": {"institution_id": abc.id},
            "xyz": {"institution_id": xyz.id},
            "mstu": {"university_id": mstu.id},
        }
        hashed = hash_password(PASSWORD)
        users: dict[str, uuid.UUID] = {}
        for email, role, name, scope in USERS:
            user = User(
                email=email,
                password_hash=hashed,
                name=name,
                role=role,
                **(scopes[scope] if scope else {}),
            )
            session.add(user)
            await session.flush()
            users[email] = user.id
        await session.commit()
    out = DecisionWorld(abc=abc.id, xyz=xyz.id, cse=cse.id, approval=approval, users=users)
    yield out
    for client in out.clients.values():
        await client.aclose()
    await truncate_all()


async def cohort(
    dw: DecisionWorld,
    n: int,
    *,
    route: AdmissionRoute = AdmissionRoute.COUNSELLING,
    seat: bool = True,
    rows: bool = True,
) -> list[uuid.UUID]:
    """n ABC CSE first-years in admission order, seated by the ledger and with their five
    rows evaluated against the in-memory sources."""
    async with session_factory()() as session:
        world = World(session)
        programme = await session.get(Programme, dw.cse)
        enrolments = await world.cohort(programme, n, route=route, prefix=f"Cohort{next(_serial)}")
        ids = [e.id for e in enrolments]
        if seat:
            await assign_seats(session, ids, actor_id=None)
        if rows:
            await checks.run_checks(session, ids, adapters())
        await session.commit()
    return ids


async def raise_case(
    dw: DecisionWorld,
    type: FlagType,
    *,
    enrolment_id: uuid.UUID | None,
    related: Sequence[uuid.UUID] = (),
    institution_id: uuid.UUID | None = None,
    severity: Severity = Severity.MEDIUM,
) -> uuid.UUID:
    n = next(_serial)
    named = [i for i in [enrolment_id, *related] if i is not None]
    async with session_factory()() as session:
        raised = await raise_flag(
            session,
            type=type,
            severity=severity,
            institution_id=institution_id or dw.abc,
            programme_id=dw.cse if institution_id in (None, dw.abc) else None,
            enrolment_id=enrolment_id,
            academic_year="2026-27",
            dedupe_key=f"TEST:{type.value}:{n}",
            evidence={
                "summary": f"Test case {n}.",
                "facts": [],
                "related_enrolment_ids": [str(i) for i in named],
                "rule_source": "Test",
            },
            actor_id=None,
        )
        await session.commit()
        return raised.flag.id


async def set_row(enrolment_id: uuid.UUID, row: CheckType, state: CheckStatus) -> None:
    async with session_factory()() as session:
        await session.execute(
            update(Check)
            .where(Check.enrolment_id == enrolment_id, Check.type == row)
            .values(status=state, resolved=None)
        )
        await session.commit()


async def row_of(enrolment_id: uuid.UUID, row: CheckType) -> Check:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(Check).where(Check.enrolment_id == enrolment_id, Check.type == row)
            )
        ).scalar_one()


async def enrolment(enrolment_id: uuid.UUID) -> Enrolment:
    async with session_factory()() as session:
        return await session.get(Enrolment, enrolment_id)


async def flag(flag_id: uuid.UUID) -> Flag:
    async with session_factory()() as session:
        return await session.get(Flag, flag_id)


async def attestation(enrolment_id: uuid.UUID) -> uuid.UUID:
    """A stored enrolment attestation standing in for an issued one."""
    n = next(_serial)
    async with session_factory()() as session:
        record = await session.get(Enrolment, enrolment_id)
        credential = Credential(
            student_id=record.student_id,
            enrolment_id=enrolment_id,
            kind=CredentialKind.ENROLMENT,
            sd_jwt="eyJhbGciOiJFUzI1NiJ9.e30.c2ln~",
            status_list_index=5000 + n,
            issuer_key_id="test-kid",
            vct="countersign:enrolment:v1",
            short_id=f"DEC{n:05d}",
        )
        session.add(credential)
        await session.commit()
        return credential.id


async def excess_case(dw: DecisionWorld) -> uuid.UUID:
    """The EXCESS_ADMISSION case of ABC CSE 2026-27, raised by the seat flags engine."""
    async with session_factory()() as session:
        await refresh_seat_flags(
            session,
            [PoolRef(approval_id=dw.approval, seat_type=SeatType.REGULAR)],
            actor_id=None,
        )
        await session.commit()
        return (
            await session.execute(select(Flag.id).where(Flag.type == FlagType.EXCESS_ADMISSION))
        ).scalar_one()


async def regular_pool(dw: DecisionWorld) -> SeatPool:
    async with session_factory()() as session:
        return (
            await session.execute(
                select(SeatPool).where(
                    SeatPool.approval_id == dw.approval, SeatPool.seat_type == SeatType.REGULAR
                )
            )
        ).scalar_one()


def decide(action: str, reason: str, **extra: Any) -> dict[str, Any]:
    return {"action": action, "reason_code": reason, "note": "Decided on the documents.", **extra}


# ------------------------------------------------------------- admission authority


@dataclass(frozen=True)
class FakeJoining:
    roll_no: str | None
    name: str
    dob: date
    programme: str
    joined_on: date
    round: int | None = 1
    route: str = "COUNSELLING"
    category: str = "GENERAL"
    apaar_last4: str | None = None


class FakeAuthority:
    """The joinings list of ENGINES §17.4, by (institution code, academic year)."""

    def __init__(self) -> None:
        self.lists: dict[tuple[str, str], list[FakeJoining]] = {}
        self.published: set[tuple[str, str]] = set()
        self.down = False
        self.calls = 0

    def publish(self, code: str, year: str, items: list[FakeJoining]) -> None:
        self.lists[(code, year)] = items
        self.published.add((code, year))

    async def joinings(self, *, institution_code: str, academic_year: str) -> Any:
        self.calls += 1
        if self.down:
            raise SourceUnavailable("admission_authority", "timeout")
        key = (institution_code, academic_year)
        return SimpleNamespace(published=key in self.published, items=self.lists.get(key, []))


def authority_adapters(authority: FakeAuthority) -> Any:
    async def aclose() -> None:
        return None

    return SimpleNamespace(name="test", admission_authority=authority, aclose=aclose)
