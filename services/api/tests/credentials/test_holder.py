"""The wallet: share codes, the QR, presentations and the student's summaries."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.errors import ApiError
from app.credentials import holder, issuer
from app.models.audit import AuditLog
from app.models.credential import Consent, CredentialPresentation
from app.models.user import User
from tests.credentials.conftest import make_countersigned, ravi_enrolment


def test_codes_are_six_groups_of_four():
    code = holder.new_code()
    groups = code.split("-")
    assert len(groups) == 6 and all(len(g) == 4 for g in groups)
    assert set(code.replace("-", "")) <= set(issuer.CROCKFORD)
    assert holder.new_code() != code


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF", "K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF"),
        ("  k7pq 3m2x 9zab w4td h8nc 2qrf ", "K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF"),
        ("K7PQ3M2X9ZABW4TDH8NC2QRF", "K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF"),
        ("O7PQ-IM2X-LZAB-W4TD-H8NC-2QRF", "07PQ-1M2X-1ZAB-W4TD-H8NC-2QRF"),
        ("K7PQ-3M2X-9ZAB-W4TD-H8NC", None),
        ("K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRFX", None),
        ("U7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF", None),
        ("", None),
    ],
)
def test_typed_codes_are_normalised(typed, expected):
    assert holder.normalise_code(typed) == expected


def test_the_code_hash_is_of_the_grouped_form():
    code = "K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF"
    assert holder.code_hash(code) == hashlib.sha256(code.encode()).hexdigest()


def test_the_qr_is_inline_svg():
    svg = holder.qr_svg("http://localhost:3000/verify/K7PQ-3M2X-9ZAB-W4TD-H8NC-2QRF")
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 41 41"')
    assert "<?xml" not in svg and "width=" not in svg and "height=" not in svg
    assert 'fill="#fff"' in svg and 'stroke="#000"' in svg


async def _ravi(session):
    enrolment = await ravi_enrolment(session)
    await make_countersigned(session, enrolment.id)
    credential = await issuer.issue_if_eligible(session, enrolment.id)
    user = (await session.execute(select(User).where(User.email == "student@demo"))).scalar_one()
    return credential, user


async def test_a_share_discloses_only_the_chosen_fields(world, session):
    credential, user = await _ravi(session)
    share = await holder.present(session, credential, user, fields=["academic_year"])
    assert share["disclosed"] == ["institution", "programme", "academic_year"]
    assert share["total"] == 8
    assert share["url"] == f"http://localhost:3000/verify/{share['code']}"
    assert holder.normalise_code(share["code"]) == share["code"]
    assert share["qr_svg"].startswith("<svg")

    row = (await session.execute(select(CredentialPresentation))).scalar_one()
    assert str(row.id) == share["id"]
    assert row.code_hash == holder.code_hash(share["code"])
    assert share["code"] not in row.presentation
    assert row.expires_at - row.created_at == timedelta(minutes=10)
    parts = row.presentation.split("~")
    assert len(parts) == 5  # issuer JWT, three disclosures, key-binding JWT
    assert set(issuer.disclosures(row.presentation)) == {
        "institution",
        "programme",
        "academic_year",
    }
    kb_header = issuer.b64url_json(parts[-1].split(".")[0])
    kb = issuer.b64url_json(parts[-1].split(".")[1])
    assert kb_header["typ"] == "kb+jwt"
    assert kb["nonce"] == share["code"] and kb["aud"] == "http://localhost:8000/verify"
    assert set(kb) == {"nonce", "aud", "iat", "sd_hash"}

    consent = (await session.execute(select(Consent))).scalar_one()
    assert consent.purpose.value == "CREDENTIAL_SHARE" and consent.status.value == "GIVEN"
    assert consent.channel == "PORTAL" and consent.notice_text == holder.SHARE_CONSENT_TEXT
    assert consent.enrolment_id is None
    entries = (
        (await session.execute(select(AuditLog).where(AuditLog.actor_id == user.id)))
        .scalars()
        .all()
    )
    shaped = {(e.action.value, e.entity_type): e.after for e in entries}
    assert shaped[("CREATE", "credential_presentation")] == {
        "credential_id": str(credential.id),
        "disclosed": ["institution", "programme", "academic_year"],
        "expires_at": share["expires_at"],
    }
    assert shaped[("READ", "credential")] == {"via": "share", "presentation_id": share["id"]}
    assert ("CREATE", "consent") in shaped
    await session.rollback()


async def test_shares_are_refused_for_unknown_fields_and_without_consent(world, session):
    credential, user = await _ravi(session)
    with pytest.raises(ApiError) as unknown:
        await holder.present(session, credential, user, fields=["name", "gpa"], consent=False)
    assert unknown.value.status_code == 422
    assert unknown.value.message == "fields: unknown field: gpa."
    assert unknown.value.details == {
        "fields": [
            {"field": "fields", "message": "Unknown field: gpa."},
            {"field": "consent", "message": "Agree to the share text to create a proof."},
        ]
    }
    await session.rollback()


async def test_revoked_and_expired_proofs_cannot_be_shared(world, session):
    credential, user = await _ravi(session)
    credential.expires_at = datetime(2026, 8, 31, 18, 29, 59, tzinfo=UTC)
    with pytest.raises(ApiError) as expired:
        await holder.present(session, credential, user, fields=[], consent=False)
    assert (expired.value.status_code, expired.value.code) == (409, "CREDENTIAL_NOT_ELIGIBLE")
    assert expired.value.message == "This proof expired on 31 Aug 2026 and cannot be shared."
    assert expired.value.details == {"reason": "EXPIRED"}

    credential.revoked = True
    credential.revoked_at = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)  # 29 Oct in IST
    with pytest.raises(ApiError) as revoked:
        await holder.present(session, credential, user, fields=["name"])
    assert revoked.value.code == "CREDENTIAL_REVOKED"
    assert revoked.value.message == "This proof was revoked on 29 Oct 2026 and cannot be shared."
    assert revoked.value.details == {"revoked_at": "2026-10-28T20:00:00Z"}
    await session.rollback()


async def test_withdrawing_share_consent_expires_live_shares(world, session):
    credential, user = await _ravi(session)
    await holder.present(session, credential, user, fields=["name"])
    await holder.present(session, credential, user, fields=["dob"])
    old = (await session.execute(select(CredentialPresentation))).scalars().first()
    old.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()

    now = datetime.now(UTC)
    assert await holder.expire_live_presentations(session, credential.student_id, now=now) == 1
    assert await holder.expire_live_presentations(session, credential.student_id, now=now) == 0
    rows = (await session.execute(select(CredentialPresentation))).scalars().all()
    for row in rows:
        await session.refresh(row)
    assert all(r.expires_at <= now for r in rows)
    await session.rollback()


async def test_summaries_for_the_student_and_the_enrolment(world, session):
    credential, _user = await _ravi(session)
    [brief] = await holder.wallet_summary(session, credential.student_id)
    assert brief == {
        "id": str(credential.id),
        "kind": "ENROLMENT",
        "status": "ACTIVE",
        "enrolment_id": str(credential.enrolment_id),
        "institution_name": "ABC College of Engineering",
        "issued_at": issuer.iso(credential.issued_at),
    }
    credential.revoked = True
    credential.revoked_at = datetime.now(UTC)
    credential.revoked_reason = "FLAG_CONFIRMED"
    await session.flush()
    [ref] = await holder.credential_refs(session, credential.enrolment_id)
    assert ref["status"] == "REVOKED" and ref["short_id"] == credential.short_id
    assert ref["revoked_reason_code"] == ref["revoked_reason"] == "FLAG_CONFIRMED"
    await session.rollback()
