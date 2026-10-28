"""Identity resolution and enrolment upsert (D14, ENGINES.md §5)."""

from datetime import date
from typing import Any

from sqlalchemy import func, select

from app.core.crypto import decrypt, hmac_bytes
from app.db.session import session_factory
from app.engine.upload.parse import parse_rows
from app.engine.upload.types import upload_date
from app.engine.upload.upsert import provisional_id_for, upsert_rows
from app.engine.upload.validate import load_context, validate_rows
from app.models.audit import AuditLog
from app.models.enums import ConsentStatus, EnrolmentStatus
from app.models.institution import Institution
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from tests.pipeline.conftest import ROW, new_batch, student_row
from tests.pipeline.fakes import FakeEngines

ENGINES = FakeEngines()


async def upsert(rows: list[dict[str, Any]], aicte_id: str = "1-ABC-0001", batch=None):
    batch = batch or await new_batch(aicte_id)
    async with session_factory()() as session:
        batch = await session.get(UploadBatch, batch.id)
        inst = await session.get(Institution, batch.institution_id)
        ctx = await load_context(session, inst, batch.academic_year, upload_date(batch.created_at))
        validated = validate_rows(parse_rows(rows), ctx)
        assert validated.rejected == [], validated.issues
        result = await upsert_rows(
            session, batch, validated.rows, engines=ENGINES, actor_id=batch.uploaded_by
        )
        await session.commit()
    return batch, result


async def one(model, *where):
    async with session_factory()() as session:
        return (await session.execute(select(model).where(*where))).scalar_one()


async def count(model, *where) -> int:
    async with session_factory()() as session:
        stmt = select(func.count()).select_from(model)
        if where:
            stmt = stmt.where(*where)
        return (await session.execute(stmt)).scalar_one()


async def test_new_rows_create_students_and_enrolments(world):
    rows = [ROW, student_row(1, apaar_id="", consent_status="", status="", admission_date="")]
    batch, result = await upsert(rows)
    assert (result.created, result.updated, result.unchanged) == (2, 0, 0)
    assert result.students_created == 2
    assert [o.outcome for o in result.outcomes] == ["created", "created"]
    assert [o.row_no for o in result.outcomes] == [1, 2]

    ravi = await one(Student, Student.apaar_hmac == hmac_bytes("123456784417", "apaar"))
    assert decrypt(ravi.apaar_encrypted) == "123456784417" and ravi.apaar_last4 == "4417"
    assert ravi.provisional_id is None and ravi.consent_status is ConsentStatus.LINKED
    assert ravi.name_normalized == "ravi kumar sharma" and ravi.name_key == "2007-03-21|r|SHARMA"
    assert ravi.mobile_last4 == "4521" and ravi.address_hmac is not None
    enrolment = await one(Enrolment, Enrolment.student_id == ravi.id)
    assert enrolment.cohort_year == "2026-27" and enrolment.status is EnrolmentStatus.ACTIVE
    assert enrolment.admission_date == date(2026, 8, 2)
    assert enrolment.status_date == upload_date(batch.created_at)
    assert enrolment.upload_batch_id == batch.id and enrolment.source_row_no == 1
    assert enrolment.apaar_problem is None and enrolment.seat_id is None

    other = await one(Student, Student.name == "Student Number 0001")
    assert other.apaar_hmac is None and other.consent_status is ConsentStatus.PENDING
    assert other.provisional_id == provisional_id_for(
        "1-ABC-0001", "student number 0001", "2007-03-21", "9800000001"
    )
    later = await one(Enrolment, Enrolment.student_id == other.id)
    assert later.admission_date == upload_date(batch.created_at)

    async with session_factory()() as session:
        entries = (await session.execute(select(AuditLog).order_by(AuditLog.seq))).scalars().all()
    entries = [e for e in entries if e.entity_type in ("student", "enrolment")]
    writes = [(e.action.value, e.entity_type) for e in entries]
    assert writes == [
        ("CREATE", "student"),
        ("CREATE", "student"),
        ("CREATE", "enrolment"),
        ("CREATE", "enrolment"),
    ]
    text = " ".join(str(e.after) for e in entries)
    for pii in ("Ravi", "123456784417", "9876504521", "Shivaji", "example.demo"):
        assert pii not in text
    student_entry = next(e for e in entries if e.entity_type == "student")
    assert student_entry.actor_id == batch.uploaded_by
    assert set(student_entry.after) == {
        "apaar_last4",
        "provisional_id",
        "consent_status",
        "changed",
    }
    enrolment_entry = next(e for e in entries if e.entity_type == "enrolment")
    assert enrolment_entry.after["batch_id"] == str(batch.id)
    assert enrolment_entry.after["row_no"] == 1


async def test_reupload_changes_nothing(world):
    rows = [ROW, student_row(2), student_row(3, apaar_id="", consent_status="PENDING")]
    first, _ = await upsert(rows)
    audit_before = await count(AuditLog)
    second, result = await upsert(rows)
    assert (result.created, result.updated, result.unchanged) == (0, 0, 3)
    assert (result.students_created, result.students_updated) == (0, 0)
    assert await count(Student) == 3 and await count(Enrolment) == 3
    # only the second batch's own CREATE entry was written
    assert await count(AuditLog) == audit_before + 1
    async with session_factory()() as session:
        batches = (await session.execute(select(Enrolment.upload_batch_id))).scalars().all()
    assert set(batches) == {first.id}


