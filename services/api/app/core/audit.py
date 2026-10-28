"""Hash-chained audit log (DECISIONS D7).

Every entry is written in the caller's transaction under a transaction-scoped
advisory lock, so `seq` and the chain advance strictly in commit order.
hash = sha256(prev_hash + canonical_json({seq, at, actor_id, action, entity_type,
entity_id, before, after})); prev_hash is null only for the first row.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction

ADVISORY_LOCK_KEY = 7260118  # arbitrary, reserved for the audit chain


@dataclass(slots=True)
class AuditEntry:
    action: AuditAction
    entity_type: str
    entity_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _iso(at: datetime) -> str:
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(UTC).isoformat()


def compute_hash(
    prev_hash: str | None,
    *,
    seq: int,
    at: datetime,
    actor_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> str:
    payload = canonical_json(
        {
            "seq": seq,
            "at": _iso(at),
            "actor_id": str(actor_id) if actor_id else None,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "before": before,
            "after": after,
        }
    )
    return hashlib.sha256(((prev_hash or "") + payload).encode("utf-8")).hexdigest()


def hash_of_row(row: AuditLog) -> str:
    return compute_hash(
        row.prev_hash,
        seq=row.seq,
        at=row.at,
        actor_id=row.actor_id,
        action=row.action.value if isinstance(row.action, AuditAction) else str(row.action),
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        before=row.before,
        after=row.after,
    )


async def record_many(session: AsyncSession, entries: Iterable[AuditEntry]) -> list[AuditLog]:
    """Append entries to the chain inside the current transaction."""
    entries = list(entries)
    if not entries:
        return []
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": ADVISORY_LOCK_KEY})
    prev_hash = (
        await session.execute(select(AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1))
    ).scalar_one_or_none()
    seqs = (
        (
            await session.execute(
                text("SELECT nextval('audit_log_seq_seq') FROM generate_series(1, :n)"),
                {"n": len(entries)},
            )
        )
        .scalars()
        .all()
    )
    rows: list[AuditLog] = []
    for seq, entry in zip(seqs, entries, strict=True):
        at = datetime.now(UTC)
        digest = compute_hash(
            prev_hash,
            seq=seq,
            at=at,
            actor_id=entry.actor_id,
            action=entry.action.value,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            before=entry.before,
            after=entry.after,
        )
        row = AuditLog(
            seq=seq,
            at=at,
            actor_id=entry.actor_id,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            before=entry.before,
            after=entry.after,
            request_id=entry.request_id,
            prev_hash=prev_hash,
            hash=digest,
        )
        session.add(row)
        rows.append(row)
        prev_hash = digest
    await session.flush()
    return rows


async def record(
    session: AsyncSession,
    actor_id: uuid.UUID | None,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditLog:
    rows = await record_many(
        session,
        [
            AuditEntry(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=actor_id,
                before=before,
                after=after,
                request_id=request_id,
            )
        ],
    )
    return rows[0]


async def record_read(
    session: AsyncSession,
    actor_id: uuid.UUID | None,
    entity_type: str,
    entity_ids: Iterable[uuid.UUID],
    request_id: str | None = None,
) -> list[AuditLog]:
    """One READ entry per distinct entity, in one lock acquisition. No PII in the payload."""
    seen: dict[uuid.UUID, None] = {}
    for entity_id in entity_ids:
        seen.setdefault(entity_id, None)
    return await record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.READ,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=actor_id,
                request_id=request_id,
            )
            for entity_id in seen
        ],
    )


async def verify_chain(session: AsyncSession) -> tuple[bool, int, int | None]:
    """Walk the chain in seq order. Returns (ok, length, first_broken_seq).

    Reads plain column tuples in large chunks rather than ORM objects: the chain holds a
    READ entry for every record view, so it grows by the hundred thousand and the walk has
    to stay quick enough for the admin page.
    """
    length = 0
    expected_prev: str | None = None
    first_broken: int | None = None
    columns = (
        AuditLog.seq,
        AuditLog.at,
        AuditLog.actor_id,
        AuditLog.action,
        AuditLog.entity_type,
        AuditLog.entity_id,
        AuditLog.before,
        AuditLog.after,
        AuditLog.prev_hash,
        AuditLog.hash,
    )
    result = await session.stream(
        select(*columns).order_by(AuditLog.seq).execution_options(yield_per=5000)
    )
    async for (
        seq,
        at,
        actor_id,
        action,
        entity_type,
        entity_id,
        before,
        after,
        prev,
        digest,
    ) in result:
        length += 1
        if first_broken is None:
            recomputed = compute_hash(
                prev,
                seq=seq,
                at=at,
                actor_id=actor_id,
                action=action.value if isinstance(action, AuditAction) else str(action),
                entity_type=entity_type,
                entity_id=entity_id,
                before=before,
                after=after,
            )
            if prev != expected_prev or recomputed != digest:
                first_broken = seq
        expected_prev = digest
    return first_broken is None, length, first_broken
