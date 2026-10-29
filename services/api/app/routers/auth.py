"""Sign-in (API_CONTRACT A.2 to A.4, §A4.12).

Officers, registrars and universities sign in with email and password. A student signs in
only through DigiLocker (D37): `GET /auth/digilocker/start` and `/callback` run the
OpenID Connect code flow against the DigiLocker adapter (in the demo, mockgov's labelled
simulator), and a person whose record has no APAAR claims it by provisional id with
`POST /auth/digilocker/claim`. Every sign-in ends with the same `cs_access` cookie.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.adapters.base import AdapterError
from app.auth import digilocker
from app.auth.digilocker import CLAIM_COOKIE, STATE_COOKIE, Failed, NeedsClaim
from app.core import audit
from app.core.config import get_settings
from app.core.deps import Adapters, CurrentUser, RequestId, SessionDep
from app.core.errors import ApiError
from app.core.ratelimit import limiter, login_limit
from app.core.security import (
    COOKIE_NAME,
    clear_auth_cookie,
    create_access_token,
    decode_access_token,
    set_auth_cookie,
    verify_password,
)
from app.engine import status as record_status
from app.models.enums import AuditAction, UserRole
from app.models.institution import Institution
from app.models.user import User
from app.notices.records import student_enrolments
from app.schemas.auth import (
    ClaimedRecords,
    ClaimRequest,
    ClaimResult,
    LoginRequest,
    PendingClaimOut,
    UserEnvelope,
    UserOut,
)
from app.schemas.students import StudentEnrolment

router = APIRouter(tags=["auth"])

INVALID_CREDENTIALS = "Email or password is incorrect."
PROVISIONAL_FORMAT = "A provisional ID is PRV- followed by 8 letters and digits."


@router.post("/auth/login", response_model=UserEnvelope)
@limiter.limit(login_limit)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: SessionDep,
    request_id: RequestId,
) -> UserEnvelope:
    stmt = (
        select(User)
        .where(User.email == body.email)
        .options(selectinload(User.institution).selectinload(Institution.region))
    )
    user = (await session.execute(stmt)).unique().scalar_one_or_none()
    # a student signs in only through DigiLocker: the same answer as a wrong password
    if (
        user is None
        or not user.is_active
        or user.role is UserRole.STUDENT
        or not verify_password(body.password, user.password_hash)
    ):
        raise ApiError(401, "INVALID_CREDENTIALS", INVALID_CREDENTIALS)
    user.last_login_at = datetime.now(UTC)
    await audit.record(session, user.id, AuditAction.LOGIN, "user", user.id, request_id=request_id)
    set_auth_cookie(response, create_access_token(user.id, user.role.value))
    return UserEnvelope(user=UserOut.from_user(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: SessionDep, request_id: RequestId) -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    token = request.cookies.get(COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    if claims and claims.get("sub"):
        try:
            user = await session.get(User, uuid.UUID(str(claims["sub"])))
        except ValueError:
            user = None
        if user is not None:
            await audit.record(
                session, user.id, AuditAction.LOGOUT, "user", user.id, request_id=request_id
            )
    clear_auth_cookie(response)
    return response


@router.get("/me", response_model=UserEnvelope)
async def me(user: CurrentUser) -> UserEnvelope:
    return UserEnvelope(user=UserOut.from_user(user))


# ------------------------------------------------------------------- DigiLocker


def _redirect(location: str) -> RedirectResponse:
    return RedirectResponse(location, status_code=302, headers={"Cache-Control": "no-store"})


@router.get("/auth/digilocker/start", status_code=302, response_class=RedirectResponse)
@limiter.limit(digilocker.SIGNIN_LIMIT)
async def digilocker_start(request: Request, adapters: Adapters, next: str | None = None):
    """302 to DigiLocker's sign-in page, with `state` and `nonce` kept in `cs_dl_state`."""
    next_path = digilocker.safe_next(next)
    try:
        location, cookie = digilocker.start_redirect(next_path, get_settings(), adapters)
    except AdapterError:
        return _redirect(digilocker.return_location(next_path, digilocker.FAILED))
    response = _redirect(location)
    digilocker.set_cookie(response, STATE_COOKIE, cookie, digilocker.STATE_MINUTES)
    return response


@router.get("/auth/digilocker/callback", status_code=302, response_class=RedirectResponse)
@limiter.limit(digilocker.SIGNIN_LIMIT)
async def digilocker_callback(
    request: Request,
    session: SessionDep,
    adapters: Adapters,
    request_id: RequestId,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Always 302 and clears `cs_dl_state`: to the return page signed in, to the claim (or
    the notice page) with `cs_dl_claim`, or to the return page with the error code."""
    outcome = await digilocker.callback(
        session,
        adapters,
        code=code,
        state=state,
        error=error,
        state_cookie=request.cookies.get(STATE_COOKIE),
        request_id=request_id,
    )
    if isinstance(outcome, Failed):
        response = _redirect(digilocker.return_location(outcome.next, outcome.code))
    elif isinstance(outcome, NeedsClaim):
        response = _redirect(outcome.location)
        digilocker.set_cookie(response, CLAIM_COOKIE, outcome.cookie, digilocker.CLAIM_MINUTES)
    else:
        token = await digilocker.record_sign_in(session, outcome.user, request_id=request_id)
        response = _redirect(digilocker.return_location(outcome.next))
        set_auth_cookie(response, token)
        digilocker.clear_cookie(response, CLAIM_COOKIE)
    digilocker.clear_cookie(response, STATE_COOKIE)
    return response


def _pending(request: Request) -> digilocker.PendingClaim:
    pending = digilocker.read_claim(request.cookies.get(CLAIM_COOKIE))
    if pending is None:
        raise digilocker.state_invalid()
    return pending


@router.get("/auth/digilocker/claim", response_model=PendingClaimOut)
async def digilocker_pending_claim(request: Request) -> PendingClaimOut:
    pending = _pending(request)
    return PendingClaimOut(
        name=pending.name, birthdate=pending.birthdate.isoformat(), next=pending.next
    )


@router.post("/auth/digilocker/claim", response_model=ClaimResult)
async def digilocker_claim(
    request: Request,
    response: Response,
    body: ClaimRequest,
    session: SessionDep,
    adapters: Adapters,
    request_id: RequestId,
) -> ClaimResult:
    """Claim a record without APAAR by its provisional id (D36): the date of birth must be
    equal and the name must reach 75; then the account is bound and signed in."""
    pending = _pending(request)
    digilocker.count_claim_try(pending)
    provisional_id = digilocker.normalise_provisional_id(body.provisional_id)
    if provisional_id is None:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"provisional_id: {PROVISIONAL_FORMAT[0].lower()}{PROVISIONAL_FORMAT[1:]}",
            {"fields": [{"field": "provisional_id", "message": PROVISIONAL_FORMAT}]},
        )
    outcome = await digilocker.claim(
        session, pending, provisional_id, adapters=adapters, request_id=request_id
    )
    token = await digilocker.record_sign_in(session, outcome.user, request_id=request_id)
    # the records' statuses and any attestation, before the answer shows them
    await record_status.settle(session)
    enrolments = await student_enrolments(session, outcome.student, only=outcome.enrolment_ids)
    set_auth_cookie(response, token)
    digilocker.clear_cookie(response, CLAIM_COOKIE)
    return ClaimResult(
        user=UserOut.from_user(outcome.user),
        next=outcome.next,
        claimed=ClaimedRecords(
            student_id=str(outcome.student.id),
            enrolments=[StudentEnrolment.model_validate(e) for e in enrolments],
        ),
    )
