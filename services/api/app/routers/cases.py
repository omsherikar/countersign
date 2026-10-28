"""Officer actions on a flag, the college's response and attachment downloads (D25,
API_CONTRACT §A3.9 to §A3.12).

POST /flags/{id}/response takes multipart/form-data, the second exemption from the
JSON-only rule after POST /uploads. Its files are checked and written before any database
write and removed again when the response does not commit, so no file outlives a
rolled-back response. The REQUEST_DOCS email goes out after the commit; a mail failure is
logged and never undoes the action.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.cases import attachments, transitions
from app.cases import service as cases
from app.core import audit
from app.core.audit import AuditEntry
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import ApiError, not_found
from app.models.enums import AuditAction, CaseActionKind, UserRole
from app.models.user import User
from app.models.verification import CaseAttachment
from app.notices.mailer import MailMessage, build_mailer
from app.routers.flags import build_detail
from app.schemas.flags import CaseActionIn, FlagDetail

log = logging.getLogger("countersign.cases")

router = APIRouter(prefix="/flags", tags=["cases"])

Officer = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER))]
College = Annotated[User, Depends(require_roles(UserRole.INSTITUTION))]
Reader = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
# more parts than this is not a college response; three are allowed
FORM_MAX_FILES = 32


async def send_mail(messages: Sequence[MailMessage]) -> None:
    """Send after the commit; a failure is logged, never raised."""
    try:
        results = await asyncio.to_thread(build_mailer().send_many, messages)
    except Exception:
        log.exception("document request email not sent", extra={"messages": len(messages)})
        return
    failed = [r.error for r in results if not r.ok]
    if failed:
        log.warning(
            "document request email not delivered",
            extra={"failed": len(failed), "error": failed[0]},
        )


@router.post("/{flag_id}/actions", response_model=FlagDetail)
async def flag_action(
    flag_id: uuid.UUID,
    body: CaseActionIn,
    session: SessionDep,
    user: Officer,
    request_id: RequestId,
) -> FlagDetail:
    result = await cases.apply_action(
        session,
        user,
        flag_id,
        action=CaseActionKind(body.action),
        note=body.note,
        due_date=body.due_date,
        assignee_id=body.assignee_id,
        assignee_given="assignee_id" in body.model_fields_set,
    )
    detail = await build_detail(session, user, flag_id, request_id=request_id)
    if result.messages:
        await session.commit()
        await send_mail(result.messages)
    return detail


def _invalid(fields: list[dict[str, str]]) -> ApiError:
    first = fields[0]
    message = first["message"]
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{first['field']}: {message[:1].lower()}{message[1:]}",
        {"fields": fields},
    )


@router.post("/{flag_id}/response", status_code=201, response_model=FlagDetail)
async def flag_response(
    flag_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: College,
    request_id: RequestId,
) -> FlagDetail:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > attachments.MAX_BODY_BYTES:
        raise attachments.too_large()
    form = await request.form(max_files=FORM_MAX_FILES, max_fields=8)
    try:
        raw_note = form.get("note")
        note = raw_note.strip() if isinstance(raw_note, str) else ""
        # an empty file input still sends a part with no name and no bytes
        files = [
            part
            for part in form.getlist("files")
            if isinstance(part, UploadFile) and (part.filename or part.size)
        ]
        fields: list[dict[str, str]] = []
        if not note:
            fields.append({"field": "note", "message": cases.NOTE_REQUIRED})
        elif len(note) > cases.NOTE_MAX:
            fields.append({"field": "note", "message": cases.NOTE_TOO_LONG})
        if len(files) > attachments.MAX_FILES:
            fields.append({"field": "files", "message": "Attach at most 3 files."})
        if fields:
            raise _invalid(fields)

        # scope and status before any file is written
        flag = await cases.scoped_flag(session, user, flag_id)
        transitions.check(user.role, flag.status, CaseActionKind.COLLEGE_RESPONSE)
        stored = await attachments.store_all(files)
    finally:
        await form.close()
    try:
        await cases.college_response(session, user, flag_id, note=note, files=stored)
        detail = await build_detail(session, user, flag_id, request_id=request_id)
        await session.commit()
    except BaseException:
        attachments.discard(s.storage_key for s in stored)
        raise
    return detail


def _disposition(filename: str) -> str:
    fallback = "".join(ch if 32 <= ord(ch) < 127 and ch not in '"\\' else "_" for ch in filename)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


@router.get("/{flag_id}/attachments/{attachment_id}")
async def flag_attachment(
    flag_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: SessionDep,
    user: Reader,
    request_id: RequestId,
) -> Response:
    try:
        flag = await cases.scoped_flag(session, user, flag_id)
    except ApiError as exc:
        if exc.status_code == 404:
            raise not_found("Attachment") from None
        raise
    attachment = (
        await session.execute(
            select(CaseAttachment).where(
                CaseAttachment.id == attachment_id, CaseAttachment.flag_id == flag.id
            )
        )
    ).scalar_one_or_none()
    if attachment is None:
        raise not_found("Attachment")
    try:
        data = await asyncio.to_thread(attachments.read, attachment.storage_key)
    except FileNotFoundError:
        log.error("attachment file missing", extra={"attachment_id": str(attachment.id)})
        raise not_found("Attachment") from None
    await audit.record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.READ,
                entity_type="case_attachment",
                entity_id=attachment.id,
                actor_id=user.id,
                after={"flag_id": str(flag.id)},
                request_id=request_id,
            )
        ],
    )
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": _disposition(attachment.filename),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
