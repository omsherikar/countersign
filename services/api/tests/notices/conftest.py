"""Notice test wiring: a small world built with the ORM, in-memory DigiLocker and mail.

Every database test here starts and ends with empty tables. Retries never pause, and the
mailer the code builds by default is a MemoryMailer, so nothing reaches an SMTP server.
"""

from __future__ import annotations

import hashlib
import itertools
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import insert, select

from app.adapters.base import AdapterSet
from app.adapters.inmemory import (
    InMemoryAbc,
    InMemoryApaar,
    InMemoryCounselling,
    InMemoryDigiLocker,
    InMemorySii,
)
from app.core import crypto
from app.core.cohort import cohort_year
from app.core.security import COOKIE_NAME, create_access_token, hash_password
from app.db.session import session_factory
from app.engine import matching
from app.engine.seatpools import build_for_approval
from app.main import app
from app.models.enums import (
    AdmissionRoute,
    Category,
    CheckStatus,
    CheckType,
    ConsentStatus,
    Discipline,
    EnrolmentStatus,
    InstitutionType,
    NoticeChannel,
    ProgrammeLevel,
    ProgrammeMode,
    Shift,
    UploadKind,
    UploadSource,
    UploadStatus,
    UserRole,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import Check, Notification
from app.notices import dispatch
from app.notices.mailer import MailMessage, MemoryMailer
from tests.conftest import PASSWORD, truncate_all

_serial = itertools.count(1)
_password_hashes: list[str] = []


def password_hash() -> str:
    """One hash for every user made here: hashing is slow on purpose."""
    if not _password_hashes:
        _password_hashes.append(hash_password(PASSWORD))
    return _password_hashes[0]


def signed_in(user: User) -> httpx.AsyncClient:
    """A client holding a session cookie for the user, as /auth/login would set it."""
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    client.cookies.set(COOKIE_NAME, create_access_token(user.id, user.role.value))
    return client


TOKEN_IN_LINK = re.compile(r"/student/notices/([A-Za-z0-9_-]{43})")


async def student_user(student_id: uuid.UUID) -> User:
    """The student's STUDENT account, made when it has none (as a first DigiLocker sign-in
    would make it)."""
    async with session_factory()() as s:
        user = (
            (
                await s.execute(
                    select(User).where(User.role == UserRole.STUDENT, User.student_id == student_id)
                )
            )
            .scalars()
            .first()
        )
        if user is None:
            user = User(
                email=f"student.{next(_serial)}@digilocker.invalid",
                password_hash=password_hash(),
                name="Student",
                role=UserRole.STUDENT,
                student_id=student_id,
            )
            s.add(user)
            await s.commit()
    return user


async def signed_in_owner(token: str) -> httpx.AsyncClient:
    """A client signed in (through DigiLocker, D37) as the student the notice is about."""
    async with session_factory()() as s:
        student_id = (
            await s.execute(
                select(Notification.student_id).where(
                    Notification.token_hash == hashlib.sha256(token.encode()).hexdigest()
                )
            )
        ).scalar_one()
    return signed_in(await student_user(student_id))


def token_of(message: MailMessage) -> str:
    match = TOKEN_IN_LINK.search(message.body)
    assert match, message.body
    return match.group(1)


def inmemory() -> AdapterSet:
    return AdapterSet(
        name="inmemory",
        apaar=InMemoryApaar(),
        counselling=InMemoryCounselling(),
        abc=InMemoryAbc(),
        digilocker=InMemoryDigiLocker(),
        sii=InMemorySii(),
    )


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch) -> None:
    monkeypatch.setattr(dispatch, "RETRY_PAUSES_SECONDS", (0, 0))


@pytest.fixture
def mailer(monkeypatch) -> MemoryMailer:
    """The mailer every default `build_mailer()` in the notices code returns."""
    box = MemoryMailer()
    monkeypatch.setattr(dispatch, "build_mailer", lambda *a, **k: box)
    return box


