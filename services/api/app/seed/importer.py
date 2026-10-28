"""Load datagen output (API_CONTRACT §E, §A2.24) into the api database. Safe to re-run.

institutions.json -> regions, states, universities, institutions, programmes (with mode),
                     approvals (+ seat pools and seats through engine.seatpools)
users.json        -> staff users first, student users after the uploads
uploads/*.csv     -> every file through run_batch in-process, the same engine a college
                     upload uses (D22): initial files first, sorted by name, then the update
                     files sorted by college and number. A file already seeded unchanged is
                     skipped.
Every step writes one SEED entry to the audit chain with counts only, never PII.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select, text, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import AdapterSet
from app.adapters.factory import build_adapters
from app.core import audit
from app.core.crypto import hmac_bytes, normalise
from app.core.rules import Rules, get_rules
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.engine.contracts import EngineSuite
from app.engine.seatpools import build_for_approval
from app.engine.upload.batches import create_batch
from app.models.enums import (
    AuditAction,
    Discipline,
    InstitutionType,
    ProgrammeLevel,
    ProgrammeMode,
    Shift,
    UploadSource,
    UploadStatus,
    UserRole,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.seat import SeatPool
from app.models.student import Student
from app.models.upload import UploadBatch
from app.models.user import User

log = logging.getLogger("countersign.seed")

UPLOAD_NAME = re.compile(r"^(?P<aicte_id>.+?)_(?P<year>\d{4}-\d{2})(?:_update(?P<n>\d+))?\.csv$")
STAFF_ROLES = (
    UserRole.AICTE_ADMIN,
    UserRole.RO_OFFICER,
    UserRole.INSTITUTION,
    UserRole.UNIVERSITY,
)

DURATION_YEARS = {
    ProgrammeLevel.DIPLOMA: 3,
    ProgrammeLevel.UG: 4,
    ProgrammeLevel.PG: 2,
    ProgrammeLevel.POST_DIPLOMA: 1,
}


@dataclass
class Counter:
    created: int = 0
    existing: int = 0

    def add(self, created: bool) -> None:
        if created:
            self.created += 1
        else:
            self.existing += 1


@dataclass
class FileResult:
    name: str
    status: str  # DONE, FAILED or SKIPPED
    batch_id: uuid.UUID | None
    counts: dict[str, Any] = field(default_factory=dict)


@dataclass
class Summary:
    counts: dict[str, Counter] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    uploads: list[FileResult] = field(default_factory=list)

    def bump(self, entity: str, created: bool, n: int = 1) -> None:
        counter = self.counts.setdefault(entity, Counter())
        if created:
            counter.created += n
        else:
            counter.existing += n

    def table(self) -> str:
        width = max([len(k) for k in self.counts] + [8])
        lines = [f"{'entity':<{width}}  {'created':>8}  {'existing':>8}"]
        for entity, counter in self.counts.items():
            lines.append(f"{entity:<{width}}  {counter.created:>8}  {counter.existing:>8}")
        if self.uploads:
            lines.append("")
            lines.append(f"{'upload':<44}  {'status':<8}  {'rows':>6}  {'errors':>6}")
            for result in self.uploads:
                lines.append(
                    f"{result.name:<44}  {result.status:<8}  "
                    f"{result.counts.get('rows', 0):>6}  {result.counts.get('errors', 0):>6}"
                )
        return "\n".join(lines)


class SeedError(ValueError):
    pass


# ------------------------------------------------------------------ public API


async def import_directory(
    factory: async_sessionmaker[AsyncSession],
    source: Path,
    reset: bool = False,
    rules: Rules | None = None,
    *,
    engines: EngineSuite | None = None,
    adapters: AdapterSet | None = None,
) -> Summary:
    source = Path(source)
    if not source.is_dir():
        raise SeedError(f"{source} is not a directory")
    rules = rules or get_rules()
    summary = Summary()

    if reset:
        async with factory() as session:
            await reset_database(session)
            await session.commit()

    async with factory() as session:
        await import_institutions(session, source / "institutions.json", rules, summary)
        await session.commit()

    users_path = source / "users.json"
    if users_path.is_file():
        # Staff first: upload batches need an owner before the files are read.
        async with factory() as session:
            await import_users(session, users_path, summary, roles=STAFF_ROLES)
            await session.commit()

    uploads = upload_files(source / "uploads")
    if uploads:
        own_adapters = adapters is None
        adapters = adapters if adapters is not None else build_adapters()
        try:
            for path in uploads:
                await import_upload(factory, path, summary, engines=engines, adapters=adapters)
        finally:
            if own_adapters:
                await adapters.aclose()

    if users_path.is_file():
        # Student logins point at rows the uploads just created.
        async with factory() as session:
            await import_users(session, users_path, summary, roles=(UserRole.STUDENT,))
            await session.commit()
    return summary


async def reset_database(session: AsyncSession) -> None:
    tables = ", ".join(f'"{t}"' for t in Base.metadata.tables)
    await session.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


# -------------------------------------------------------------- institutions


async def import_institutions(
    session: AsyncSession, path: Path, rules: Rules, summary: Summary
) -> None:
    if not path.is_file():
        raise SeedError(f"{path} is missing")
    data = json.loads(path.read_text(encoding="utf-8"))

    regions: dict[str, Region] = {
        r.code: r for r in (await session.execute(select(Region))).scalars()
    }
    for row in data.get("regions", []):
        region = regions.get(row["code"])
        if region is None:
            region = Region(code=row["code"], name=row["name"], hq_city=row["hq_city"])
            session.add(region)
            regions[row["code"]] = region
            summary.bump("regions", True)
        else:
            region.name, region.hq_city = row["name"], row["hq_city"]
            summary.bump("regions", False)
    await session.flush()

    states: dict[str, State] = {s.code: s for s in (await session.execute(select(State))).scalars()}
    for row in data.get("states", []):
        region = regions.get(row["region"])
        if region is None:
            raise SeedError(f"state {row['code']} references unknown region {row['region']}")
        state = states.get(row["code"])
        if state is None:
            state = State(code=row["code"], name=row["name"], region_id=region.id)
            session.add(state)
            states[row["code"]] = state
            summary.bump("states", True)
        else:
            state.name, state.region_id = row["name"], region.id
            summary.bump("states", False)
    await session.flush()

    universities: dict[str, University] = {
        u.code: u for u in (await session.execute(select(University))).scalars()
    }
    for row in data.get("universities", []):
        state = states.get(row["state_code"])
        if state is None:
            raise SeedError(
                f"university {row['code']} references unknown state {row['state_code']}"
            )
        uni = universities.get(row["code"])
        if uni is None:
            uni = University(code=row["code"], name=row["name"], state_id=state.id)
            session.add(uni)
            universities[row["code"]] = uni
            summary.bump("universities", True)
        else:
            uni.name, uni.state_id = row["name"], state.id
            summary.bump("universities", False)
    await session.flush()

    institutions: dict[str, Institution] = {
        i.aicte_permanent_id: i for i in (await session.execute(select(Institution))).scalars()
    }
    for row in data.get("institutions", []):
        state = states.get(row["state_code"])
        if state is None:
            raise SeedError(
                f"institution {row['aicte_permanent_id']} references unknown state "
                f"{row['state_code']}"
            )
        uni = universities.get(row["university_code"]) if row.get("university_code") else None
        inst = institutions.get(row["aicte_permanent_id"])
        values = dict(
            name=row["name"],
            type=InstitutionType(row["type"]),
            state_id=state.id,
            region_id=state.region_id,
            university_id=uni.id if uni else None,
            address_city=row.get("address_city"),
            established_year=row.get("established_year"),
        )
        if inst is None:
            inst = Institution(aicte_permanent_id=row["aicte_permanent_id"], **values)
            session.add(inst)
            institutions[row["aicte_permanent_id"]] = inst
            summary.bump("institutions", True)
        else:
            for key, value in values.items():
                setattr(inst, key, value)
            summary.bump("institutions", False)
        await session.flush()
        await _import_programmes(session, inst, row.get("programmes", []), rules, summary)

    await audit.record(
        session,
        None,
        AuditAction.SEED,
        "institutions_file",
        after={
            "file": path.name,
            "institutions": len(data.get("institutions", [])),
            "created": {k: v.created for k, v in summary.counts.items()},
        },
    )


async def _import_programmes(
    session: AsyncSession,
    institution: Institution,
    rows: list[dict[str, Any]],
    rules: Rules,
    summary: Summary,
) -> None:
    existing = {
        (p.code, p.shift): p
        for p in (
            await session.execute(
                select(Programme).where(Programme.institution_id == institution.id)
            )
        ).scalars()
    }
    for row in rows:
        level = ProgrammeLevel(row["level"])
        shift = Shift(row.get("shift") or "FIRST")
        programme = existing.get((row["code"], shift))
        values = dict(
            name=row["name"],
            level=level,
            discipline=Discipline(row["discipline"]),
            shift=shift,
            duration_years=int(row.get("duration_years") or DURATION_YEARS[level]),
            mode=ProgrammeMode(row.get("mode") or ProgrammeMode.PHYSICAL.value),
        )
        if programme is None:
            programme = Programme(institution_id=institution.id, code=row["code"], **values)
            session.add(programme)
            existing[(row["code"], shift)] = programme
            summary.bump("programmes", True)
        else:
            for key, value in values.items():
                setattr(programme, key, value)
            summary.bump("programmes", False)
        await session.flush()

        approvals = {
            a.academic_year: a
            for a in (
                await session.execute(select(Approval).where(Approval.programme_id == programme.id))
            ).scalars()
        }
        for arow in row.get("approvals", []):
            year = arow["academic_year"]
            cutoff = rules.cutoff_dates.get(year)
            approval = approvals.get(year)
            if approval is None:
                approval = Approval(
                    programme_id=programme.id,
                    academic_year=year,
                    approved_intake=int(arow["approved_intake"]),
                    cutoff_date=date.fromisoformat(cutoff) if cutoff else None,
                )
                session.add(approval)
                await session.flush()
                approvals[year] = approval
                summary.bump("approvals", True)
            else:
                approval.approved_intake = int(arow["approved_intake"])
                if cutoff:
                    approval.cutoff_date = date.fromisoformat(cutoff)
                summary.bump("approvals", False)

            has_pools = (
                await session.execute(
                    select(SeatPool.id).where(SeatPool.approval_id == approval.id).limit(1)
                )
            ).first()
            if has_pools is None:
                pools = build_for_approval(approval, programme, rules)
                session.add_all(pools)
                summary.bump("seat_pools", True, len(pools))
                summary.bump("seats", True, sum(len(p.seats) for p in pools))
            else:
                summary.bump("seat_pools", False, 5)
        await session.flush()


# ------------------------------------------------------------------- uploads


def upload_files(directory: Path) -> list[Path]:
    """Initial files sorted by name, then update files sorted by college and number."""
    if not directory.is_dir():
        return []
    initial: list[Path] = []
    updates: list[tuple[str, int, Path]] = []
    for path in directory.glob("*.csv"):
        match = UPLOAD_NAME.match(path.name)
        if not match:
            raise SeedError(f"{path.name}: expected <aicte_id>_<year>.csv or _update<n>.csv")
        if match["n"] is None:
            initial.append(path)
        else:
            updates.append((match["aicte_id"], int(match["n"]), path))
    return sorted(initial, key=lambda p: p.name) + [p for *_, p in sorted(updates)]


async def _owner(session: AsyncSession, institution: Institution, filename: str) -> uuid.UUID:
    """The college's registrar uploads its seed files; the AICTE admin when it has none."""
    for role, scope in (
        (UserRole.INSTITUTION, User.institution_id == institution.id),
        (UserRole.AICTE_ADMIN, true()),
    ):
        owner = (
            (
                await session.execute(
                    select(User.id).where(User.role == role, scope).order_by(User.created_at)
                )
            )
            .scalars()
            .first()
        )
        if owner is not None:
            return owner
    raise SeedError(
        f"{filename}: no INSTITUTION or AICTE_ADMIN user to own the upload batch "
        "(users.json is imported before uploads)"
    )


