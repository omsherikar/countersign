import asyncio
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core import audit
from app.core.crypto import decrypt, hmac_bytes
from app.db.session import session_factory
from app.engine.upload.upsert import provisional_id_for
from app.models.enums import (
    ConsentStatus,
    EnrolmentStatus,
    ProgrammeMode,
    SeatType,
    UploadKind,
    UploadSource,
    UserRole,
)
from app.models.institution import Approval, Institution, Programme
from app.models.seat import Seat, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.seed import cli
from app.seed.importer import SeedError, import_directory
from tests.conftest import API_ROOT, FIXTURE_DIR


async def _count(model) -> int:
    async with session_factory()() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_import_fixture_then_rerun_is_idempotent(clean_db):
    summary = await import_directory(session_factory(), FIXTURE_DIR)
    created = {k: v.created for k, v in summary.counts.items()}
    assert created["regions"] == 3 and created["states"] == 3 and created["universities"] == 3
    assert created["institutions"] == 3 and created["programmes"] == 5 and created["approvals"] == 8
    assert created["seat_pools"] == 40
    # 2026-27: 120 -> 156, 60 (MBA) -> 84, 60 (ECE) -> 78, 30 (MCA, 25% intl) -> 43, 40 (DME)
    # -> 52; 2025-26 for the lateral entrants: CSE 156, ECE 78, DME 52
    assert created["seats"] == 156 + 84 + 78 + 43 + 52 + 156 + 78 + 52
    assert created["upload_batches"] == 4 and created["users"] == 7
    # initial files by name, then the update file
    assert summary.files == [
        "1-ABC-0001_2026-27.csv",
        "1-PQR-0003_2026-27.csv",
        "1-XYZ-0002_2026-27.csv",
        "1-PQR-0003_2026-27_update1.csv",
    ]
    assert [u.status for u in summary.uploads] == ["DONE"] * 4
    update = summary.uploads[-1].counts
    assert (update["created"], update["updated"], update["withdrawn"], update["transferred"]) == (
        2,
        2,
        1,
        1,
    )
    assert created["enrolments"] == 41 + 2
    assert await _count(Student) == 42 and await _count(Enrolment) == 43
    assert "entity" in summary.table() and "1-PQR-0003_2026-27_update1.csv" in summary.table()

    again = await import_directory(session_factory(), FIXTURE_DIR)
    assert all(v.created == 0 for v in again.counts.values()), again.counts
    assert [u.status for u in again.uploads] == ["SKIPPED"] * 4
    assert await _count(Student) == 42 and await _count(Enrolment) == 43 and await _count(User) == 7

    async with session_factory()() as session:
        ok, length, broken = await audit.verify_chain(session)
        assert ok and broken is None and length > 0