@pytest.fixture
def gov(monkeypatch) -> AdapterSet:
    """In-memory sources, used by the app for requests and by the notices code by default."""
    adapters = inmemory()
    monkeypatch.setattr(app.state, "adapters", adapters, raising=False)
    monkeypatch.setattr(dispatch, "build_adapters", lambda *a, **k: adapters)
    return adapters


@pytest.fixture
async def db() -> AsyncIterator[None]:
    await truncate_all()
    yield
    await truncate_all()


@dataclass
class World:
    """Two colleges in two regions, their staff, and students made on demand."""

    abc: Institution
    xyz: Institution
    cse: Programme
    ece: Programme
    users: dict[str, User]
    gov: AdapterSet
    batches: dict[uuid.UUID, UploadBatch] = field(default_factory=dict)

    async def batch(self, institution: Institution | None = None, **values) -> UploadBatch:
        institution = institution or self.abc
        async with session_factory()() as s:
            batch = UploadBatch(
                institution_id=institution.id,
                academic_year="2026-27",
                filename=values.pop("filename", f"{institution.aicte_permanent_id}_2026-27.csv"),
                kind=UploadKind.INITIAL,
                status=values.pop("status", UploadStatus.DONE),
                source=values.pop("source", UploadSource.FILE),
                uploaded_by=self.users["admin"].id,
            )
            s.add(batch)
            await s.commit()
        self.batches[batch.id] = batch
        return batch

    async def enrolment(
        self,
        name: str | None = None,
        *,
        email: str | None | bool = True,
        apaar: str | None | bool = True,
        consent: ConsentStatus | None = None,
        digilocker: bool = True,
        batch: UploadBatch | None = None,
        row_no: int | None = None,
        programme: Programme | None = None,
        status: EnrolmentStatus = EnrolmentStatus.ACTIVE,
    ) -> Enrolment:
        """One student and one enrolment. `apaar=True` makes a fresh APAAR; `digilocker`
        says whether that APAAR has a DigiLocker account."""
        n = next(_serial)
        name = name or f"Notice Student {n:05d}"
        dob = date(2007, 1, 1)
        apaar_id = f"5{n:011d}" if apaar is True else (apaar or None)
        mail = f"student.{n:05d}@example.demo" if email is True else (email or None)
        consent = consent or (ConsentStatus.LINKED if apaar_id else ConsentStatus.PENDING)
        programme = programme or self.cse
        async with session_factory()() as s:
            student = Student(
                name=name,
                name_normalized=matching.normalise_name(name),
                name_key=matching.name_key(name, dob),
                dob=dob,
                consent_status=consent,
                apaar_hmac=crypto.hmac_bytes(apaar_id, "apaar") if apaar_id else None,
                apaar_encrypted=crypto.encrypt(apaar_id) if apaar_id else None,
                apaar_last4=apaar_id[-4:] if apaar_id else None,
                provisional_id=None if apaar_id else f"PRV-N{n:07d}",
                email=mail,
            )
            s.add(student)
            await s.flush()
            enrolment = Enrolment(
                student_id=student.id,
                institution_id=programme.institution_id,
                programme_id=programme.id,
                academic_year="2026-27",
                year_of_study=1,
                cohort_year=cohort_year("2026-27", 1),
                admission_route=AdmissionRoute.COUNSELLING,
                category=Category.GENERAL,
                status=status,
                upload_batch_id=batch.id if batch else None,
                source_row_no=row_no if row_no is not None else (n + 1 if batch else None),
                admission_date=date(2026, 8, 1),
                status_date=date(2026, 8, 1),
            )
            s.add(enrolment)
            await s.commit()
        if apaar_id and digilocker:
            self.gov.digilocker.linked.add(apaar_id)  # type: ignore[attr-defined]
        return enrolment

    async def bulk(self, count: int, batch: UploadBatch) -> list[uuid.UUID]:
        """`count` students with an email and a DigiLocker-linked APAAR, one enrolment each
        in the batch, inserted in bulk."""
        dob = date(2007, 1, 1)
        students, enrolments = [], []
        for i in range(count):
            n = next(_serial)
            apaar_id = f"6{n:011d}"
            student_id, enrolment_id = uuid.uuid4(), uuid.uuid4()
            students.append(
                {
                    "id": student_id,
                    "name": f"Bulk Student {n:05d}",
                    "name_normalized": f"bulk student {n:05d}",
                    "dob": dob,
                    "consent_status": ConsentStatus.LINKED,
                    "apaar_hmac": crypto.hmac_bytes(apaar_id, "apaar"),
                    "apaar_encrypted": crypto.encrypt(apaar_id),
                    "apaar_last4": apaar_id[-4:],
                    "email": f"bulk.{n:05d}@example.demo",
                }
            )
            enrolments.append(
                {
                    "id": enrolment_id,
                    "student_id": student_id,
                    "institution_id": self.cse.institution_id,
                    "programme_id": self.cse.id,
                    "academic_year": "2026-27",
                    "year_of_study": 1,
                    "cohort_year": "2026-27",
                    "admission_route": AdmissionRoute.COUNSELLING,
                    "category": Category.GENERAL,
                    "status": EnrolmentStatus.ACTIVE,
                    "upload_batch_id": batch.id,
                    "source_row_no": i + 2,
                }
            )
            self.gov.digilocker.linked.add(apaar_id)  # type: ignore[attr-defined]
        async with session_factory()() as s:
            await s.execute(insert(Student), students)
            await s.execute(insert(Enrolment), enrolments)
            await s.commit()
        return [e["id"] for e in enrolments]

    async def student_login(self, enrolment: Enrolment) -> httpx.AsyncClient:
        async with session_factory()() as s:
            user = User(
                email=f"student.{next(_serial)}@demo",
                password_hash=password_hash(),
                name="Student",
                role=UserRole.STUDENT,
                student_id=enrolment.student_id,
            )
            s.add(user)
            await s.commit()
        return signed_in(user)