async def import_upload(
    factory: async_sessionmaker[AsyncSession],
    path: Path,
    summary: Summary,
    *,
    engines: EngineSuite | None = None,
    adapters: AdapterSet | None = None,
) -> FileResult:
    """One datagen file through run_batch, as a SEED batch with no actor."""
    from app.engine.pipeline import run_batch

    match = UPLOAD_NAME.match(path.name)
    if not match:
        raise SeedError(f"{path.name}: expected <aicte_id>_<year>.csv or _update<n>.csv")
    aicte_id, year = match["aicte_id"], match["year"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    async with factory() as session:
        institution = (
            await session.execute(
                select(Institution).where(Institution.aicte_permanent_id == aicte_id)
            )
        ).scalar_one_or_none()
        if institution is None:
            raise SeedError(f"{path.name}: institution {aicte_id} is not in institutions.json")
        seeded = (
            await session.execute(
                select(UploadBatch.id).where(
                    UploadBatch.institution_id == institution.id,
                    UploadBatch.academic_year == year,
                    UploadBatch.source == UploadSource.SEED,
                    UploadBatch.status == UploadStatus.DONE,
                    UploadBatch.file_sha256 == digest,
                )
            )
        ).first()
        if seeded is not None:
            result = FileResult(path.name, "SKIPPED", seeded.id)
            summary.bump("upload_batches", False)
            summary.uploads.append(result)
            summary.files.append(path.name)
            return result
        batch = await create_batch(
            session,
            institution_id=institution.id,
            academic_year=year,
            filename=path.name,
            source=UploadSource.SEED,
            uploaded_by=await _owner(session, institution, path.name),
            file_sha256=digest,
            actor_id=None,
        )
        await session.commit()
    summary.bump("upload_batches", True)

    batch = await run_batch(
        batch.id, factory=factory, adapters=adapters, engines=engines, source=path
    )
    counts = {k: v for k, v in batch.counts.items() if k not in ("sources", "timings_ms")}
    result = FileResult(path.name, batch.status.value, batch.id, counts)
    summary.uploads.append(result)
    summary.files.append(path.name)
    summary.bump("enrolments", True, counts.get("created", 0))
    summary.bump("enrolments", False, counts.get("updated", 0) + counts.get("unchanged", 0))

    async with factory() as session:
        await audit.record(
            session,
            None,
            AuditAction.SEED,
            "upload_file",
            entity_id=institution.id,
            after={
                "file": path.name,
                "batch_id": str(batch.id),
                "status": batch.status.value,
                **counts,
            },
        )
        await session.commit()
    if batch.status is not UploadStatus.DONE:
        raise SeedError(f"{path.name}: {batch.error}")
    return result


# --------------------------------------------------------------------- users


async def import_users(
    session: AsyncSession,
    path: Path,
    summary: Summary,
    roles: tuple[UserRole, ...] | None = None,
) -> None:
    all_rows = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in all_rows if roles is None or UserRole(r["role"]) in roles]
    existing = {u.email.lower(): u for u in (await session.execute(select(User))).scalars()}
    for row in rows:
        role = UserRole(row["role"])
        scope: dict[str, uuid.UUID | None] = {
            "institution_id": None,
            "region_id": None,
            "student_id": None,
            "university_id": None,
        }
        if role is UserRole.INSTITUTION:
            scope["institution_id"] = await _lookup(
                session,
                Institution.id,
                Institution.aicte_permanent_id,
                row.get("institution_aicte_id"),
                row,
            )
        elif role is UserRole.RO_OFFICER:
            scope["region_id"] = await _lookup(
                session, Region.id, Region.code, row.get("region"), row
            )
        elif role is UserRole.STUDENT:
            ref = normalise(str(row.get("student_ref") or ""), "apaar")
            scope["student_id"] = await _lookup(
                session,
                Student.id,
                Student.apaar_hmac,
                hmac_bytes(ref, "apaar") if ref else None,
                row,
            )
        elif role is UserRole.UNIVERSITY:
            scope["university_id"] = await _lookup(
                session, University.id, University.code, row.get("university_code"), row
            )

        user = existing.get(row["email"].lower())
        if user is None:
            user = User(
                email=row["email"],
                password_hash=hash_password(row["password"]),
                name=row["name"],
                role=role,
                is_active=True,
                **scope,
            )
            session.add(user)
            existing[row["email"].lower()] = user
            summary.bump("users", True)
        else:
            user.name, user.role = row["name"], role
            for key, value in scope.items():
                setattr(user, key, value)
            if not verify_password(row["password"], user.password_hash):
                user.password_hash = hash_password(row["password"])
            summary.bump("users", False)
    await session.flush()
    await audit.record(
        session,
        None,
        AuditAction.SEED,
        "users_file",
        after={
            "file": path.name,
            "users": len(rows),
            "roles": [r.value for r in (roles or tuple(UserRole))],
        },
    )


async def _lookup(
    session: AsyncSession, id_col, key_col, key: Any, row: dict[str, Any]
) -> uuid.UUID:
    if key is None:
        raise SeedError(f"user {row.get('email')}: scope reference is missing")
    found = (await session.execute(select(id_col).where(key_col == key))).scalar_one_or_none()
    if found is None:
        raise SeedError(f"user {row.get('email')}: scope reference {key!r} not found")
    return found
