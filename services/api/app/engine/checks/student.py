"""STUDENT: the student's own reply to a notice. PENDING until the student loop sends one."""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet
from app.engine import evidence as ev
from app.engine.checks.base import CheckSubject
from app.engine.contracts import CheckOutcome
from app.models.enums import CheckStatus, CheckType

SOURCE = "STUDENT_NOTICE"
CHECK = CheckType.STUDENT


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    return CheckOutcome(
        type=CHECK, status=CheckStatus.PENDING, source=SOURCE, detail=ev.student_notice_not_sent()
    )
