"""Issuance: who is eligible, what an Enrolment or Degree proof holds, revocation."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from jwcrypto.jws import JWS
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.credentials import issuer, keys, status_list
from app.models.audit import AuditLog
from app.models.credential import Credential, HolderKey
from app.models.enums import (
    CheckStatus,
    CheckType,
    CredentialKind,
    EnrolmentStatus,
    FlagStatus,
    FlagType,
    Severity,
)
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Flag
from tests.credentials.conftest import make_countersigned, ravi_enrolment, set_check


def _jwt_part(token: str, n: int) -> dict:
    return issuer.b64url_json(token.split("~")[0].split(".")[n])


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _flag(session, enrolment, severity: Severity, status: FlagStatus, related=False) -> Flag:
    flag = Flag(
        type=FlagType.NAME_MISMATCH,
        severity=severity,
        status=status,
        institution_id=enrolment.institution_id,
        enrolment_id=None if related else enrolment.id,
        related_enrolment_ids=[enrolment.id] if related else [],
        evidence={"summary": "test"},
        dedupe_key=f"test:{uuid.uuid4()}",
    )
    session.add(flag)
    await session.flush()
    return flag


async def test_an_enrolment_proof_waits_for_the_students_yes(world, session):
    enrolment = await ravi_enrolment(session)
    assert await issuer.issue_if_eligible(session, enrolment.id) is None
    assert await _count(session, Credential) == 0
    assert await _count(session, HolderKey) == 0

    await make_countersigned(session, enrolment.id)
    credential = await issuer.issue_if_eligible(session, enrolment.id)
    assert credential is not None
    assert await issuer.issue_if_eligible(session, enrolment.id) is None  # one live proof
    await session.commit()

    assert credential.kind is CredentialKind.ENROLMENT
    assert credential.vct == "countersign:enrolment:v1"
    assert len(credential.short_id) == 8 and set(credential.short_id) <= set(issuer.CROCKFORD)
    assert credential.disclosable == list(issuer.ENROLMENT_DISCLOSABLE)
    assert credential.expires_at == datetime(2027, 8, 31, 18, 29, 59, tzinfo=UTC)
    assert 0 <= credential.status_list_index < status_list.SIZE

    header = _jwt_part(credential.sd_jwt, 0)
    payload = _jwt_part(credential.sd_jwt, 1)
    active = await keys.active_issuer_key(session)
    assert header == {"alg": "ES256", "typ": "dc+sd-jwt", "kid": active.kid}
    assert credential.issuer_key_id == active.kid
    assert payload["iss"] == "http://localhost:8000"
    assert payload["exp"] == int(credential.expires_at.timestamp())
    assert payload["iat"] == int(credential.issued_at.timestamp())
    assert payload["vct"] == "countersign:enrolment:v1"
    assert payload["status"] == {
        "status_list": {
            "idx": credential.status_list_index,
            "uri": "http://localhost:8000/status-lists/1",
        }
    }
    holder = await keys.holder_key(session, enrolment.student_id, create=False)
    public = holder.export_public(as_dict=True)
    assert payload["cnf"] == {"jwk": {k: public[k] for k in ("kty", "crv", "x", "y")}}
    assert payload["_sd_alg"] == "sha-256" and len(payload["_sd"]) == 8
    assert not set(payload) & set(issuer.ENROLMENT_DISCLOSABLE)
    signed = JWS()
    signed.deserialize(credential.sd_jwt.split("~")[0])
    signed.verify(keys.key_in(await keys.jwks(session), header["kid"]))

    today = issuer.ist_date(credential.issued_at)
    assert issuer.disclosures(credential.sd_jwt) == {
        "name": "Ravi Kumar Sharma",
        "dob": "2007-03-21",
        "apaar_masked": "XXXX XXXX 4417",
        "institution": {"name": "ABC College of Engineering", "aicte_id": "1-ABC-0001"},
        "programme": {"name": "B.Tech Computer Science and Engineering", "level": "UG"},
        "academic_year": "2026-27",
        "year_of_study": 1,
        "countersigned": {
            "checks": ["IDENTITY", "ADMISSION", "SEAT", "STUDENT"],
            "on": today.isoformat(),
        },
    }
    claims = {
        c["key"]: (c["label"], c["value"], c["disclosable"]) for c in issuer.claims_for(credential)
    }
    assert claims["dob"] == ("Date of birth", "21 Mar 2007", True)
    assert claims["institution"][1] == "ABC College of Engineering (1-ABC-0001)"
    assert claims["programme"][1] == "B.Tech Computer Science and Engineering (UG)"
    assert claims["year_of_study"] == ("Year of study", "1", True)
    assert claims["countersigned"] == (
        "Countersigned by",
        f"Identity, Admission, Seat and Student, as of {issuer.display_date(today)}",
        True,
    )
    assert claims["expires"] == ("Valid until", "31 Aug 2027", False)
    assert claims["issued"][2] is False

    entry = (
        await session.execute(select(AuditLog).where(AuditLog.entity_type == "credential"))
    ).scalar_one()
    assert entry.actor_id is None and entry.entity_id == credential.id
    assert entry.after == {
        "kind": "ENROLMENT",
        "enrolment_id": str(enrolment.id),
        "short_id": credential.short_id,
        "status_list_index": credential.status_list_index,
    }


async def test_no_apaar_means_no_masked_apaar_claim(world, session):
    enrolment = await ravi_enrolment(session)
    student = await session.get(Student, enrolment.student_id)
    student.apaar_last4 = None
    await make_countersigned(session, enrolment.id)
    credential = await issuer.issue_if_eligible(session, enrolment.id)
    assert "apaar_masked" not in credential.disclosable
    assert len(credential.disclosable) == 7
    assert "apaar_masked" not in issuer.disclosures(credential.sd_jwt)
    await session.rollback()


@pytest.mark.parametrize(
    "blocker",
    ["student_pending", "student_fail", "other_fail", "withdrawn", "high_flag", "related_high"],
)
async def test_what_blocks_an_enrolment_proof(world, session, blocker):
    enrolment = await ravi_enrolment(session)
    await make_countersigned(session, enrolment.id)
    if blocker == "student_pending":
        await set_check(session, enrolment.id, CheckType.STUDENT, CheckStatus.PENDING)
    elif blocker == "student_fail":
        await set_check(session, enrolment.id, CheckType.STUDENT, CheckStatus.FAIL)
    elif blocker == "other_fail":
        await set_check(session, enrolment.id, CheckType.ADMISSION, CheckStatus.FAIL)
    elif blocker == "withdrawn":
        enrolment.status = EnrolmentStatus.WITHDRAWN
    elif blocker == "high_flag":
        await _flag(session, enrolment, Severity.HIGH, FlagStatus.ESCALATED)
    else:
        await _flag(session, enrolment, Severity.HIGH, FlagStatus.DOCS_REQUESTED, related=True)
    await session.flush()
    assert await issuer.eligibility(session, enrolment.id) is False
    assert await issuer.issue_if_eligible(session, enrolment.id) is None
    await session.rollback()


async def test_pending_studying_cleared_and_lesser_flags_do_not_block(world, session):
    enrolment = await ravi_enrolment(session)
    await make_countersigned(session, enrolment.id)
    await set_check(session, enrolment.id, CheckType.STUDYING, CheckStatus.PENDING)
    await _flag(session, enrolment, Severity.HIGH, FlagStatus.CLEARED)
    await _flag(session, enrolment, Severity.MEDIUM, FlagStatus.OPEN)
    assert await issuer.eligibility(session, enrolment.id) is True
    credential = await issuer.issue_if_eligible(session, enrolment.id)
    payload_checks = issuer.disclosures(credential.sd_jwt)["countersigned"]["checks"]
    assert payload_checks == ["IDENTITY", "ADMISSION", "SEAT", "STUDENT"]
    await session.rollback()


async def test_a_concurrent_issue_wins_quietly(world, session, monkeypatch):
    enrolment = await ravi_enrolment(session)
    await make_countersigned(session, enrolment.id)
    first = await issuer.issue_if_eligible(session, enrolment.id)

    async def always(*_args, **_kwargs):
        return True

    monkeypatch.setattr(issuer, "_eligible", always)
    assert await issuer.issue_if_eligible(session, enrolment.id) is None
    rows = (await session.execute(select(Credential))).scalars().all()
    assert [c.id for c in rows] == [first.id]
    await session.rollback()


async def test_a_short_id_clash_draws_again(world, session, monkeypatch):
    enrolment = await ravi_enrolment(session)
    await make_countersigned(session, enrolment.id)
    first = await issuer.issue_if_eligible(session, enrolment.id)
    first.revoked = True
    await session.flush()
    draws = iter([first.short_id, "ZZZZZZZZ"])
    monkeypatch.setattr(issuer, "new_short_id", lambda: next(draws))
    second = await issuer.issue_if_eligible(session, enrolment.id)
    assert second.short_id == "ZZZZZZZZ"
    await session.rollback()


async def _graduate(session, name: str) -> Enrolment:
    return (
        await session.execute(
            select(Enrolment)
            .join(Student, Student.id == Enrolment.student_id)
            .where(Student.name == name, Enrolment.status == EnrolmentStatus.GRADUATED)
        )
    ).scalar_one()


async def test_degree_proofs(world, session):
    admin = (
        await session.execute(select(User).where(User.email == "admin@aicte.demo"))
    ).scalar_one()
    with pytest.raises(ApiError) as refused:
        await issuer.issue_degree(session, (await ravi_enrolment(session)).id, actor_id=admin.id)
    assert refused.value.status_code == 409
    assert refused.value.code == "CREDENTIAL_NOT_ELIGIBLE"
    assert refused.value.details == {"reason": "NOT_GRADUATED"}

    enrolment = await _graduate(session, "Meera Kulkarni")
    degree, created = await issuer.issue_degree(session, enrolment.id, actor_id=admin.id)
    assert created is True
    again, created_again = await issuer.issue_degree(session, enrolment.id, actor_id=admin.id)
    assert (again.id, created_again) == (degree.id, False)

    payload = _jwt_part(degree.sd_jwt, 1)
    assert payload["vct"] == "countersign:degree:v1"
    assert "cnf" not in payload and "exp" not in payload and degree.expires_at is None
    assert degree.disclosable == list(issuer.DEGREE_DISCLOSABLE)
    values = issuer.disclosures(degree.sd_jwt)
    assert values["university"] == {
        "name": "Maharashtra State Technical University",
        "code": "MSTU",
    }
    assert values["year_of_award"] == 2026
    assert values["apaar_masked"] == "XXXX XXXX 0401"
    assert issuer.holder_bound(degree) is False
    entry = (
        await session.execute(select(AuditLog).where(AuditLog.entity_id == degree.id))
    ).scalar_one()
    assert entry.actor_id == admin.id and entry.after["kind"] == "DEGREE"

    provisional = await _graduate(session, "Gauri Sathe")
    no_apaar, _ = await issuer.issue_degree(session, provisional.id, actor_id=admin.id)
    assert "apaar_masked" not in no_apaar.disclosable

    await issuer.revoke(
        session, degree, reason="Degree withdrawn by the university.", actor_id=admin.id
    )
    fresh, created = await issuer.issue_degree(session, enrolment.id, actor_id=admin.id)
    assert created is True and fresh.id != degree.id
    await session.rollback()


async def test_an_officer_revocation(world, session):
    admin = (
        await session.execute(select(User).where(User.email == "admin@aicte.demo"))
    ).scalar_one()
    enrolment = await ravi_enrolment(session)
    await make_countersigned(session, enrolment.id)
    credential = await issuer.issue_if_eligible(session, enrolment.id)
    await issuer.revoke(
        session, credential, reason="Admission found to be fraudulent.", actor_id=admin.id
    )
    assert credential.revoked and credential.revoked_by_id == admin.id
    assert credential.revoked_reason == "Admission found to be fraudulent."
    assert issuer.reason_code(credential.revoked_reason) == "ADMIN"
    assert issuer.status_of(credential) == "REVOKED"
    entry = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_id == credential.id)
                .order_by(AuditLog.seq.desc())
            )
        )
        .scalars()
        .first()
    )
    assert entry.after == {"revoked": True, "reason_code": "ADMIN"}
    assert "fraudulent" not in json.dumps(entry.after)

    with pytest.raises(ApiError) as again:
        await issuer.revoke(session, credential, reason="Again.", actor_id=admin.id)
    assert again.value.code == "CREDENTIAL_REVOKED"
    assert again.value.message == "This proof is already revoked."
    await session.rollback()


def test_reason_codes_and_words():
    assert [
        issuer.reason_code(r) for r in (None, "ENROLMENT_WITHDRAWN", "FLAG_CONFIRMED", "x")
    ] == [
        None,
        "ENROLMENT_WITHDRAWN",
        "FLAG_CONFIRMED",
        "ADMIN",
    ]
    assert issuer.join_words(["Identity"]) == "Identity"
    assert issuer.join_words(["Identity", "Seat"]) == "Identity and Seat"
    assert issuer.display_date(datetime(2026, 10, 5).date()) == "5 Oct 2026"
    assert issuer.enrolment_expiry("2026-27").isoformat() == "2027-08-31T18:29:59+00:00"
