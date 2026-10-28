"""The student's wallet: proofs, shares and presentations (D26, API_CONTRACT A3.16, A3.17).

A share is an SD-JWT presentation made on the server from the custodial holder key: the
chosen disclosures plus a key-binding JWT whose nonce is a one-time share code and whose
audience is `{ISSUER_URL}/verify`, so a copied presentation cannot be replayed under
another code. Only the hash of the code is stored, and a share lives for 10 minutes.
"""

from __future__ import annotations

import hashlib
import io
import re
import secrets
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import segno
from sd_jwt.holder import SDJWTHolder
from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import AuditEntry
from app.core.config import get_settings
from app.core.errors import ApiError
from app.credentials import issuer, keys
from app.credentials.issuer import display_date, iso, ist_date
from app.models.credential import Credential, CredentialPresentation
from app.models.enums import (
    AuditAction,
    ConsentPurpose,
    ConsentState,
    CredentialKind,
    UserRole,
)
from app.models.geo import University
from app.models.institution import Institution, Programme
from app.models.student import Enrolment
from app.models.user import User
from app.privacy import service as privacy
from app.privacy.notice import consent_text
from app.schemas.common import Page, PageParams

SHARE_TTL = timedelta(minutes=10)
CODE_LENGTH = 24
GROUP = 4
RECENT_SHARES = 5
CONSENT_CHANNEL = "PORTAL"
# copy deck §9 consent.credential_share, stored verbatim with every share
SHARE_CONSENT_TEXT = consent_text(ConsentPurpose.CREDENTIAL_SHARE)
_SPACES_AND_HYPHENS = re.compile(r"[\s-]+")
_LOOKALIKES = str.maketrans({"O": "0", "I": "1", "L": "1"})


@dataclass(frozen=True, slots=True)
class CredentialFilters:
    """AICTE_ADMIN's filters on GET /credentials; a student's are ignored."""

    student_id: uuid.UUID | None = None
    enrolment_id: uuid.UUID | None = None
    kind: CredentialKind | None = None
    status: str | None = None  # ACTIVE, REVOKED or EXPIRED


# ------------------------------------------------------------------- share codes


def new_code() -> str:
    """120 random bits as six groups of four Crockford base32 characters."""
    raw = "".join(secrets.choice(issuer.CROCKFORD) for _ in range(CODE_LENGTH))
    return _group(raw)


def _group(raw: str) -> str:
    return "-".join(raw[i : i + GROUP] for i in range(0, len(raw), GROUP))


def normalise_code(raw: str) -> str | None:
    """The six-group form of a typed code, or None when it cannot be one.

    Trim, upper case, drop spaces and hyphens, read O as 0 and I and L as 1, then require
    exactly 24 characters of the alphabet.
    """
    if not isinstance(raw, str):
        return None
    text = _SPACES_AND_HYPHENS.sub("", raw.strip().upper()).translate(_LOOKALIKES)
    if len(text) != CODE_LENGTH or any(c not in issuer.CROCKFORD for c in text):
        return None
    return _group(text)


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("ascii")).hexdigest()


def audience() -> str:
    return f"{get_settings().issuer_url}/verify"


def share_url(code: str) -> str:
    return f"{get_settings().web_origin}/verify/{code}"


def qr_svg(url: str) -> str:
    """Black on white, error correction M, quiet zone 4, a viewBox, no size and no XML
    declaration, so the web can insert it as markup."""
    qr = segno.make(url, error="m", boost_error=False)
    out = io.BytesIO()
    qr.save(
        out,
        kind="svg",
        xmldecl=False,
        svgns=True,
        omitsize=True,
        border=4,
        dark="#000",
        light="#fff",
        nl=False,
    )
    return out.getvalue().decode("utf-8")


# ------------------------------------------------------------------------ share


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


