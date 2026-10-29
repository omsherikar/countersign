"""Issuing and revoking attestations (D26, D44; API_CONTRACT A3.15, A3.18, §A4.14).

An enrolment attestation is an SD-JWT VC bound to the student's holder key (`cnf`), issued
when the record is COUNTERSIGNED (the evidence rule, D35): the attestation says what the
record card says. A completion attestation, for the awarding body's own certificate, has
no `cnf` and no `exp`, because a printed block cannot be tied to a phone; Countersign
issues no degree. Every claim that identifies the student is selectively disclosable, one
top-level disclosure each, so the holder chooses what a verifier sees.
"""

from __future__ import annotations

import base64
import json
import secrets
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from jwcrypto.jwk import JWK
from sd_jwt.common import SDObj
from sd_jwt.issuer import SDJWTIssuer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.crypto import mask_apaar
from app.core.errors import ApiError
from app.credentials import keys, status_list
from app.engine.contracts import CHECK_ORDER
from app.models.credential import Credential
from app.models.enums import (
    AuditAction,
    CheckStatus,
    CheckType,
    CredentialKind,
    EnrolmentStatus,
    RecordStatus,
)
from app.models.geo import University
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.verification import Check

ENROLMENT_VCT = "countersign:enrolment:v1"
COMPLETION_VCT = "countersign:completion:v1"
# completion attestations issued before D44 carry this type and still verify
DEGREE_VCT = "countersign:degree:v1"
ENROLMENT_DISCLOSABLE = (
    "name",
    "dob",
    "apaar_masked",
    "institution",
    "programme",
    "academic_year",
    "year_of_study",
    "countersigned",
)
DEGREE_DISCLOSABLE = (
    "name",
    "apaar_masked",
    "institution",
    "programme",
    "university",
    "year_of_award",
)
ALWAYS_DISCLOSED = ("institution", "programme")
REASON_CODES = (
    "ENROLMENT_WITHDRAWN",
    "ENROLMENT_TRANSFERRED",
    "CLAIM_WITHDRAWN",
    "STUDENT_DISPUTE",
    "FLAG_CONFIRMED",
)
ADMIN_REASON = "ADMIN"

ISSUER_NAME = "Countersign"
SD_JWT_TYP = "dc+sd-jwt"
IST = timezone(timedelta(hours=5, minutes=30), "IST")
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
SHORT_ID_LENGTH = 8
_ATTEMPTS = 8

LABELS = {
    "name": "Name",
    "dob": "Date of birth",
    "apaar_masked": "APAAR (masked)",
    "provisional_id": "Provisional id",
    "institution": "Institution",
    "programme": "Programme",
    "academic_year": "Academic year",
    "year_of_study": "Year of study",
    "countersigned": "Countersigned by",
    "university": "University",
    "year_of_award": "Year of completion",
    "proof_id": "Attestation id",
    "issued": "Issued",
    "expires": "Valid until",
}
# the rows' labels (copy deck check.*)
CHECK_WORDS = {
    CheckType.IDENTITY: "Identity",
    CheckType.SEAT: "Seat",
    CheckType.ADMISSION: "Joining record",
    CheckType.STUDYING: "Credits",
    CheckType.STUDENT: "Student",
}
_VCT_KIND = {
    ENROLMENT_VCT: CredentialKind.ENROLMENT,
    COMPLETION_VCT: CredentialKind.COMPLETION,
    DEGREE_VCT: CredentialKind.COMPLETION,
}


# ------------------------------------------------------------------ wire helpers


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def display_date(value: date) -> str:
    """`5 Oct 2026`, the date form used inside sentences and claim values."""
    return f"{value.day} {value.strftime('%b')} {value.year}"


def ist_date(value: datetime) -> date:
    return value.astimezone(IST).date()


def issuer_ref() -> dict[str, str]:
    return {"name": ISSUER_NAME, "url": get_settings().issuer_url}


def year_end(academic_year: str) -> int:
    """The calendar year an academic year ends in: `2025-26` gives 2026."""
    return int(academic_year[:4]) + 1


def enrolment_expiry(academic_year: str) -> datetime:
    """31 August of the year the academic year ends, 23:59:59 IST."""
    return datetime(year_end(academic_year), 8, 31, 23, 59, 59, tzinfo=IST).astimezone(UTC)


def new_short_id() -> str:
    return "".join(secrets.choice(CROCKFORD) for _ in range(SHORT_ID_LENGTH))


def kind_of(vct: Any) -> CredentialKind | None:
    return _VCT_KIND.get(vct) if isinstance(vct, str) else None


def disclosable_for(kind: CredentialKind) -> tuple[str, ...]:
    return ENROLMENT_DISCLOSABLE if kind is CredentialKind.ENROLMENT else DEGREE_DISCLOSABLE


