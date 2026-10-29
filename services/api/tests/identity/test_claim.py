"""A student without APAAR claims the record by provisional id (D36, API_CONTRACT §A4.12):
the date of birth must be equal and the name must reach 75; the DigiLocker sign-in decides,
and the record is countersigned when the rest of its evidence allows."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select, update

from app.core import crypto
from app.core.ratelimit import limiter
from app.db.session import session_factory
from app.models.audit import AuditLog
from app.models.credential import Credential
from app.models.enums import (
    AuditAction,
    CheckType,
    ConsentStatus,
    CredentialKind,
    RecordStatus,
)
from app.models.student import Enrolment, Student
from app.models.verification import Check
from tests.identity.conftest import (
    UNCLAIMED_ROWS,
    add_account,
    client,
    pending_client,
    sign_in,
    student_of,
    user_of,
    write_rows,
)

DOB = date(2007, 1, 1)  # every world student's date of birth
NO_MATCH = {
    "error": {
        "code": "CLAIM_NO_MATCH",
        "message": (
            "This provisional ID does not match the name and date of birth on your DigiLocker."
        ),
        "details": {},
    }
}


async def claim(c, provisional_id: str):
    return await c.post("/auth/digilocker/claim", json={"provisional_id": provisional_id})


async def unclaimed(world, name: str = "Asha Patil") -> tuple[Enrolment, Student]:
    """A refused-consent record at ABC CSE whose seat fits and whose joining record was
    found: only Identity is missing (NOT_APPLICABLE), so it waits for evidence."""
    enrolment = await world.enrolment(name, apaar=None, consent=ConsentStatus.REFUSED)
    await write_rows(enrolment.id, UNCLAIMED_ROWS)
    async with session_factory()() as s:
        assert (await s.get(Enrolment, enrolment.id)).record_status is (
            RecordStatus.AWAITING_EVIDENCE
        )
    return enrolment, await student_of(enrolment)


async def test_a_refused_consent_student_claims_and_the_record_is_countersigned(world, gov):
    enrolment, student = await unclaimed(world)
    add_account(gov, "DL-ASHA-0001", "Asha Patil", DOB)
    async with client() as c:
        signed = await sign_in(c, gov, "DL-ASHA-0001", "/student")
        assert signed.headers["location"] == "/student/claim?next=/student"
        typed = f"  {student.provisional_id.lower()} "  # trimmed and upper-cased
        response = await c.post("/auth/digilocker/claim", json={"provisional_id": typed})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user"]["role"] == "STUDENT" and body["next"] == "/student"
        assert body["user"]["scope"]["student_id"] == str(student.id)
        [record] = body["claimed"]["enrolments"]
        assert body["claimed"]["student_id"] == str(student.id)
        assert record["id"] == str(enrolment.id) and record["claimed"] is True
        assert record["record_status"] == "COUNTERSIGNED"
        [identity] = [r for r in record["checks"] if r["type"] == "IDENTITY"]
        assert (identity["state"], identity["independent"]) == ("CONFIRMED", True)
        # signed in now, and the pending claim is gone
        assert (await c.get("/me")).json()["user"]["scope"]["student_id"] == str(student.id)
        assert (await c.get("/auth/digilocker/claim")).status_code == 401
        me = (await c.get("/students/me")).json()
        assert me["enrolments"][0]["claimed"] is True

    async with session_factory()() as s:
        row = (
            await s.execute(
                select(Check).where(
                    Check.enrolment_id == enrolment.id, Check.type == CheckType.IDENTITY
                )
            )
        ).scalar_one()
        stored = await s.get(Student, student.id)
        attestations = (
            (await s.execute(select(Credential).where(Credential.enrolment_id == enrolment.id)))
            .scalars()
            .all()
        )
        claimed = (
            (
                await s.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "student",
                        AuditLog.action == AuditAction.UPDATE,
                        AuditLog.entity_id == student.id,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert (row.supplied_by, row.independent) == ("Student via DigiLocker sign-in", True)
    assert row.detail["basis"] == "DIGILOCKER_CLAIM"
    # the claim never stores an APAAR on a student who refused consent (D36)
    assert stored.apaar_hmac is None and stored.consent_status is ConsentStatus.REFUSED
    # countersigned, so the enrolment attestation is issued at once
    assert [(a.kind, a.revoked) for a in attestations] == [(CredentialKind.ENROLMENT, False)]
    [entry] = claimed
    user = await user_of(student.id)
    assert entry.actor_id == user.id
    assert entry.after == {"claimed_via": "digilocker", "enrolments": 1}
    assert user.digilocker_sub == "DL-ASHA-0001"


async def test_no_match_is_the_same_answer_whatever_failed(world):
    _enrolment, student = await unclaimed(world, "Asha Patil")
    attempts = [
        ("Asha Patil", DOB, "PRV-ZZZZ2222"),  # an id nobody holds
        ("Asha Patil", date(2007, 1, 2), student.provisional_id),  # another birth date
        ("Rohan Kulkarni", DOB, student.provisional_id),  # another person's name
    ]
    for name, dob, provisional_id in attempts:
        async with pending_client(name, dob) as c:
            response = await c.post(
                "/auth/digilocker/claim", json={"provisional_id": provisional_id}
            )
        assert (response.status_code, response.json()) == (422, NO_MATCH), (name, dob)
    # a small spelling difference still matches: the name supports, the sign-in decides
    async with pending_client("Aasha Patil", DOB) as c:
        close = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": student.provisional_id}
        )
    assert close.status_code == 200, close.text


async def test_not_needed_and_already_claimed_answer_only_after_a_match(world):
    # a record that has since gained a linked APAAR keeps its provisional id
    enrolment = await world.enrolment("Kiran Rao", apaar=None, consent=ConsentStatus.PENDING)
    linked = await student_of(enrolment)
    async with session_factory()() as s:
        await s.execute(
            update(Student)
            .where(Student.id == linked.id)
            .values(
                consent_status=ConsentStatus.LINKED,
                apaar_hmac=crypto.hmac_bytes("777766665555", "apaar"),
                apaar_encrypted=crypto.encrypt("777766665555"),
                apaar_last4="5555",
            )
        )
        await s.commit()
    async with pending_client("Kiran Rao", date(2000, 1, 1)) as c:
        hidden = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": linked.provisional_id}
        )
    assert (hidden.status_code, hidden.json()) == (422, NO_MATCH)
    async with pending_client("Kiran Rao", DOB) as c:
        not_needed = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": linked.provisional_id}
        )
    assert not_needed.status_code == 409
    assert not_needed.json()["error"] == {
        "code": "CLAIM_NOT_NEEDED",
        "message": "This record has an APAAR, so it links to DigiLocker on its own.",
        "details": {},
    }

    _other, student = await unclaimed(world, "Sneha Patil")
    async with pending_client("Sneha Patil", DOB, sub="DL-SNEH-0001") as c:
        first = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": student.provisional_id}
        )
    assert first.status_code == 200
    async with pending_client("Sneha Patil", date(1999, 9, 9), sub="DL-SNEH-0002") as c:
        hidden = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": student.provisional_id}
        )
    assert (hidden.status_code, hidden.json()) == (422, NO_MATCH)
    async with pending_client("Sneha Patil", DOB, sub="DL-SNEH-0002") as c:
        taken = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": student.provisional_id}
        )
    assert taken.status_code == 409
    assert taken.json()["error"] == {
        "code": "CLAIM_ALREADY_CLAIMED",
        "message": "This record is already claimed through another DigiLocker sign-in.",
        "details": {},
    }
    # the same DigiLocker account claiming again just signs in again
    async with pending_client("Sneha Patil", DOB, sub="DL-SNEH-0001") as c:
        again = await c.post(
            "/auth/digilocker/claim", json={"provisional_id": student.provisional_id}
        )
    assert again.status_code == 200


async def test_the_format_and_the_pending_claim(world):
    async with pending_client("Asha Patil", DOB) as c:
        for typed in ("PRV-12", "7Q2MK4PX", "PRV-7Q2MK4P!", ""):
            response = await c.post("/auth/digilocker/claim", json={"provisional_id": typed})
            assert response.status_code == 422, typed
            error = response.json()["error"]
            assert error["code"] == "VALIDATION_ERROR"
            assert error["details"]["fields"] == [
                {
                    "field": "provisional_id",
                    "message": "A provisional ID is PRV- followed by 8 letters and digits.",
                }
            ]
    async with client() as c:
        nobody = await c.post("/auth/digilocker/claim", json={"provisional_id": "PRV-ZZZZ2222"})
        c.cookies.set("cs_dl_claim", "forged.claim.cookie")
        forged = await c.post("/auth/digilocker/claim", json={"provisional_id": "PRV-ZZZZ2222"})
    for response in (nobody, forged):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "DIGILOCKER_STATE_INVALID"


async def test_the_sixth_try_in_fifteen_minutes_is_refused(world):
    limiter.enabled = True
    limiter.reset()
    try:
        async with pending_client("Asha Patil", DOB, sub="DL-TRY-0001") as c:
            statuses = [
                (
                    await c.post("/auth/digilocker/claim", json={"provisional_id": "PRV-ZZZZ2222"})
                ).status_code
                for _ in range(6)
            ]
            last = await c.post("/auth/digilocker/claim", json={"provisional_id": "PRV-ZZZZ2222"})
        # another DigiLocker subject has its own five tries
        async with pending_client("Asha Patil", DOB, sub="DL-TRY-0002") as other:
            fresh = await other.post(
                "/auth/digilocker/claim", json={"provisional_id": "PRV-ZZZZ2222"}
            )
    finally:
        limiter.enabled = False
        limiter.reset()
    assert statuses == [422] * 5 + [429]
    error = last.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert 0 < error["details"]["retry_after"] <= 15 * 60
    assert last.headers["retry-after"] == str(error["details"]["retry_after"])
    assert fresh.status_code == 422


@pytest.mark.parametrize("next_page", ["/student", "/student/notices/" + "N" * 43])
async def test_the_claim_returns_where_the_sign_in_started(world, next_page):
    _enrolment, student = await unclaimed(world)
    async with pending_client("Asha Patil", DOB, next_path=next_page) as c:
        body = (await claim(c, student.provisional_id)).json()
    assert body["next"] == next_page
