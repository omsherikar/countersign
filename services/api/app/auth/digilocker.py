"""A student signs in through DigiLocker, and claims a record by provisional id (D36, D37).

API_CONTRACT §A4.12 and §A4.13, ENGINES §17.6. The flow is OpenID Connect's authorisation
code flow; in the demo the other side is mockgov's labelled simulator, never the real
DigiLocker.

- `start_redirect` sends the browser to DigiLocker with a fresh `state` and `nonce`, kept in
  the short-lived signed cookie `cs_dl_state` with the page to return to.
- `callback` checks the state, exchanges the code through the DigiLocker adapter (which
  verifies the id token) and finds the student: by an earlier binding of the DigiLocker
  subject, else by the APAAR on the token when a student holds it with consent LINKED. A
  person found nowhere gets the signed cookie `cs_dl_claim` (never an APAAR) and can claim a
  record without APAAR by its provisional id (`claim`): the date of birth must be equal and
  the name must reach the review threshold; the name supports the claim, the sign-in
  decides it.
- `notice_viewer` says who is looking at a notice page, so only the record's own student
  sees Yes and No.

The APAAR on a token is used in memory for the lookup only; it is never stored or logged.
One DigiLocker account binds to one student record.
"""

from __future__ import annotations

import re
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import jwt
from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterError, AdapterSet, DigiLockerIdentity
from app.auth import unusable_password_hash
from app.core import audit
from app.core.config import Settings, get_settings
from app.core.crypto import hmac_bytes
from app.core.errors import ApiError
from app.core.ratelimit import limiter
from app.core.rules import get_rules
from app.core.security import create_access_token, decode_access_token
from app.engine import checks, status
from app.engine.matching import match_names
from app.models.enums import AuditAction, CheckType, ConsentStatus, EnrolmentStatus, UserRole
from app.models.student import Enrolment, Student
from app.models.user import User
from app.models.verification import Notification

__all__ = ["DigiLockerIdentity"]

STATE_COOKIE = "cs_dl_state"  # 10 minutes
CLAIM_COOKIE = "cs_dl_claim"  # 15 minutes
STATE_MINUTES = 10
CLAIM_MINUTES = 15
CLAIM_TRIES = (5, timedelta(minutes=15))
CLAIM_LIMIT = "5/15minutes"  # per DigiLocker subject, as CLAIM_TRIES says
SIGNIN_LIMIT = "30/minute"  # start and callback, per client address

CALLBACK_PATH = "/api/auth/digilocker/callback"
RETURN_PAGE = "/auth/digilocker/return"
CLAIM_PAGE = "/student/claim"
STUDENT_HOME = "/student"
EMAIL_DOMAIN = "digilocker.invalid"
VIA = "digilocker"

# the cookies are signed with API_SECRET_KEY, like cs_access, so each carries its own `typ`
_STATE_TYP = "cs_dl_state"
_CLAIM_TYP = "cs_dl_claim"
_NEXT = re.compile(r"/student(?:[/?][A-Za-z0-9._~/?=&-]*)?")
_NOTICE_PAGE = re.compile(r"/student/notices/[A-Za-z0-9_-]{43}")
_PROVISIONAL = re.compile(r"PRV-[A-Z0-9]{8}")
_NEXT_MAX = 512

# error codes of the return page (copy deck err.*)
STATE_INVALID = "DIGILOCKER_STATE_INVALID"
CANCELLED = "DIGILOCKER_CANCELLED"
FAILED = "DIGILOCKER_FAILED"

# notice viewer matches (API_CONTRACT §A4.13)
MATCH = "MATCH"
SOMEONE_ELSE = "SOMEONE_ELSE"
CLAIM_NEEDED = "CLAIM_NEEDED"


@dataclass(frozen=True, slots=True)
class PendingClaim:
    """A DigiLocker identity that has not claimed a record yet (the `cs_dl_claim` cookie)."""

    sub: str
    name: str
    birthdate: date
    next: str