def join_words(words: Iterable[str]) -> str:
    """`Identity, Seat and Joining record`."""
    items = list(words)
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def display_value(key: str, value: Any) -> str:
    """The `value` a person reads for a claim (API_CONTRACT A3.15 table)."""
    if key == "dob" and isinstance(value, str):
        try:
            return display_date(date.fromisoformat(value))
        except ValueError:
            return value
    if key == "institution" and isinstance(value, Mapping):
        return f"{value.get('name')} ({value.get('aicte_id')})"
    if key == "programme" and isinstance(value, Mapping):
        return f"{value.get('name')} ({value.get('level')})"
    if key == "university" and isinstance(value, Mapping):
        return f"{value.get('name')} ({value.get('code')})"
    if key == "countersigned" and isinstance(value, Mapping):
        words = [CHECK_WORDS.get(c, str(c)) for c in value.get("checks", [])]
        on = value.get("on")
        try:
            when = display_date(date.fromisoformat(on)) if isinstance(on, str) else ""
        except ValueError:
            when = on
        return f"{join_words(words)}, as of {when}"
    return str(value)


def status_of(credential: Credential, now: datetime | None = None) -> str:
    """REVOKED when revoked, else EXPIRED once `expires_at` has passed, else ACTIVE."""
    if credential.revoked:
        return "REVOKED"
    if credential.expires_at is not None and credential.expires_at <= (now or datetime.now(UTC)):
        return "EXPIRED"
    return "ACTIVE"


def reason_code(stored: str | None) -> str | None:
    """The stored value when it is a system code, else ADMIN (an officer's own words)."""
    if stored is None:
        return None
    return stored if stored in REASON_CODES else ADMIN_REASON


def wire_reason_code(credential: Credential) -> str | None:
    if not credential.revoked:
        return None
    return reason_code(credential.revoked_reason) or ADMIN_REASON


def holder_bound(credential: Credential) -> bool:
    """Enrolment attestations carry the holder's key; completion attestations do not."""
    return credential.kind is CredentialKind.ENROLMENT


def b64url_json(text: str) -> Any:
    return json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))


def disclosures(sd_jwt: str) -> dict[str, Any]:
    """{claim name: value} of every disclosure in an issued SD-JWT or a presentation."""
    out: dict[str, Any] = {}
    for part in sd_jwt.split("~")[1:]:
        if not part or "." in part:  # the empty tail or a key-binding JWT
            continue
        decoded = b64url_json(part)
        if isinstance(decoded, list) and len(decoded) == 3 and isinstance(decoded[1], str):
            out[decoded[1]] = decoded[2]
    return out


def claims_for(credential: Credential) -> list[dict[str, Any]]:
    """Every claim the credential holds, for its holder: [{key, label, value, disclosable}]."""
    values = disclosures(credential.sd_jwt)
    out = [
        {
            "key": key,
            "label": LABELS[key],
            "value": display_value(key, values[key]),
            "disclosable": True,
        }
        for key in credential.disclosable
        if key in values
    ]
    out.append(
        {
            "key": "issued",
            "label": LABELS["issued"],
            "value": display_date(ist_date(credential.issued_at)),
            "disclosable": False,
        }
    )
    if credential.expires_at is not None:
        out.append(
            {
                "key": "expires",
                "label": LABELS["expires"],
                "value": display_date(ist_date(credential.expires_at)),
                "disclosable": False,
            }
        )
    return out


# ------------------------------------------------------------------ eligibility


async def _checks(session: AsyncSession, enrolment_id: uuid.UUID) -> dict[CheckType, CheckStatus]:
    rows = await session.execute(
        select(Check.type, Check.status).where(Check.enrolment_id == enrolment_id)
    )
    return {check_type: status for check_type, status in rows}


async def _active_credential(
    session: AsyncSession, enrolment_id: uuid.UUID, kind: CredentialKind
) -> Credential | None:
    return (
        await session.execute(
            select(Credential).where(
                Credential.enrolment_id == enrolment_id,
                Credential.kind == kind,
                Credential.revoked.is_(False),
            )
        )
    ).scalar_one_or_none()


async def _eligible(session: AsyncSession, enrolment: Enrolment) -> bool:
    """D44: ACTIVE, COUNTERSIGNED, no live enrolment attestation, and none revoked with a
    code that holds."""
    if enrolment.status is not EnrolmentStatus.ACTIVE:
        return False
    if enrolment.record_status is not RecordStatus.COUNTERSIGNED:
        return False
    if await _revoked_by_officer(session, enrolment.id):
        return False
    return await _active_credential(session, enrolment.id, CredentialKind.ENROLMENT) is None


