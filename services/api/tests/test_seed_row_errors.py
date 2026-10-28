from sqlalchemy import func, select

from app.db.session import session_factory
from app.engine.upload.validate import apaar_problem
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch, UploadRowError
from app.seed.importer import import_directory
from tests.conftest import FIXTURE_DIR


def test_apaar_problem():
    assert apaar_problem("") is None
    assert apaar_problem("123456784417") is None
    assert apaar_problem("1234 5678 4417") is None
    assert apaar_problem("12345678441") == "has 11 digits, expected 12"
    assert apaar_problem("1234567844170") == "has 13 digits, expected 12"
    assert apaar_problem("2026000003A09") == "contains characters other than digits"


async def test_invalid_apaar_rows_are_recorded_not_fatal(clean_db):
    summary = await import_directory(session_factory(), FIXTURE_DIR)
    assert summary.counts["upload_batches"].created == 4
    async with session_factory()() as session:
        error = (await session.execute(select(UploadRowError))).scalar_one()
        assert (error.code, error.field, error.row_no) == ("APAAR_FORMAT", "apaar_id", 10)
        assert (error.level.value, error.message) == ("WARNING", "APAAR must be 12 digits")
        assert error.value_masked == "<13 characters>"
        assert error.raw["name"] == "Lokesh Patil" and error.raw["apaar_id"] == "<13 characters>"
        assert set(error.raw) == {
            "apaar_id",
            "name",
            "programme_code",
            "academic_year",
            "admission_route",
        }
        batch = await session.get(UploadBatch, error.batch_id)
        assert batch.total_rows == 9
        counts = batch.counts
        assert (counts["accepted"], counts["errors"], counts["warnings"]) == (9, 0, 1)
        assert batch.status.value == "DONE" and batch.kind.value == "INITIAL"
        assert batch.source.value == "SEED" and batch.stage.value == "DONE"
        lokesh = (
            await session.execute(select(Student).where(Student.name == "Lokesh Patil"))
        ).scalar_one()
        assert lokesh.apaar_hmac is None and lokesh.provisional_id.startswith("PRV-")
        assert lokesh.consent_status.value == "PENDING"
        enrolled = (
            (await session.execute(select(Enrolment).where(Enrolment.student_id == lokesh.id)))
            .scalars()
            .all()
        )
        assert len(enrolled) == 1 and enrolled[0].upload_batch_id == batch.id
        assert enrolled[0].apaar_problem == "contains characters other than digits"

    again = await import_directory(session_factory(), FIXTURE_DIR)
    assert again.counts["upload_batches"].existing == 4
    assert again.counts["upload_batches"].created == 0
    async with session_factory()() as session:
        n = (await session.execute(select(func.count()).select_from(UploadRowError))).scalar_one()
    assert n == 1
