"""Upload endpoints (API_CONTRACT §A2.4 to §A2.9, §A4.16, scoping §A2.22).

POST /uploads takes multipart/form-data (the one exemption from the JSON-only rule) and
POST /uploads/rows takes JSON. Both check the header synchronously, through the college's
saved column mapping (422 UPLOAD_HEADER_UNMAPPED when unknown headers leave a required
column missing; nothing is saved then), spool the upload
encrypted, commit the batch as QUEUED and hand it to run_batch: inline after the response
when UPLOAD_INLINE is true (then the batch's student notices follow it), otherwise on the
Celery worker, which queues the notices itself.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import ApiError, not_found
from app.db.session import session_factory
from app.engine import pipeline
from app.engine.upload import mapping as column_mapping
from app.engine.upload.batches import COUNT_KEYS, batch_in_progress, create_batch
from app.engine.upload.parse import file_kind, parse_rows, parse_upload, too_many_rows
from app.engine.upload.spool import canonical_rows, delete_spool, write_spool
from app.engine.upload.types import UPLOAD_COLUMNS, UploadFileError
from app.models.enums import (
    RecordStatus,
    RowErrorLevel,
    UploadSource,
    UploadStage,
    UploadStatus,
    UserRole,
)
from app.models.institution import Approval, Institution, Programme
from app.models.upload import UploadBatch, UploadRowError
from app.models.user import User
from app.schemas.common import Page, PageParams, page_params
from app.schemas.uploads import (
    MappedColumn,
    SameFile,
    UploadAccepted,
    UploadBatchOut,
    UploadCounts,
    Uploader,
    UploadRowErrorOut,
    UploadRowsIn,
    UploadSourceStat,
)

log = logging.getLogger("countersign.uploads")

router = APIRouter(prefix="/uploads", tags=["uploads"])

Writer = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.INSTITUTION))]
Reader = Annotated[
    User,
    Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER, UserRole.INSTITUTION)),
]
Paging = Annotated[PageParams, Depends(page_params)]

ACADEMIC_YEAR = re.compile(r"^\d{4}-\d{2}$")
FORM_OVERHEAD = 64 * 1024  # multipart boundaries and the small form fields
LABEL_MAX = 120
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HTTP_STATUS = {
    "UNSUPPORTED_FILE_TYPE": 415,
    "UPLOAD_HEADER_INVALID": 422,
    "UPLOAD_HEADER_UNMAPPED": 422,
    "UPLOAD_EMPTY": 422,
    "TOO_MANY_ROWS": 413,
}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _file_error(exc: UploadFileError) -> ApiError:
    return ApiError(HTTP_STATUS.get(exc.code, 422), exc.code, exc.message, exc.details)


def _too_large() -> ApiError:
    size = f"{get_settings().upload_max_bytes / (1024 * 1024):g} MB"
    return ApiError(
        413,
        "FILE_TOO_LARGE",
        f"The file is larger than {size}. Split it by programme and upload each part.",
    )


def _invalid(fields: list[dict[str, str]]) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", fields[0]["message"], {"fields": fields})


# ------------------------------------------------------------------- serialising


async def _same_file(session: AsyncSession, batch: UploadBatch) -> SameFile | None:
    if not batch.file_sha256:
        return None
    earlier = (
        await session.execute(
            select(UploadBatch.id, UploadBatch.created_at)
            .where(
                UploadBatch.institution_id == batch.institution_id,
                UploadBatch.file_sha256 == batch.file_sha256,
                UploadBatch.created_at < batch.created_at,
                UploadBatch.id != batch.id,
            )
            .order_by(UploadBatch.created_at.desc())
            .limit(1)
        )
    ).first()
    if earlier is None:
        return None
    return SameFile(batch_id=str(earlier.id), uploaded_at=_iso(earlier.created_at) or "")


async def _batch_out(
    session: AsyncSession, batch: UploadBatch, institution_name: str, uploader: User | None
) -> UploadBatchOut:
    counts = batch.counts or {}
    sources = counts.get("sources") or {}
    return UploadBatchOut(
        id=str(batch.id),
        institution_id=str(batch.institution_id),
        institution_name=institution_name,
        academic_year=batch.academic_year,
        filename=batch.filename,
        source=batch.source.value,
        kind=batch.kind.value,
        status=batch.status.value,
        stage=batch.stage.value if batch.stage else None,
        total_rows=batch.total_rows,
        stage_total=batch.stage_total,
        processed_rows=batch.processed_rows,
        progress_pct=pipeline.progress_pct(
            batch.status, batch.stage, batch.processed_rows, batch.stage_total
        ),
        counts=UploadCounts(
            **{k: int(counts.get(k) or 0) for k in COUNT_KEYS},
            records={
                s.value: int((counts.get("records") or {}).get(s.value) or 0) for s in RecordStatus
            },
        ),
        sources=[
            UploadSourceStat(
                source=name,
                calls=int(stat.get("calls") or 0),
                unavailable=int(stat.get("unavailable") or 0),
            )
            for name, stat in sources.items()
        ],
        timings_ms={k: int(v) for k, v in (counts.get("timings_ms") or {}).items()},
        error=batch.error,
        ignored_columns=list(batch.ignored_columns or []),
        column_mapping=[
            MappedColumn(header=str(m.get("header", "")), column=str(m.get("column", "")))
            for m in counts.get("column_mapping") or []
            if isinstance(m, dict)
        ],
        same_file_as=await _same_file(session, batch),
        uploaded_by=Uploader(
            id=str(batch.uploaded_by), name=uploader.name if uploader is not None else ""
        ),
        uploaded_at=_iso(batch.created_at) or "",
        started_at=_iso(batch.started_at),
        finished_at=_iso(batch.finished_at),
    )


def _scoped(stmt: Select, user: User) -> Select:
    """Restrict a SELECT joined to institutions to the user's uploads (§A2.22)."""
    if user.role is UserRole.AICTE_ADMIN:
        return stmt
    if user.role is UserRole.RO_OFFICER:
        return stmt.where(Institution.region_id == user.region_id)
    return stmt.where(Institution.id == user.institution_id)


