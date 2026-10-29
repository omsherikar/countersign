"""Enrolment versions (D42; API_CONTRACT §A4.7; ENGINES §17.8).

Every change to an enrolment, by an upload, an officer's decision or the seed, is stored in
`enrolment_versions` as the changed fields with their values before and after. Version 1 of
a record lists every versioned field with `before` null; an unchanged row writes nothing, so
uploading a file again stays a no-op. Derived fields (seat, cohort year, record status) are
never versions: the seat history is the Seat Ledger's.

Values are JSON: dates as YYYY-MM-DD, enums as their values. An APAAR is only ever stored
masked ("XXXX XXXX 4417"); a mobile number, an email address or an address never is.

Version numbers are safe without a sequence because every writer holds the enrolment's row
lock (the upsert chunk, a decision's `FOR UPDATE`).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from sqlalchemy import Select, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.crypto import mask_apaar
from app.engine.contracts import CHUNK_SIZE
from app.models.enums import VersionSource
from app.models.student import Enrolment, EnrolmentVersion, Student
from app.models.upload import UploadBatch
from app.models.user import User
from app.models.verification import CaseAction, Flag
from app.schemas.common import PageParams

VERSIONED_FIELDS: tuple[str, ...] = (
    "name",
    "dob",
    "apaar_masked",
    "consent_status",
    "year_of_study",
    "admission_route",
    "counselling_ref",
    "category",
    "admission_date",
    "status",
    "status_date",
    "tfw_income_certified",
    "nri_sponsored",
    "ciwg",
)
STUDENT_FIELDS: tuple[str, ...] = ("name", "dob", "apaar_masked", "consent_status")
ELIGIBILITY_FIELDS: tuple[str, ...] = ("tfw_income_certified", "nri_sponsored", "ciwg")
# the actions whose case action row a DECISION version points at
DECISION_ACTIONS = ("UPHOLD", "CORRECT", "WITHDRAW")


def _json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def student_fields(student: Student) -> dict[str, Any]:
    """The versioned fields a student carries for every one of its enrolments."""
    return {
        "name": student.name,
        "dob": _json(student.dob),
        "apaar_masked": mask_apaar(student.apaar_last4),
        "consent_status": _json(student.consent_status),
    }


def enrolment_fields(enrolment: Enrolment) -> dict[str, Any]:
    """The versioned fields of the enrolment itself, the eligibility markers included."""
    eligibility = enrolment.eligibility or {}
    return {
        "year_of_study": enrolment.year_of_study,
        "admission_route": _json(enrolment.admission_route),
        "counselling_ref": enrolment.counselling_ref,
        "category": _json(enrolment.category),
        "admission_date": _json(enrolment.admission_date),
        "status": _json(enrolment.status),
        "status_date": _json(enrolment.status_date),
        **{key: eligibility.get(key) for key in ELIGIBILITY_FIELDS},
    }


def snapshot(enrolment: Enrolment, student: Student) -> dict[str, Any]:
    """Every versioned field as JSON values, in VERSIONED_FIELDS order; APAAR only masked."""
    values = {**student_fields(student), **enrolment_fields(enrolment)}
    return {key: values.get(key) for key in VERSIONED_FIELDS}


def diff(before: Mapping[str, Any] | None, after: Mapping[str, Any]) -> dict[str, list[Any]]:
    """{field: [before, after]} for the fields that changed, in VERSIONED_FIELDS order.

    With no `before` (a new record) every versioned field is listed with `before` null.
    """
    out: dict[str, list[Any]] = {}
    for key in VERSIONED_FIELDS:
        if key not in after:
            continue
        new = _json(after[key])
        if before is None:
            out[key] = [None, new]
            continue
        old = _json(before.get(key))
        if old != new:
            out[key] = [old, new]
    return out


@dataclass(frozen=True, slots=True)
class VersionWrite:
    enrolment_id: uuid.UUID
    changes: Mapping[str, list[Any]]
    source: VersionSource
    batch_id: uuid.UUID | None = None
    case_action_seq: int | None = None
    actor_id: uuid.UUID | None = None
    # when the change was made: a seed batch's submitted_at, else now
    at: datetime | None = None


def _ordered(changes: Mapping[str, list[Any]]) -> dict[str, list[Any]]:
    return {key: list(changes[key]) for key in VERSIONED_FIELDS if key in changes}


async def _latest_numbers(
    session: AsyncSession, enrolment_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not enrolment_ids:
        return {}
    rows = await session.execute(
        select(EnrolmentVersion.enrolment_id, func.max(EnrolmentVersion.version))
        .where(EnrolmentVersion.enrolment_id.in_(list(enrolment_ids)))
        .group_by(EnrolmentVersion.enrolment_id)
    )
    return dict(rows.all())


async def record(session: AsyncSession, write: VersionWrite) -> EnrolmentVersion | None:
    """Store one version; None when nothing changed. Flushes, never commits."""
    if not write.changes:
        return None
    number = (await _latest_numbers(session, [write.enrolment_id])).get(write.enrolment_id, 0)
    version = EnrolmentVersion(
        id=uuid.uuid4(),
        enrolment_id=write.enrolment_id,
        version=number + 1,
        changes=_ordered(write.changes),
        source=VersionSource(write.source).value,
        batch_id=write.batch_id,
        case_action_seq=write.case_action_seq,
        actor_id=write.actor_id,
        at=write.at or datetime.now(UTC),
    )
    session.add(version)
    await session.flush()
    return version


async def record_many(session: AsyncSession, writes: Sequence[VersionWrite]) -> int:
    """Store the versions of many records, two statements per chunk of CHUNK_SIZE; returns
    how many were written. Writes without changes are skipped. Flushes, never commits."""
    pending = [w for w in writes if w.changes]
    written = 0
    now = datetime.now(UTC)
    for start in range(0, len(pending), CHUNK_SIZE):
        part = pending[start : start + CHUNK_SIZE]
        numbers = await _latest_numbers(session, list({w.enrolment_id for w in part}))
        values: list[dict[str, Any]] = []
        for write in part:
            number = numbers.get(write.enrolment_id, 0) + 1
            numbers[write.enrolment_id] = number
            values.append(
                {
                    "id": uuid.uuid4(),
                    "enrolment_id": write.enrolment_id,
                    "version": number,
                    "changes": _ordered(write.changes),
                    "source": VersionSource(write.source).value,
                    "batch_id": write.batch_id,
                    "case_action_seq": write.case_action_seq,
                    "actor_id": write.actor_id,
                    "at": write.at or now,
                }
            )
        await session.execute(insert(EnrolmentVersion), values)
        written += len(values)
    return written


# --------------------------------------------------------------------------- reads


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _changes(stored: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {"field": key, "before": stored[key][0], "after": stored[key][1]}
        for key in VERSIONED_FIELDS
        if key in stored
    ]


def _stmt(enrolment_id: uuid.UUID) -> Select:
    actor = aliased(User)
    return (
        select(
            EnrolmentVersion,
            actor.id,
            actor.name,
            actor.role,
            UploadBatch.id,
            UploadBatch.filename,
            CaseAction.flag_id,
            CaseAction.action,
            CaseAction.reason_code,
            Flag.type,
            Enrolment.upload_batch_id,
            Enrolment.source_row_no,
        )
        .join(Enrolment, Enrolment.id == EnrolmentVersion.enrolment_id)
        .outerjoin(actor, actor.id == EnrolmentVersion.actor_id)
        .outerjoin(UploadBatch, UploadBatch.id == EnrolmentVersion.batch_id)
        .outerjoin(CaseAction, CaseAction.seq == EnrolmentVersion.case_action_seq)
        .outerjoin(Flag, Flag.id == CaseAction.flag_id)
        .where(EnrolmentVersion.enrolment_id == enrolment_id)
        .order_by(EnrolmentVersion.version.desc())
    )


def _item(row: Any, *, with_actor: bool = True) -> dict[str, Any]:
    (
        version,
        actor_id,
        actor_name,
        actor_role,
        batch_id,
        filename,
        flag_id,
        action,
        reason_code,
        flag_type,
        current_batch,
        current_row,
    ) = row
    item: dict[str, Any] = {
        "version": version.version,
        "at": _iso(version.at),
        "source": version.source,
        "batch": {
            "id": str(batch_id),
            "filename": filename,
            # the file's row is known for the batch that last wrote the record
            "row_no": current_row if batch_id == current_batch else None,
        }
        if batch_id is not None
        else None,
        "case": {
            "id": str(flag_id),
            "type": flag_type.value,
            "action": action.value,
            "case_action_seq": version.case_action_seq,
            "reason_code": reason_code,
        }
        if flag_id is not None
        else None,
        "changes": _changes(version.changes or {}),
    }
    if with_actor:
        item["actor"] = (
            {"id": str(actor_id), "name": actor_name, "role": actor_role.value}
            if actor_id is not None and version.source != VersionSource.SEED.value
            else None
        )
    return item


async def history(
    session: AsyncSession, enrolment_id: uuid.UUID, *, page: PageParams, user: User | None = None
) -> dict[str, Any]:
    """`GET /enrolments/{id}/history`: the record's versions, newest first, as a page.
    Scope is the caller's: the router checks it as for the enrolment detail."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(EnrolmentVersion)
            .where(EnrolmentVersion.enrolment_id == enrolment_id)
        )
    ).scalar_one()
    rows = (
        await session.execute(_stmt(enrolment_id).offset(page.offset).limit(page.page_size))
    ).all()
    return {
        "items": [_item(row) for row in rows],
        "total": total,
        "page": page.page,
        "page_size": page.page_size,
    }