async def test_withdrawal_and_blank_status_keeps_it(world):
    await upsert([ROW, student_row(4)])
    withdrawal = dict(ROW, status="WITHDRAWN", status_date="2026-09-20", admission_date="")
    transfer = student_row(4, status="Transferred", admission_date="")
    batch, result = await upsert([withdrawal, transfer])
    assert (result.updated, result.withdrawn, result.transferred) == (2, 1, 1)
    assert [o.released for o in result.outcomes] == [True, True]
    ravi = await one(Enrolment, Enrolment.source_row_no == 1, Enrolment.upload_batch_id == batch.id)
    assert ravi.status is EnrolmentStatus.WITHDRAWN and ravi.status_date == date(2026, 9, 20)
    assert ravi.admission_date == date(2026, 8, 2)  # blank keeps what is stored
    moved = await one(
        Enrolment, Enrolment.source_row_no == 2, Enrolment.upload_batch_id == batch.id
    )
    assert moved.status is EnrolmentStatus.TRANSFERRED
    assert moved.status_date == upload_date(batch.created_at)

    # the initial file again: blank status leaves the withdrawal in place
    _, again = await upsert([ROW, student_row(4)])
    assert (again.unchanged, again.updated) == (2, 0)
    assert [o.status for o in again.outcomes] == [
        EnrolmentStatus.WITHDRAWN,
        EnrolmentStatus.TRANSFERRED,
    ]
    assert [o.released for o in again.outcomes] == [False, False]


async def test_withdrawal_of_an_unknown_student_is_recorded_without_a_seat(world):
    _, result = await upsert([student_row(5, status="WITHDRAWN", status_date="2026-10-01")])
    assert (result.created, result.withdrawn) == (1, 1)
    assert result.outcomes[0].status is EnrolmentStatus.WITHDRAWN
    assert result.outcomes[0].released is False
    (issue,) = result.issues
    assert (issue.level.value, issue.field, issue.code, issue.value_masked) == (
        "WARNING",
        "status",
        "NOT_PREVIOUSLY_ENROLLED",
        "WITHDRAWN",
    )
    assert issue.message == (
        "No earlier enrolment matches this student; recorded as Withdrawn with no seat"
    )


async def test_provisional_student_gains_its_apaar_in_place(world):
    without = student_row(6, apaar_id="", consent_status="PENDING")
    await upsert([without])
    provisional = await one(Student, Student.name == "Student Number 0006")
    assert provisional.apaar_hmac is None

    with_apaar = student_row(6, apaar_id="600000000006", consent_status="LINKED")
    _, result = await upsert([with_apaar])
    assert (result.students_created, result.students_updated, result.unchanged) == (0, 1, 1)
    upgraded = await one(Student, Student.id == provisional.id)
    assert upgraded.apaar_hmac == hmac_bytes("600000000006", "apaar")
    assert upgraded.consent_status is ConsentStatus.LINKED
    assert upgraded.provisional_id == provisional.provisional_id
    assert await count(Student) == 1 and await count(Enrolment) == 1

    # a later row without the APAAR still finds the student and never removes the APAAR
    _, again = await upsert([without])
    assert again.unchanged == 1 and again.students_updated == 0
    assert (await one(Student, Student.id == provisional.id)).apaar_last4 == "0006"


async def test_passport_resolves_to_the_oldest_student(world):
    intl = student_row(
        7,
        apaar_id="",
        consent_status="",
        nationality="BD",
        passport_no="N1234567",
        admission_route="INTERNATIONAL",
        category="OTHER",
    )
    await upsert([intl])
    renamed = dict(intl, name="Aisha Rahman Khan", mobile="")
    _, result = await upsert([renamed])
    assert result.students_created == 0 and result.students_updated == 1
    student = await one(Student, Student.passport_hmac == hmac_bytes("N1234567", "passport"))
    assert student.name == "Aisha Rahman Khan" and decrypt(student.passport_encrypted) == "N1234567"
    assert student.mobile_last4 == "0007"  # a blank mobile keeps the stored one
    assert student.consent_status is ConsentStatus.INTERNATIONAL and student.nationality == "BD"


async def test_malformed_apaar_is_recorded_on_the_enrolment(world):
    _, result = await upsert([student_row(8, apaar_id="2026000003A09")])
    assert result.created == 1
    enrolment = await one(Enrolment, Enrolment.id == result.outcomes[0].enrolment_id)
    assert enrolment.apaar_problem == "contains characters other than digits"
    student = await one(Student, Student.id == enrolment.student_id)
    assert student.apaar_hmac is None and student.consent_status is ConsentStatus.PENDING
    assert student.provisional_id.startswith("PRV-")


async def test_same_apaar_at_two_institutions_is_one_student(world):
    await upsert([ROW])
    xyz = dict(ROW, programme_code="ECE", counselling_ref="TNEA-2026-R1-000001")
    _, result = await upsert([xyz], aicte_id="1-XYZ-0002")
    assert result.created == 1 and result.students_created == 0
    assert await count(Student) == 1 and await count(Enrolment) == 2


async def test_changed_fields_update_the_enrolment(world):
    batch, _ = await upsert([ROW])
    changed = dict(ROW, category="EWS", admission_date="2026-08-05")
    second, result = await upsert([changed])
    assert result.updated == 1 and result.withdrawn == 0
    enrolment = await one(Enrolment, Enrolment.id == result.outcomes[0].enrolment_id)
    assert enrolment.category.value == "EWS" and enrolment.admission_date == date(2026, 8, 5)
    assert enrolment.upload_batch_id == second.id
    assert enrolment.status_date == upload_date(batch.created_at)  # status unchanged
