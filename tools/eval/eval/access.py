"""Cross-college access attempts through the api, in process (ASGI), as college users.

One INSTITUTION user per institution is created for the run (unusable password, signed in by
a minted session cookie, deactivated at the end). Each asks, for every other institution,
for the institution, its enrolment list and its completeness, and for one of its enrolments,
that enrolment's history, one of its cases and one of its uploads when it has them. Refused
means 403 or 404; anything else is a leak (2xx) or an error. Routes the api does not have
yet are skipped and listed. As a control, each user also asks for its own institution and
enrolment list, which must answer 200.
"""

from __future__ import annotations

import asyncio
import re
import secrets
import uuid
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

REFUSED = frozenset({403, 404})
CONCURRENCY = 16
EMAIL = "eval.{code}@eval.countersign.invalid"
# (template, which id of the target it needs)
FOREIGN_PATHS: tuple[tuple[str, str], ...] = (
    ("/institutions/{id}", "institution"),
    ("/institutions/{id}/enrolments", "institution"),
    ("/institutions/{id}/completeness", "institution"),
    ("/enrolments/{id}", "enrolment"),
    ("/enrolments/{id}/history", "enrolment"),
    ("/flags/{id}", "flag"),
    ("/uploads/{id}", "upload"),
)
OWN_PATHS = ("/institutions/{id}", "/institutions/{id}/enrolments")


@dataclass(frozen=True, slots=True)
class Attempt:
    requester: str  # AICTE id
    target: str
    path: str  # the template
    status: int


def summarise(
    attempts: Sequence[Attempt], controls: Sequence[Attempt], skipped: Iterable[str] = ()
) -> dict[str, Any]:
    refused = [a for a in attempts if a.status in REFUSED]
    leaks = [a for a in attempts if 200 <= a.status < 300]
    errors = [a for a in attempts if a.status not in REFUSED and not 200 <= a.status < 300]
    by_path: dict[str, dict[str, int]] = {}
    for a in attempts:
        tally = by_path.setdefault(a.path, {"attempts": 0, "refused": 0})
        tally["attempts"] += 1
        tally["refused"] += a.status in REFUSED
    return {
        "attempts": len(attempts),
        "refused": len(refused),
        "leaks": [
            {"requester": a.requester, "target": a.target, "path": a.path, "status": a.status}
            for a in leaks
        ],
        "errors": [
            {"requester": a.requester, "target": a.target, "path": a.path, "status": a.status}
            for a in errors[:20]
        ],
        "error_count": len(errors),
        "statuses": dict(sorted(Counter(str(a.status) for a in attempts).items())),
        "by_path": dict(sorted(by_path.items())),
        "skipped_paths": sorted(set(skipped)),
        "controls": {
            "attempts": len(controls),
            "ok": sum(1 for c in controls if c.status == 200),
        },
    }


def all_refused(result: dict[str, Any]) -> bool:
    return result["attempts"] > 0 and result["refused"] == result["attempts"]


def _template(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{id}", path)


def routed_paths(app: Any) -> set[str]:
    """The GET paths the api serves, with every parameter written {id}."""
    paths = app.openapi().get("paths", {})
    return {_template(p) for p, ops in paths.items() if "get" in ops}


async def _ensure_users(session: Any, institutions: dict[uuid.UUID, tuple[str, str]]) -> dict:
    from sqlalchemy import select

    from app.core import audit
    from app.core.security import hash_password
    from app.models.enums import AuditAction, UserRole
    from app.models.user import User

    emails = {EMAIL.format(code=code.lower()): inst for inst, (code, _) in institutions.items()}
    existing = {
        u.email.lower(): u
        for u in (await session.execute(select(User).where(User.email.in_(list(emails)))))
        .unique()
        .scalars()
    }
    unusable = hash_password(secrets.token_urlsafe(32))
    entries = []
    users: dict[uuid.UUID, uuid.UUID] = {}
    for email, inst in emails.items():
        user = existing.get(email)
        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=unusable,
                name=f"Evaluation user, {institutions[inst][1]}",
                role=UserRole.INSTITUTION,
                institution_id=inst,
                is_active=True,
            )
            session.add(user)
            entries.append(
                audit.AuditEntry(
                    action=AuditAction.CREATE,
                    entity_type="user",
                    entity_id=user.id,
                    actor_id=None,
                    after={"role": "INSTITUTION", "via": "eval"},
                )
            )
        elif not user.is_active:
            user.is_active = True
            entries.append(
                audit.AuditEntry(
                    action=AuditAction.UPDATE,
                    entity_type="user",
                    entity_id=user.id,
                    actor_id=None,
                    after={"is_active": True, "via": "eval"},
                )
            )
        users[inst] = user.id
    await session.flush()
    await audit.record_many(session, entries)
    return users