async def test_students_are_stored_masked_and_scoped(clean_db):
    await import_directory(session_factory(), FIXTURE_DIR)
    async with session_factory()() as session:
        ravi = (
            await session.execute(
                select(Student).where(Student.apaar_hmac == hmac_bytes("123456784417", "apaar"))
            )
        ).scalar_one()
        assert ravi.apaar_last4 == "4417"
        assert decrypt(ravi.apaar_encrypted) == "123456784417"
        assert ravi.name_normalized == "ravi kumar sharma"
        assert ravi.mobile_last4 == "4521" and ravi.mobile_hmac == hmac_bytes(
            "9876504521", "mobile"
        )
        assert ravi.address_hmac is not None and ravi.consent_status is ConsentStatus.LINKED
        assert ravi.gender.value == "M" and ravi.nationality == "IN"

        demo = (
            await session.execute(select(User).where(User.email == "student@demo"))
        ).scalar_one()
        assert demo.role is UserRole.STUDENT and demo.student_id == ravi.id
        ro = (
            await session.execute(select(User).where(User.email == "ro.west@aicte.demo"))
        ).scalar_one()
        assert ro.region_id is not None and ro.institution_id is None
        registrar = (
            await session.execute(select(User).where(User.email == "registrar@xyz.edu.demo"))
        ).scalar_one()
        xyz = (
            await session.execute(
                select(Institution).where(Institution.aicte_permanent_id == "1-XYZ-0002")
            )
        ).scalar_one()
        assert registrar.institution_id == xyz.id

        aisha = (
            await session.execute(select(Student).where(Student.name == "Aisha Rahman"))
        ).scalar_one()
        assert aisha.apaar_hmac is None and aisha.passport_hmac is not None
        assert aisha.consent_status is ConsentStatus.INTERNATIONAL and aisha.nationality == "BD"
        assert aisha.provisional_id == provisional_id_for(
            "1-ABC-0001", "aisha rahman", "2006-07-07", ""
        )
        assert decrypt(aisha.passport_encrypted) == "N1234567"

        shared = (
            await session.execute(select(Student).where(Student.name == "Ananya Krishnan"))
        ).scalar_one()
        enrolments = (
            (await session.execute(select(Enrolment).where(Enrolment.student_id == shared.id)))
            .scalars()
            .all()
        )
        assert len(enrolments) == 2 and all(e.seat_id is None for e in enrolments)

        cse = (
            await session.execute(
                select(Approval)
                .join(Programme)
                .join(Institution)
                .where(
                    Institution.aicte_permanent_id == "1-ABC-0001",
                    Programme.code == "CSE",
                    Approval.academic_year == "2026-27",
                )
            )
        ).scalar_one()
        pools = {
            p.seat_type: p
            for p in (
                await session.execute(select(SeatPool).where(SeatPool.approval_id == cse.id))
            ).scalars()
        }
        assert {k: v.capacity for k, v in pools.items()} == {
            SeatType.REGULAR: 114,
            SeatType.NRI: 6,
            SeatType.TFW: 6,
            SeatType.LATERAL: 12,
            SeatType.INTERNATIONAL: 18,
        }
        assert cse.cutoff_date.isoformat() == "2026-09-15"
        ciwg = (
            await session.execute(
                select(func.count())
                .select_from(Seat)
                .where(
                    Seat.pool_id == pools[SeatType.INTERNATIONAL].id, Seat.reserved_for == "CIWG"
                )
            )
        ).scalar_one()
        assert ciwg == 6
        assert (await session.get(Programme, cse.programme_id)).mode is ProgrammeMode.PHYSICAL

        # the update file: a withdrawal, a transfer and two late admissions
        by_name = {
            student.name: enrolment
            for enrolment, student in (
                await session.execute(
                    select(Enrolment, Student).join(Student, Student.id == Enrolment.student_id)
                )
            ).all()
        }
        update = (
            await session.execute(
                select(UploadBatch).where(UploadBatch.filename == "1-PQR-0003_2026-27_update1.csv")
            )
        ).scalar_one()
        assert update.source is UploadSource.SEED and update.kind is UploadKind.UPDATE
        withdrawn, moved = by_name["Prajwal Shetty"], by_name["Kiran Kumar"]
        assert withdrawn.status is EnrolmentStatus.WITHDRAWN
        assert withdrawn.status_date == date(2026, 9, 20)
        assert moved.status is EnrolmentStatus.TRANSFERRED and moved.upload_batch_id == update.id
        late = by_name["Yashas Gowda"]
        assert late.admission_date == date(2026, 10, 10) and late.source_row_no == 4
        assert by_name["Divya Iyer"].cohort_year == "2025-26"
        assert by_name["Ravi Kumar Sharma"].admission_date == date(2026, 7, 8)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """The real entry point, in its own process, against the same test database."""
    return subprocess.run(
        [sys.executable, "-m", "app.seed.cli", *args],
        cwd=API_ROOT,
        env={**os.environ, "AUTO_MIGRATE": "false"},
        capture_output=True,
        text=True,
        timeout=120,
    )


async def test_reset_flag_and_cli(clean_db):
    await import_directory(session_factory(), FIXTURE_DIR)
    async with session_factory()() as session:
        session.add(
            Student(
                name="Stray",
                name_normalized="stray",
                dob=date(2000, 1, 1),
                consent_status=ConsentStatus.PENDING,
                provisional_id="PRV-STRAY001",
            )
        )
        await session.commit()
    assert await _count(Student) == 43

    result = await asyncio.to_thread(_run_cli, "--from", str(FIXTURE_DIR), "--reset")
    assert result.returncode == 0, result.stderr
    assert "enrolments" in result.stdout and "created" in result.stdout
    assert "seeded 4 upload files, 45 rows, in " in result.stdout
    assert await _count(Student) == 42


async def test_bad_input_fails_loudly(clean_db, tmp_path: Path):
    result = await asyncio.to_thread(_run_cli, "--from", str(tmp_path / "missing"))
    assert result.returncode == 2 and "seed failed" in result.stderr
    assert cli.build_parser().parse_args(["--from", "x", "--reset"]).reset is True
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "institutions.json").write_text(
        '{"regions":[],"states":[{"code":"MH","name":"Maharashtra","region":"NOPE"}],"universities":[],"institutions":[]}'
    )
    with pytest.raises(SeedError):
        await import_directory(session_factory(), bad)
