"""STUDENT: the student's own reply to a notice, derived from the notices (D24)."""

from __future__ import annotations

import asyncio

from app.adapters.base import AdapterSet
from app.engine.checks.base import CheckSubject
from app.engine.contracts import CheckOutcome
from app.models.enums import CheckType
from app.notices import student_check

SOURCE = student_check.SOURCE
CHECK = CheckType.STUDENT


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    """No adapter call: the notices on the subject decide."""
    return student_check.derive(subject)