def _batches_stmt() -> Select:
    return (
        select(UploadBatch, Institution.name, User)
        .join(Institution, Institution.id == UploadBatch.institution_id)
        .outerjoin(User, User.id == UploadBatch.uploaded_by)
    )


async def _scoped_batch(
    session: AsyncSession, user: User, batch_id: uuid.UUID
) -> tuple[UploadBatch, str, User | None]:
    row = (
        await session.execute(_scoped(_batches_stmt().where(UploadBatch.id == batch_id), user))
    ).first()
    if row is None:
        raise not_found("Upload")
    return row[0], row[1], row[2]


# ---------------------------------------------------------------------- templates


@router.get("/template.csv")
async def template_csv(user: Reader) -> Response:
    return Response(
        ",".join(UPLOAD_COLUMNS) + "\r\n",
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="countersign_upload_template.csv"'},
    )


@router.get("/template.xlsx")
async def template_xlsx(user: Reader) -> Response:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "students"
    sheet.append(list(UPLOAD_COLUMNS))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return Response(
        buffer.getvalue(),
        media_type=XLSX_TYPE,
        headers={"Content-Disposition": 'attachment; filename="countersign_upload_template.xlsx"'},
    )


# ------------------------------------------------------------------------ writes


async def _target_institution(
    session: AsyncSession, user: User, raw_id: Any, fields: list[dict[str, str]]
) -> Institution | None:
    """INSTITUTION: its own (any other id is 404). AICTE_ADMIN: the required institution_id."""
    given = str(raw_id).strip() if raw_id not in (None, "") else ""
    if user.role is UserRole.INSTITUTION:
        if given and given != str(user.institution_id):
            raise not_found("Institution")
        return await session.get(Institution, user.institution_id)
    if not given:
        fields.append(
            {"field": "institution_id", "message": "Choose the college this upload is for."}
        )
        return None
    try:
        institution_id = uuid.UUID(given)
    except ValueError:
        raise not_found("Institution") from None
    institution = await session.get(Institution, institution_id)
    if institution is None:
        raise not_found("Institution")
    return institution


async def _check_year(
    session: AsyncSession,
    institution: Institution | None,
    raw: Any,
    fields: list[dict[str, str]],
) -> str:
    year = str(raw).strip() if raw is not None else ""
    if not year:
        message = "Choose the academic year."
    elif not ACADEMIC_YEAR.match(year):
        message = "Academic year must look like 2026-27."
    elif (
        institution is not None
        and not (
            await session.execute(
                select(Approval.id)
                .join(Programme, Programme.id == Approval.programme_id)
                .where(Programme.institution_id == institution.id, Approval.academic_year == year)
                .limit(1)
            )
        ).first()
    ):
        message = f"Your college has no approvals for {year}."
    else:
        return year
    fields.append({"field": "academic_year", "message": message})
    return year


def _check_declaration(raw: Any, fields: list[dict[str, str]]) -> None:
    if raw is True or (isinstance(raw, str) and raw.strip().lower() == "true"):
        return
    fields.append({"field": "declaration", "message": "Tick the declaration to upload."})