# revocations that do not hold: a later upload can undo a withdrawal or a transfer (the
# enrolment comes back ACTIVE), and a dispute an officer later upheld does not block a new
# attestation (R6). Every other code holds until an officer acts again: ADMIN (an officer's
# own words), CLAIM_WITHDRAWN and the retired FLAG_CONFIRMED.
SYSTEM_RELEASES = ("ENROLMENT_WITHDRAWN", "ENROLMENT_TRANSFERRED", "STUDENT_DISPUTE")
HOLDING_CODES = ("ADMIN", "CLAIM_WITHDRAWN", "FLAG_CONFIRMED")


async def _revoked_by_officer(session: AsyncSession, enrolment_id: uuid.UUID) -> bool:
    """Whether an enrolment attestation of this enrolment was revoked with a code that
    holds; such an attestation is never issued again on its own."""
    found = await session.scalar(
        select(Credential.id)
        .where(
            Credential.enrolment_id == enrolment_id,
            Credential.kind == CredentialKind.ENROLMENT,
            Credential.revoked.is_(True),
            func.coalesce(Credential.revoked_reason, "").not_in(SYSTEM_RELEASES),
        )
        .limit(1)
    )
    return found is not None


async def eligibility(session: AsyncSession, enrolment_id: uuid.UUID) -> bool:
    """Whether an enrolment attestation may be issued for the enrolment now (D44)."""
    enrolment = await session.get(Enrolment, enrolment_id)
    if enrolment is None:
        return False
    return await _eligible(session, enrolment)


# --------------------------------------------------------------------- issuance


def _public_only(key: JWK) -> JWK:
    """The holder key as `cnf.jwk` carries it: kty, crv, x and y only."""
    public = key.export_public(as_dict=True)
    return JWK(**{k: public[k] for k in ("kty", "crv", "x", "y")})


def _org_claims(institution: Institution, programme: Programme) -> dict[str, Any]:
    return {
        "institution": {"name": institution.name, "aicte_id": institution.aicte_permanent_id},
        "programme": {"name": programme.name, "level": programme.level.value},
    }


async def _sign_and_store(
    session: AsyncSession,
    *,
    enrolment: Enrolment,
    kind: CredentialKind,
    claims: dict[str, Any],
    holder: JWK | None,
    expires_at: datetime | None,
    actor_id: uuid.UUID | None,
) -> Credential | None:
    """Sign the SD-JWT and insert the row; None when another transaction issued first.

    A clash on the status-list index or the short id draws both again and re-signs, since
    the index is inside the signed payload.
    """
    key = await keys.active_issuer_key(session)
    vct = ENROLMENT_VCT if kind is CredentialKind.ENROLMENT else COMPLETION_VCT
    order = [k for k in disclosable_for(kind) if k in claims]
    for _ in range(_ATTEMPTS):
        now = datetime.now(UTC)
        index = await status_list.allocate_index(session)
        payload: dict[Any, Any] = {"iss": get_settings().issuer_url, "iat": int(now.timestamp())}
        if expires_at is not None:
            payload["exp"] = int(expires_at.timestamp())
        payload["vct"] = vct
        payload["status"] = {"status_list": {"idx": index, "uri": status_list.uri()}}
        payload.update({SDObj(k): claims[k] for k in order})
        issued = SDJWTIssuer(
            payload,
            key.jwk,
            holder_key=holder,
            sign_alg=keys.ALG,
            add_decoy_claims=False,
            extra_header_parameters={"typ": SD_JWT_TYP, "kid": key.kid},
        )
        credential = Credential(
            student_id=enrolment.student_id,
            enrolment_id=enrolment.id,
            kind=kind,
            vct=vct,
            short_id=new_short_id(),
            sd_jwt=issued.sd_jwt_issuance,
            status_list_index=index,
            disclosable=order,
            revoked=False,
            issued_at=now,
            expires_at=expires_at,
            issuer_key_id=key.kid,
        )
        try:
            async with session.begin_nested():
                session.add(credential)
                await session.flush()
        except IntegrityError as exc:
            clash = str(exc.orig)
            if "uq_credentials_enrolment_id_kind" in clash:
                return None
            if "uq_credentials_status_list_index" in clash or "uq_credentials_short_id" in clash:
                continue
            raise
        await audit.record(
            session,
            actor_id,
            AuditAction.CREATE,
            "credential",
            credential.id,
            after={
                "kind": kind.value,
                "enrolment_id": str(enrolment.id),
                "short_id": credential.short_id,
                "status_list_index": index,
            },
        )
        return credential
    raise RuntimeError("could not draw a free status-list index and short id")


async def _parts(
    session: AsyncSession, enrolment: Enrolment
) -> tuple[Student, Institution, Programme]:
    student = await session.get(Student, enrolment.student_id)
    institution = await session.get(Institution, enrolment.institution_id)
    programme = await session.get(Programme, enrolment.programme_id)
    assert student is not None and institution is not None and programme is not None
    return student, institution, programme


