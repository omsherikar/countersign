"""Column mapping and enrolment versions (D42; API_CONTRACT §A4.7, §A4.16; ENGINES §17.8,
§17.9): a college maps its own headers once and later files map automatically; a file whose
unknown headers leave a required column missing is answered with UPLOAD_HEADER_UNMAPPED and
suggestions; every change to a record is a version, and an unchanged row writes none."""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.rules import get_rules
from app.db.session import session_factory
from app.engine import pipeline, versions
from app.engine.upload import mapping as column_mapping
from app.engine.upload.parse import parse_upload
from app.engine.upload.types import UploadFileError
from app.models.audit import AuditLog
from app.models.institution import Institution
from app.models.student import Enrolment, EnrolmentVersion, Student
from app.schemas.common import PageParams
from app.seed.importer import STAFF_ROLES, Summary, import_institutions, import_users
from tests.conftest import FIXTURE_DIR, login_as, truncate_all
from tests.pipeline.fakes import FakeEngines

THEIRS = {
    "Student Name": "name",
    "D.O.B.": "dob",
    "Course Code": "programme_code",
    "Year": "year_of_study",
    "Admission Type": "admission_route",
    "Caste Category": "category",
    "APAAR No.": "apaar_id",
    "APAAR Consent": "consent_status",
}
HEADERS = list(THEIRS) + ["Remarks"]