async def _build_world(gov: AdapterSet) -> World:
    async with session_factory()() as s:
        west = Region(code="WEST", name="Western", hq_city="Mumbai")
        south = Region(code="SOUTH", name="Southern", hq_city="Chennai")
        s.add_all([west, south])
        await s.flush()
        mh = State(code="MH", name="Maharashtra", region_id=west.id)
        tn = State(code="TN", name="Tamil Nadu", region_id=south.id)
        s.add_all([mh, tn])
        await s.flush()
        uni = University(code="MSTU", name="Maharashtra State Technical University", state_id=mh.id)
        s.add(uni)
        await s.flush()
        abc = Institution(
            aicte_permanent_id="1-ABC-0001",
            name="ABC College of Engineering",
            type=InstitutionType.PRIVATE_SELF_FINANCED,
            state_id=mh.id,
            region_id=west.id,
            university_id=uni.id,
        )
        xyz = Institution(
            aicte_permanent_id="1-XYZ-0002",
            name="XYZ Institute of Technology",
            type=InstitutionType.PRIVATE_SELF_FINANCED,
            state_id=tn.id,
            region_id=south.id,
        )
        s.add_all([abc, xyz])
        await s.flush()
        programmes = []
        for inst, code, name in (
            (abc, "CSE", "B.Tech Computer Science and Engineering"),
            (xyz, "ECE", "B.Tech Electronics and Communication Engineering"),
        ):
            programme = Programme(
                institution_id=inst.id,
                code=code,
                name=name,
                level=ProgrammeLevel.UG,
                discipline=Discipline.ENGINEERING,
                shift=Shift.FIRST,
                duration_years=4,
                mode=ProgrammeMode.PHYSICAL,
            )
            s.add(programme)
            await s.flush()
            approval = Approval(programme=programme, academic_year="2026-27", approved_intake=120)
            s.add(approval)
            s.add_all(build_for_approval(approval, programme))
            programmes.append(programme)
        users = {
            "admin": User(role=UserRole.AICTE_ADMIN, name="AICTE Administrator"),
            "ro_west": User(role=UserRole.RO_OFFICER, name="RO West", region_id=west.id),
            "ro_south": User(role=UserRole.RO_OFFICER, name="RO South", region_id=south.id),
            "abc": User(role=UserRole.INSTITUTION, name="Registrar ABC", institution_id=abc.id),
            "xyz": User(role=UserRole.INSTITUTION, name="Registrar XYZ", institution_id=xyz.id),
            "university": User(role=UserRole.UNIVERSITY, name="CoE MSTU", university_id=uni.id),
        }
        for key, user in users.items():
            user.email = f"{key}.{next(_serial)}@notices.demo"
            user.password_hash = password_hash()
            s.add(user)
        await s.commit()
    return World(abc=abc, xyz=xyz, cse=programmes[0], ece=programmes[1], users=users, gov=gov)


