"""One read of what the engine produced, as the plain views the scoring modules take.

Runs inside the api's environment (`app` importable). Reads only; the throughput college's
records and checks are left out (they would add 50,000 records nobody scores), its cases are
not (it should have none).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

from .views import BatchView, CaseView, RecordView, SignalView

POOL_CASES = ("EXCESS_ADMISSION", "QUOTA_BREACH")


@dataclass(slots=True)
class Snapshot:
    cases: list[CaseView] = field(default_factory=list)
    records: dict[str, RecordView] = field(default_factory=dict)
    signals: list[SignalView] = field(default_factory=list)
    batches: list[BatchView] = field(default_factory=list)
    # (upload file name, row number) -> the enrolment that row created or last updated
    row_index: dict[tuple[str, int], str] = field(default_factory=dict)
    institutions: dict[str, str] = field(default_factory=dict)  # AICTE id -> name

    def active_records(self, exclude: Collection[str] = ()) -> int:
        return sum(1 for r in self.records.values() if r.active and r.institution not in exclude)


def pool_of(case_type: str, dedupe_key: str) -> str | None:
    """The pool of a seat case: the last part of `QUOTA_BREACH:<programme>:<year>:<seat type>`;
    EXCESS_ADMISSION is always the REGULAR pool."""
    if case_type == "EXCESS_ADMISSION":
        return "REGULAR"
    if case_type == "QUOTA_BREACH":
        return dedupe_key.rsplit(":", 1)[-1] or None
    return None


def facts_of(evidence: Any) -> int:
    facts = evidence.get("facts") if isinstance(evidence, dict) else None
    return len(facts) if isinstance(facts, list) else 0


async def take(session: Any, *, exclude: Collection[str] = ()) -> Snapshot:
    from sqlalchemy import select

    from app.models.audit import AuditLog
    from app.models.enums import AuditAction, UploadSource
    from app.models.institution import Institution, Programme
    from app.models.signal import Signal
    from app.models.student import Enrolment
    from app.models.upload import UploadBatch
    from app.models.verification import Check, Flag

    snap = Snapshot()
    aicte: dict[uuid.UUID, str] = {}
    for inst_id, code, name in (
        await session.execute(
            select(Institution.id, Institution.aicte_permanent_id, Institution.name)
        )
    ).all():
        aicte[inst_id] = code
        snap.institutions[code] = name
    excluded_ids = [i for i, code in aicte.items() if code in exclude]
    programmes = dict((await session.execute(select(Programme.id, Programme.code))).all())

    for row in (
        await session.execute(
            select(
                Flag.id,
                Flag.type,
                Flag.severity,
                Flag.status,
                Flag.institution_id,
                Flag.programme_id,
                Flag.enrolment_id,
                Flag.related_enrolment_ids,
                Flag.academic_year,
                Flag.dedupe_key,
                Flag.evidence,
            )
        )
    ).all():
        named = {str(i) for i in row.related_enrolment_ids or ()}
        if row.enrolment_id is not None:
            named.add(str(row.enrolment_id))
        snap.cases.append(
            CaseView(
                id=str(row.id),
                type=row.type.value,
                severity=row.severity.value,
                status=row.status.value,
                institution=aicte.get(row.institution_id, ""),
                enrolments=frozenset(named),
                programme_code=programmes.get(row.programme_id),
                academic_year=row.academic_year,
                pool=pool_of(row.type.value, row.dedupe_key),
                facts=facts_of(row.evidence),
            )
        )

    batches: dict[uuid.UUID, str] = {}
    for row in (
        await session.execute(
            select(
                UploadBatch.id,
                UploadBatch.filename,
                UploadBatch.institution_id,
                UploadBatch.total_rows,
                UploadBatch.status,
                UploadBatch.source,
                UploadBatch.started_at,
                UploadBatch.finished_at,
            ).order_by(UploadBatch.created_at)
        )
    ).all():
        institution = aicte.get(row.institution_id, "")
        snap.batches.append(
            BatchView(
                filename=row.filename,
                institution=institution,
                rows=int(row.total_rows or 0),
                status=row.status.value,
                started_at=row.started_at,
                finished_at=row.finished_at,
            )
        )
        if row.source is UploadSource.SEED and institution not in exclude:
            batches[row.id] = row.filename

    states: dict[uuid.UUID, dict[str, str]] = defaultdict(dict)
    record_rows = select(Check.enrolment_id, Check.type, Check.status).join(
        Enrolment, Enrolment.id == Check.enrolment_id
    )
    if excluded_ids:
        record_rows = record_rows.where(Enrolment.institution_id.not_in(excluded_ids))
    for enrolment_id, check_type, state in (await session.execute(record_rows)).all():
        states[enrolment_id][check_type.value] = state.value

    enrolments = select(
        Enrolment.id,
        Enrolment.institution_id,
        Enrolment.status,
        Enrolment.record_status,
        Enrolment.upload_batch_id,
        Enrolment.source_row_no,
    )
    if excluded_ids:
        enrolments = enrolments.where(Enrolment.institution_id.not_in(excluded_ids))
    for row in (await session.execute(enrolments)).all():
        key = str(row.id)
        snap.records[key] = RecordView(
            id=key,
            institution=aicte.get(row.institution_id, ""),
            status=row.status.value,
            record_status=row.record_status.value if row.record_status is not None else None,
            from_upload=row.upload_batch_id is not None,
            rows=states.get(row.id, {}),
        )
        filename = batches.get(row.upload_batch_id)
        if filename is not None and row.source_row_no is not None:
            snap.row_index[(filename, int(row.source_row_no))] = key

    # rows whose enrolment a later file updated: the upsert's audit entries keep every
    # (batch, row) an enrolment was written from
    if batches:
        batch_of = AuditLog.after["batch_id"].astext
        for entity_id, batch_id, row_no in (
            await session.execute(
                select(AuditLog.entity_id, batch_of, AuditLog.after["row_no"].astext).where(
                    AuditLog.entity_type == "enrolment",
                    AuditLog.action.in_([AuditAction.CREATE, AuditAction.UPDATE]),
                    batch_of.in_([str(b) for b in batches]),
                )
            )
        ).all():
            filename = batches.get(uuid.UUID(batch_id))
            if filename is None or entity_id is None or not row_no:
                continue
            snap.row_index.setdefault((filename, int(row_no)), str(entity_id))

    for row in (
        await session.execute(
            select(Signal.id, Signal.type, Signal.institution_ids, Signal.enrolment_ids)
        )
    ).all():
        snap.signals.append(
            SignalView(
                id=str(row.id),
                type=row.type.value,
                institutions=frozenset(aicte.get(i, "") for i in row.institution_ids or ()),
                enrolments=frozenset(str(i) for i in row.enrolment_ids or ()),
            )
        )
    return snap
