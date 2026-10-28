"""Consent records and data rights (D30). `record_consent` and `notice_consent_withdrawn` are
used by the notices loop and the wallet; the rest of the privacy service lives here too."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.models.credential import Consent
from app.models.enums import AuditAction, ConsentPurpose, ConsentState


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
