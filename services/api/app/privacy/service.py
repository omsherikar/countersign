"""Consent records and data rights (D30). `record_consent` and `notice_consent_withdrawn` are
used by the notices loop and the wallet; the rest of the privacy service lives here too.

Every function runs in the caller's transaction and flushes, never commits. A student's
own reads never show in their access log, and no reader is ever named to them.
"""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core import audit
from app.core.audit import AuditEntry
from app.core.crypto import mask_apaar, mask_mobile
from app.core.errors import ApiError
from app.credentials import holder
from app.engine.contracts import CHECK_ORDER
from app.engine.evidence import fmt_date
from app.models.audit import AuditLog
from app.models.credential import Consent, Credential, CredentialPresentation, DataRequest
from app.models.enums import (
    AuditAction,
    ConsentPurpose,
    ConsentState,
    ConsentStatus,
    DataRequestKind,
    DataRequestStatus,
    EnrolmentStatus,
)
from app.models.institution import Institution, Programme
from app.models.seat import Seat
from app.models.student import Enrolment, EnrolmentVersion, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import CaseAction, Check, Flag, Notification
from app.privacy.notice import NOTICE_VERSION, UNLINK_APAAR, WITHDRAW_TEXTS, consent_text
from app.schemas.common import PageParams

PURPOSE_ORDER = (ConsentPurpose.APAAR_LINK, ConsentPurpose.NOTICE, ConsentPurpose.CREDENTIAL_SHARE)
WITHDRAWABLE = (ConsentPurpose.NOTICE, ConsentPurpose.CREDENTIAL_SHARE)
COLLEGE_UPLOAD = "COLLEGE_UPLOAD"
PORTAL = "PORTAL"
ACCESS_READY = "Your data is ready to download."
EXPORT_PATH = "/students/me/export.json"
# readers with no account: how a public page reached the record
# (`degree-*` entries were written before D44 and stay readable)
VERIFIER_VIAS = frozenset(
    {
        "verifier",
        "verifier-paste",
        "completion-qr",
        "completion-lookup",
        "degree-qr",
        "degree-lookup",
    }
)
# a university reading the record for its certificate (`degree-print` before D44)
CERTIFICATE_VIAS = frozenset({"certificate-print", "degree-print"})
NOTICE_LINK_VIA = "notice-link"
CLAIM_LABELS = {
    "name": "Name",
    "dob": "Date of birth",
    "apaar_masked": "APAAR (masked)",
    "institution": "Institution",
    "programme": "Programme",
    "academic_year": "Academic year",
    "year_of_study": "Year of study",
    "countersigned": "Countersigned by",
    "university": "University",
    "year_of_award": "Year of completion",
}
# the rows' labels (copy deck check.*)
CHECK_WORDS = {
    "IDENTITY": "Identity",
    "SEAT": "Seat",
    "ADMISSION": "Joining record",
    "STUDYING": "Credits",
    "STUDENT": "Student",
}


@dataclass(frozen=True, slots=True)
class DataRequestQuery:
    page: PageParams
    status: DataRequestStatus | None = None
    kind: DataRequestKind | None = None


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value.isoformat()


def invalid(field_name: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"{field_name}: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": field_name, "message": message}]},
    )


def _page(items: list[Any], total: int, page: PageParams) -> dict[str, Any]:
    return {"items": items, "total": total, "page": page.page, "page_size": page.page_size}