@pytest.fixture
async def world(db, gov, mailer) -> World:
    return await _build_world(gov)


@pytest.fixture
async def clients(world) -> AsyncIterator[dict[str, httpx.AsyncClient]]:
    out = {key: signed_in(user) for key, user in world.users.items()}
    yield out
    for client in out.values():
        await client.aclose()


@pytest.fixture
async def public() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def notices_of(enrolment_id: uuid.UUID) -> list[Notification]:
    async with session_factory()() as s:
        return list(
            (
                await s.execute(
                    select(Notification)
                    .where(Notification.enrolment_id == enrolment_id)
                    .order_by(Notification.created_at, Notification.channel)
                )
            )
            .scalars()
            .all()
        )


async def delivered(
    world: World, mailer: MemoryMailer, **student
) -> tuple[Enrolment, dict[NoticeChannel, str]]:
    """A student with an enrolment in a new DONE batch whose notices were sent; returns the
    enrolment and the link token each channel carried."""
    from app.notices.dispatch import send_notices_for_batch

    batch = await world.batch()
    enrolment = await world.enrolment(batch=batch, **student)
    mail_seen, inbox_seen = len(mailer.sent), len(world.gov.digilocker.inbox)  # type: ignore[attr-defined]
    await send_notices_for_batch(batch.id)
    tokens: dict[NoticeChannel, str] = {}
    for message in mailer.sent[mail_seen:]:
        tokens[NoticeChannel.EMAIL] = token_of(message)
    for item in world.gov.digilocker.inbox[inbox_seen:]:  # type: ignore[attr-defined]
        tokens[NoticeChannel.DIGILOCKER] = item["callback_url"].rsplit("/", 1)[1]
    return enrolment, tokens


async def confirm_rows(enrolment_id: uuid.UUID, *, admission: bool = False) -> None:
    """Identity and Seat CONFIRMED (and, with `admission`, an independent Joining record),
    as the engine would write them, so that one more independent row countersigns."""
    now = datetime.now(UTC)
    rows = [
        (CheckType.IDENTITY, "APAAR", "APAAR registry", True),
        (CheckType.SEAT, "SEAT_LEDGER", "AICTE approval v1, 2026-27 (Seat Ledger, derived)", False),
    ]
    if admission:
        rows.append((CheckType.ADMISSION, "ADMISSION_AUTHORITY", "State admission authority", True))
    async with session_factory()() as s:
        for check_type, source, supplied_by, independent in rows:
            s.add(
                Check(
                    enrolment_id=enrolment_id,
                    type=check_type,
                    status=CheckStatus.CONFIRMED,
                    source=source,
                    detail={"summary": "Confirmed.", "finding": None, "source_line": supplied_by},
                    checked_at=now,
                    supplied_by=supplied_by,
                    observed_at=now,
                    independent=independent,
                )
            )
        await s.commit()
