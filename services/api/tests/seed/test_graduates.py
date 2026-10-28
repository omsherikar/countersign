"""graduates.jsonl -> GRADUATED enrolments of 2025-26 (D28): stored like an upload, idempotent,
and never counted in the 2026-27 figures."""

import json
import shutil

import pytest
from sqlalchemy import func, select

from app.core import audit
from app.core.crypto import decrypt, hmac_bytes
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import AdmissionRoute, Category, ConsentStatus, EnrolmentStatus
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.verification import Check, Flag
from app.seed.importer import SeedError, import_directory
from tests.conftest import FIXTURE_DIR, institution_id, truncate_all

GRADUATES = [json.loads(line) for line in (FIXTURE_DIR / "graduates.jsonl").open()]


async def graduate_rows():
    async with session_factory()() as session:
        stmt = (
            select(Enrolment, Student, Institution.aicte_permanent_id, Programme.code)
            .join(Student, Student.id == Enrolment.student_id)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .where(Enrolment.status == EnrolmentStatus.GRADUATED)
            .order_by(Student.name)
        )
        return (await session.execute(stmt)).all()


async def count(stmt) -> int:
    async with session_factory()() as session:
        return (await session.execute(stmt)).scalar_one()


async def test_graduates_are_stored_like_an_upload_and_a_rerun_changes_nothing(clean_db):
    summary = await import_directory(session_factory(), FIXTURE_DIR)
    created = {k: v.created for k, v in summary.counts.items()}
    assert created["graduate_students"] == 4 and created["graduates"] == 4
    assert "graduate_students" in summary.table()

    rows = await graduate_rows()
    assert len(rows) == 4
    by_name = {student.name: (e, student, aid, code) for e, student, aid, code in rows}
    for grad in GRADUATES:
        e, student, aid, code = by_name[grad["name"]]
        assert (aid, code) == (grad["institution_aicte_id"], grad["programme_code"])
        assert (e.academic_year, e.year_of_study, e.cohort_year) == ("2025-26", 4, "2022-23")
        assert e.seat_id is None and e.upload_batch_id is None and e.source_row_no is None
        assert e.admission_date.isoformat() == grad["admission_date"]
        assert e.status_date.isoformat() == grad["status_date"]
        assert e.admission_route is AdmissionRoute(grad["admission_route"])
        assert e.category is Category(grad["category"])
        assert student.dob.isoformat() == grad["dob"] and student.email == grad["email"]
        assert student.mobile_hmac == hmac_bytes(grad["mobile"], "mobile")
        assert student.mobile_last4 == grad["mobile"][-4:]
        assert student.name_normalized and student.name_key
        if grad["apaar_id"]:
            assert student.consent_status is ConsentStatus.LINKED
            assert student.apaar_hmac == hmac_bytes(grad["apaar_id"], "apaar")
            assert decrypt(student.apaar_encrypted) == grad["apaar_id"]
            assert student.apaar_last4 == grad["apaar_id"][-4:]
            assert student.provisional_id is None
        else:
            assert student.consent_status is ConsentStatus.PENDING
            assert student.apaar_hmac is None and student.apaar_encrypted is None
            assert student.apaar_last4 is None
            assert student.provisional_id == grad["provisional_id"] == "PRV-GQ4DKN7A"
    ids = [e.id for e, *_ in rows]
    assert (
        await count(select(func.count()).select_from(Check).where(Check.enrolment_id.in_(ids))) == 0
    )
    assert (
        await count(select(func.count()).select_from(Flag).where(Flag.enrolment_id.in_(ids))) == 0
    )

    students = await count(select(func.count()).select_from(Student))
    enrolments = await count(select(func.count()).select_from(Enrolment))
    again = await import_directory(session_factory(), FIXTURE_DIR)
    assert again.counts["graduate_students"].created == 0
    assert again.counts["graduate_students"].existing == 4
    assert (again.counts["graduates"].created, again.counts["graduates"].existing) == (0, 4)
    assert await count(select(func.count()).select_from(Student)) == students
    assert await count(select(func.count()).select_from(Enrolment)) == enrolments

    async with session_factory()() as session:
        seeds = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type == "graduates_file")
                    .order_by(AuditLog.seq)
                )
            )
            .scalars()
            .all()
        )
        assert [s.actor_id for s in seeds] == [None, None]
        assert seeds[0].after == {
            "file": "graduates.jsonl",
            "graduates": 4,
            "students_created": 4,
            "enrolments_created": 4,
        }
        assert seeds[1].after["students_created"] == 0 and seeds[1].after["enrolments_created"] == 0
        assert "Meera" not in json.dumps(seeds[0].after)
        ok, _, broken = await audit.verify_chain(session)
        assert ok and broken is None


