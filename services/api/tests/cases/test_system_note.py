"""Engines never decide a flag, but the history says when they changed its evidence after
an officer did."""

from __future__ import annotations

from sqlalchemy import select

from app.cases.service import EVIDENCE_UPDATED_NOTE
from app.db.session import session_factory
from app.engine.flags import raise_flag
from app.models.enums import CaseActionKind, FlagStatus, FlagType, Severity
from app.models.verification import CaseAction, Flag
from tests.cases.conftest import evidence, new_flag, set_status


async def test_an_engine_refresh_of_a_decided_flag_adds_a_system_note(cw, logins) -> None:
    flag_id = await new_flag(cw)
    async with session_factory()() as session:
        flag = await session.get(Flag, flag_id)
        key, n = flag.dedupe_key, int(flag.dedupe_key.split(":")[1])

    async def refresh(extra: str) -> None:
        async with session_factory()() as session:
            await raise_flag(
                session,
                type=FlagType.NAME_MISMATCH,
                severity=Severity.HIGH,
                institution_id=cw.abc,
                programme_id=cw.cse,
                enrolment_id=cw.ravi,
                academic_year="2026-27",
                dedupe_key=key,
                evidence=evidence(n, [cw.ravi], extra=extra),
                actor_id=None,
            )
            await session.commit()

    async def system_notes() -> list[CaseAction]:
        async with session_factory()() as session:
            return list(
                (
                    await session.execute(
                        select(CaseAction).where(
                            CaseAction.flag_id == flag_id,
                            CaseAction.action == CaseActionKind.SYSTEM_NOTE,
                        )
                    )
                ).scalars()
            )

    await refresh("; open and refreshed")  # an open flag gets no note
    assert await system_notes() == []
    await set_status(flag_id, FlagStatus.UPHELD)
    await refresh("; open and refreshed")  # the same evidence again changes nothing
    assert await system_notes() == []
    await refresh("; refreshed after clearing")
    notes = await system_notes()
    assert len(notes) == 1
    assert notes[0].note == EVIDENCE_UPDATED_NOTE and notes[0].actor_id is None
    assert notes[0].from_status is notes[0].to_status is FlagStatus.UPHELD
    async with session_factory()() as session:
        flag = await session.get(Flag, flag_id)
    assert flag.status is FlagStatus.UPHELD  # the engine still decides nothing

    for email in ("ro.west@aicte.demo", "registrar@abc.edu.demo"):
        history = (await (await logins(email)).get(f"/flags/{flag_id}")).json()["history"]
        assert history[-1]["action"] == "SYSTEM_NOTE"
        assert history[-1]["actor"] is None
        assert history[-1]["note"] == "Evidence updated after the decision."
