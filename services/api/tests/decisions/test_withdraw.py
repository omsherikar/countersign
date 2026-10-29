"""WITHDRAW (D43, API_CONTRACT §A4.9, §A4.10): in one transaction the record is withdrawn by
decision, its seat goes to the pool's backlog, its attestation is revoked, a DECISION
version is stored and the audit trail says so. A dry run answers with the same effects and
stores nothing."""

from __future__ import annotations

from sqlalchemy import func, select

from app.cases.decisions import RELEASE_REASON, withdraw_code
from app.core.audit import verify_chain
from app.db.session import session_factory
from app.engine.upload.types import INDIA
from app.models.audit import AuditLog
from app.models.credential import Credential
from app.models.enums import (
    CheckStatus,
    CheckType,
    EnrolmentStatus,
    FlagType,
    SeatEventKind,
)
from app.models.seat import Seat, SeatEvent
from app.models.student import EnrolmentVersion
from app.models.verification import CaseAction
from tests.decisions.conftest import (
    attestation,
    cohort,
    decide,
    enrolment,
    flag,
    raise_case,
    row_of,
    set_row,
)


async def _counts() -> tuple[int, int, int, int]:
    async with session_factory()() as session:
        audit = (await session.execute(select(func.count()).select_from(AuditLog))).scalar_one()
        versions = (
            await session.execute(select(func.count()).select_from(EnrolmentVersion))
        ).scalar_one()
        actions = (await session.execute(select(func.count()).select_from(CaseAction))).scalar_one()
        events = (await session.execute(select(func.count()).select_from(SeatEvent))).scalar_one()
    return audit, versions, actions, events


def _today() -> str:
    from datetime import datetime

    return datetime.now(INDIA).date().isoformat()


