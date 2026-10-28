"""POST /flags/{id}/response and GET /flags/{id}/attachments/{attachment_id}: files are
checked by their bytes, all or nothing, encrypted at rest, and downloaded only in scope,
with a READ in the audit log."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import func, select

from app.cases import attachments
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.enums import FlagStatus
from app.models.verification import CaseAction, CaseAttachment
from tests.cases.conftest import load_flag, new_flag, stored_files

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
EXE = b"MZ\x90\x00\x03" + b"\x00" * 64


async def respond(client, flag_id, files, note: str = "Extract attached."):
    return await client.post(f"/flags/{flag_id}/response", data={"note": note}, files=files)


async def counts(flag_id) -> tuple[int, int]:
    async with session_factory()() as session:
        actions = (
            await session.execute(
                select(func.count())
                .select_from(CaseAction)
                .where(CaseAction.flag_id == flag_id, CaseAction.action == "COLLEGE_RESPONSE")
            )
        ).scalar_one()
        files = (
            await session.execute(
                select(func.count())
                .select_from(CaseAttachment)
                .where(CaseAttachment.flag_id == flag_id)
            )
        ).scalar_one()
    return actions, files


async def test_three_files_are_accepted_and_stored_encrypted(cw, logins, case_files) -> None:
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    files = [
        ("files", ("admission_register_cse.pdf", PDF, "application/pdf")),
        ("files", ("photo.png", PNG, "image/png")),
        # the declared type is not trusted: these bytes are a JPEG
        ("files", ("../../scan.bin", JPEG, "application/octet-stream")),
    ]
    response = await respond(registrar, flag_id, files)
    assert response.status_code == 201, response.text
    detail = response.json()
    assert detail["status"] == "DOCS_REQUESTED" and detail["response_received"] is True
    assert detail["can_respond"] is True
    row = detail["history"][-1]
    assert row["action"] == "COLLEGE_RESPONSE" and row["note"] == "Extract attached."
    assert row["from_status"] == row["to_status"] == "DOCS_REQUESTED"
    assert row["actor"]["role"] == "INSTITUTION"
    assert [(a["filename"], a["content_type"], a["size_bytes"]) for a in row["attachments"]] == [
        ("admission_register_cse.pdf", "application/pdf", len(PDF)),
        ("photo.png", "image/png", len(PNG)),
        ("scan.bin", "image/jpeg", len(JPEG)),
    ]
    assert row["attachments"][0]["sha256"] == hashlib.sha256(PDF).hexdigest()

    on_disk = stored_files(case_files)
    assert len(on_disk) == 3
    for path in on_disk:
        raw = path.read_bytes()
        assert PDF not in raw and b"PNG" not in raw  # encrypted at rest
        assert len(path.name) == 32  # a random name, never the college's
    assert (await counts(flag_id)) == (1, 3)

    async with session_factory()() as session:
        entries = (
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.entity_type.in_(["flag", "case_attachment"]))
                    .where(AuditLog.action.in_(["UPDATE", "CREATE"]))
                    .order_by(AuditLog.seq.desc())
                    .limit(4)
                )
            )
            .scalars()
            .all()
        )
    kinds = sorted((e.action.value, e.entity_type) for e in entries)
    assert kinds == [("CREATE", "case_attachment")] * 3 + [("UPDATE", "flag")]
    created = next(e for e in entries if e.entity_type == "case_attachment")
    assert set(created.after) == {"flag_id", "sha256", "size_bytes", "content_type"}
    assert all(e.actor_id == cw.users["registrar@abc.edu.demo"] for e in entries)


@pytest.mark.parametrize(
    ("files", "status", "code", "filename"),
    [
        (
            [("files", (f"part{i}.pdf", PDF, "application/pdf")) for i in range(4)],
            422,
            "VALIDATION_ERROR",
            None,
        ),
        (
            [
                ("files", ("ok.pdf", PDF, "application/pdf")),
                ("files", ("big.pdf", PDF + b"0" * (6 * 1024 * 1024), "application/pdf")),
            ],
            413,
            "ATTACHMENT_TOO_LARGE",
            "big.pdf",
        ),
        (
            [
                ("files", ("ok.pdf", PDF, "application/pdf")),
                ("files", ("register.pdf", EXE, "application/pdf")),
            ],
            415,
            "ATTACHMENT_TYPE",
            "register.pdf",
        ),
    ],
    ids=["fourth file", "six megabytes", "renamed exe"],
)
async def test_one_bad_file_rejects_the_whole_response(
    cw, logins, case_files, files, status, code, filename
) -> None:
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    response = await respond(registrar, flag_id, files)
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert error["code"] == code
    if filename is not None:
        assert error["details"]["filename"] == filename
    if status == 413:
        assert error["message"] == "Each file can be at most 5 MB."
        assert error["details"]["max_bytes"] == 5_242_880
    if status == 415:
        assert error["message"] == "Only PDF, PNG and JPEG files can be attached."
    if status == 422:
        assert error["details"]["fields"] == [
            {"field": "files", "message": "Attach at most 3 files."}
        ]
    assert stored_files(case_files) == []
    assert (await counts(flag_id)) == (0, 0)
    assert (await load_flag(flag_id)).response_received is False


async def test_a_failed_save_leaves_no_file_behind(cw, logins, case_files, monkeypatch) -> None:
    async def broken(*args, **kwargs):
        raise RuntimeError("database went away")

    monkeypatch.setattr("app.cases.service.college_response", broken)
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    with pytest.raises(RuntimeError):
        await respond(registrar, flag_id, [("files", ("a.pdf", PDF, "application/pdf"))])
    assert stored_files(case_files) == []


async def test_a_body_over_the_limit_is_refused_before_reading(
    cw, logins, case_files, monkeypatch
) -> None:
    monkeypatch.setattr(attachments, "MAX_BODY_BYTES", 1024)
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    big = [("files", ("a.pdf", PDF * 40, "application/pdf"))]
    response = await respond(registrar, flag_id, big)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "ATTACHMENT_TOO_LARGE"
    assert stored_files(case_files) == []


async def test_note_is_required_and_no_file_is_written_out_of_turn(cw, logins, case_files) -> None:
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    one = [("files", ("a.pdf", PDF, "application/pdf"))]
    blank = await respond(registrar, flag_id, one, note="  ")
    assert blank.status_code == 422
    assert blank.json()["error"]["details"]["fields"][0] == {
        "field": "note",
        "message": "Add a note before you continue.",
    }
    other = await new_flag(cw, institution="xyz", status=FlagStatus.DOCS_REQUESTED)
    assert (await respond(registrar, other, one)).status_code == 404
    closed = await new_flag(cw, status=FlagStatus.OPEN)
    assert (await respond(registrar, closed, one)).status_code == 409
    assert stored_files(case_files) == []
    # a form is the only body this route takes
    as_json = await registrar.post(f"/flags/{flag_id}/response", json={"note": "x"})
    assert as_json.status_code == 415


async def test_download_is_scoped_and_audited(cw, logins, case_files) -> None:
    registrar = await logins("registrar@abc.edu.demo")
    flag_id = await new_flag(cw, status=FlagStatus.DOCS_REQUESTED)
    files = [("files", ("admission register (CSE).pdf", PDF, "application/pdf"))]
    detail = (await respond(registrar, flag_id, files)).json()
    attachment = detail["history"][-1]["attachments"][0]
    url = f"/flags/{flag_id}/attachments/{attachment['id']}"

    for email in ("admin@aicte.demo", "ro.west@aicte.demo", "registrar@abc.edu.demo"):
        response = await (await logins(email)).get(url)
        assert response.status_code == 200, email
        assert response.content == PDF
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-disposition"] == (
            'attachment; filename="admission register (CSE).pdf"; '
            "filename*=UTF-8''admission%20register%20%28CSE%29.pdf"
        )
    for email in ("ro.south@aicte.demo", "registrar@xyz.edu.demo"):
        response = await (await logins(email)).get(url)
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Attachment not found."
    for email in ("coe@univ.demo", "student@demo"):
        assert (await (await logins(email)).get(url)).status_code == 403
    # an attachment asked for under another flag does not exist there
    other = await new_flag(cw)
    elsewhere = await (await logins("admin@aicte.demo")).get(
        f"/flags/{other}/attachments/{attachment['id']}"
    )
    assert elsewhere.status_code == 404

    async with session_factory()() as session:
        reads = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "case_attachment",
                        AuditLog.action == "READ",
                        AuditLog.entity_id == attachment["id"],
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(reads) == 3
    assert {r.actor_id for r in reads} == {
        cw.users[e] for e in ("admin@aicte.demo", "ro.west@aicte.demo", "registrar@abc.edu.demo")
    }
    assert all(r.after == {"flag_id": str(flag_id)} for r in reads)
