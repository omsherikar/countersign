"""Officer case work on flags (D25). `add_system_note` is used by the notices loop and the
flags engine; the rest of the case service lives here too."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.models.enums import AuditAction, CaseActionKind
from app.models.verification import CaseAction, Flag


async def add_system_note(session: AsyncSession, flag: Flag, text: str) -> CaseAction:
    """A SYSTEM_NOTE in the flag's history; never changes the flag's status. Flushes only."""
    now = datetime.now(UTC)
    row = CaseAction(
        flag_id=flag.id,
        actor_id=None,
        action=CaseActionKind.SYSTEM_NOTE,
        note=text,
        attachments=[],
        from_status=flag.status,
        to_status=flag.status,
        at=now,
    )
    session.add(row)
    flag.last_action_at = now
    await session.flush()
    await audit.record(
        session,
        None,
        AuditAction.CREATE,
        "case_action",
        flag.id,
        after={"action": CaseActionKind.SYSTEM_NOTE.value, "seq": row.seq},
    )
    return row