async def _deactivate(session: Any, user_ids: Iterable[uuid.UUID]) -> None:
    from sqlalchemy import update

    from app.core import audit
    from app.models.enums import AuditAction
    from app.models.user import User

    ids = list(user_ids)
    await session.execute(update(User).where(User.id.in_(ids)).values(is_active=False))
    await audit.record_many(
        session,
        [
            audit.AuditEntry(
                action=AuditAction.UPDATE,
                entity_type="user",
                entity_id=i,
                actor_id=None,
                after={"is_active": False, "via": "eval"},
            )
            for i in ids
        ],
    )


async def _one_of_each(session: Any) -> dict[str, dict[uuid.UUID, uuid.UUID]]:
    """For each institution: one ACTIVE enrolment, one case and one upload, when it has them."""
    from sqlalchemy import select

    from app.models.enums import EnrolmentStatus
    from app.models.student import Enrolment
    from app.models.upload import UploadBatch
    from app.models.verification import Flag

    out: dict[str, dict[uuid.UUID, uuid.UUID]] = {}
    for name, model, extra in (
        ("enrolment", Enrolment, Enrolment.status == EnrolmentStatus.ACTIVE),
        ("flag", Flag, None),
        ("upload", UploadBatch, None),
    ):
        out[name] = {}
        stmt = (
            select(model.institution_id, model.id)
            .distinct(model.institution_id)
            .order_by(model.institution_id, model.id)
        )
        if extra is not None:
            stmt = stmt.where(extra)
        for inst, item in (await session.execute(stmt)).all():
            out[name][inst] = item
    return out


async def cross_college(app: Any, factory: Any) -> dict[str, Any]:
    import httpx
    from sqlalchemy import select

    from app.core.security import COOKIE_NAME, create_access_token
    from app.models.institution import Institution

    async with factory() as session:
        institutions = {
            i: (code, name)
            for i, code, name in (
                await session.execute(
                    select(Institution.id, Institution.aicte_permanent_id, Institution.name)
                )
            ).all()
        }
        users = await _ensure_users(session, institutions)
        await session.commit()
    async with factory() as session:
        items = await _one_of_each(session)

    routed = routed_paths(app)
    foreign = [(p, kind) for p, kind in FOREIGN_PATHS if p in routed]
    skipped = [p for p, _ in FOREIGN_PATHS if p not in routed]
    gate = asyncio.Semaphore(CONCURRENCY)
    transport = httpx.ASGITransport(app=app)

    async def ask(client: httpx.AsyncClient, path: str) -> int:
        async with gate:
            return (await client.get(path)).status_code

    attempts: list[Attempt] = []
    controls: list[Attempt] = []
    try:
        for requester, user_id in users.items():
            code = institutions[requester][0]
            token = create_access_token(user_id, "INSTITUTION")
            async with httpx.AsyncClient(
                transport=transport, base_url="http://eval", cookies={COOKIE_NAME: token}
            ) as client:
                jobs: list[tuple[str, str, str]] = []
                for target in institutions:
                    if target == requester:
                        continue
                    for template, kind in foreign:
                        ident = target if kind == "institution" else items[kind].get(target)
                        if ident is not None:
                            jobs.append(
                                (institutions[target][0], template, template.format(id=ident))
                            )
                own = [(code, t, t.format(id=requester)) for t in OWN_PATHS]
                statuses = await asyncio.gather(*(ask(client, url) for _, _, url in jobs + own))
                for (target, template, _), status in zip(jobs, statuses, strict=False):
                    attempts.append(Attempt(code, target, template, status))
                for (target, template, _), status in zip(own, statuses[len(jobs) :], strict=True):
                    controls.append(Attempt(code, target, template, status))
    finally:
        async with factory() as session:
            await _deactivate(session, users.values())
            await session.commit()
    return summarise(attempts, controls, skipped)


async def deadline_states(
    app: Any, factory: Any, aicte_ids: Sequence[str], academic_year: str
) -> dict[str, str | None] | None:
    """`deadline_state` of each institution as an AICTE officer reads it; None when the api
    has no completeness route."""
    import httpx
    from sqlalchemy import select

    from app.core.security import COOKIE_NAME, create_access_token
    from app.models.enums import UserRole
    from app.models.institution import Institution
    from app.models.user import User

    if "/institutions/{id}/completeness" not in routed_paths(app):
        return None
    async with factory() as session:
        admin = (
            await session.execute(
                select(User.id)
                .where(User.role == UserRole.AICTE_ADMIN, User.is_active.is_(True))
                .order_by(User.created_at)
                .limit(1)
            )
        ).scalar_one()
        ids = dict(
            (
                await session.execute(
                    select(Institution.aicte_permanent_id, Institution.id).where(
                        Institution.aicte_permanent_id.in_(list(aicte_ids))
                    )
                )
            ).all()
        )
    out: dict[str, str | None] = {}
    token = create_access_token(admin, "AICTE_ADMIN")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://eval",
        cookies={COOKIE_NAME: token},
    ) as client:
        for code in aicte_ids:
            if code not in ids:
                out[code] = None
                continue
            response = await client.get(
                f"/institutions/{ids[code]}/completeness", params={"academic_year": academic_year}
            )
            body = response.json() if response.status_code == 200 else {}
            out[code] = body.get("deadline_state")
    return out
