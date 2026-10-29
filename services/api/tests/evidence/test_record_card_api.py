"""The record card, its history and the enrolment list over the mini seed (API_CONTRACT
§A4.5 to §A4.7, §A4.16 `counts.records`)."""

from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import session_factory
from app.models.enums import EnrolmentStatus
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from tests.conftest import institution_id

ROW_TYPES = ["IDENTITY", "SEAT", "ADMISSION", "STUDYING", "STUDENT"]
FULL_ROW = {
    "type",
    "state",
    "finding",
    "source_line",
    "summary",
    "supplied_by",
    "observed_at",
    "independent",
    "resolved",
    "source",
    "checked_at",
    "attempts",
    "detail",
}


async def _ravi() -> str:
    async with session_factory()() as session:
        return str(
            (
                await session.execute(
                    select(Enrolment.id)
                    .join(Student, Student.id == Enrolment.student_id)
                    .where(Student.name == "Ravi Kumar Sharma")
                )
            ).scalar_one()
        )


async def test_the_record_card_carries_rows_status_approval_and_history(
    admin, registrar_abc, registrar_xyz, student
) -> None:
    ravi = await _ravi()
    body = (await registrar_abc.get(f"/enrolments/{ravi}")).json()
    assert [r["type"] for r in body["checks"]] == ROW_TYPES
    assert all(set(r) == FULL_ROW for r in body["checks"])
    assert all("{date}" not in r["source_line"] for r in body["checks"])
    assert body["record_status"] in {
        "AWAITING_EVIDENCE",
        "COUNTERSIGNED",
        "UNDER_REVIEW",
        "DISPUTED",
    }
    assert body["status_reason"] and body["next_step"]
    assert body["approval"]["academic_year"] == "2026-27"
    assert body["approval"]["version"] >= 1
    assert body["eligibility"] == {
        "tfw_income_certified": None,
        "nri_sponsored": None,
        "ciwg": None,
    }
    assert body["claim"] is None  # a linked APAAR
    assert body["history_count"] >= 1 and len(body["versions"]) == body["history_count"]
    first = body["versions"][-1]
    assert (first["version"], first["source"], first["actor"]) == (1, "SEED", None)
    assert first["batch"]["filename"] == "1-ABC-0001_2026-27.csv"

    history = await registrar_abc.get(f"/enrolments/{ravi}/history", params={"page_size": 1})
    assert history.status_code == 200, history.text
    page = history.json()
    assert (page["total"], page["page"], page["page_size"]) == (body["history_count"], 1, 1)
    assert page["items"][0]["version"] == body["versions"][0]["version"]
    assert (await registrar_xyz.get(f"/enrolments/{ravi}/history")).status_code == 404
    assert (await student.get(f"/enrolments/{ravi}/history")).status_code == 403


async def test_a_refused_consent_record_shows_whether_it_was_claimed(registrar_abc) -> None:
    async with session_factory()() as session:
        refused = (
            await session.execute(
                select(Enrolment.id)
                .join(Student, Student.id == Enrolment.student_id)
                .where(Student.name == "Suresh Pawar")
            )
        ).scalar_one()
    body = (await registrar_abc.get(f"/enrolments/{refused}")).json()
    assert body["claim"] == {"claimed": False, "claimed_at": None}
    identity = body["checks"][0]
    assert (identity["state"], identity["source_line"]) == (
        "NOT_APPLICABLE",
        "APAAR not linked; alternative route not used yet",
    )
    assert body["next_step"] == (
        "Waiting for the student to sign in with DigiLocker and claim this record with its "
        "provisional ID."
    )


async def test_the_list_counts_records_by_status(admin) -> None:
    abc = await institution_id("1-ABC-0001")
    body = (await admin.get(f"/institutions/{abc}/enrolments", params={"page_size": 100})).json()
    active = sum(1 for r in body["items"] if r["status"] == "ACTIVE")
    assert sum(body["status_counts"].values()) == active
    left = [r for r in body["items"] if r["status"] != "ACTIVE"]
    assert all(r["record_status"] is None and r["status_reason"] is None for r in left)


async def test_each_upload_batch_counts_its_records_by_status(seeded) -> None:
    async with session_factory()() as session:
        for batch in (await session.execute(select(UploadBatch))).scalars():
            records = batch.counts["records"]
            assert set(records) == {
                "AWAITING_EVIDENCE",
                "COUNTERSIGNED",
                "UNDER_REVIEW",
                "DISPUTED",
            }
            active = await session.scalar(
                select(func.count())
                .select_from(Enrolment)
                .where(
                    Enrolment.upload_batch_id == batch.id,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                )
            )
            # an update file names some records of earlier batches too
            assert sum(records.values()) >= active
