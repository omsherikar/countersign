"""The public verifier (D27, D28; API_CONTRACT A3.20).

Every answer is checked the way a third party would check it: the issuer key comes from
the same JWKS document /.well-known/jwks.json serves, and the revocation bit from the same
status-list token /status-lists/1 serves. The answer names only what the presentation
disclosed, never says why a proof was revoked, and there is no search: a proof is reached
only through a code, a pasted presentation, a degree QR or a printed proof id.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS
from sd_jwt.verifier import SDJWTVerifier
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit, crypto
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.errors import ApiError
from app.credentials import degree, holder, issuer, keys, status_list
from app.credentials.issuer import iso
from app.models.credential import Credential, CredentialPresentation
from app.models.enums import AuditAction, CredentialKind
from app.models.geo import University

VALID = "VALID"
REVOKED = "REVOKED"
EXPIRED = "EXPIRED"
INVALID = "INVALID"
SIGNATURE = "signature"
REGISTER_LOOKUP = "register_lookup"


class Invalid(Exception):
    """Anything cryptographic failed, or the input could not be read."""


def presentation_not_found() -> ApiError:
    return ApiError(404, "PRESENTATION_NOT_FOUND", "This code is not a Countersign proof.")


def ip_hash(ip: str) -> str:
    """First 16 hex characters of HMAC-SHA256(PII_HMAC_KEY, client address)."""
    return crypto.hmac_id(ip)[:16]


def _b64url_hash(text: str) -> str:
    return status_list.b64url(hashlib.sha256(text.encode("ascii")).digest())


def key_callback(document: dict[str, Any]) -> Callable[[str, dict[str, Any]], JWK]:
    """The issuer-key lookup given to SDJWTVerifier: Countersign's issuer only, by kid,
    from a JWKS document."""
    expected_issuer = get_settings().issuer_url

    def callback(iss: str, header: dict[str, Any]) -> JWK:
        if iss != expected_issuer:
            raise Invalid("not issued by Countersign")
        if header.get("alg") != keys.ALG:
            raise Invalid("unexpected algorithm")
        key = keys.key_in(document, header.get("kid"))
        if key is None:
            raise Invalid("unknown kid")
        return key

    return callback


@dataclass(slots=True)
class Checked:
    """What a presentation check established."""

    payload: dict[str, Any] | None = None  # set once the issuer signature verified
    valid: bool = False  # every cryptographic check passed
    disclosed: dict[str, Any] = field(default_factory=dict)
    kb: dict[str, Any] | None = None  # the key-binding claims, when there is one

    @property
    def kind(self) -> CredentialKind | None:
        return issuer.kind_of(self.payload.get("vct")) if self.payload else None

    @property
    def status_index(self) -> int | None:
        try:
            index = self.payload["status"]["status_list"]["idx"]  # type: ignore[index]
        except (KeyError, TypeError):
            return None
        return index if isinstance(index, int) and 0 <= index < status_list.SIZE else None


def unverified_kb(presentation: str) -> dict[str, Any] | None:
    """The key-binding JWT's claims, read without checking them, or None when absent."""
    tail = presentation.rsplit("~", 1)[-1]
    if not tail:
        return None
    try:
        claims = issuer.b64url_json(tail.split(".")[1])
    except (ValueError, IndexError):
        raise Invalid("unreadable key-binding JWT") from None
    if not isinstance(claims, dict):
        raise Invalid("unreadable key-binding JWT")
    return claims