def their_file(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADERS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode()


def row(n: int, *, category: str = "GENERAL") -> dict[str, str]:
    return {
        "Student Name": f"Mapped Student {n:03d}",
        "D.O.B.": f"2007-02-{n:02d}",
        "Course Code": "CSE",
        "Year": "1",
        "Admission Type": "COUNSELLING",
        "Caste Category": category,
        "APAAR No.": "",
        "APAAR Consent": "PENDING",
        "Remarks": "ok",
    }


@pytest.fixture
async def clients(tmp_path, monkeypatch) -> AsyncIterator[dict]:
    await truncate_all()
    summary = Summary()
    async with session_factory()() as session:
        await import_institutions(session, FIXTURE_DIR / "institutions.json", get_rules(), summary)
        await import_users(session, FIXTURE_DIR / "users.json", summary, roles=STAFF_ROLES)
        await session.commit()
    monkeypatch.setattr(get_settings(), "upload_spool_dir", str(tmp_path / "spool"))
    monkeypatch.setattr(get_settings(), "upload_inline", True)
    monkeypatch.setattr(pipeline, "default_engines", FakeEngines)
    emails = {
        "admin": "admin@aicte.demo",
        "abc": "registrar@abc.edu.demo",
        "xyz": "registrar@xyz.edu.demo",
        "west": "ro.west@aicte.demo",
        "south": "ro.south@aicte.demo",
        "university": "coe@univ.demo",
    }
    out = {key: await login_as(email) for key, email in emails.items()}
    async with session_factory()() as session:
        out["abc_id"] = str(
            (
                await session.execute(
                    select(Institution.id).where(Institution.aicte_permanent_id == "1-ABC-0001")
                )
            ).scalar_one()
        )
    yield out
    for key, client in out.items():
        if key != "abc_id":
            await client.aclose()
    await truncate_all()


async def upload(client, data: bytes):
    return await client.post(
        "/uploads",
        data={"academic_year": "2026-27", "declaration": "true"},
        files={"file": ("1-ABC-0001_2026-27.csv", data, "text/csv")},
    )


def test_apply_and_suggest_are_pure() -> None:
    header_map = column_mapping.apply(HEADERS, THEIRS)
    assert header_map.missing == [] and header_map.unknown == ["Remarks"]
    assert header_map.mapped[:2] == [("Student Name", "name"), ("D.O.B.", "dob")]
    # without the mapping every required column is missing and the file is answered with
    # the headers to map
    with pytest.raises(UploadFileError) as caught:
        parse_upload(their_file([row(1)]), "f.csv")
    error = caught.value
    assert error.code == "UPLOAD_HEADER_UNMAPPED"
    assert error.message == (
        "The file has columns Countersign does not recognise. Map them to the template once, "
        "then upload again."
    )
    assert error.details["missing_columns"] == [
        "name",
        "dob",
        "programme_code",
        "year_of_study",
        "admission_route",
        "category",
    ]
    assert {s["header"]: s["column"] for s in error.details["suggestions"]} == THEIRS
    assert "Remarks" in error.details["unknown_headers"]
    # a template file with no unknown header keeps the older answer
    with pytest.raises(UploadFileError) as caught:
        parse_upload(b"name,dob\nA,2007-01-01\n", "f.csv")
    assert caught.value.code == "UPLOAD_HEADER_INVALID"
    parsed = parse_upload(their_file([row(1)]), "f.csv", mapping=THEIRS)
    assert parsed.rows[0].values["name"] == "Mapped Student 001"
    assert parsed.rows[0].values["year_of_study"] == "1"
    assert parsed.ignored_columns == ["Remarks"]
    assert parsed.column_mapping[0] == {"header": "Student Name", "column": "name"}


async def test_a_saved_mapping_reads_the_college_file(clients) -> None:
    abc, url = clients["abc"], f"/institutions/{clients['abc_id']}/column-mapping"
    data = their_file([row(1), row(2), row(3)])

    refused = await upload(abc, data)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "UPLOAD_HEADER_UNMAPPED"
    empty = (await abc.get(url)).json()
    assert empty["mapping"] == {} and empty["updated_at"] is None and empty["updated_by"] is None
    assert {"column": "name", "required": True} in empty["columns"]

    # the PUT rules
    bad = await abc.put(url, json={"mapping": {"Student Name": "student"}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"
    assert bad.json()["error"]["details"]["fields"][0]["message"] == "Map to a template column."
    twice = await abc.put(url, json={"mapping": {"Student Name": "name", "Full Name": "name"}})
    assert twice.status_code == 422 and twice.json()["error"]["code"] == "MAPPING_DUPLICATE"
    assert twice.json()["error"]["details"] == {"column": "name"}
    short = await abc.put(url, json={"mapping": {"Student Name": "name"}, "headers": HEADERS})
    assert short.status_code == 422 and short.json()["error"]["code"] == "MAPPING_INCOMPLETE"
    assert short.json()["error"]["details"]["missing_columns"][0] == "dob"
    assert (await clients["west"].put(url, json={"mapping": THEIRS})).status_code == 403
    assert (await clients["xyz"].get(url)).status_code == 404
    assert (await clients["south"].get(url)).status_code == 404
    assert (await clients["university"].get(url)).status_code == 403

    saved = await abc.put(url, json={"mapping": THEIRS, "headers": HEADERS})
    assert saved.status_code == 200, saved.text
    assert saved.json()["mapping"] == THEIRS
    assert saved.json()["updated_by"]["name"] == "Registrar, ABC College of Engineering"
    assert (await clients["west"].get(url)).json()["mapping"] == THEIRS
    async with session_factory()() as session:
        entry = (
            await session.execute(
                select(AuditLog).where(AuditLog.entity_type == "institution_column_mapping")
            )
        ).scalar_one()
    assert entry.after == {"headers": len(THEIRS)}

    accepted = await upload(abc, data)
    assert accepted.status_code == 202, accepted.text
    batch_id = accepted.json()["batch"]["id"]
    batch = (await abc.get(f"/uploads/{batch_id}")).json()
    assert batch["status"] == "DONE", batch
    assert batch["column_mapping"][:2] == [
        {"header": "Student Name", "column": "name"},
        {"header": "D.O.B.", "column": "dob"},
    ]
    assert batch["ignored_columns"] == ["Remarks"]
    assert batch["counts"]["created"] == 3 and batch["counts"]["versions"] == 3


async def test_versions_on_create_change_and_no_change(clients) -> None:
    abc = clients["abc"]
    url = f"/institutions/{clients['abc_id']}/column-mapping"
    assert (await abc.put(url, json={"mapping": THEIRS})).status_code == 200

    first = await upload(abc, their_file([row(1), row(2)]))
    assert first.status_code == 202
    async with session_factory()() as session:
        target = (
            await session.execute(
                select(Enrolment.id)
                .join(Student, Student.id == Enrolment.student_id)
                .where(Student.name == "Mapped Student 001")
            )
        ).scalar_one()
        created = (
            await session.execute(
                select(EnrolmentVersion).where(EnrolmentVersion.enrolment_id == target)
            )
        ).scalar_one()
    assert (created.version, created.source) == (1, "UPLOAD")
    assert set(created.changes) == set(versions.VERSIONED_FIELDS)
    assert created.changes["category"] == [None, "GENERAL"]
    assert created.changes["apaar_masked"] == [None, None]

    same = await upload(abc, their_file([row(1), row(2)]))
    batch = (await abc.get(f"/uploads/{same.json()['batch']['id']}")).json()
    assert batch["counts"]["unchanged"] == 2 and batch["counts"]["versions"] == 0

    changed = await upload(abc, their_file([row(1, category="OBC"), row(2)]))
    batch = (await abc.get(f"/uploads/{changed.json()['batch']['id']}")).json()
    assert batch["counts"]["updated"] == 1 and batch["counts"]["versions"] == 1
    async with session_factory()() as session:
        history = await versions.history(session, target, page=PageParams())
        latest = await versions.latest(session, target)
        assert await versions.count(session, target) == 2
    assert history["total"] == 2 and [i["version"] for i in history["items"]] == [2, 1]
    newest = history["items"][0]
    assert newest["changes"] == [{"field": "category", "before": "GENERAL", "after": "OBC"}]
    assert newest["source"] == "UPLOAD" and newest["case"] is None
    assert newest["actor"]["role"] == "INSTITUTION"
    assert newest["batch"] == {
        "id": changed.json()["batch"]["id"],
        "filename": "1-ABC-0001_2026-27.csv",
        "row_no": 2,
    }
    assert history["items"][1]["batch"]["row_no"] is None  # an earlier file's row
    assert latest == history["items"]