async def _count(session: AsyncSession, stmt) -> int:
    return (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()


# -------------------------------------------------------------------------- consents


async def record_consent(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    purpose: ConsentPurpose,
    status: ConsentState,
    channel: str,
    notice_text: str,
    enrolment_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Consent:
    """Append one consent row with the exact text shown, audited. Flushes only."""
    row = Consent(
        student_id=student_id,
        purpose=purpose,
        status=status,
        channel=channel,
        notice_text=notice_text,
        notice_version=NOTICE_VERSION,
        enrolment_id=enrolment_id,
        # not the transaction's now(): two records in one transaction must keep their order
        recorded_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    await audit.record(
        session,
        actor_id,
        AuditAction.CREATE,
        "consent",
        row.id,
        after={"purpose": purpose.value, "status": status.value, "channel": channel},
    )
    return row


async def record_apaar_link(
    session: AsyncSession,
    *,
    student_id: uuid.UUID,
    enrolment_id: uuid.UUID,
    consent_status: ConsentStatus,
    institution_name: str,
    actor_id: uuid.UUID | None,
    audit_sink: list[AuditEntry] | None = None,
) -> Consent | None:
    """The APAAR_LINK row a college upload records: LINKED gives GIVEN, REFUSED gives
    REFUSED, PENDING and INTERNATIONAL write nothing. Called by the upload only when a
    student is created or its consent changes. With `audit_sink` the row is only added to
    the session (the upload flushes it after the students it names) and its audit entry
    goes to the sink; without it the row is flushed and audited at once."""
    status = {
        ConsentStatus.LINKED: ConsentState.GIVEN,
        ConsentStatus.REFUSED: ConsentState.REFUSED,
    }.get(consent_status)
    if status is None:
        return None
    now = datetime.now(UTC)
    row = Consent(
        id=uuid.uuid4(),
        student_id=student_id,
        purpose=ConsentPurpose.APAAR_LINK,
        status=status,
        channel=COLLEGE_UPLOAD,
        notice_text=consent_text(ConsentPurpose.APAAR_LINK, institution_name=institution_name),
        notice_version=NOTICE_VERSION,
        enrolment_id=enrolment_id,
        recorded_at=now,
        created_at=now,
    )
    session.add(row)
    entry = AuditEntry(
        action=AuditAction.CREATE,
        entity_type="consent",
        entity_id=row.id,
        actor_id=actor_id,
        after={"purpose": row.purpose.value, "status": status.value, "channel": COLLEGE_UPLOAD},
    )
    if audit_sink is not None:
        audit_sink.append(entry)
    else:
        await session.flush()
        await audit.record_many(session, [entry])
    return row


async def notice_consent_withdrawn(
    session: AsyncSession, student_ids: Sequence[uuid.UUID]
) -> set[uuid.UUID]:
    """Students whose latest NOTICE consent is WITHDRAWN."""
    if not student_ids:
        return set()
    rows = await session.execute(
        select(Consent.student_id, Consent.status)
        .where(Consent.student_id.in_(student_ids), Consent.purpose == ConsentPurpose.NOTICE)
        .order_by(Consent.recorded_at)
    )
    latest = {student_id: status for student_id, status in rows}
    return {sid for sid, status in latest.items() if status == ConsentState.WITHDRAWN}


async def _briefs(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID | None]
) -> dict[uuid.UUID, dict[str, str]]:
    ids = list({i for i in enrolment_ids if i is not None})
    if not ids:
        return {}
    rows = await session.execute(
        select(Enrolment.id, Institution.name, Programme.name, Enrolment.academic_year)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .where(Enrolment.id.in_(ids))
    )
    return {
        enrolment_id: {
            "id": str(enrolment_id),
            "institution_name": institution_name,
            "programme_name": programme_name,
            "academic_year": academic_year,
        }
        for enrolment_id, institution_name, programme_name, academic_year in rows
    }


async def _consent_rows(session: AsyncSession, student_id: uuid.UUID) -> list[Consent]:
    return list(
        (
            await session.execute(
                select(Consent)
                .where(Consent.student_id == student_id)
                .order_by(Consent.recorded_at.desc(), Consent.id)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )


async def consents_view(session: AsyncSession, student_id: uuid.UUID) -> dict[str, Any]:
    """Every consent row, newest first, and the current state of each purpose."""
    rows = await _consent_rows(session, student_id)
    briefs = await _briefs(session, [r.enrolment_id for r in rows])
    items = [
        {
            "id": str(row.id),
            "purpose": row.purpose.value,
            "status": row.status.value,
            "channel": row.channel,
            "notice_text": row.notice_text,
            "notice_version": row.notice_version,
            "recorded_at": _iso(row.recorded_at),
            "withdrawn_at": _iso(row.withdrawn_at),
            "enrolment": briefs.get(row.enrolment_id) if row.enrolment_id else None,
        }
        for row in rows
    ]
    current = []
    for purpose in PURPOSE_ORDER:
        latest = next((r for r in rows if r.purpose is purpose), None)
        status = latest.status.value if latest else "NONE"
        since = None
        if latest is not None:
            since = _iso(latest.withdrawn_at or latest.recorded_at)
        if purpose is ConsentPurpose.NOTICE:
            can_withdraw = status != ConsentState.WITHDRAWN.value
        elif purpose is ConsentPurpose.CREDENTIAL_SHARE:
            can_withdraw = status == ConsentState.GIVEN.value
        else:
            can_withdraw = False  # unlinking an APAAR is a correction request
        current.append(
            {
                "purpose": purpose.value,
                "status": status,
                "since": since,
                "can_withdraw": can_withdraw,
            }
        )
    return {"current": current, "items": items}


def parse_purpose(raw: str) -> ConsentPurpose:
    """A purpose the student may withdraw; 422 otherwise, with the APAAR explanation."""
    if raw == ConsentPurpose.APAAR_LINK.value:
        raise invalid("purpose", UNLINK_APAAR)
    for purpose in WITHDRAWABLE:
        if raw == purpose.value:
            return purpose
    raise invalid("purpose", "Only NOTICE and CREDENTIAL_SHARE can be withdrawn.")


async def withdraw(
    session: AsyncSession, student_id: uuid.UUID, purpose: ConsentPurpose, user: User
) -> dict[str, Any]:
    """Withdraw NOTICE (no new notices) or CREDENTIAL_SHARE (every live proof expires now).
    Withdrawing what is already withdrawn changes nothing."""
    if purpose is ConsentPurpose.APAAR_LINK:
        raise invalid("purpose", UNLINK_APAAR)
    now = datetime.now(UTC)
    given = list(
        (
            await session.execute(
                select(Consent)
                .where(
                    Consent.student_id == student_id,
                    Consent.purpose == purpose,
                    Consent.status == ConsentState.GIVEN,
                )
                .order_by(Consent.recorded_at)
                .with_for_update()
            )
        ).scalars()
    )
    entries = []
    for row in given:
        row.status = ConsentState.WITHDRAWN
        row.withdrawn_at = now
        entries.append(
            AuditEntry(
                action=AuditAction.UPDATE,
                entity_type="consent",
                entity_id=row.id,
                actor_id=user.id,
                after={"purpose": purpose.value, "status": ConsentState.WITHDRAWN.value},
            )
        )
    if entries:
        await session.flush()
        await audit.record_many(session, entries)
    elif purpose is ConsentPurpose.NOTICE:
        latest = (
            await session.execute(
                select(Consent.status)
                .where(Consent.student_id == student_id, Consent.purpose == purpose)
                .order_by(Consent.recorded_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest is not ConsentState.WITHDRAWN:
            # nothing was given yet: keep the choice so no notice is sent later
            row = await record_consent(
                session,
                student_id=student_id,
                purpose=purpose,
                status=ConsentState.WITHDRAWN,
                channel=PORTAL,
                notice_text=WITHDRAW_TEXTS[purpose],
                actor_id=user.id,
            )
            row.withdrawn_at = row.recorded_at
            await session.flush()
    expired = 0
    if purpose is ConsentPurpose.CREDENTIAL_SHARE:
        expired = await holder.expire_live_presentations(session, student_id, now=now)
    view = await consents_view(session, student_id)
    return {**view, "presentations_expired": expired}


# -------------------------------------------------------------------------- access log


def _access_stmt(student_id: uuid.UUID, own_user_id: uuid.UUID | None):
    notices = select(Notification.id).where(Notification.student_id == student_id)
    credentials = select(Credential.id).where(Credential.student_id == student_id)
    proofs = (
        select(CredentialPresentation.id)
        .join(Credential, Credential.id == CredentialPresentation.credential_id)
        .where(Credential.student_id == student_id)
    )
    reader = aliased(User)
    stmt = (
        select(AuditLog.at, AuditLog.entity_type, AuditLog.after["via"].astext, reader.role)
        .outerjoin(reader, reader.id == AuditLog.actor_id)
        .where(AuditLog.action == AuditAction.READ)
        .where(
            or_(
                and_(AuditLog.entity_type == "student", AuditLog.entity_id == student_id),
                and_(AuditLog.entity_type == "notification", AuditLog.entity_id.in_(notices)),
                and_(AuditLog.entity_type == "credential", AuditLog.entity_id.in_(credentials)),
                and_(
                    AuditLog.entity_type == "credential_presentation",
                    AuditLog.entity_id.in_(proofs),
                ),
            )
        )
        .order_by(AuditLog.seq.desc())
    )
    if own_user_id is not None:
        stmt = stmt.where(or_(AuditLog.actor_id.is_(None), AuditLog.actor_id != own_user_id))
    return stmt


def _access_row(at: datetime, entity_type: str, via: str | None, role: Any) -> dict[str, Any]:
    if entity_type == "student":
        if via in CERTIFICATE_VIAS:
            what = "COMPLETION"
        else:
            what = {"export": "EXPORT"}.get(via or "", "RECORD")
    else:
        what = {"notification": "NOTICE", "credential": "CREDENTIAL"}.get(entity_type, "PROOF")
    if role is not None:
        who = role.value
    elif via in VERIFIER_VIAS:
        who = "VERIFIER"
    elif via == NOTICE_LINK_VIA:
        who = "NOTICE_LINK"
    else:
        who = "SYSTEM"
    return {"at": _iso(at), "role": who, "what": what}


async def access_log(
    session: AsyncSession, student_id: uuid.UUID, *, own_user_id: uuid.UUID, page: PageParams
) -> dict[str, Any]:
    """READ entries about the student's record, notices, proofs and shares, newest first:
    the reader's role and the date only, never the student's own reads."""
    stmt = _access_stmt(student_id, own_user_id)
    total = await _count(session, stmt)
    rows = (await session.execute(stmt.offset(page.offset).limit(page.page_size))).all()
    # the view is itself a read of the record, by the student, so it never shows here
    await audit.record(
        session, own_user_id, AuditAction.READ, "student", student_id, after={"via": "access-log"}
    )
    return _page([_access_row(*row) for row in rows], total, page)


# ------------------------------------------------------------------------ data requests


async def _request_rows(
    session: AsyncSession, requests: Sequence[DataRequest]
) -> list[dict[str, Any]]:
    briefs = await _briefs(
        session,
        [uuid.UUID(r.payload["enrolment_id"]) for r in requests if r.payload.get("enrolment_id")],
    )
    out = []
    for request in requests:
        enrolment_id = request.payload.get("enrolment_id")
        out.append(
            {
                "id": str(request.id),
                "kind": request.kind.value,
                "status": request.status.value,
                "details": request.details,
                "response": request.response,
                "enrolment": briefs.get(uuid.UUID(enrolment_id)) if enrolment_id else None,
                "created_at": _iso(request.created_at),
                "resolved_at": _iso(request.resolved_at),
                "export_path": EXPORT_PATH if request.kind is DataRequestKind.ACCESS else None,
            }
        )
    return out


async def create_request(
    session: AsyncSession, student_id: uuid.UUID, user: User, body: Any
) -> dict[str, Any]:
    """A student's request. ACCESS is fulfilled at once; CORRECTION and ERASURE wait for an
    AICTE officer."""
    if body.enrolment_id is not None:
        own = (
            await session.execute(
                select(Enrolment.id).where(
                    Enrolment.id == body.enrolment_id, Enrolment.student_id == student_id
                )
            )
        ).scalar_one_or_none()
        if own is None:
            raise invalid("enrolment_id", "Choose one of your enrolments.")
    now = datetime.now(UTC)
    access = body.kind is DataRequestKind.ACCESS
    request = DataRequest(
        id=uuid.uuid4(),
        student_id=student_id,
        kind=body.kind,
        status=DataRequestStatus.DONE if access else DataRequestStatus.OPEN,
        payload={"enrolment_id": str(body.enrolment_id)} if body.enrolment_id else {},
        details=body.details,
        response=ACCESS_READY if access else None,
        resolved_at=now if access else None,
        created_at=now,
    )
    session.add(request)
    await session.flush()
    await audit.record(
        session,
        user.id,
        AuditAction.CREATE,
        "data_request",
        request.id,
        after={"kind": request.kind.value, "status": request.status.value},
    )
    return (await _request_rows(session, [request]))[0]


async def student_requests(
    session: AsyncSession, student_id: uuid.UUID, page: PageParams
) -> dict[str, Any]:
    stmt = (
        select(DataRequest)
        .where(DataRequest.student_id == student_id)
        .order_by(DataRequest.created_at.desc(), DataRequest.id)
    )
    total = await _count(session, stmt)
    requests = list(
        (await session.execute(stmt.offset(page.offset).limit(page.page_size))).scalars()
    )
    return _page(await _request_rows(session, requests), total, page)


async def _admin_rows(
    session: AsyncSession, rows: Sequence[tuple[DataRequest, Student, Any, Any]]
) -> list[dict[str, Any]]:
    base = await _request_rows(session, [request for request, *_ in rows])
    out = []
    for item, (_, student, resolver_id, resolver_name) in zip(base, rows, strict=True):
        out.append(
            {
                **item,
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "apaar_masked": mask_apaar(student.apaar_last4),
                    "provisional_id": student.provisional_id,
                },
                "resolved_by": {"id": str(resolver_id), "name": resolver_name}
                if resolver_id is not None
                else None,
            }
        )
    return out


def _admin_stmt():
    resolver = aliased(User)
    return (
        select(DataRequest, Student, resolver.id, resolver.name)
        .join(Student, Student.id == DataRequest.student_id)
        .outerjoin(resolver, resolver.id == DataRequest.resolved_by_id)
    )


async def admin_requests(
    session: AsyncSession, user: User, query: DataRequestQuery
) -> dict[str, Any]:
    """Correction and erasure requests, OPEN first, then oldest first. An access request is
    fulfilled at once, so it is listed only when asked for by kind. Each student shown is
    a READ in the audit log."""
    stmt = _admin_stmt()
    if query.status is not None:
        stmt = stmt.where(DataRequest.status == query.status)
    if query.kind is not None:
        stmt = stmt.where(DataRequest.kind == query.kind)
    else:
        stmt = stmt.where(DataRequest.kind != DataRequestKind.ACCESS)
    total = await _count(session, stmt)
    open_first = case((DataRequest.status == DataRequestStatus.OPEN, 0), else_=1)
    rows = (
        await session.execute(
            stmt.order_by(open_first, DataRequest.created_at, DataRequest.id)
            .offset(query.page.offset)
            .limit(query.page.page_size)
        )
    ).all()
    await audit.record_read(session, user.id, "student", [student.id for _, student, *_ in rows])
    return _page(await _admin_rows(session, rows), total, query.page)


async def resolve(
    session: AsyncSession, request_id: uuid.UUID, user: User, body: Any
) -> dict[str, Any]:
    """DONE or REJECTED with a written response. Resolving changes no other data."""
    request = (
        await session.execute(
            select(DataRequest).where(DataRequest.id == request_id).with_for_update()
        )
    ).scalar_one_or_none()
    if request is None:
        raise ApiError(404, "NOT_FOUND", "Data request not found.")
    if request.status is not DataRequestStatus.OPEN:
        raise ApiError(
            409, "CONFLICT", "This request is already resolved.", {"reason": "ALREADY_RESOLVED"}
        )
    request.status = DataRequestStatus(body.status)
    request.response = body.response
    request.resolved_at = datetime.now(UTC)
    request.resolved_by_id = user.id
    await session.flush()
    await audit.record(
        session,
        user.id,
        AuditAction.UPDATE,
        "data_request",
        request.id,
        after={"status": request.status.value},
    )
    rows = (
        await session.execute(
            _admin_stmt()
            .where(DataRequest.id == request.id)
            .execution_options(populate_existing=True)
        )
    ).all()
    return (await _admin_rows(session, rows))[0]


# ----------------------------------------------------------------------------- export


def _b64json(part: str) -> Any:
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def _day(value: Any) -> str:
    try:
        return fmt_date(date.fromisoformat(str(value)))
    except ValueError:
        return str(value)


def _claim_value(key: str, value: Any) -> str:
    """The display value of API_CONTRACT §A3.15."""
    if key == "dob":
        return _day(value)
    if key == "countersigned" and isinstance(value, dict):
        checks = [CHECK_WORDS.get(c, str(c)) for c in value.get("checks", [])]
        words = " and ".join([", ".join(checks[:-1]), checks[-1]]) if len(checks) > 1 else ""
        words = words or "".join(checks)
        return f"{words}, as of {_day(value['on'])}" if value.get("on") else words
    if isinstance(value, dict):
        name = value.get("name", "")
        extra = value.get("aicte_id") or value.get("level") or value.get("code")
        return f"{name} ({extra})" if extra else str(name)
    return str(value)


def disclosed_claims(sd_jwt: str) -> list[dict[str, str]]:
    """The selectively disclosable claims of a stored SD-JWT, as {key, label, value}."""
    claims = []
    for part in sd_jwt.split("~")[1:]:
        if not part:
            continue
        try:
            disclosure = _b64json(part)
        except (ValueError, json.JSONDecodeError):
            continue
        if not isinstance(disclosure, list) or len(disclosure) != 3:
            continue
        _, key, value = disclosure
        claims.append(
            {"key": key, "label": CLAIM_LABELS.get(key, key), "value": _claim_value(key, value)}
        )
    return claims


def _credential_status(credential: Credential, now: datetime) -> str:
    if credential.revoked:
        return "REVOKED"
    if credential.expires_at is not None and credential.expires_at <= now:
        return "EXPIRED"
    return "ACTIVE"


async def _histories(
    session: AsyncSession, enrolment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Each enrolment's versions, newest first, as §A4.7 gives them without `actor`."""
    out: dict[uuid.UUID, list[dict[str, Any]]] = {}
    if not enrolment_ids:
        return out
    rows = (
        await session.execute(
            select(
                EnrolmentVersion,
                UploadBatch.filename,
                Enrolment.source_row_no,
                CaseAction.action,
                CaseAction.reason_code,
                Flag.id,
                Flag.type,
            )
            .join(Enrolment, Enrolment.id == EnrolmentVersion.enrolment_id)
            .outerjoin(UploadBatch, UploadBatch.id == EnrolmentVersion.batch_id)
            .outerjoin(CaseAction, CaseAction.seq == EnrolmentVersion.case_action_seq)
            .outerjoin(Flag, Flag.id == CaseAction.flag_id)
            .where(EnrolmentVersion.enrolment_id.in_(enrolment_ids))
            .order_by(EnrolmentVersion.enrolment_id, EnrolmentVersion.version.desc())
        )
    ).all()
    for version, filename, row_no, action, reason_code, flag_id, flag_type in rows:
        out.setdefault(version.enrolment_id, []).append(
            {
                "version": version.version,
                "at": _iso(version.at),
                "source": version.source,
                "batch": (
                    {"id": str(version.batch_id), "filename": filename, "row_no": row_no}
                    if version.batch_id is not None
                    else None
                ),
                "case": (
                    {
                        "id": str(flag_id),
                        "type": flag_type.value,
                        "action": action.value,
                        "case_action_seq": version.case_action_seq,
                        "reason_code": reason_code,
                    }
                    if version.case_action_seq is not None and flag_id is not None
                    else None
                ),
                "changes": [
                    {"field": name, "before": pair[0], "after": pair[1]}
                    for name, pair in (version.changes or {}).items()
                    if isinstance(pair, list | tuple) and len(pair) == 2
                ],
            }
        )
    return out


async def export(session: AsyncSession, student_id: uuid.UUID, user: User) -> dict[str, Any]:
    """Everything held about the student, APAAR masked, never another person's data. The
    export itself is a READ in the audit log."""
    from app.routers._enrolment_rows import flags_for, visible_summary

    student = await session.get(Student, student_id)
    if student is None:
        raise ApiError(404, "NOT_FOUND", "Student not found.")
    now = datetime.now(UTC)
    enrolment_rows = (
        await session.execute(
            select(Enrolment, Institution.name, Programme.name, Seat.seat_code)
            .join(Institution, Institution.id == Enrolment.institution_id)
            .join(Programme, Programme.id == Enrolment.programme_id)
            .outerjoin(Seat, Seat.id == Enrolment.seat_id)
            .where(Enrolment.student_id == student_id)
            .order_by(Enrolment.academic_year.desc(), Institution.name)
        )
    ).all()
    ids = [enrolment.id for enrolment, *_ in enrolment_rows]
    checks: dict[uuid.UUID, list[dict[str, Any]]] = {i: [] for i in ids}
    if ids:
        rows = list(
            (await session.execute(select(Check).where(Check.enrolment_id.in_(ids)))).scalars()
        )
        rows.sort(key=lambda c: CHECK_ORDER.index(c.type))
        for check in rows:
            detail = check.detail or {}
            checks[check.enrolment_id].append(
                {
                    "type": check.type.value,
                    "state": check.status.value,
                    "finding": detail.get("finding"),
                    "source_line": detail.get("source_line") or "",
                    "summary": detail.get("summary", ""),
                    "supplied_by": check.supplied_by,
                    "observed_at": _iso(check.observed_at),
                    "checked_at": _iso(check.checked_at),
                }
            )
    history = await _histories(session, ids)
    flags = await flags_for(
        session,
        {enrolment.id: enrolment.institution_id for enrolment, *_ in enrolment_rows},
        unresolved_only=False,
    )
    # the student is never an officer: flag summaries use the institution's wording
    enrolments = [
        {
            "id": str(enrolment.id),
            "institution_name": institution_name,
            "programme_name": programme_name,
            "academic_year": enrolment.academic_year,
            "year_of_study": enrolment.year_of_study,
            "admission_route": enrolment.admission_route.value,
            "category": enrolment.category.value,
            "status": enrolment.status.value,
            "status_date": _iso(enrolment.status_date),
            "admission_date": _iso(enrolment.admission_date),
            "seat_code": seat_code,
            "record_status": (
                enrolment.record_status.value
                if enrolment.status is EnrolmentStatus.ACTIVE
                else None
            ),
            "status_reason": (
                enrolment.status_reason if enrolment.status is EnrolmentStatus.ACTIVE else None
            ),
            "checks": checks[enrolment.id],
            "flags": [
                {
                    "type": flag.type.value,
                    "status": flag.status.value,
                    "summary": visible_summary(user, flag.evidence),
                    "created_at": _iso(flag.created_at),
                }
                for flag in flags.get(enrolment.id, [])
            ],
            "history": history.get(enrolment.id, []),
        }
        for enrolment, institution_name, programme_name, seat_code in enrolment_rows
    ]
    notices = [
        {
            "channel": n.channel.value,
            "sent_at": _iso(n.sent_at),
            "expires_at": _iso(n.expires_at),
            "delivery_status": n.delivery_status.value,
            "response": n.response.value if n.response else None,
            "responded_at": _iso(n.responded_at),
            "changed_at": _iso(n.changed_at),
            "comment": n.comment,
        }
        for n in (
            await session.execute(
                select(Notification)
                .where(Notification.student_id == student_id)
                .order_by(Notification.created_at, Notification.id)
            )
        ).scalars()
    ]
    credentials = list(
        (
            await session.execute(
                select(Credential)
                .where(Credential.student_id == student_id)
                .order_by(Credential.issued_at, Credential.id)
            )
        ).scalars()
    )
    presentations = []
    if credentials:
        presentations = [
            {
                "credential_id": str(p.credential_id),
                "created_at": _iso(p.created_at),
                "expires_at": _iso(p.expires_at),
                "disclosed": list(p.disclosed),
                "verify_count": p.verify_count,
            }
            for p in (
                await session.execute(
                    select(CredentialPresentation)
                    .where(CredentialPresentation.credential_id.in_([c.id for c in credentials]))
                    .order_by(CredentialPresentation.created_at, CredentialPresentation.id)
                )
            ).scalars()
        ]
    requests = list(
        (
            await session.execute(
                select(DataRequest)
                .where(DataRequest.student_id == student_id)
                .order_by(DataRequest.created_at.desc(), DataRequest.id)
            )
        ).scalars()
    )
    access = [
        _access_row(*row)
        for row in (await session.execute(_access_stmt(student_id, user.id))).all()
    ]
    body = {
        "generated_at": _iso(now),
        "privacy_notice_version": NOTICE_VERSION,
        "student": {
            "id": str(student.id),
            "name": student.name,
            "dob": _iso(student.dob),
            "gender": student.gender.value,
            "nationality": student.nationality,
            "apaar_masked": mask_apaar(student.apaar_last4),
            "provisional_id": student.provisional_id,
            "consent_status": student.consent_status.value,
            "email": student.email,
            "mobile_masked": mask_mobile(student.mobile_last4),
        },
        "enrolments": enrolments,
        "notices": notices,
        "consents": (await consents_view(session, student_id))["items"],
        "credentials": [
            {
                "id": str(c.id),
                "kind": c.kind.value,
                "status": _credential_status(c, now),
                "issued_at": _iso(c.issued_at),
                "expires_at": _iso(c.expires_at),
                "revoked_at": _iso(c.revoked_at),
                "revoked_reason": c.revoked_reason,
                "claims": disclosed_claims(c.sd_jwt),
            }
            for c in credentials
        ],
        "presentations": presentations,
        "data_requests": await _request_rows(session, requests),
        "access_log": access,
    }
    await audit.record(
        session, user.id, AuditAction.READ, "student", student.id, after={"via": "export"}
    )
    return body
