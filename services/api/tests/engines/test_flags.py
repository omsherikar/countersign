"""raise_flag: an upsert by dedupe_key that never deletes, never lowers, always audits."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.engine.flags import dedupe_key, raise_flag
from app.models.audit import AuditLog
from app.models.enums import AuditAction, FlagStatus, FlagType, Severity


def _evidence(summary: str = "APAAR ending 4417 is not in the APAAR registry.", related=()):
    return {
        "summary": summary,
        "facts": [{"label": "Registry reply", "value": "Not found", "source": "APAAR registry"}],
        "related_enrolment_ids": [str(r) for r in related],
        "rule_source": "APAAR verification",
    }


async def _audits(session) -> list[AuditLog]:
    rows = await session.execute(
        select(AuditLog).where(AuditLog.entity_type == "flag").order_by(AuditLog.seq)
    )
    return list(rows.scalars().all())


async def _raise(session, inst, *, key="INVALID_APAAR:x", severity=Severity.MEDIUM, **kw):
    params = dict(
        type=FlagType.INVALID_APAAR,
        severity=severity,
        institution_id=inst.id,
        programme_id=None,
        enrolment_id=None,
        academic_year="2026-27",
        dedupe_key=key,
        evidence=_evidence(),
        actor_id=None,
    )
    params.update(kw)
    return await raise_flag(session, **params)


def test_dedupe_key_format() -> None:
    e = uuid.UUID("0b6f0000-0000-4000-8000-0000000000e1")
    assert dedupe_key(FlagType.INVALID_APAAR, e) == f"INVALID_APAAR:{e}"
    assert dedupe_key(FlagType.EXCESS_ADMISSION, e, "2026-27", "REGULAR") == (
        f"EXCESS_ADMISSION:{e}:2026-27:REGULAR"
    )


async def test_new_flag_opens_and_audits(world, session) -> None:
    inst = await world.institution()
    a, b = uuid.uuid4(), uuid.uuid4()
    raised = await _raise(session, inst, evidence=_evidence(related=[a, b]))
    assert raised.created and not raised.changed
    flag = raised.flag
    assert flag.status is FlagStatus.OPEN
    assert flag.related_enrolment_ids == [a, b]
    assert flag.academic_year == "2026-27"
    [entry] = await _audits(session)
    assert entry.action is AuditAction.CREATE
    assert entry.after == {
        "type": "INVALID_APAAR",
        "severity": "MEDIUM",
        "status": "OPEN",
        "dedupe_key": "INVALID_APAAR:x",
        "summary": "APAAR ending 4417 is not in the APAAR registry.",
    }


async def test_same_evidence_is_unchanged_and_writes_nothing(world, session) -> None:
    inst = await world.institution()
    await _raise(session, inst)
    again = await _raise(session, inst)
    assert not again.created and not again.changed
    assert len(await _audits(session)) == 1
    assert (await session.execute(select(func.count()).select_from(AuditLog))).scalar_one() == 1


async def test_update_merges_related_and_never_lowers_severity(world, session) -> None:
    inst = await world.institution()
    prog = await world.programme(inst)
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    first = await _raise(session, inst, severity=Severity.HIGH, evidence=_evidence(related=[a, b]))
    first.flag.status = FlagStatus.ESCALATED
    await session.flush()
    raised = await _raise(
        session,
        inst,
        severity=Severity.LOW,
        programme_id=prog.id,
        evidence=_evidence("New sentence.", related=[c, a]),
    )
    assert raised.changed and not raised.created
    flag = raised.flag
    assert flag.severity is Severity.HIGH
    assert flag.status is FlagStatus.ESCALATED
    assert flag.related_enrolment_ids == [a, b, c]
    assert flag.evidence["related_enrolment_ids"] == [str(a), str(b), str(c)]
    assert flag.evidence["summary"] == "New sentence."
    assert flag.programme_id == prog.id
    update = (await _audits(session))[-1]
    assert update.action is AuditAction.UPDATE
    assert update.before == {
        "severity": "HIGH",
        "summary": "APAAR ending 4417 is not in the APAAR registry.",
    }

    replaced = await _raise(
        session, inst, evidence=_evidence("New sentence.", related=[c]), replace_related=True
    )
    assert replaced.flag.related_enrolment_ids == [c]


@pytest.mark.parametrize(
    "bad",
    [
        {"summary": "", "facts": [], "related_enrolment_ids": []},
        {"facts": [], "related_enrolment_ids": []},
        {"summary": "x", "facts": [{"label": "a", "value": "b"}], "related_enrolment_ids": []},
        {"summary": "x", "facts": "nope", "related_enrolment_ids": []},
        {"summary": "x", "facts": [], "related_enrolment_ids": "e1"},
    ],
)
async def test_evidence_schema_is_enforced(world, session, bad) -> None:
    inst = await world.institution()
    with pytest.raises(ValueError):
        await _raise(session, inst, evidence=bad)