async def test_withdraw_releases_the_seat_to_the_backlog_and_revokes_together(dw) -> None:
    # 19 Regular seats: the 20th admission waits in the backlog
    ids = await cohort(dw, 20)
    ravi, backlog = ids[0], ids[19]
    held = (await enrolment(ravi)).seat_id
    assert held is not None and (await enrolment(backlog)).seat_id is None
    seat_code = await _seat_code(held)
    await set_row(ravi, CheckType.ADMISSION, CheckStatus.CONTRADICTED)
    case = await raise_case(dw, FlagType.NOT_IN_JOINING_RECORD, enrolment_id=ravi)
    credential = await attestation(ravi)
    admin = await dw.login("admin@aicte.demo")
    body = decide("WITHDRAW", "STUDENT_NEVER_JOINED")

    before = await _counts()
    preview = await admin.post(f"/flags/{case}/actions", json={**body, "dry_run": True})
    assert preview.status_code == 200, preview.text
    assert preview.json()["dry_run"] is True
    effects = preview.json()["effects"]
    assert effects["case_status"] == "WITHDRAWN"
    assert effects["seats_released"] == [{"enrolment_id": str(ravi), "seat_code": seat_code}]
    assert effects["seats_assigned"] == [{"enrolment_id": str(backlog), "seat_code": seat_code}]
    assert [a["credential_id"] for a in effects["attestations_revoked"]] == [str(credential)]
    assert effects["version"] == 1 and effects["changes"] == []
    assert effects["rows_rerun"] == 1
    withdrawn = next(r for r in effects["records"] if r["enrolment_id"] == str(ravi))
    assert withdrawn == {
        "enrolment_id": str(ravi),
        "status": "WITHDRAWN",
        "record_status": None,
        "status_reason": None,
    }
    # nothing stored, audited or revoked
    assert await _counts() == before
    record = await enrolment(ravi)
    assert record.status is EnrolmentStatus.ACTIVE and record.seat_id == held
    async with session_factory()() as session:
        assert (await session.get(Credential, credential)).revoked is False
    assert (await flag(case)).status.value == "OPEN"

    response = await admin.post(f"/flags/{case}/actions", json=body)
    assert response.status_code == 200, response.text
    done = response.json()
    assert done["status"] == "WITHDRAWN" and done["decision"]["action"] == "WITHDRAW"
    real = done["effects"]
    for key in ("case_status", "seats_released", "seats_assigned", "version", "changes"):
        assert real[key] == effects[key], key
    assert real["attestations_revoked"] == effects["attestations_revoked"]

    record = await enrolment(ravi)
    assert record.status is EnrolmentStatus.WITHDRAWN and record.seat_id is None
    assert record.status_date.isoformat() == _today()
    assert record.status_reason is None and record.next_step.startswith(
        "None. The record was withdrawn by an officer's decision"
    )
    assert (await enrolment(backlog)).seat_id == held
    assert (await row_of(backlog, CheckType.SEAT)).status is CheckStatus.CONFIRMED

    async with session_factory()() as session:
        revoked = await session.get(Credential, credential)
        assert revoked.revoked is True and revoked.revoked_reason == withdraw_code()
        assert revoked.revoked_by_id == dw.users["admin@aicte.demo"]
        release = (
            await session.execute(
                select(SeatEvent).where(
                    SeatEvent.enrolment_id == ravi, SeatEvent.kind == SeatEventKind.RELEASE
                )
            )
        ).scalar_one()
        assert release.reason == RELEASE_REASON == "withdrawn by decision"
        version = (
            await session.execute(
                select(EnrolmentVersion).where(EnrolmentVersion.enrolment_id == ravi)
            )
        ).scalar_one()
        assert (version.version, version.source) == (1, "DECISION")
        assert version.changes["status"] == ["ACTIVE", "WITHDRAWN"]
        assert version.actor_id == dw.users["admin@aicte.demo"]
        row = (
            await session.execute(select(CaseAction).where(CaseAction.flag_id == case))
        ).scalar_one()
        assert version.case_action_seq == row.seq
        assert row.withdrawn_enrolment_ids == [ravi]
        assert row.reason_code == "STUDENT_NEVER_JOINED"

        entries = (
            (await session.execute(select(AuditLog).where(AuditLog.seq > before[0] - 1)))
            .scalars()
            .all()
        )
        assert (await verify_chain(session))[0]
    kinds = {(e.entity_type, e.entity_id) for e in entries}
    assert ("flag", case) in kinds and ("credential", credential) in kinds
    assert ("seat", held) in kinds
    flag_entry = next(e for e in entries if e.entity_type == "flag" and e.entity_id == case)
    assert flag_entry.after["withdrawn_enrolment_ids"] == [str(ravi)]
    assert flag_entry.after["reason_code"] == "STUDENT_NEVER_JOINED"
    status_entry = next(
        e
        for e in entries
        if e.entity_type == "enrolment" and e.entity_id == ravi and "status" in (e.after or {})
    )
    assert status_entry.after["status"] == "WITHDRAWN"
    versioned = next(
        e
        for e in entries
        if e.entity_type == "enrolment" and e.entity_id == ravi and "version" in (e.after or {})
    )
    assert versioned.after == {
        "version": 1,
        "source": "DECISION",
        "changed": ["status", "status_date"],
    }
    # notes never reach the audit log
    assert "Decided on the documents" not in str([e.after for e in entries])

    # the record is no longer named as an ACTIVE record: withdrawing it again is refused
    again = await admin.post(f"/flags/{case}/actions", json={"action": "REOPEN", "note": "Again."})
    assert again.status_code == 200
    refused = await admin.post(f"/flags/{case}/actions", json=body)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "WITHDRAW_NOT_NAMED"
    assert refused.json()["error"]["details"] == {"n": 1, "named_enrolment_ids": []}


async def test_withdraw_only_records_the_case_names(dw) -> None:
    ids = await cohort(dw, 3)
    case = await raise_case(dw, FlagType.NOT_IN_JOINING_RECORD, enrolment_id=ids[0])
    admin = await dw.login("admin@aicte.demo")
    url = f"/flags/{case}/actions"
    other = await admin.post(
        url, json=decide("WITHDRAW", "OTHER", withdrawn_enrolment_ids=[str(ids[1])])
    )
    assert other.status_code == 409
    error = other.json()["error"]
    assert error["code"] == "WITHDRAW_NOT_NAMED"
    assert error["message"] == "1 of the selected records are not named by this case."
    assert error["details"] == {"n": 1, "named_enrolment_ids": [str(ids[0])]}
    none = await admin.post(url, json=decide("WITHDRAW", "OTHER", withdrawn_enrolment_ids=[]))
    assert none.status_code == 422 and none.json()["error"]["code"] == "WITHDRAW_NONE_SELECTED"
    # a regional officer of another region does not see the case
    south = await dw.login("ro.south@aicte.demo")
    assert (await south.post(url, json=decide("WITHDRAW", "OTHER"))).status_code == 404
    registrar = await dw.login("registrar@abc.edu.demo")
    assert (await registrar.post(url, json=decide("WITHDRAW", "OTHER"))).status_code == 403
    assert (await enrolment(ids[0])).status is EnrolmentStatus.ACTIVE


async def _seat_code(seat_id) -> str:
    async with session_factory()() as session:
        return (await session.get(Seat, seat_id)).seat_code