@dataclass(frozen=True, slots=True)
class SignedIn:
    user: User
    next: str


@dataclass(frozen=True, slots=True)
class NeedsClaim:
    cookie: str
    next: str
    location: str


@dataclass(frozen=True, slots=True)
class Failed:
    code: str
    next: str


CallbackOutcome = SignedIn | NeedsClaim | Failed


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    user: User
    student: Student
    enrolment_ids: list[uuid.UUID]
    next: str


# ------------------------------------------------------------------- small pieces


def safe_next(raw: str | None) -> str:
    """A path under /student to come back to, else /student. Never another site, never a
    path that climbs out of /student."""
    if not raw:
        return STUDENT_HOME
    value = raw.strip()
    if len(value) > _NEXT_MAX or not _NEXT.fullmatch(value) or "//" in value or ".." in value:
        return STUDENT_HOME
    return value


def is_notice_page(path: str) -> bool:
    return _NOTICE_PAGE.fullmatch(path) is not None


def redirect_uri(settings: Settings | None = None) -> str:
    """Where DigiLocker sends the browser back: the web's /api proxy of the callback."""
    settings = settings or get_settings()
    return f"{settings.web_origin.rstrip('/')}{CALLBACK_PATH}"


def _query(**params: str | None) -> str:
    return urlencode({k: v for k, v in params.items() if v is not None}, safe="/")


def return_location(next_path: str, error: str | None = None) -> str:
    """The web page every sign-in lands on: `/auth/digilocker/return?error=&next=`."""
    return f"{RETURN_PAGE}?{_query(error=error, next=next_path)}"


def claim_location(next_path: str) -> str:
    return f"{CLAIM_PAGE}?{_query(next=next_path)}"


def sign_in_url(next_path: str) -> str:
    """The link a page uses to start a sign-in (through the web's /api proxy)."""
    return f"/api/auth/digilocker/start?{_query(next=next_path)}"


def normalise_provisional_id(raw: str) -> str | None:
    """`PRV-` and 8 letters or digits, trimmed and upper-cased; None when it cannot be one."""
    value = (raw or "").strip().upper()
    return value if _PROVISIONAL.fullmatch(value) else None


def has_linked_apaar(student: Student) -> bool:
    """The record links to DigiLocker by APAAR on its own (D36)."""
    return student.consent_status is ConsentStatus.LINKED and student.apaar_hmac is not None


def _sign(claims: dict[str, Any], typ: str, minutes: int) -> str:
    now = int(time.time())
    payload = {**claims, "typ": typ, "iat": now, "exp": now + minutes * 60}
    return jwt.encode(payload, get_settings().api_secret_key, algorithm="HS256")