async def _accept(
    session: AsyncSession,
    background: BackgroundTasks,
    *,
    user: User,
    institution: Institution,
    academic_year: str,
    filename: str,
    source: UploadSource,
    kind: str,
    data: bytes,
    request_id: str | None,
    response: Response,
) -> UploadAccepted:
    """Spool the upload, commit the QUEUED batch with its audit entry, then start it."""
    running = await batch_in_progress(session, institution.id, academic_year)
    if running is not None:
        raise ApiError(
            409,
            "UPLOAD_IN_PROGRESS",
            "An upload for this college and year is still being processed.",
            {"batch_id": str(running.id)},
        )
    batch_id = uuid.uuid4()
    await asyncio.to_thread(write_spool, batch_id, kind, data)  # type: ignore[arg-type]
    try:
        batch = await create_batch(
            session,
            institution_id=institution.id,
            academic_year=academic_year,
            filename=filename,
            source=source,
            uploaded_by=user.id,
            file_sha256=hashlib.sha256(data).hexdigest(),
            actor_id=user.id,
            batch_id=batch_id,
            request_id=request_id,
        )
        await session.commit()
    except BaseException:
        delete_spool(batch_id)
        raise
    await _start(session, batch, background)
    response.headers["Location"] = f"/uploads/{batch.id}"
    return UploadAccepted(batch=await _batch_out(session, batch, institution.name, user))


async def _run_inline(batch_id: uuid.UUID) -> None:
    """UPLOAD_INLINE: the batch, then its student notices and the college's completeness
    once it is DONE, as the worker would chain them. A failure in either is logged; the batch
    stays DONE."""
    batch = await pipeline.run_batch(batch_id)
    if batch.status is not UploadStatus.DONE:
        return
    from app.engine.completeness import refresh_one
    from app.notices.dispatch import send_notices_for_batch

    try:
        await send_notices_for_batch(batch_id)
    except Exception:
        log.exception("could not send student notices", extra={"batch_id": str(batch_id)})
    try:
        await refresh_one(session_factory(), batch.institution_id, batch.academic_year)
    except Exception:
        log.exception("could not refresh completeness", extra={"batch_id": str(batch_id)})


async def _start(session: AsyncSession, batch: UploadBatch, background: BackgroundTasks) -> None:
    if get_settings().upload_inline:
        background.add_task(_run_inline, batch.id)
        return
    from app.worker import enqueue_batch

    try:
        enqueue_batch(batch.id)
    except Exception:
        # Without a queue the batch would block this college's uploads; fail it instead.
        log.exception("could not enqueue upload batch", extra={"batch_id": str(batch.id)})
        stage = UploadStage.PARSE
        batch.status, batch.stage = UploadStatus.FAILED, stage
        batch.error, batch.finished_at = pipeline.stopped_error(stage), datetime.now(UTC)
        await session.execute(
            update(UploadBatch)
            .where(UploadBatch.id == batch.id)
            .values(
                status=batch.status,
                stage=stage,
                error=batch.error,
                finished_at=batch.finished_at,
            )
        )
        await session.commit()
        delete_spool(batch.id)


@router.post("", status_code=202, response_model=UploadAccepted)
async def create_upload(
    request: Request,
    response: Response,
    background: BackgroundTasks,
    session: SessionDep,
    user: Writer,
    request_id: RequestId,
) -> UploadAccepted:
    settings = get_settings()
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > settings.upload_max_bytes + FORM_OVERHEAD:
        raise _too_large()
    form = await request.form(max_files=1, max_fields=16)
    fields: list[dict[str, str]] = []
    institution = await _target_institution(session, user, form.get("institution_id"), fields)
    academic_year = await _check_year(session, institution, form.get("academic_year"), fields)
    _check_declaration(form.get("declaration"), fields)
    upload = form.get("file")
    if not isinstance(upload, UploadFile) or not upload.filename:
        fields.append({"field": "file", "message": "Choose a file to upload."})
    if fields:
        raise _invalid(fields)
    assert isinstance(upload, UploadFile) and upload.filename and institution is not None

    filename = PurePath(upload.filename.replace("\\", "/")).name
    kind = file_kind(filename)
    if kind is None:
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Only .csv and .xlsx files can be uploaded.")
    data = await upload.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise _too_large()
    saved = await column_mapping.load(session, institution.id)
    try:
        await asyncio.to_thread(parse_upload, data, filename, mapping=saved)
    except UploadFileError as exc:
        raise _file_error(exc) from None
    return await _accept(
        session,
        background,
        user=user,
        institution=institution,
        academic_year=academic_year,
        filename=filename,
        source=UploadSource.FILE,
        kind=kind,
        data=data,
        request_id=request_id,
        response=response,
    )


