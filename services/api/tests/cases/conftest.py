"""Case test fixtures: one small world per module, flags raised through the engine's own
`raise_flag`, a login per role, a memory mailbox and a private case-files directory.

ABC College (Maharashtra, Western region) has Ravi Kumar Sharma and Asha Patil in CSE,
both seated; XYZ Institute (Tamil Nadu, Southern region) has one IT student. Every
module starts and ends with empty tables.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import session_factory
from app.engine import evidence as ev
from app.engine.flags import raise_flag
from app.engine.suite import DefaultEngines
from app.models.credential import Credential
from app.models.enums import CredentialKind, FlagStatus, FlagType, Severity, UserRole
from app.models.geo import University
from app.models.user import User
from app.models.verification import Flag
from app.notices.mailer import MailMessage, MailResult, MemoryMailer
from tests.conftest import PASSWORD, login_as, truncate_all
from tests.engines.conftest import World

DOB = date(2007, 3, 21)
RAVI_APAAR = "123456784417"
_serial = itertools.count(1)

# email, role, name, scope key, active
USERS = [
    ("admin@aicte.demo", UserRole.AICTE_ADMIN, "AICTE Administrator", None, True),
    ("senior@aicte.demo", UserRole.AICTE_ADMIN, "Senior AICTE Officer", None, True),
    ("retired@aicte.demo", UserRole.AICTE_ADMIN, "Retired AICTE Officer", None, False),
    ("ro.west@aicte.demo", UserRole.RO_OFFICER, "Regional Officer, Western", "WEST", True),
    ("deputy.west@aicte.demo", UserRole.RO_OFFICER, "Deputy Officer, Western", "WEST", True),
    ("ro.south@aicte.demo", UserRole.RO_OFFICER, "Regional Officer, Southern", "SOUTH", True),
    ("registrar@abc.edu.demo", UserRole.INSTITUTION, "Registrar, ABC College", "abc", True),
    ("office@abc.edu.demo", UserRole.INSTITUTION, "Admissions Office, ABC College", "abc", True),
    ("former@abc.edu.demo", UserRole.INSTITUTION, "Former Registrar, ABC College", "abc", False),
    ("registrar@xyz.edu.demo", UserRole.INSTITUTION, "Registrar, XYZ Institute", "xyz", True),
    ("coe@univ.demo", UserRole.UNIVERSITY, "Controller of Examinations, MSTU", "mstu", True),
    ("student@demo", UserRole.STUDENT, "Ravi Kumar Sharma", "ravi", True),
]


@dataclass
class CaseWorld:
    abc: uuid.UUID
    xyz: uuid.UUID
    cse: uuid.UUID
    it: uuid.UUID
    west: uuid.UUID
    ravi_student: uuid.UUID
    ravi: uuid.UUID
    asha: uuid.UUID
    xyz_student: uuid.UUID
    users: dict[str, uuid.UUID] = field(default_factory=dict)


@pytest.fixture(scope="module")
async def cw() -> AsyncIterator[CaseWorld]:
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
        cse = await world.programme(abc, "CSE")
        it = await world.programme(xyz, "IT", name="B.Tech Information Technology")
        ravi_student = await world.student(
            "Ravi Kumar Sharma", DOB, apaar=RAVI_APAAR, mobile="9876504521"
        )
        ravi = await world.enrol(ravi_student, cse, row_no=2)
        asha = await world.enrol(
            await world.student("Asha Patil", date(2007, 11, 2), apaar="987654320011"),
            cse,
            row_no=3,
        )
        xyz_student = await world.student("Meena Iyer", date(2007, 6, 1), apaar="222233334444")
        xyz_enrolment = await world.enrol(xyz_student, it)
        await DefaultEngines().assign_seats(
            session, [ravi.id, asha.id, xyz_enrolment.id], actor_id=None
        )
        scopes = {
            "WEST": {"region_id": world.regions["WEST"].id},
            "SOUTH": {"region_id": world.regions["SOUTH"].id},
            "abc": {"institution_id": abc.id},
            "xyz": {"institution_id": xyz.id},
            "mstu": {"university_id": mstu.id},
            "ravi": {"student_id": ravi_student.id},
        }
        hashed = hash_password(PASSWORD)
        users: dict[str, uuid.UUID] = {}
        for email, role, name, scope, active in USERS:
            user = User(
                email=email,
                password_hash=hashed,
                name=name,
                role=role,
                is_active=active,
                **(scopes[scope] if scope else {}),
            )
            session.add(user)
            await session.flush()
            users[email] = user.id
        await session.commit()
        result = CaseWorld(
            abc=abc.id,
            xyz=xyz.id,
            cse=cse.id,
            it=it.id,
            west=world.regions["WEST"].id,
            ravi_student=ravi_student.id,
            ravi=ravi.id,
            asha=asha.id,
            xyz_student=xyz_student.id,
            users=users,
        )
    yield result
    await truncate_all()


@pytest.fixture(scope="module")
async def logins(cw) -> AsyncIterator[Callable[[str], Awaitable[httpx.AsyncClient]]]:
    """`await logins(email)`: one signed-in client per user for the whole module."""
    clients: dict[str, httpx.AsyncClient] = {}

    async def _login(email: str) -> httpx.AsyncClient:
        if email not in clients:
            clients[email] = await login_as(email)
        return clients[email]

    yield _login
    for client in clients.values():
        await client.aclose()


def evidence(n: int, related: list[uuid.UUID], *, extra: str = "") -> dict:
    return {
        "summary": f"Name on upload differs from the APAAR registry (case {n}){extra}.",
        "summary_for_institution": f"The name you uploaded differs from APAAR (case {n}).",
        "facts": [
            ev.fact("Name score", "0.71", "APAAR registry"),
            ev.fact("Officer note", "checked twice", None, ev.AUDIENCE_OFFICER),
        ],
        "related_enrolment_ids": [str(i) for i in related],
        "rule_source": "APAAR registry",
    }


async def new_flag(
    cw: CaseWorld,
    *,
    institution: str = "abc",
    status: FlagStatus = FlagStatus.OPEN,
    related: list[uuid.UUID] | None = None,
) -> uuid.UUID:
    """A fresh STUDENT_DENIED-style flag on Ravi (ABC) or on the XYZ student's college."""
    n = next(_serial)
    institution_id = cw.abc if institution == "abc" else cw.xyz
    programme_id = cw.cse if institution == "abc" else cw.it
    enrolment_id = cw.ravi if institution == "abc" else None
    named = related if related is not None else ([cw.ravi] if enrolment_id else [])
    async with session_factory()() as session:
        raised = await raise_flag(
            session,
            type=FlagType.NAME_MISMATCH,
            severity=Severity.HIGH,
            institution_id=institution_id,
            programme_id=programme_id,
            enrolment_id=enrolment_id,
            academic_year="2026-27",
            dedupe_key=f"TEST:{n}",
            evidence=evidence(n, named),
            actor_id=None,
        )
        flag_id = raised.flag.id
        if status is not FlagStatus.OPEN:
            await session.execute(update(Flag).where(Flag.id == flag_id).values(status=status))
        await session.commit()
    return flag_id