async def _lock(session: AsyncSession, enrolment_id: uuid.UUID) -> Enrolment | None:
    return (
        await session.execute(
            select(Enrolment)
            .where(Enrolment.id == enrolment_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def issue_if_eligible(session: AsyncSession, enrolment_id: uuid.UUID) -> Credential | None:
    """The enrolment attestation, issued in the caller's transaction when the enrolment is
    eligible; None otherwise (never raises for an ineligible enrolment). Flushes only.

    The `countersigned` claim lists the rows CONFIRMED at issue, in row order."""
    enrolment = await _lock(session, enrolment_id)
    if enrolment is None:
        return None
    if not await _eligible(session, enrolment):
        return None
    checks = await _checks(session, enrolment.id)
    student, institution, programme = await _parts(session, enrolment)
    holder = await keys.holder_key(session, student.id, create=True)
    assert holder is not None
    now = datetime.now(UTC)
    claims: dict[str, Any] = {"name": student.name, "dob": student.dob.isoformat()}
    if student.apaar_last4:
        claims["apaar_masked"] = mask_apaar(student.apaar_last4)
    claims.update(_org_claims(institution, programme))
    claims["academic_year"] = enrolment.academic_year
    claims["year_of_study"] = enrolment.year_of_study
    claims["countersigned"] = {
        "checks": [t.value for t in CHECK_ORDER if checks.get(t) is CheckStatus.CONFIRMED],
        "on": ist_date(now).isoformat(),
    }
    return await _sign_and_store(
        session,
        enrolment=enrolment,
        kind=CredentialKind.ENROLMENT,
        claims=claims,
        holder=_public_only(holder),
        expires_at=enrolment_expiry(enrolment.academic_year),
        actor_id=None,
    )


def not_graduated() -> ApiError:
    return ApiError(
        409,
        "CREDENTIAL_NOT_ELIGIBLE",
        "Completion attestations are issued only for graduated students.",
        {"reason": "NOT_GRADUATED"},
    )


async def issue_degree(
    session: AsyncSession, enrolment_id: uuid.UUID, *, actor_id: uuid.UUID
) -> tuple[Credential, bool]:
    """(the active completion attestation, whether it was made now), for the awarding
    body's certificate (D44). A revoked earlier one does not block a new one. 409
    CREDENTIAL_NOT_ELIGIBLE NOT_GRADUATED for any other status."""
    enrolment = await _lock(session, enrolment_id)
    if enrolment is None:
        raise ApiError(404, "NOT_FOUND", "Enrolment not found.")
    if enrolment.status is not EnrolmentStatus.GRADUATED:
        raise not_graduated()
    existing = await _active_credential(session, enrolment.id, CredentialKind.COMPLETION)
    if existing is not None:
        return existing, False
    student, institution, programme = await _parts(session, enrolment)
    university = (
        await session.get(University, institution.university_id)
        if institution.university_id
        else None
    )
    if university is None:
        raise ApiError(
            409,
            "CONFLICT",
            "This institution is not affiliated to a university.",
            {"reason": "NO_UNIVERSITY"},
        )
    claims: dict[str, Any] = {"name": student.name}
    if student.apaar_last4:
        claims["apaar_masked"] = mask_apaar(student.apaar_last4)
    claims.update(_org_claims(institution, programme))
    claims["university"] = {"name": university.name, "code": university.code}
    claims["year_of_award"] = year_end(enrolment.academic_year)
    credential = await _sign_and_store(
        session,
        enrolment=enrolment,
        kind=CredentialKind.COMPLETION,
        claims=claims,
        holder=None,
        expires_at=None,
        actor_id=actor_id,
    )
    if credential is None:  # issued by a concurrent request a moment ago
        winner = await _active_credential(session, enrolment.id, CredentialKind.COMPLETION)
        assert winner is not None
        return winner, False
    return credential, True


# ------------------------------------------------------------------- revocation


async def revoke(
    session: AsyncSession, credential: Credential, *, reason: str, actor_id: uuid.UUID
) -> None:
    """An officer's revocation with their own words as the reason (code ADMIN). The
    reason text stays out of the audit log. 409 CREDENTIAL_REVOKED when already revoked."""
    await session.refresh(credential, with_for_update=True)
    if credential.revoked:
        raise ApiError(
            409,
            "CREDENTIAL_REVOKED",
            "This attestation is already revoked.",
            {"revoked_at": iso(credential.revoked_at)},
        )
    credential.revoked = True
    credential.revoked_at = datetime.now(UTC)
    credential.revoked_reason = reason
    credential.revoked_by_id = actor_id
    await session.flush()
    await audit.record(
        session,
        actor_id,
        AuditAction.UPDATE,
        "credential",
        credential.id,
        before={"revoked": False},
        after={"revoked": True, "reason_code": ADMIN_REASON},
    )
    status_list.invalidate_after_commit(session)