async def latest(
    session: AsyncSession, enrolment_id: uuid.UUID, limit: int = 20, *, with_actor: bool = True
) -> list[dict[str, Any]]:
    """The record's most recent versions, newest first (the History section of the card)."""
    rows = (await session.execute(_stmt(enrolment_id).limit(limit))).all()
    return [_item(row, with_actor=with_actor) for row in rows]


async def count(session: AsyncSession, enrolment_id: uuid.UUID) -> int:
    """How many versions the record has (`history_count`)."""
    return (
        await session.execute(
            select(func.count())
            .select_from(EnrolmentVersion)
            .where(EnrolmentVersion.enrolment_id == enrolment_id)
        )
    ).scalar_one()


async def for_case_action(session: AsyncSession, seqs: Sequence[int]) -> dict[int, dict[str, Any]]:
    """The DECISION versions written by case actions, keyed by `case_action_seq`, as
    `{"enrolment_id", "version", "changes": [{field, before, after}]}` (the first version per
    action, which is the record a CORRECT changed)."""
    if not seqs:
        return {}
    rows = (
        await session.execute(
            select(EnrolmentVersion)
            .where(EnrolmentVersion.case_action_seq.in_(list(seqs)))
            .order_by(EnrolmentVersion.case_action_seq, EnrolmentVersion.at, EnrolmentVersion.id)
        )
    ).scalars()
    out: dict[int, dict[str, Any]] = {}
    for version in rows:
        assert version.case_action_seq is not None
        out.setdefault(
            version.case_action_seq,
            {
                "enrolment_id": str(version.enrolment_id),
                "version": version.version,
                "changes": _changes(version.changes or {}),
            },
        )
    return out
