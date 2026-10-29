"""CORRECT stores a version and runs the record's rows and the Seat Ledger again; UPHOLD
leaves the covered row CONTRADICTED with `resolved` and closes the case; REOPEN clears the
markers; every decision needs a reason (D43, R2; API_CONTRACT §A4.9, §A4.10)."""

from __future__ import annotations

from sqlalchemy import select

from app.db.session import session_factory
from app.engine import versions
from app.models.audit import AuditLog
from app.models.enums import AdmissionRoute, CheckStatus, CheckType, FlagType, SeatType
from app.models.seat import Seat, SeatPool
from app.models.student import EnrolmentVersion
from app.models.verification import CaseAction
from app.schemas.common import PageParams
from tests.decisions.conftest import (
    cohort,
    decide,
    enrolment,
    flag,
    raise_case,
    row_of,
    set_row,
)


async def _pool_of_seat(seat_id) -> SeatType:
    async with session_factory()() as session:
        seat = await session.get(Seat, seat_id)
        return (await session.get(SeatPool, seat.pool_id)).seat_type


async def test_correct_stores_a_version_and_runs_the_rows_and_the_ledger(dw) -> None:
    ids = await cohort(dw, 20)  # 19 seated, the 20th in the Regular backlog
    target, backlog = ids[3], ids[19]
    regular_seat = (await enrolment(target)).seat_id
    case = await raise_case(dw, FlagType.ELIGIBILITY_BREACH, enrolment_id=target)
    checked_before = (await row_of(target, CheckType.IDENTITY)).checked_at
    west = await dw.login("ro.west@aicte.demo")
    body = decide(
        "CORRECT",
        "WRONG_SEAT_CATEGORY",
        correction={
            "fields": {
                "admission_route": "NRI",
                "nri_sponsored": "yes",
                "counselling_ref": "MHCET-2026-R1-009999",
            }
        },
    )
    response = await west.post(f"/flags/{case}/actions", json=body)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "CORRECTED"
    effects = detail["effects"]
    assert effects["case_status"] == "CORRECTED" and effects["version"] == 1
    assert effects["changes"] == [
        {"field": "admission_route", "before": "COUNSELLING", "after": "NRI"},
        {"field": "counselling_ref", "before": None, "after": "MHCET-2026-R1-009999"},
        {"field": "nri_sponsored", "before": None, "after": True},
    ]
    # the Regular seat is released and taken by the backlog; the record gets the NRI seat
    assert [s["enrolment_id"] for s in effects["seats_released"]] == [str(target)]
    assigned = {s["enrolment_id"] for s in effects["seats_assigned"]}
    assert assigned == {str(target), str(backlog)}
    assert effects["rows_rerun"] == 5 + 1

    record = await enrolment(target)
    assert record.admission_route is AdmissionRoute.NRI
    assert record.counselling_ref == "MHCET-2026-R1-009999"
    assert record.eligibility["nri_sponsored"] is True
    assert await _pool_of_seat(record.seat_id) is SeatType.NRI
    assert (await enrolment(backlog)).seat_id == regular_seat
    assert (await row_of(target, CheckType.SEAT)).status is CheckStatus.CONFIRMED
    assert (await row_of(target, CheckType.IDENTITY)).checked_at >= checked_before

    async with session_factory()() as session:
        stored = (
            await session.execute(
                select(EnrolmentVersion).where(EnrolmentVersion.enrolment_id == target)
            )
        ).scalar_one()
        row = (
            await session.execute(select(CaseAction).where(CaseAction.flag_id == case))
        ).scalar_one()
        history = await versions.history(session, target, page=PageParams())
        audit_fields = (
            (
                await session.execute(
                    select(AuditLog.after).where(
                        AuditLog.entity_type == "flag", AuditLog.entity_id == case
                    )
                )
            )
            .scalars()
            .all()
        )
    assert (stored.source, stored.case_action_seq) == ("DECISION", row.seq)
    assert stored.changes["admission_route"] == ["COUNSELLING", "NRI"]
    assert row.correction == {
        "enrolment_id": str(target),
        "fields": {
            "admission_route": "NRI",
            "nri_sponsored": True,
            "counselling_ref": "MHCET-2026-R1-009999",
        },
    }
    # the record's history names the case and the officer
    item = history["items"][0]
    assert history["total"] == 1 and item["source"] == "DECISION"
    assert item["case"]["type"] == "ELIGIBILITY_BREACH" and item["case"]["action"] == "CORRECT"
    assert item["case"]["reason_code"] == "WRONG_SEAT_CATEGORY"
    assert item["actor"]["role"] == "RO_OFFICER" and item["batch"] is None
    # the case history carries the change; the audit log only the field names
    last = detail["history"][-1]
    assert last["correction"]["enrolment_id"] == str(target)
    assert last["correction"]["changes"] == effects["changes"]
    assert any(a.get("fields") for a in audit_fields if a)
    assert "MHCET-2026-R1-009999" not in str(audit_fields)