async def present(
    session: AsyncSession,
    credential: Credential,
    user: User,
    *,
    fields: Sequence[str],
    consent: bool = True,
) -> dict[str, Any]:
    """Create a share of the chosen fields (institution and programme always go too).

    Answers in the contract's order: a revoked or expired proof first (409), then unknown
    fields and missing consent together (422).
    """
    now = datetime.now(UTC)
    status = issuer.status_of(credential, now)
    if status == "REVOKED":
        assert credential.revoked_at is not None
        raise ApiError(
            409,
            "CREDENTIAL_REVOKED",
            f"This proof was revoked on {display_date(ist_date(credential.revoked_at))} "
            "and cannot be shared.",
            {"revoked_at": iso(credential.revoked_at)},
        )
    if status == "EXPIRED":
        assert credential.expires_at is not None
        raise ApiError(
            409,
            "CREDENTIAL_NOT_ELIGIBLE",
            f"This proof expired on {display_date(ist_date(credential.expires_at))} "
            "and cannot be shared.",
            {"reason": "EXPIRED"},
        )
    errors = [
        _field_error("fields", f"Unknown field: {key}.")
        for key in dict.fromkeys(fields)
        if key not in credential.disclosable
    ]
    if consent is not True:
        errors.append(_field_error("consent", "Agree to the share text to create a proof."))
    if errors:
        first = errors[0]
        message = first["message"]
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"{first['field']}: {message[:1].lower()}{message[1:]}",
            {"fields": errors},
        )

    chosen = set(fields) | set(issuer.ALWAYS_DISCLOSED)
    disclosed = [key for key in credential.disclosable if key in chosen]
    code = new_code()
    holder = SDJWTHolder(credential.sd_jwt)
    if issuer.holder_bound(credential):
        holder_key = await keys.holder_key(session, credential.student_id, create=False)
        if holder_key is None:
            raise RuntimeError("an enrolment proof without its holder key")
        holder.create_presentation(
            {key: True for key in disclosed},
            nonce=code,
            aud=audience(),
            holder_key=holder_key,
            sign_alg=keys.ALG,
        )
    else:
        holder.create_presentation({key: True for key in disclosed})
    row = CredentialPresentation(
        credential_id=credential.id,
        code_hash=code_hash(code),
        presentation=holder.sd_jwt_presentation,
        disclosed=disclosed,
        created_at=now,
        expires_at=now + SHARE_TTL,
        verify_count=0,
    )
    session.add(row)
    await session.flush()
    await privacy.record_consent(
        session,
        student_id=credential.student_id,
        purpose=ConsentPurpose.CREDENTIAL_SHARE,
        status=ConsentState.GIVEN,
        channel=CONSENT_CHANNEL,
        notice_text=SHARE_CONSENT_TEXT,
        actor_id=user.id,
    )
    await audit.record_many(
        session,
        [
            AuditEntry(
                action=AuditAction.CREATE,
                entity_type="credential_presentation",
                entity_id=row.id,
                actor_id=user.id,
                after={
                    "credential_id": str(credential.id),
                    "disclosed": disclosed,
                    "expires_at": iso(row.expires_at),
                },
            ),
            AuditEntry(
                action=AuditAction.READ,
                entity_type="credential",
                entity_id=credential.id,
                actor_id=user.id,
                after={"via": "share", "presentation_id": str(row.id)},
            ),
        ],
    )
    url = share_url(code)
    return {
        "id": str(row.id),
        "code": code,
        "url": url,
        "qr_svg": qr_svg(url),
        "expires_at": iso(row.expires_at),
        "disclosed": disclosed,
        "total": len(credential.disclosable),
    }


# ------------------------------------------------------------------- the wallet


def _status_clause(status: str, now: datetime) -> Any:
    if status == "REVOKED":
        return Credential.revoked.is_(True)
    expired = and_(Credential.expires_at.is_not(None), Credential.expires_at <= now)
    if status == "EXPIRED":
        return and_(Credential.revoked.is_(False), expired)
    return and_(Credential.revoked.is_(False), or_(Credential.expires_at.is_(None), ~expired))


def _card_query() -> Select:
    return (
        select(Credential, Enrolment.academic_year, Institution.name, Programme.name, University)
        .join(Enrolment, Enrolment.id == Credential.enrolment_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .outerjoin(University, University.id == Institution.university_id)
    )


def _presentation_brief(p: CredentialPresentation) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "created_at": iso(p.created_at),
        "expires_at": iso(p.expires_at),
        "disclosed": list(p.disclosed),
        "verify_count": p.verify_count,
        "last_verified_at": iso(p.last_verified_at),
    }