async def test_graduates_never_count_in_the_current_year(seeded, admin, registrar_abc, university):
    abc = await institution_id("1-ABC-0001")
    active = (
        select(func.count())
        .select_from(Enrolment)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .where(Enrolment.academic_year == "2026-27", Enrolment.status == EnrolmentStatus.ACTIVE)
    )
    national = await count(active)
    at_abc = await count(active.where(Institution.aicte_permanent_id == "1-ABC-0001"))
    graduated_at_abc = sum(g["institution_aicte_id"] == "1-ABC-0001" for g in GRADUATES)
    assert graduated_at_abc == 3

    summary = (await admin.get("/dashboard/summary")).json()
    assert summary["kpis"]["enrolments"] == national
    last_year = (await admin.get("/dashboard/summary", params={"academic_year": "2025-26"})).json()
    assert last_year["kpis"]["enrolments"] == 0  # GRADUATED is not on that year's roll either
    rows = (await admin.get("/institutions")).json()["items"]
    assert next(r for r in rows if r["id"] == abc)["enrolments"] == at_abc
    detail = (await admin.get(f"/institutions/{abc}")).json()
    assert detail["enrolments"] == at_abc
    assert (await registrar_abc.get("/dashboard/summary")).json()["kpis"]["enrolments"] == at_abc
    assert (await university.get("/dashboard/summary")).json()["kpis"]["enrolments"] == at_abc

    url = f"/institutions/{abc}/enrolments"
    current = (await registrar_abc.get(url, params={"academic_year": "2026-27"})).json()
    assert current["total"] == at_abc
    assert all(r["status"] != "GRADUATED" for r in current["items"])
    previous = (
        await registrar_abc.get(url, params={"academic_year": "2025-26", "status": "GRADUATED"})
    ).json()
    assert previous["total"] == graduated_at_abc
    assert {r["student"]["name"] for r in previous["items"]} == {
        g["name"] for g in GRADUATES if g["institution_aicte_id"] == "1-ABC-0001"
    }
    assert all(r["seat_code"] is None and r["flags"] == [] for r in previous["items"])


async def test_notice_replies_are_left_to_their_own_command(clean_db, tmp_path):
    source = tmp_path / "data"
    shutil.copytree(FIXTURE_DIR, source)
    (source / "notice_replies.jsonl").write_text("not json at all\n", encoding="utf-8")
    summary = await import_directory(session_factory(), source)
    assert "notice_replies.jsonl" not in summary.files
    assert summary.counts["graduates"].created == 4


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"academic_year": "2026-27"}, "is the current academic year"),
        ({"institution_aicte_id": "1-NOPE-0000"}, "institution 1-NOPE-0000"),
        ({"programme_code": "MBA-X"}, "programme MBA-X"),
        ({"apaar_id": None, "consent_status": "PENDING", "provisional_id": None}, "needs an APAAR"),
    ],
)
async def test_a_bad_graduate_line_stops_the_seed(clean_db, tmp_path, change, message):
    source = tmp_path / "data"
    shutil.copytree(FIXTURE_DIR, source)
    lines = [{**GRADUATES[0], **change}, *GRADUATES[1:]]
    (source / "graduates.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8"
    )
    try:
        with pytest.raises(SeedError, match=message):
            await import_directory(session_factory(), source)
    finally:
        await truncate_all()  # the institutions went in before the bad line