def check(
    presentation: str, document: dict[str, Any], *, nonce: str | None, aud: str | None
) -> Checked:
    """Check a compact SD-JWT presentation against a JWKS document.

    The issuer signature first (so a failure later still knows which credential it was),
    then the key binding against `cnf` with the expected nonce and audience, then that
    every disclosure is one the issuer signed. A holder-bound proof without key binding,
    or key binding on a proof that is not holder-bound, is invalid.
    """
    out = Checked()
    callback = key_callback(document)
    try:
        issuer_only = SDJWTVerifier(presentation, callback)
        signed_jwt = presentation.split("~", 1)[0]
        out.payload = issuer.b64url_json(signed_jwt.split(".")[1])
        if not isinstance(out.payload, dict) or out.kind is None:
            out.payload = None
            raise Invalid("not a Countersign proof")
        kb_claims = unverified_kb(presentation)
        bound = "cnf" in out.payload
        if bound != (kb_claims is not None):
            raise Invalid("key binding missing or unexpected")
        if bound:
            if not (nonce and aud):
                raise Invalid("no nonce or audience to check")
            SDJWTVerifier(presentation, callback, expected_aud=aud, expected_nonce=nonce)
            out.kb = kb_claims
        claims = issuer_only.get_verified_payload()
    except Exception:  # Invalid, and the library's jwcrypto and ValueError failures alike
        return out

    signed_digests = set(out.payload.get("_sd", []))
    parts = presentation.split("~")[1:]
    if out.kb is not None:
        parts = parts[:-1]
    shown = issuer.disclosures(presentation)
    for part in parts:
        if part and _b64url_hash(part) not in signed_digests:
            return out  # a disclosure the issuer never signed
    order = issuer.disclosable_for(out.kind)  # type: ignore[arg-type]
    out.disclosed = {key: claims[key] for key in order if key in shown and key in claims}
    out.valid = out.status_index is not None
    return out


def _fields(disclosed: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"key": key, "label": issuer.LABELS[key], "value": issuer.display_value(key, value)}
        for key, value in disclosed.items()
    ]


def answer(
    result: str,
    *,
    method: str = SIGNATURE,
    kind: CredentialKind | None = None,
    issued_at: str | None = None,
    expires_at: str | None = None,
    revoked_at: str | None = None,
    institution_name: str | None = None,
    university_name: str | None = None,
    disclosed: list[dict[str, str]] | None = None,
    holder_bound: bool = False,
    status_checked_at: str | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    """The VerifyResult: only VALID names an institution and carries fields; INVALID says
    nothing about any credential."""
    valid = result == VALID
    invalid = result == INVALID
    return {
        "result": result,
        "kind": None if invalid or kind is None else kind.value,
        "issuer": None if invalid else issuer.issuer_ref(),
        "institution_name": institution_name if valid else None,
        "university_name": university_name if valid else None,
        "issued_at": None if invalid else issued_at,
        "expires_at": None if invalid else expires_at,
        "revoked_at": revoked_at if result == REVOKED else None,
        "disclosed": (disclosed or []) if valid else [],
        "holder_bound": False if invalid else holder_bound,
        "status_checked_at": None if invalid else status_checked_at,
        "method": method,
        "nonce": nonce,
    }


def _timestamp(value: Any) -> datetime | None:
    return datetime.fromtimestamp(value, UTC) if isinstance(value, int | float) else None


async def _read(
    session: AsyncSession, entity_type: str, entity_id: Any, *, via: str, ip: str, result: str
) -> None:
    await audit.record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.READ,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=None,
                after={"via": via, "ip_hash": ip_hash(ip), "result": result},
            )
        ],
    )


async def _count_verification(session: AsyncSession, row: CredentialPresentation) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(CredentialPresentation)
        .where(CredentialPresentation.id == row.id)
        .values(
            verify_count=CredentialPresentation.verify_count + 1,
            first_verified_at=func.coalesce(CredentialPresentation.first_verified_at, now),
            last_verified_at=now,
        )
        .execution_options(synchronize_session=False)
    )


async def _judge(
    session: AsyncSession,
    checked: Checked,
    *,
    credential: Credential | None,
    expired: bool,
    expires_at: datetime | None,
    nonce: str | None,
) -> dict[str, Any]:
    """INVALID, then REVOKED (status bit), then EXPIRED, else VALID."""
    if not checked.valid or checked.payload is None:
        return answer(INVALID, nonce=nonce)
    token = await status_list.current(session)
    kind = checked.kind
    assert kind is not None and checked.status_index is not None
    common = {
        "kind": kind,
        "issued_at": iso(_timestamp(checked.payload.get("iat"))),
        "expires_at": iso(expires_at),
        "holder_bound": checked.kb is not None,
        "status_checked_at": iso(token.iat),
        "nonce": nonce,
    }
    if status_list.bit(token.bits, checked.status_index):
        revoked_at = iso(credential.revoked_at) if credential is not None else None
        return answer(REVOKED, revoked_at=revoked_at, **common)
    if expired:
        return answer(EXPIRED, **common)
    institution = checked.disclosed.get("institution")
    university = checked.disclosed.get("university")
    return answer(
        VALID,
        institution_name=institution.get("name") if isinstance(institution, dict) else None,
        university_name=university.get("name") if isinstance(university, dict) else None,
        disclosed=_fields(checked.disclosed),
        **common,
    )