async def _share_stats(
    session: AsyncSession, credential_ids: Sequence[uuid.UUID]
) -> tuple[dict[uuid.UUID, tuple[int, datetime | None]], dict[uuid.UUID, list[dict[str, Any]]]]:
    """Per credential: (shares, latest verification) and the most recent shares."""
    if not credential_ids:
        return {}, {}
    totals = {
        credential_id: (count, last)
        for credential_id, count, last in await session.execute(
            select(
                CredentialPresentation.credential_id,
                func.count(),
                func.max(CredentialPresentation.last_verified_at),
            )
            .where(CredentialPresentation.credential_id.in_(credential_ids))
            .group_by(CredentialPresentation.credential_id)
        )
    }
    ranked = (
        select(
            CredentialPresentation.id,
            func.row_number()
            .over(
                partition_by=CredentialPresentation.credential_id,
                order_by=(
                    CredentialPresentation.created_at.desc(),
                    CredentialPresentation.id.desc(),
                ),
            )
            .label("rank"),
        )
        .where(CredentialPresentation.credential_id.in_(credential_ids))
        .subquery()
    )
    recent: dict[uuid.UUID, list[dict[str, Any]]] = defaultdict(list)
    rows = await session.execute(
        select(CredentialPresentation)
        .join(ranked, ranked.c.id == CredentialPresentation.id)
        .where(ranked.c.rank <= RECENT_SHARES)
        .order_by(CredentialPresentation.created_at.desc(), CredentialPresentation.id.desc())
    )
    for presentation in rows.scalars():
        recent[presentation.credential_id].append(_presentation_brief(presentation))
    return totals, recent


