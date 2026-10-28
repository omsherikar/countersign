from sqlalchemy import func, select

from app.db.session import session_factory
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch, UploadRowError
from app.seed.importer import describe_apaar_problem, import_directory
from tests.conftest import FIXTURE_DIR


def test_describe_apaar_problem():
    assert describe_apaar_problem("") is None
    assert describe_apaar_problem("123456784417") is None
    assert describe_apaar_problem("1234 5678 4417") is None
    assert describe_apaar_problem("12345678441") == "apaar_id has 11 digits, expected 12"
    assert describe_apaar_problem("1234567844170") == "apaar_id has 13 digits, expected 12"
    assert (
        describe_apaar_problem("2026000003A09") == "apaar_id contains characters other than digits"
    )


async def test_invalid_apaar_rows_are_recorded_not_fatal(clean_db):
    summary = await import_directory(session_factory(), FIXTURE_DIR)
    assert summary.counts["upload_row_errors"].created == 1
    assert summary.counts["upload_batches"].created == 3
    async with session_factory()() as session:
        error = (await session.execute(select(UploadRowError))).scalar_one()
        assert (error.code, error.field, error.row_no) == ("APAAR_FORMAT", "apaar_id", 10)
        assert "digits" in error.message
        assert error.raw["name"] == "Lokesh Patil"
        assert error.raw["apaar_id"].startswith("<13 chars")
        assert set(error.raw) == {
            "apaar_id",
            "name",
            "programme_code",
            "academic_year",
            "admission_route",
        }
        batch = await session.get(UploadBatch, error.batch_id)
        assert (batch.rows_total, batch.rows_ok, batch.rows_error) == (9, 8, 1)
        assert batch.status.value == "DONE" and batch.kind.value == "INITIAL"
        lokesh = (
            await session.execute(select(Student).where(Student.name == "Lokesh Patil"))
        ).scalar_one()
        assert lokesh.apaar_hmac is None and lokesh.provisional_id.startswith("PRV-")
        enrolled = (
            (await session.execute(select(Enrolment).where(Enrolment.student_id == lokesh.id)))
            .scalars()
            .all()
        )
        assert len(enrolled) == 1 and enrolled[0].upload_batch_id is None

    again = await import_directory(session_factory(), FIXTURE_DIR)
    assert again.counts["upload_batches"].existing == 3
    assert again.counts["upload_batches"].created == 0
    async with session_factory()() as session:
        n = (await session.execute(select(func.count()).select_from(UploadRowError))).scalar_one()
    assert n == 1