# ------------------------------------------------------------------ share codes


async def verify_code(session: AsyncSession, raw_code: str, *, ip: str) -> dict[str, Any]:
    """GET /verify/{code}: the stored presentation, with the code as the expected nonce.
    404 PRESENTATION_NOT_FOUND for a malformed or unknown code."""
    code = holder.normalise_code(raw_code)
    if code is None:
        raise presentation_not_found()
    row = (
        await session.execute(
            select(CredentialPresentation).where(
                CredentialPresentation.code_hash == holder.code_hash(code)
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise presentation_not_found()
    credential = await session.get(Credential, row.credential_id)
    checked = check(row.presentation, await keys.jwks(session), nonce=code, aud=holder.audience())
    now = datetime.now(UTC)
    exp = _timestamp(checked.payload.get("exp")) if checked.payload else None
    result = await _judge(
        session,
        checked,
        credential=credential,
        expired=row.expires_at <= now or (exp is not None and exp <= now),
        expires_at=row.expires_at,
        nonce=None,
    )
    await _count_verification(session, row)
    await _read(
        session,
        "credential_presentation",
        row.id,
        via="verifier",
        ip=ip,
        result=result["result"],
    )
    return result


async def verify_presentation(
    session: AsyncSession, presentation: str, *, ip: str
) -> dict[str, Any]:
    """POST /verify: a pasted presentation. The key binding is checked against `cnf` with
    the nonce and audience it carries, so they are reported, not enforced; a key binding
    older than a share's 10 minutes is EXPIRED."""
    text = presentation.strip()
    try:
        kb = unverified_kb(text)
    except Invalid:
        kb = None
    nonce = kb.get("nonce") if kb and isinstance(kb.get("nonce"), str) else None
    aud = kb.get("aud") if kb and isinstance(kb.get("aud"), str) else None
    checked = check(text, await keys.jwks(session), nonce=nonce, aud=aud)

    credential = None
    if checked.payload is not None and checked.status_index is not None:
        credential = (
            await session.execute(
                select(Credential).where(Credential.status_list_index == checked.status_index)
            )
        ).scalar_one_or_none()
    now = datetime.now(UTC)
    exp = _timestamp(checked.payload.get("exp")) if checked.payload else None
    bound_at = _timestamp(checked.kb.get("iat")) if checked.kb else None
    expired = (exp is not None and exp <= now) or (
        bound_at is not None and now - bound_at > holder.SHARE_TTL
    )
    result = await _judge(
        session, checked, credential=credential, expired=expired, expires_at=exp, nonce=nonce
    )

    code = holder.normalise_code(nonce) if nonce else None
    if code is not None:
        row = (
            await session.execute(
                select(CredentialPresentation).where(
                    CredentialPresentation.code_hash == holder.code_hash(code)
                )
            )
        ).scalar_one_or_none()
        if row is not None and row.presentation == text:
            await _count_verification(session, row)
    await _read(
        session,
        "credential",
        credential.id if credential is not None else None,
        via="verifier-paste",
        ip=ip,
        result=result["result"],
    )
    return result


# ---------------------------------------------------------------------- degrees


def _degree_fields(
    *,
    short_id: str,
    name: str,
    programme: str,
    institution: str,
    university: str,
    year: Any,
    id_value: str,
) -> list[dict[str, str]]:
    id_key = "apaar_masked" if id_value.startswith("XXXX") else "provisional_id"
    rows = [
        ("proof_id", short_id),
        ("name", name),
        ("programme", programme),
        ("institution", institution),
        ("university", university),
        ("year_of_award", str(year)),
    ]
    if id_value:
        rows.append((id_key, id_value))
    return [{"key": k, "label": issuer.LABELS[k], "value": v} for k, v in rows]


def read_degree_jws(jws: str, document: dict[str, Any]) -> dict[str, Any]:
    """The verified payload of a degree QR; Invalid when unreadable, unsigned by a key in
    the document, or not version 1."""
    try:
        header = issuer.b64url_json(jws.split(".")[0])
        if not isinstance(header, dict) or header.get("alg") != keys.ALG:
            raise Invalid("unexpected header")
        key = keys.key_in(document, header.get("kid"))
        if key is None:
            raise Invalid("unknown kid")
        token = JWS()
        token.deserialize(jws)
        token.verify(key, alg=keys.ALG)
        claims = json.loads(token.payload)
    except Invalid:
        raise
    except Exception as exc:
        raise Invalid("unreadable or unsigned") from exc
    if not isinstance(claims, dict) or claims.get("v") != 1:
        raise Invalid("not a version 1 degree proof")
    if not isinstance(claims.get("cid"), str):
        raise Invalid("no proof id")
    return claims


async def _degree_by_short_id(session: AsyncSession, short_id: str) -> Credential | None:
    return (
        await session.execute(
            select(Credential).where(
                Credential.short_id == short_id, Credential.kind == CredentialKind.COMPLETION
            )
        )
    ).scalar_one_or_none()


async def verify_degree_jws(session: AsyncSession, jws: str, *, ip: str) -> dict[str, Any]:
    """GET /verify/d/{jws}: the signed summary of a printed degree proof, and its status bit."""
    credential = None
    try:
        claims = read_degree_jws(jws, await keys.jwks(session))
        credential = await _degree_by_short_id(session, claims["cid"])
        if credential is None:
            raise Invalid("unknown proof id")
    except Invalid:
        result = answer(INVALID)
    else:
        token = await status_list.current(session)
        university = (
            await session.execute(select(University).where(University.code == claims.get("u")))
        ).scalar_one_or_none()
        university_name = university.name if university is not None else str(claims.get("u"))
        a = str(claims.get("a") or "")
        common = {
            "method": SIGNATURE,
            "kind": CredentialKind.COMPLETION,
            "issued_at": iso(credential.issued_at),
            "status_checked_at": iso(token.iat),
        }
        if status_list.bit(token.bits, credential.status_list_index):
            result = answer(REVOKED, revoked_at=iso(credential.revoked_at), **common)
        else:
            result = answer(
                VALID,
                institution_name=str(claims.get("i")),
                university_name=university_name,
                disclosed=_degree_fields(
                    short_id=claims["cid"],
                    name=str(claims.get("n")),
                    programme=str(claims.get("p")),
                    institution=str(claims.get("i")),
                    university=f"{university_name} ({claims.get('u')})",
                    year=claims.get("y"),
                    id_value=f"XXXX XXXX {a}" if a.isdigit() and len(a) == 4 else a,
                ),
                **common,
            )
    await _read(
        session,
        "credential",
        credential.id if credential is not None else None,
        via="degree-qr",
        ip=ip,
        result=result["result"],
    )
    return result


async def verify_degree_id(session: AsyncSession, raw_short_id: str, *, ip: str) -> dict[str, Any]:
    """GET /verify/degree/{short_id}: AICTE's own record of a degree proof, for a reader who
    has the printed proof id but cannot scan. 404 PRESENTATION_NOT_FOUND when unknown."""
    short_id = degree.normalise_short_id(raw_short_id)
    credential = await _degree_by_short_id(session, short_id) if short_id else None
    if credential is None:
        raise presentation_not_found()
    record = await degree.record_for(session, credential.enrolment_id)
    common = {
        "method": REGISTER_LOOKUP,
        "kind": CredentialKind.COMPLETION,
        "issued_at": iso(credential.issued_at),
        "status_checked_at": iso(datetime.now(UTC)),
    }
    if credential.revoked:
        result = answer(REVOKED, revoked_at=iso(credential.revoked_at), **common)
    else:
        result = answer(
            VALID,
            institution_name=record.institution.name,
            university_name=record.university.name if record.university else None,
            disclosed=_degree_fields(
                short_id=credential.short_id,
                name=record.student.name,
                programme=record.programme.name,
                institution=record.institution.name,
                university=(
                    f"{record.university.name} ({record.university.code})"
                    if record.university
                    else ""
                ),
                year=issuer.year_end(record.enrolment.academic_year),
                id_value=degree.masked_id(record.student)[1],
            ),
            **common,
        )
    await _read(
        session,
        "credential",
        credential.id,
        via="degree-lookup",
        ip=ip,
        result=result["result"],
    )
    return result