def _card(
    credential: Credential,
    academic_year: str,
    institution_name: str,
    programme_name: str,
    university: University | None,
    stats: tuple[int, datetime | None],
    recent: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    is_degree = credential.kind is CredentialKind.COMPLETION
    return {
        "id": str(credential.id),
        "kind": credential.kind.value,
        "status": issuer.status_of(credential, now),
        "vct": credential.vct,
        "short_id": credential.short_id,
        "issuer": issuer.issuer_ref(),
        "enrolment_id": str(credential.enrolment_id),
        "institution_name": institution_name,
        "programme_name": programme_name,
        "academic_year": academic_year,
        "university_name": university.name if is_degree and university is not None else None,
        "issued_at": iso(credential.issued_at),
        "expires_at": iso(credential.expires_at),
        "revoked_at": iso(credential.revoked_at),
        "revoked_reason_code": issuer.wire_reason_code(credential),
        "revoked_reason": credential.revoked_reason if credential.revoked else None,
        "holder_bound": issuer.holder_bound(credential),
        "disclosable": [
            {
                "key": key,
                "label": issuer.LABELS[key],
                "always": key in issuer.ALWAYS_DISCLOSED,
            }
            for key in credential.disclosable
        ],
        "shares": stats[0],
        "last_verified_at": iso(stats[1]),
        "presentations": recent,
    }


async def _cards(session: AsyncSession, stmt: Select) -> list[dict[str, Any]]:
    rows = (await session.execute(stmt)).all()
    totals, recent = await _share_stats(session, [row[0].id for row in rows])
    now = datetime.now(UTC)
    return [
        _card(
            credential,
            year,
            institution_name,
            programme_name,
            university,
            totals.get(credential.id, (0, None)),
            recent.get(credential.id, []),
            now,
        )
        for credential, year, institution_name, programme_name, university in rows
    ]


async def cards(
    session: AsyncSession, user: User, *, filters: CredentialFilters, page: PageParams
) -> Page:
    """GET /credentials: a student's own proofs, or any for AICTE_ADMIN with filters.
    Writes a READ audit entry per proof returned."""
    stmt = _card_query()
    if user.role is UserRole.STUDENT:
        stmt = stmt.where(Credential.student_id == user.student_id)
    else:
        if filters.student_id is not None:
            stmt = stmt.where(Credential.student_id == filters.student_id)
        if filters.enrolment_id is not None:
            stmt = stmt.where(Credential.enrolment_id == filters.enrolment_id)
        if filters.kind is not None:
            stmt = stmt.where(Credential.kind == filters.kind)
        if filters.status is not None:
            stmt = stmt.where(_status_clause(filters.status, datetime.now(UTC)))
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    items = await _cards(
        session,
        stmt.order_by(Credential.issued_at.desc(), Credential.id.desc())
        .offset(page.offset)
        .limit(page.page_size),
    )
    await audit.record_read(session, user.id, "credential", [uuid.UUID(c["id"]) for c in items])
    return Page[dict[str, Any]](items=items, total=total, page=page.page, page_size=page.page_size)


async def card(session: AsyncSession, credential: Credential) -> dict[str, Any]:
    [one] = await _cards(session, _card_query().where(Credential.id == credential.id))
    return one


async def detail(session: AsyncSession, credential: Credential) -> dict[str, Any]:
    """The card plus every claim the proof holds, for its holder to read."""
    return {**await card(session, credential), "claims": issuer.claims_for(credential)}


async def presentations(session: AsyncSession, credential: Credential, page: PageParams) -> Page:
    """Every share of the proof, newest first; never the code or the presentation."""
    base = select(CredentialPresentation).where(
        CredentialPresentation.credential_id == credential.id
    )
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                base.order_by(
                    CredentialPresentation.created_at.desc(), CredentialPresentation.id.desc()
                )
                .offset(page.offset)
                .limit(page.page_size)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    items = [
        {
            "id": str(p.id),
            "created_at": iso(p.created_at),
            "expires_at": iso(p.expires_at),
            "state": "LIVE" if p.expires_at > now else "EXPIRED",
            "disclosed": list(p.disclosed),
            "verify_count": p.verify_count,
            "first_verified_at": iso(p.first_verified_at),
            "last_verified_at": iso(p.last_verified_at),
        }
        for p in rows
    ]
    return Page[dict[str, Any]](items=items, total=total, page=page.page, page_size=page.page_size)


async def expire_live_presentations(
    session: AsyncSession, student_id: uuid.UUID, *, now: datetime
) -> int:
    """Expire every live share of the student's proofs at `now`; returns how many.
    Called when the student withdraws consent to share. Flushes only."""
    result = await session.execute(
        update(CredentialPresentation)
        .where(
            CredentialPresentation.credential_id.in_(
                select(Credential.id).where(Credential.student_id == student_id)
            ),
            CredentialPresentation.expires_at > now,
        )
        .values(expires_at=now)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount or 0


async def wallet_summary(session: AsyncSession, student_id: uuid.UUID) -> list[dict[str, Any]]:
    """The student's proofs for GET /students/me, newest first."""
    rows = await session.execute(
        select(Credential, Institution.name)
        .join(Enrolment, Enrolment.id == Credential.enrolment_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .where(Credential.student_id == student_id)
        .order_by(Credential.issued_at.desc(), Credential.id.desc())
    )
    now = datetime.now(UTC)
    return [
        {
            "id": str(credential.id),
            "kind": credential.kind.value,
            "status": issuer.status_of(credential, now),
            "enrolment_id": str(credential.enrolment_id),
            "institution_name": institution_name,
            "issued_at": iso(credential.issued_at),
        }
        for credential, institution_name in rows
    ]


async def credential_refs(session: AsyncSession, enrolment_id: uuid.UUID) -> list[dict[str, Any]]:
    """Every proof issued for one enrolment, newest first, for enrolment detail."""
    rows = (
        (
            await session.execute(
                select(Credential)
                .where(Credential.enrolment_id == enrolment_id)
                .order_by(Credential.issued_at.desc(), Credential.id.desc())
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    return [
        {
            "id": str(credential.id),
            "kind": credential.kind.value,
            "status": issuer.status_of(credential, now),
            "short_id": credential.short_id,
            "issued_at": iso(credential.issued_at),
            "revoked_at": iso(credential.revoked_at),
            "revoked_reason_code": issuer.wire_reason_code(credential),
            "revoked_reason": credential.revoked_reason if credential.revoked else None,
        }
        for credential in rows
    ]
