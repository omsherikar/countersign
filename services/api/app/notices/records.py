"""A student's own records as `GET /students/me` lists them (API_CONTRACT §A4.5, §A4.13).

Each record carries its status, the brief evidence rows, the answer the student gave, and,
after an officer acted on the student's dispute, the outcome (never the note or the
officer). Shared by `GET /students/me`, the student's own answer and the claim, which all
answer with these records.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.digilocker import is_claimed
from app.engine.contracts import CHECK_ORDER
from app.engine.flags import dedupe_key
from app.models.enums import CaseActionKind, EnrolmentStatus, FlagType, NoticeResponse
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.verification import CaseAction, Check, Flag, Notification

# the decisions and the escalation a student hears about, with their outcome word
DECISION_OUTCOMES = {
    CaseActionKind.UPHOLD: "UPHELD",
    CaseActionKind.CORRECT: "CORRECTED",
    CaseActionKind.WITHDRAW: "WITHDRAWN",
    CaseActionKind.ESCALATE: "ESCALATED",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def brief_rows(checks: Sequence[Check]) -> list[dict[str, Any]]:
    """EvidenceRowBrief (§A4.5) in row order; [] before the first evaluation."""
    by_type = {c.type: c for c in checks}
    return [
        {
            "type": t.value,
            "state": by_type[t].status.value,
            "finding": (by_type[t].detail or {}).get("finding"),
            "independent": bool(by_type[t].independent),
            "resolved": by_type[t].resolved is not None,
        }
        for t in CHECK_ORDER
        if t in by_type
    ]


def current_answer(notices: Sequence[Notification]) -> str | None:
    """The answer that stands on the record: a No beats a Yes (D24)."""
    answers = {n.response for n in notices if n.response is not None}
    if NoticeResponse.NO in answers:
        return NoticeResponse.NO.value
    if NoticeResponse.YES in answers:
        return NoticeResponse.YES.value
    return None


async def _decisions(
    session: AsyncSession, enrolment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    """{enrolment: the latest decision or escalation of its STUDENT_DENIED case}."""
    keys = {dedupe_key(FlagType.STUDENT_DENIED, i): i for i in enrolment_ids}
    if not keys:
        return {}
    rows = (
        await session.execute(
            select(Flag.dedupe_key, CaseAction.action, CaseAction.reason_code, CaseAction.at)
            .join(CaseAction, CaseAction.flag_id == Flag.id)
            .where(
                Flag.dedupe_key.in_(list(keys)),
                CaseAction.action.in_(list(DECISION_OUTCOMES)),
            )
            .order_by(CaseAction.seq)
        )
    ).all()
    out: dict[uuid.UUID, dict[str, Any]] = {}
    for key, action, reason_code, at in rows:  # later actions win
        out[keys[key]] = {
            "outcome": DECISION_OUTCOMES[action],
            "reason_code": reason_code,
            "at": _iso(at),
        }
    return out


async def student_enrolments(
    session: AsyncSession, student: Student, *, only: Sequence[uuid.UUID] | None = None
) -> list[dict[str, Any]]:
    """StudentEnrolment (§A4.5) for each of the student's enrolments (or those in `only`),
    newest academic year first."""
    stmt = (
        select(Enrolment, Institution, Programme)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .where(Enrolment.student_id == student.id)
        .order_by(Enrolment.academic_year.desc(), Institution.name, Enrolment.id)
    )
    if only is not None:
        stmt = stmt.where(Enrolment.id.in_(list(only)))
    rows = (await session.execute(stmt)).all()
    ids = [enrolment.id for enrolment, _, _ in rows]
    checks: dict[uuid.UUID, list[Check]] = defaultdict(list)
    notices: dict[uuid.UUID, list[Notification]] = defaultdict(list)
    if ids:
        for check in (
            await session.execute(select(Check).where(Check.enrolment_id.in_(ids)))
        ).scalars():
            checks[check.enrolment_id].append(check)
        for notice in (
            await session.execute(select(Notification).where(Notification.enrolment_id.in_(ids)))
        ).scalars():
            notices[notice.enrolment_id].append(notice)
    decisions = await _decisions(session, ids)
    claimed = await is_claimed(session, student)
    out = []
    for enrolment, institution, programme in rows:
        active = enrolment.status is EnrolmentStatus.ACTIVE
        out.append(
            {
                "id": str(enrolment.id),
                "institution_id": str(institution.id),
                "institution_name": institution.name,
                "programme_code": programme.code,
                "programme_name": programme.name,
                "academic_year": enrolment.academic_year,
                "year_of_study": enrolment.year_of_study,
                "status": enrolment.status.value,
                "record_status": enrolment.record_status.value if active else None,
                "status_reason": enrolment.status_reason if active else None,
                "next_step": enrolment.next_step,
                "checks": brief_rows(checks[enrolment.id]),
                "response": current_answer(notices[enrolment.id]),
                "can_respond": active,
                "claimed": claimed,
                "decision": decisions.get(enrolment.id),
            }
        )
    return out