async def set_status(flag_id: uuid.UUID, status: FlagStatus, **values) -> None:
    async with session_factory()() as session:
        await session.execute(
            update(Flag).where(Flag.id == flag_id).values(status=status, **values)
        )
        await session.commit()


async def load_flag(flag_id: uuid.UUID) -> Flag:
    async with session_factory()() as session:
        return (await session.execute(select(Flag).where(Flag.id == flag_id))).scalar_one()


async def add_credential(student_id: uuid.UUID, enrolment_id: uuid.UUID) -> uuid.UUID:
    """A stored credential row standing in for an issued enrolment proof."""
    n = next(_serial)
    async with session_factory()() as session:
        credential = Credential(
            student_id=student_id,
            enrolment_id=enrolment_id,
            kind=CredentialKind.ENROLMENT,
            sd_jwt="eyJhbGciOiJFUzI1NiJ9.e30.c2ln~",
            status_list_index=1000 + n,
            issuer_key_id="test-kid",
            vct="countersign:enrolment:v1",
            short_id=f"TEST{n:04d}",
        )
        session.add(credential)
        await session.commit()
        return credential.id


class FailingMailer:
    def send_many(self, messages: list[MailMessage]) -> list[MailResult]:
        raise ConnectionRefusedError("mail server down")


@pytest.fixture
def mailbox(monkeypatch) -> MemoryMailer:
    """Every REQUEST_DOCS email lands here instead of Mailpit."""
    box = MemoryMailer()
    monkeypatch.setattr("app.routers.cases.build_mailer", lambda: box)
    return box


@pytest.fixture
def case_files(tmp_path, monkeypatch) -> Path:
    directory = tmp_path / "case-files"
    monkeypatch.setattr(get_settings(), "case_files_dir", str(directory))
    return directory


def stored_files(directory: Path) -> list[Path]:
    return sorted(directory.iterdir()) if directory.exists() else []