async def test_correction_rules(dw) -> None:
    ids = await cohort(dw, 2, rows=False)
    case = await raise_case(dw, FlagType.NAME_MISMATCH, enrolment_id=ids[0])
    admin = await dw.login("admin@aicte.demo")
    url = f"/flags/{case}/actions"

    async def correct(fields: dict) -> tuple[int, dict]:
        response = await admin.post(
            url, json=decide("CORRECT", "UPLOAD_ERROR", correction={"fields": fields})
        )
        return response.status_code, response.json().get("error", {})

    status, error = await correct({})
    assert (status, error["code"]) == (422, "CORRECTION_EMPTY")
    status, error = await correct({"admission_route": "counselling"})  # the value it has
    assert (status, error["code"]) == (422, "CORRECTION_EMPTY")
    status, error = await correct({"year_of_study": 9})
    assert (status, error["code"]) == (422, "CORRECTION_INVALID")
    assert error["message"] == (
        "Year of study: Year of study must be a whole number between 1 and 4"
    )
    assert error["details"] == {"field": "year_of_study"}
    status, error = await correct({"dob": "21/03/2007"})
    assert error["message"] == "Date of birth: Date of birth must be YYYY-MM-DD"
    status, error = await correct({"category": "ROYAL"})
    assert error["message"].startswith("Category: Category must be one of")
    status, error = await correct({"admission_date": "2099-01-01"})
    assert error["message"] == "Admission date: Admission date 2099-01-01 is after today"
    status, error = await correct({"ciwg": "maybe"})
    assert error["message"] == "CIWG: CIWG must be yes or no"
    for upload_only in ("apaar_id", "status", "programme_code", "mobile"):
        status, error = await correct({upload_only: "x"})
        assert (status, error["code"], error["details"]["field"]) == (
            422,
            "CORRECTION_INVALID",
            upload_only,
        )
    # a record the case does not name
    other = await admin.post(
        url,
        json=decide(
            "CORRECT",
            "UPLOAD_ERROR",
            correction={"enrolment_id": str(ids[1]), "fields": {"category": "OBC"}},
        ),
    )
    assert other.status_code == 409 and other.json()["error"]["code"] == "WITHDRAW_NOT_NAMED"
    # nothing was written by any of them
    assert (await flag(case)).status.value == "OPEN"
    async with session_factory()() as session:
        assert (await session.execute(select(EnrolmentVersion))).first() is None
        assert (await session.execute(select(CaseAction))).first() is None


async def test_uphold_resolves_the_row_and_reopen_clears_it(dw) -> None:
    ids = await cohort(dw, 1)
    record = ids[0]
    await set_row(record, CheckType.ADMISSION, CheckStatus.CONTRADICTED)
    case = await raise_case(dw, FlagType.NOT_IN_JOINING_RECORD, enrolment_id=record)
    admin = await dw.login("admin@aicte.demo")
    registrar = await dw.login("registrar@abc.edu.demo")
    url = f"/flags/{case}/actions"

    # every decision needs a reason and a note
    for action in ("UPHOLD", "CORRECT", "WITHDRAW"):
        missing = await admin.post(url, json={"action": action, "note": "No reason."})
        assert missing.status_code == 422, action
        assert missing.json()["error"]["code"] == "REASON_REQUIRED", action

    upheld = await admin.post(url, json=decide("UPHOLD", "SOURCE_RECORD_WRONG"))
    assert upheld.status_code == 200, upheld.text
    body = upheld.json()
    assert body["status"] == "UPHELD" and body["effects"]["rows_resolved"] == 1
    row = await row_of(record, CheckType.ADMISSION)
    # a decision resolves the contradiction; it is not evidence (R2)
    assert row.status is CheckStatus.CONTRADICTED
    assert row.resolved["outcome"] == "UPHELD"
    assert row.resolved["case_id"] == str(case)
    assert row.resolved["reason_code"] == "SOURCE_RECORD_WRONG"
    assert row.resolved["by_id"] == str(dw.users["admin@aicte.demo"])
    assert (await flag(case)).resolved_at is not None
    # the college reads the outcome, the reason and the note
    seen = (await registrar.get(f"/flags/{case}")).json()
    assert seen["decision"]["reason_code"] == "SOURCE_RECORD_WRONG"
    assert seen["history"][-1]["note"] == "Decided on the documents."

    reopened = await admin.post(url, json={"action": "REOPEN", "note": "The student wrote in."})
    assert reopened.status_code == 200 and reopened.json()["status"] == "OPEN"
    assert (await row_of(record, CheckType.ADMISSION)).resolved is None
    async with session_factory()() as session:
        marks = (
            (
                await session.execute(
                    select(AuditLog.after)
                    .where(AuditLog.entity_type == "check", AuditLog.entity_id == row.id)
                    .order_by(AuditLog.seq)
                )
            )
            .scalars()
            .all()
        )
    assert marks == [
        {"type": "ADMISSION", "resolved": True},
        {"type": "ADMISSION", "resolved": False},
    ]


async def test_decisions_that_do_not_fit_the_case_are_refused(dw) -> None:
    case = await raise_case(dw, FlagType.MISSING_FROM_UPLOAD, enrolment_id=None)
    admin = await dw.login("admin@aicte.demo")
    detail = (await admin.get(f"/flags/{case}")).json()
    assert detail["scope"] == "INSTITUTION" and detail["covers"] is None
    assert detail["allowed_actions"] == ["UPHOLD", "REQUEST_DOCS", "ESCALATE", "NOTE", "ASSIGN"]
    for action in ("CORRECT", "WITHDRAW"):
        response = await admin.post(f"/flags/{case}/actions", json=decide(action, "OTHER"))
        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "DECISION_NOT_AVAILABLE"
        assert error["message"] == "This decision does not apply to a Missing from upload case."
        assert error["details"]["type"] == "MISSING_FROM_UPLOAD"
    upheld = await admin.post(
        f"/flags/{case}/actions", json=decide("UPHOLD", "MISSING_NOW_UPLOADED")
    )
    assert upheld.status_code == 200 and upheld.json()["status"] == "UPHELD"
