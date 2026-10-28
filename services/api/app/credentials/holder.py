"""The student's wallet: proofs, shares and presentations (D26).

The three functions below are what the notices loop and the privacy service call; the
credentials module fills them in with the rest of the wallet.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def wallet_summary(session: AsyncSession, student_id: uuid.UUID) -> list[dict[str, Any]]:
    """The student's proofs for GET /students/me."""
    return []


async def credential_refs(session: AsyncSession, enrolment_id: uuid.UUID) -> list[dict[str, Any]]:
    """The proofs issued for one enrolment, for enrolment detail."""
    return []


async def expire_live_presentations(
    session: AsyncSession, student_id: uuid.UUID, *, now: datetime
) -> int:
    """Expire every live share of the student's proofs; returns how many."""
    return 0
