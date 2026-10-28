"""Engine test fixtures: small worlds built straight with the ORM, InMemory adapters.

Every database test here starts and ends with empty tables, so the shared `seeded`
fixture of tests/conftest.py imports its own data when a later test asks for it.
"""

from __future__ import annotations

import itertools
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.core.security import hash_password
from app.db.session import session_factory
from app.engine import matching
from app.engine.seatpools import build_for_approval
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
from tests.conftest import PASSWORD, truncate_all

_serial = itertools.count(1)


def adapters() -> AdapterSet:
    return AdapterSet(
        name="inmemory",
        apaar=InMemoryApaar(),
        counselling=InMemoryCounselling(),
        abc=InMemoryAbc(),
        digilocker=InMemoryDigiLocker(),
        sii=InMemorySii(),
    )


@pytest.fixture
def gov() -> AdapterSet:
    return adapters()


@pytest.fixture
async def db() -> AsyncIterator[None]:
    await truncate_all()
    yield
    await truncate_all()


@pytest.fixture
async def session(db) -> AsyncIterator[AsyncSession]:
    async with session_factory()() as s:
        yield s
        await s.rollback()


@dataclass
class World:
    """Factories bound to one session; ids are unique per test."""

    session: AsyncSession
    regions: dict[str, Region] = field(default_factory=dict)
    states: dict[str, State] = field(default_factory=dict)
    admin: User | None = None
    next_row: int = 2  # spreadsheet rows keep increasing across cohorts

    async def region(self, code: str = "WEST", name: str = "Western") -> Region:
        if code not in self.regions:
            region = Region(code=code, name=name, hq_city="Mumbai")
            self.session.add(region)
            await self.session.flush()
            self.regions[code] = region
        return self.regions[code]

    async def state(self, code: str = "MH", name: str = "Maharashtra", region: str = "WEST"):
        if code not in self.states:
            state = State(code=code, name=name, region_id=(await self.region(region)).id)
            self.session.add(state)
            await self.session.flush()
            self.states[code] = state
        return self.states[code]

    async def institution(
        self,
        name: str = "ABC College of Engineering",
        aicte_id: str | None = None,
        state: str = "MH",
        state_name: str = "Maharashtra",
        region: str = "WEST",
        university: University | None = None,
    ) -> Institution:
        st = await self.state(state, state_name, region)
        inst = Institution(
            aicte_permanent_id=aicte_id or f"1-T-{next(_serial):04d}",
            name=name,
            type=InstitutionType.PRIVATE_SELF_FINANCED,
            state_id=st.id,
            region_id=st.region_id,
            university_id=university.id if university else None,
        )
        self.session.add(inst)
        await self.session.flush()
        return inst

    async def programme(
        self,
        institution: Institution,
        code: str = "CSE",
        *,
        name: str = "B.Tech Computer Science and Engineering",
        mode: ProgrammeMode = ProgrammeMode.PHYSICAL,
        level: ProgrammeLevel = ProgrammeLevel.UG,
        discipline: Discipline = Discipline.ENGINEERING,
        intakes: dict[str, int] | None = None,
        cutoff: date | None = date(2026, 9, 15),
    ) -> Programme:
        programme = Programme(
            institution_id=institution.id,
            code=code,
            name=name,
            level=level,
            discipline=discipline,
            shift=Shift.FIRST,
            duration_years=4,
            mode=mode,
        )
        self.session.add(programme)
        await self.session.flush()
        for year, intake in (intakes or {"2026-27": 120}).items():
            approval = Approval(
                programme=programme,
                academic_year=year,
                approved_intake=intake,
                cutoff_date=cutoff if year == "2026-27" else None,
            )
            self.session.add(approval)
            self.session.add_all(build_for_approval(approval, programme))
        await self.session.flush()
        return programme

    async def student(
        self,
        name: str,
        dob: date = date(2008, 1, 1),
        *,
        apaar: str | None = None,
        mobile: str | None = None,
        consent: ConsentStatus | None = None,
        nationality: str = "IN",
        passport: str | None = None,
    ) -> Student:
        consent = consent or (ConsentStatus.LINKED if apaar else ConsentStatus.PENDING)
        stu = Student(
            name=name,
            name_normalized=matching.normalise_name(name),
            name_key=matching.name_key(name, dob),
            dob=dob,
            consent_status=consent,
            apaar_hmac=crypto.hmac_bytes(apaar, "apaar") if apaar else None,
            apaar_encrypted=crypto.encrypt(apaar) if apaar else None,
            apaar_last4=apaar[-4:] if apaar else None,
            provisional_id=None if apaar else f"PRV-T{next(_serial):07d}",
            mobile_hmac=crypto.hmac_bytes(mobile, "mobile") if mobile else None,
            mobile_last4=mobile[-4:] if mobile else None,
            nationality=nationality,
            passport_hmac=crypto.hmac_bytes(passport, "passport") if passport else None,
            passport_encrypted=crypto.encrypt(passport) if passport else None,
        )
        self.session.add(stu)
        await self.session.flush()
        return stu

    async def user(self) -> User:
        if self.admin is None:
            self.admin = User(
                email=f"engine-admin-{next(_serial)}@aicte.demo",
                password_hash=hash_password(PASSWORD),
                name="AICTE Administrator",
                role=UserRole.AICTE_ADMIN,
            )
            self.session.add(self.admin)
            await self.session.flush()
        return self.admin

    async def batch(
        self, institution: Institution, filename: str = "1-ABC-0001_2026-27.csv"
    ) -> UploadBatch:
        batch = UploadBatch(
            institution_id=institution.id,
            academic_year="2026-27",
            filename=filename,
            kind=UploadKind.INITIAL,
            status=UploadStatus.DONE,
            source=UploadSource.FILE,
            uploaded_by=(await self.user()).id,
        )
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def enrol(
        self,
        student: Student,
        programme: Programme,
        *,
        year_of_study: int = 1,
        route: AdmissionRoute = AdmissionRoute.COUNSELLING,
        academic_year: str = "2026-27",
        admission_date: date = date(2026, 8, 1),
        status: EnrolmentStatus = EnrolmentStatus.ACTIVE,
        batch: UploadBatch | None = None,
        row_no: int | None = None,
        counselling_ref: str | None = None,
        apaar_problem: str | None = None,
    ) -> Enrolment:
        enrolment = Enrolment(
            student_id=student.id,
            institution_id=programme.institution_id,
            programme_id=programme.id,
            academic_year=academic_year,
            year_of_study=year_of_study,
            cohort_year=cohort_year(academic_year, year_of_study),
            admission_route=route,
            counselling_ref=counselling_ref,
            category=Category.GENERAL,
            status=status,
            upload_batch_id=batch.id if batch else None,
            source_row_no=row_no,
            admission_date=admission_date,
            status_date=admission_date,
            apaar_problem=apaar_problem,
        )
        self.session.add(enrolment)
        await self.session.flush()
        return enrolment

    async def cohort(
        self,
        programme: Programme,
        count: int,
        *,
        route: AdmissionRoute = AdmissionRoute.COUNSELLING,
        start_row: int | None = None,
        batch: UploadBatch | None = None,
        admission_date: date = date(2026, 8, 1),
        prefix: str = "Student",
    ) -> list[Enrolment]:
        out = []
        start_row = self.next_row if start_row is None else start_row
        self.next_row = max(self.next_row, start_row + count)
        for i in range(count):
            n = next(_serial)
            stu = await self.student(f"{prefix} {n:05d}", date(2008, 1, 1 + n % 28))
            out.append(
                await self.enrol(
                    stu,
                    programme,
                    route=route,
                    batch=batch,
                    row_no=start_row + i,
                    admission_date=admission_date,
                )
            )
        return out


@pytest.fixture
async def world(session) -> World:
    return World(session)


def new_id() -> uuid.UUID:
    return uuid.uuid4()