def _unsign(token: str | None, typ: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        claims = jwt.decode(
            token,
            get_settings().api_secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    return claims if claims.get("typ") == typ else None


def set_cookie(response: Response, name: str, value: str, minutes: int) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=minutes * 60,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        path="/",
    )


def clear_cookie(response: Response, name: str) -> None:
    response.set_cookie(
        key=name,
        value="",
        max_age=0,
        expires=0,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        path="/",
    )


# ------------------------------------------------------------------------- start


def start_redirect(next_path: str, settings: Settings, adapters: AdapterSet) -> tuple[str, str]:
    """(Location of DigiLocker's sign-in page, the `cs_dl_state` cookie value)."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    location = adapters.digilocker.authorize_url(
        state=state, nonce=nonce, redirect_uri=redirect_uri(settings)
    )
    cookie = _sign({"state": state, "nonce": nonce, "next": next_path}, _STATE_TYP, STATE_MINUTES)
    return location, cookie


def _read_state(cookie: str | None) -> dict[str, Any] | None:
    claims = _unsign(cookie, _STATE_TYP)
    if claims is None:
        return None
    if not all(isinstance(claims.get(k), str) for k in ("state", "nonce", "next")):
        return None
    return claims


# ---------------------------------------------------------------------- callback


async def _user_by_sub(session: AsyncSession, sub: str) -> User | None:
    return (
        await session.execute(select(User).where(User.digilocker_sub == sub))
    ).scalar_one_or_none()


async def _student_user(session: AsyncSession, student_id: uuid.UUID) -> User | None:
    """The student's own STUDENT account, the oldest when there are several."""
    return (
        (
            await session.execute(
                select(User)
                .where(User.role == UserRole.STUDENT, User.student_id == student_id)
                .order_by(User.created_at, User.id)
                .limit(1)
                .with_for_update(of=User)
            )
        )
        .scalars()
        .first()
    )


async def _linked_student(session: AsyncSession, apaar_id: str) -> Student | None:
    return (
        await session.execute(
            select(Student).where(
                Student.apaar_hmac == hmac_bytes(apaar_id, "apaar"),
                Student.consent_status == ConsentStatus.LINKED,
            )
        )
    ).scalar_one_or_none()


class AlreadyBound(Exception):
    """The student's account is bound to another DigiLocker subject."""


async def bind(
    session: AsyncSession,
    identity: DigiLockerIdentity,
    student: Student,
    *,
    request_id: str | None = None,
) -> User:
    """The student's STUDENT account with `digilocker_sub` set, created when there is none
    (a `@digilocker.invalid` address and no usable password). Audited: CREATE on `user` for
    a new account, UPDATE with `digilocker_bound` when an existing one is bound. Raises
    AlreadyBound when the account carries another subject."""
    user = await _student_user(session, student.id)
    if user is None:
        user = User(
            email=f"{identity.sub.lower()}@{EMAIL_DOMAIN}",
            password_hash=unusable_password_hash(),
            name=identity.name,
            role=UserRole.STUDENT,
            student_id=student.id,
            digilocker_sub=identity.sub,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        await audit.record(
            session,
            user.id,
            AuditAction.CREATE,
            "user",
            user.id,
            after={"role": UserRole.STUDENT.value, "via": VIA},
            request_id=request_id,
        )
        return user
    if user.digilocker_sub == identity.sub:
        return user
    if user.digilocker_sub is not None:
        raise AlreadyBound()
    user.digilocker_sub = identity.sub
    await session.flush()
    await audit.record(
        session,
        user.id,
        AuditAction.UPDATE,
        "user",
        user.id,
        after={"digilocker_bound": True},
        request_id=request_id,
    )
    return user


async def callback(
    session: AsyncSession,
    adapters: AdapterSet,
    *,
    code: str | None,
    state: str | None,
    error: str | None,
    state_cookie: str | None,
    request_id: str | None,
) -> CallbackOutcome:
    """Steps 1 to 6 of API_CONTRACT §A4.12; never raises for a bad request."""
    saved = _read_state(state_cookie)
    next_path = safe_next(saved["next"]) if saved else STUDENT_HOME
    if saved is None or not state or not secrets.compare_digest(state, saved["state"]):
        return Failed(STATE_INVALID, next_path)
    if error:
        return Failed(CANCELLED if error == "access_denied" else FAILED, next_path)
    if not code:
        return Failed(FAILED, next_path)
    try:
        identity = await adapters.digilocker.exchange_code(
            code=code, redirect_uri=redirect_uri(), nonce=saved["nonce"]
        )
    except AdapterError:
        return Failed(FAILED, next_path)

    user = await _user_by_sub(session, identity.sub)
    if user is not None:
        if user.role is not UserRole.STUDENT or not user.is_active:
            return Failed(FAILED, next_path)
        return SignedIn(user, next_path)
    if identity.apaar_id:
        student = await _linked_student(session, identity.apaar_id)
        if student is not None:
            try:
                user = await bind(session, identity, student, request_id=request_id)
            except AlreadyBound:
                return Failed(FAILED, next_path)
            if not user.is_active:
                return Failed(FAILED, next_path)
            return SignedIn(user, next_path)
    cookie = claim_cookie(identity, next_path)
    location = next_path if is_notice_page(next_path) else claim_location(next_path)
    return NeedsClaim(cookie, next_path, location)


async def record_sign_in(session: AsyncSession, user: User, *, request_id: str | None) -> str:
    """LOGIN in the audit chain with `via` digilocker; returns the `cs_access` token, set
    exactly as POST /auth/login sets it."""
    user.last_login_at = datetime.now(UTC)
    await audit.record(
        session,
        user.id,
        AuditAction.LOGIN,
        "user",
        user.id,
        after={"via": VIA},
        request_id=request_id,
    )
    return create_access_token(user.id, user.role.value)


# ------------------------------------------------------------------------- claim


def claim_cookie(identity: DigiLockerIdentity, next_path: str) -> str:
    """The `cs_dl_claim` value: who signed in and where to go, never the APAAR."""
    return _sign(
        {
            "sub": identity.sub,
            "name": identity.name,
            "birthdate": identity.birthdate.isoformat(),
            "next": next_path,
        },
        _CLAIM_TYP,
        CLAIM_MINUTES,
    )


def read_claim(cookie: str | None) -> PendingClaim | None:
    claims = _unsign(cookie, _CLAIM_TYP)
    if claims is None:
        return None
    try:
        return PendingClaim(
            sub=str(claims["sub"]),
            name=str(claims["name"]),
            birthdate=date.fromisoformat(str(claims["birthdate"])),
            next=safe_next(str(claims.get("next") or "")),
        )
    except (KeyError, ValueError):
        return None


def state_invalid() -> ApiError:
    return ApiError(
        401,
        STATE_INVALID,
        "This sign-in has expired or was started in another browser.",
        {},
    )


def count_claim_try(pending: PendingClaim) -> None:
    """One try against CLAIM_TRIES for the DigiLocker subject; 429 RATE_LIMITED with
    `retry_after` (seconds) once they are used up. Off when rate limits are off."""
    if not limiter.enabled:
        return
    from limits import parse

    item = parse(CLAIM_LIMIT)
    strategy = limiter.limiter
    if strategy.hit(item, "digilocker-claim", pending.sub):
        return
    reset_at = strategy.get_window_stats(item, "digilocker-claim", pending.sub).reset_time
    retry_after = max(1, int(reset_at - time.time()))
    raise ApiError(
        429,
        "RATE_LIMITED",
        "Too many requests. Try again shortly.",
        {"retry_after": retry_after},
        {"Retry-After": str(retry_after)},
    )


def _no_match() -> ApiError:
    return ApiError(
        422,
        "CLAIM_NO_MATCH",
        "This provisional ID does not match the name and date of birth on your DigiLocker.",
        {},
    )


def _not_needed() -> ApiError:
    return ApiError(
        409,
        "CLAIM_NOT_NEEDED",
        "This record has an APAAR, so it links to DigiLocker on its own.",
        {},
    )


def _already_claimed() -> ApiError:
    return ApiError(
        409,
        "CLAIM_ALREADY_CLAIMED",
        "This record is already claimed through another DigiLocker sign-in.",
        {},
    )


def names_match(record_name: str, digilocker_name: str) -> bool:
    """The name supports the claim when it reaches the review threshold (75)."""
    threshold = get_rules().name_matching.review_threshold
    return match_names(record_name, digilocker_name).score >= threshold


async def active_enrolment_ids(session: AsyncSession, student_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await session.execute(
                select(Enrolment.id)
                .where(
                    Enrolment.student_id == student_id,
                    Enrolment.status == EnrolmentStatus.ACTIVE,
                )
                .order_by(Enrolment.academic_year, Enrolment.id)
            )
        ).scalars()
    )


async def recheck_identity(
    session: AsyncSession,
    enrolment_ids: list[uuid.UUID],
    adapters: AdapterSet | None,
    *,
    actor_id: uuid.UUID | None,
) -> None:
    """The IDENTITY row of each record again, now that a DigiLocker claim binds it (its
    basis becomes DIGILOCKER_CLAIM, ENGINES §17.3), and the records queued for their status."""
    if enrolment_ids:
        await checks.rerun(
            session, enrolment_ids, adapters, types=[CheckType.IDENTITY], actor_id=actor_id
        )
    status.mark(session, enrolment_ids)


async def claim(
    session: AsyncSession,
    pending: PendingClaim,
    provisional_id: str,
    *,
    adapters: AdapterSet | None,
    request_id: str | None = None,
) -> ClaimOutcome:
    """Steps 1 to 3 of API_CONTRACT §A4.12, then the binding, in the caller's transaction.

    `provisional_id` is already normalised. Steps 2 and 3 answer only after step 1 matched,
    so nobody learns which ids exist.
    """
    student = (
        await session.execute(
            select(Student).where(Student.provisional_id == provisional_id).with_for_update()
        )
    ).scalar_one_or_none()
    if (
        student is None
        or student.dob != pending.birthdate
        or not names_match(student.name, pending.name)
    ):
        raise _no_match()
    if has_linked_apaar(student):
        raise _not_needed()
    holder = await _user_by_sub(session, pending.sub)
    if holder is not None and holder.student_id != student.id:
        raise _already_claimed()
    identity = DigiLockerIdentity(sub=pending.sub, name=pending.name, birthdate=pending.birthdate)
    try:
        user = await bind(session, identity, student, request_id=request_id)
    except AlreadyBound:
        raise _already_claimed() from None
    if not user.is_active:
        raise _already_claimed()
    enrolment_ids = await active_enrolment_ids(session, student.id)
    await recheck_identity(session, enrolment_ids, adapters, actor_id=user.id)
    await audit.record(
        session,
        user.id,
        AuditAction.UPDATE,
        "student",
        student.id,
        after={"claimed_via": VIA, "enrolments": len(enrolment_ids)},
        request_id=request_id,
    )
    return ClaimOutcome(user=user, student=student, enrolment_ids=enrolment_ids, next=pending.next)


async def is_claimed(session: AsyncSession, student: Student) -> bool:
    """A record without a linked APAAR that a DigiLocker sign-in has claimed."""
    if has_linked_apaar(student):
        return False
    bound = await session.scalar(
        select(User.id)
        .where(
            User.role == UserRole.STUDENT,
            User.student_id == student.id,
            User.digilocker_sub.is_not(None),
        )
        .limit(1)
    )
    return bound is not None


# ------------------------------------------------------------------ who is looking


async def session_user(session: AsyncSession, token: str | None) -> User | None:
    """The signed-in user behind a `cs_access` cookie, or None; never raises."""
    claims = decode_access_token(token) if token else None
    if not claims or "sub" not in claims:
        return None
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError:
        return None
    user = await session.get(User, user_id)
    return user if user is not None and user.is_active else None


async def notice_viewer(
    session: AsyncSession, notice: Notification, user: User | None, pending: PendingClaim | None
) -> dict[str, Any]:
    """`{"signed_in", "name", "match"}` for GET /notices/{token} (API_CONTRACT §A4.13).

    `name` is what DigiLocker returned for the person looking, never the record's name, and
    null for anyone who is not a student.
    """
    if user is not None:
        if user.role is UserRole.STUDENT:
            match = MATCH if user.student_id == notice.student_id else SOMEONE_ELSE
            return {"signed_in": True, "name": user.name, "match": match}
        return {"signed_in": True, "name": None, "match": SOMEONE_ELSE}
    if pending is None:
        return {"signed_in": False, "name": None, "match": None}
    student = await session.get(Student, notice.student_id)
    assert student is not None
    if has_linked_apaar(student) or await is_claimed(session, student):
        return {"signed_in": True, "name": pending.name, "match": SOMEONE_ELSE}
    return {"signed_in": True, "name": pending.name, "match": CLAIM_NEEDED}
