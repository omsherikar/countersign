"""Signal test worlds: forty colleges in two regions, built straight with the ORM.

`ring_world` plants one shared contact ring of 40 students across three colleges (two in the
West, one in the South). `anomaly_world` plants two colleges that stand out: one admits about
three times its previous cohort, one fills its first year through the NRI and management
routes. Every other college is ordinary, with a little variation. Tests start and end with
empty tables so the shared `seeded` fixture imports its own data when a later test asks.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date

import httpx
import pytest

from app.core import crypto
from app.core.cohort import cohort_year
from app.core.security import COOKIE_NAME, create_access_token, hash_password
from app.db.session import session_factory
from app.engine import matching
from app.main import app
from app.models.enums import (
    AdmissionRoute,
    Category,
    ConsentStatus,
    Discipline,
    EnrolmentStatus,
    InstitutionType,
    ProgrammeLevel,
    ProgrammeMode,
    Shift,
    UserRole,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.student import Enrolment, Student
from app.models.user import User
from tests.conftest import PASSWORD, truncate_all

YEAR = "2026-27"
COLLEGES = 40
RING_COLLEGES = (0, 1, 20)  # two in Maharashtra (WEST), one in Karnataka (SOUTH)
SPIKE_COLLEGE = 9
SHARE_COLLEGE = 29


@dataclass
class SignalWorld:
    institutions: list[Institution] = field(default_factory=list)
    enrolments: dict[uuid.UUID, list[Enrolment]] = field(default_factory=dict)
    ring: list[Enrolment] = field(default_factory=list)
    users: dict[str, User] = field(default_factory=dict)

    def college(self, index: int) -> Institution:
        return self.institutions[index]


_serial = iter(range(1, 10_000_000))


def _student(n: int, *, mobile: str, email: str, address: str, apaar: bool = True) -> Student:
    name = f"Signal Student {n:05d}"
    dob = date(2006, 1, 1)
    apaar_id = f"5{n:011d}" if apaar else None
    return Student(
        id=uuid.uuid4(),
        name=name,
        name_normalized=matching.normalise_name(name),
        dob=dob,
        consent_status=ConsentStatus.LINKED if apaar_id else ConsentStatus.PENDING,
        apaar_hmac=crypto.hmac_bytes(apaar_id, "apaar") if apaar_id else None,
        apaar_last4=apaar_id[-4:] if apaar_id else None,
        provisional_id=None if apaar_id else f"PRV-S{n:07d}",
        mobile_hmac=crypto.hmac_bytes(mobile, "mobile"),
        mobile_last4=mobile[-4:],
        email=email,
        address_hmac=crypto.hmac_bytes(address, "address"),
    )


def _plan(index: int, rng: random.Random, *, anomalies: bool) -> list[tuple[int, AdmissionRoute]]:
    """(year of study, route) per record of one college."""
    first = 15 + rng.randint(0, 3)
    second = 13 + rng.randint(0, 2)
    management = 2 + rng.randint(0, 2)
    nri = rng.randint(0, 1)
    if anomalies and index == SPIKE_COLLEGE:
        first = 3 * second
    if anomalies and index == SHARE_COLLEGE:
        management, nri = 8, 6
    plan = [(1, AdmissionRoute.MANAGEMENT)] * management + [(1, AdmissionRoute.NRI)] * nri
    plan += [(1, AdmissionRoute.COUNSELLING)] * (first - management - nri)
    plan += [(2, AdmissionRoute.COUNSELLING)] * second
    return plan


async def build_world(*, ring: bool, anomalies: bool) -> SignalWorld:
    world = SignalWorld()
    rng = random.Random(2026)
    async with session_factory()() as session:
        west = Region(code="WEST", name="Western", hq_city="Mumbai")
        south = Region(code="SOUTH", name="Southern", hq_city="Chennai")
        session.add_all([west, south])
        await session.flush()
        mh = State(code="MH", name="Maharashtra", region_id=west.id)
        ka = State(code="KA", name="Karnataka", region_id=south.id)
        session.add_all([mh, ka])
        await session.flush()
        uni = University(code="SGU", name="Signal Test University", state_id=mh.id)
        session.add(uni)
        await session.flush()

        for i in range(COLLEGES):
            state = mh if i < COLLEGES // 2 else ka
            inst = Institution(
                id=uuid.uuid4(),
                aicte_permanent_id=f"1-SIG-{i + 1:04d}",
                name=f"Signal College {i + 1:02d}",
                type=InstitutionType.GOVERNMENT
                if i % 4 == 0
                else InstitutionType.PRIVATE_SELF_FINANCED,
                state_id=state.id,
                region_id=state.region_id,
                university_id=uni.id if i < 5 else None,
            )
            world.institutions.append(inst)
        session.add_all(world.institutions)
        await session.flush()

        students: list[Student] = []
        enrolments: list[Enrolment] = []
        for i, inst in enumerate(world.institutions):
            programme = Programme(
                id=uuid.uuid4(),
                institution_id=inst.id,
                code="CSE",
                name="B.Tech Computer Science and Engineering",
                level=ProgrammeLevel.UG,
                discipline=Discipline.ENGINEERING,
                shift=Shift.FIRST,
                duration_years=4,
                mode=ProgrammeMode.PHYSICAL,
            )
            session.add(programme)
            session.add_all(
                [
                    Approval(programme=programme, academic_year=YEAR, approved_intake=120),
                    Approval(programme=programme, academic_year="2025-26", approved_intake=120),
                ]
            )
            own: list[Enrolment] = []
            for year_of_study, route in _plan(i, rng, anomalies=anomalies):
                n = next(_serial)
                student = _student(
                    n,
                    mobile=f"9{n:09d}",
                    email=f"signal.student{n}@example.demo",
                    address=f"{n} Signal Road",
                    apaar=n % 7 != 0,
                )
                students.append(student)
                enrolment = Enrolment(
                    id=uuid.uuid4(),
                    student_id=student.id,
                    institution_id=inst.id,
                    programme_id=programme.id,
                    academic_year=YEAR,
                    year_of_study=year_of_study,
                    cohort_year=cohort_year(YEAR, year_of_study),
                    admission_route=route,
                    category=Category.GENERAL,
                    status=EnrolmentStatus.ACTIVE,
                    admission_date=date(2026, 8, 1),
                    status_date=date(2026, 8, 1),
                )
                own.append(enrolment)
            enrolments.extend(own)
            world.enrolments[inst.id] = own

        if ring:
            # 40 first-years across three colleges: four mobiles and four addresses, crossed so
            # that every member links to every other through some chain
            picks = [14, 13, 13]
            by_student = {s.id: s for s in students}
            for college, k in zip(RING_COLLEGES, picks, strict=True):
                firsts = [
                    e
                    for e in world.enrolments[world.institutions[college].id]
                    if e.year_of_study == 1
                ]
                world.ring.extend(firsts[:k])
            for j, enrolment in enumerate(world.ring):
                student = by_student[enrolment.student_id]
                mobile = f"98000000{j % 4:02d}"
                student.mobile_hmac = crypto.hmac_bytes(mobile, "mobile")
                student.mobile_last4 = mobile[-4:]
                student.address_hmac = crypto.hmac_bytes(f"Ring House {(j // 4) % 4}", "address")
        session.add_all(students)
        await session.flush()
        session.add_all(enrolments)

        def user(key: str, role: UserRole, **scope) -> None:
            world.users[key] = User(
                id=uuid.uuid4(),
                email=f"{key}@signals.demo",
                password_hash=hash_password(PASSWORD),
                name=key.replace(".", " ").title(),
                role=role,
                **scope,
            )

        user("admin", UserRole.AICTE_ADMIN)
        user("admin.two", UserRole.AICTE_ADMIN)
        user("ro.west", UserRole.RO_OFFICER, region_id=west.id)
        user("ro.south", UserRole.RO_OFFICER, region_id=south.id)
        user("registrar", UserRole.INSTITUTION, institution_id=world.institutions[0].id)
        user("university", UserRole.UNIVERSITY, university_id=uni.id)
        session.add_all(world.users.values())
        await session.commit()
    return world


def client_for(user: User) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=transport, base_url="http://test")
    c.cookies.set(COOKIE_NAME, create_access_token(user.id, user.role.value))
    return c


@pytest.fixture
async def ring_world() -> AsyncIterator[SignalWorld]:
    await truncate_all()
    yield await build_world(ring=True, anomalies=False)
    await truncate_all()


@pytest.fixture
async def anomaly_world() -> AsyncIterator[SignalWorld]:
    await truncate_all()
    yield await build_world(ring=False, anomalies=True)
    await truncate_all()


@pytest.fixture
async def clients(ring_world) -> AsyncIterator[dict[str, httpx.AsyncClient]]:
    out = {key: client_for(u) for key, u in ring_world.users.items()}
    yield out
    for c in out.values():
        await c.aclose()


@pytest.fixture(autouse=True)
def model_of_these_worlds(monkeypatch) -> None:
    """These forty-college worlds plant two outliers, so their model keeps a contamination of
    5% whatever rules.yaml sets for the demo data (0.1 on the small seed)."""
    from app.signals import anomaly

    monkeypatch.setattr(anomaly, "settings", lambda path=None: anomaly.AnomalySettings())