@router.post("/rows", status_code=202, response_model=UploadAccepted)
async def create_upload_rows(
    body: UploadRowsIn,
    response: Response,
    background: BackgroundTasks,
    session: SessionDep,
    user: Writer,
    request_id: RequestId,
) -> UploadAccepted:
    settings = get_settings()
    fields: list[dict[str, str]] = []
    institution = await _target_institution(session, user, body.institution_id, fields)
    academic_year = await _check_year(session, institution, body.academic_year, fields)
    _check_declaration(body.declaration, fields)
    label = body.label
    if label is not None and (not isinstance(label, str) or len(label.strip()) > LABEL_MAX):
        fields.append({"field": "label", "message": "Label must be at most 120 characters."})
    if fields:
        raise _invalid(fields)
    assert institution is not None
    if len(body.rows) > settings.upload_rows_api_max:
        raise _file_error(too_many_rows(settings.upload_rows_api_max))
    saved = await column_mapping.load(session, institution.id)
    try:
        parse_rows(body.rows, max_rows=settings.upload_rows_api_max, mapping=saved)
    except UploadFileError as exc:
        raise _file_error(exc) from None
    return await _accept(
        session,
        background,
        user=user,
        institution=institution,
        academic_year=academic_year,
        filename=(label or "").strip() or "rows.json",
        source=UploadSource.API,
        kind="json",
        data=canonical_rows(body.rows),
        request_id=request_id,
        response=response,
    )


# ------------------------------------------------------------------------- reads


@router.get("", response_model=Page[UploadBatchOut])
async def list_uploads(
    session: SessionDep,
    user: Reader,
    paging: Paging,
    institution_id: uuid.UUID | None = None,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    status: UploadStatus | None = None,
) -> Page[UploadBatchOut]:
    stmt = _scoped(_batches_stmt(), user)
    if institution_id is not None and user.role is not UserRole.INSTITUTION:
        stmt = stmt.where(UploadBatch.institution_id == institution_id)
    if academic_year:
        stmt = stmt.where(UploadBatch.academic_year == academic_year)
    if status is not None:
        stmt = stmt.where(UploadBatch.status == status)
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(UploadBatch.created_at.desc(), UploadBatch.id.desc())
            .offset(paging.offset)
            .limit(paging.page_size)
        )
    ).all()
    items = [await _batch_out(session, batch, name, uploader) for batch, name, uploader in rows]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/{batch_id}", response_model=UploadBatchOut)
async def get_upload(batch_id: uuid.UUID, session: SessionDep, user: Reader) -> UploadBatchOut:
    batch, name, uploader = await _scoped_batch(session, user, batch_id)
    return await _batch_out(session, batch, name, uploader)


def _errors_stmt(batch_id: uuid.UUID) -> Select:
    return (
        select(UploadRowError)
        .where(UploadRowError.batch_id == batch_id)
        .order_by(
            UploadRowError.row_no,
            UploadRowError.field.asc().nulls_first(),
            UploadRowError.created_at,
            UploadRowError.id,
        )
    )


def _error_out(error: UploadRowError) -> UploadRowErrorOut:
    return UploadRowErrorOut(
        row_no=error.row_no,
        level=error.level.value,
        field=error.field,
        code=error.code,
        message=error.message,
        value_masked=error.value_masked,
    )


@router.get("/{batch_id}/errors", response_model=Page[UploadRowErrorOut])
async def upload_errors(
    batch_id: uuid.UUID,
    session: SessionDep,
    user: Reader,
    paging: Paging,
    level: RowErrorLevel | None = None,
    code: Annotated[str | None, Query(max_length=40)] = None,
) -> Page[UploadRowErrorOut]:
    batch, _, _ = await _scoped_batch(session, user, batch_id)
    stmt = _errors_stmt(batch.id)
    if level is not None:
        stmt = stmt.where(UploadRowError.level == level)
    if code:
        stmt = stmt.where(UploadRowError.code == code.strip().upper())
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    errors = (
        (await session.execute(stmt.offset(paging.offset).limit(paging.page_size))).scalars().all()
    )
    return Page(
        items=[_error_out(e) for e in errors],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/{batch_id}/errors.csv")
async def upload_errors_csv(batch_id: uuid.UUID, session: SessionDep, user: Reader) -> Response:
    batch, _, _ = await _scoped_batch(session, user, batch_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["row_no", "level", "field", "code", "message", "value_masked"])
    for error in (await session.execute(_errors_stmt(batch.id))).scalars():
        writer.writerow(
            [
                error.row_no,
                error.level.value,
                error.field or "",
                error.code,
                error.message,
                error.value_masked or "",
            ]
        )
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", PurePath(batch.filename).stem) or "upload"
    return Response(
        "﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}_errors.csv"'},
    )
