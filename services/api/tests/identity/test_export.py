"""The student's export carries evidence states, provenance, the record status and the
record's history (API_CONTRACT §A4.13, §A3.22)."""

from __future__ import annotations

from app.db.session import session_factory
from app.models.enums import UploadSource
from app.models.student import EnrolmentVersion
from tests.identity.conftest import COUNTERSIGNED_ROWS, as_user, write_rows
from tests.notices.conftest import student_user

FILE = "1-ABC-0001_2026-27.csv"


async def test_the_export_carries_states_provenance_status_and_history(world):
    batch = await world.batch(source=UploadSource.SEED, filename=FILE)
    enrolment = await world.enrolment("Ravi Kumar Sharma", batch=batch, row_no=2)
    await write_rows(enrolment.id, COUNTERSIGNED_ROWS)
    async with session_factory()() as s:
        s.add(
            EnrolmentVersion(
                enrolment_id=enrolment.id,
                version=1,
                changes={"name": [None, "Ravi Kumar Sharma"], "year_of_study": [None, 1]},
                source="SEED",
                batch_id=batch.id,
            )
        )
        await s.commit()
    student = await student_user(enrolment.student_id)
    async with as_user(student) as c:
        export = (await c.get("/students/me/export.json")).json()
    [record] = export["enrolments"]
    assert record["record_status"] == "COUNTERSIGNED" and record["status_reason"]
    rows = {row["type"]: row for row in record["checks"]}
    assert set(rows) == {"IDENTITY", "SEAT", "ADMISSION"}
    admission = rows["ADMISSION"]
    assert admission["state"] == "CONFIRMED" and "status" not in admission
    assert admission["supplied_by"] == "State admission authority"
    assert admission["observed_at"] and "finding" in admission and "source_line" in admission
    [version] = record["history"]
    assert version == {
        "version": 1,
        "at": version["at"],
        "source": "SEED",
        "batch": {"id": str(batch.id), "filename": FILE, "row_no": 2},
        "case": None,
        "changes": [
            {"field": "name", "before": None, "after": "Ravi Kumar Sharma"},
            {"field": "year_of_study", "before": None, "after": 1},
        ],
    }
    assert "actor" not in version
