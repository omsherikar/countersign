"""Load datagen output (API_CONTRACT §E) into the api database. Idempotent on re-run.

institutions.json -> regions, states, universities, institutions, programmes, approvals
                     (+ seat pools and seats through engine.seatpools)
uploads/*.csv     -> students (HMAC / Fernet / last4) and enrolments (seat_id null in Week 1)
users.json        -> demo users (argon2), scoped to institution / region / student / university
Every step writes one SEED entry to the audit chain with counts only, never PII.
"""

from __future__ import annotations

import base64
import csv
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import audit
from app.core.cohort import cohort_year
from app.core.crypto import (
    encrypt,
    hmac_bytes,
    last4,
    mask_apaar,
    normalise,
    normalise_name,
)
from app.core.rules import Rules, get_rules
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.engine.seatpools import build_for_approval
from app.models.enums import (
    AdmissionRoute,
    AuditAction,
    Category,
    ConsentStatus,
    Discipline,
    EnrolmentStatus,
    Gender,
    InstitutionType,
    ProgrammeLevel,
    Shift,
    UploadKind,
    UploadSource,
    UploadStage,
    UploadStatus,
    UserRole,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.seat import SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch, UploadRowError
from app.models.user import User

log = logging.getLogger("countersign.seed")

UPLOAD_NAME = re.compile(r"^(?P<aicte_id>.+?)_(?P<year>\d{4}-\d{2})\.csv$")
APAAR_FORMAT = re.compile(r"^[0-9]{12}$")
BATCH = 1000
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
class Summary:
    counts: dict[str, Counter] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)

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
        return "\n".join(lines)


class SeedError(ValueError):
    pass


# ------------------------------------------------------------------ public API


async def import_directory(
    factory: async_sessionmaker[AsyncSession],
    source: Path,
    reset: bool = False,
    rules: Rules | None = None,
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
        # Staff first: upload batches need an owner before the CSVs are read.
        async with factory() as session:
            await import_users(session, users_path, summary, roles=STAFF_ROLES)
            await session.commit()

    uploads = sorted((source / "uploads").glob("*.csv")) if (source / "uploads").is_dir() else []
    for path in uploads:
        async with factory() as session:
            await import_upload(session, path, summary)
            await session.commit()

    if users_path.is_file():
        # Student logins point at rows the CSVs just created.
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


def provisional_id_for(institution_aicte_id: str, name: str, dob: str, mobile: str) -> str:
    """Deterministic PRV-XXXXXXXX so a re-run finds the same APAAR-less student."""
    seed = f"{institution_aicte_id}|{normalise_name(name)}|{dob}|{normalise(mobile, 'mobile')}"
    digest = hmac_bytes(seed, "generic")
    return "PRV-" + base64.b32encode(digest).decode("ascii")[:8]


def _gender(value: str | None) -> Gender:
    first = (value or "").strip()[:1].upper()
    return Gender(first) if first in ("M", "F", "O") else Gender.U


def _enum(enum_cls, value: str | None, row_no: int, column: str):
    raw = (value or "").strip().upper()
    try:
        return enum_cls(raw)
    except ValueError:
        raise SeedError(
            f"row {row_no}: {column} {value!r} is not one of {[e.value for e in enum_cls]}"
        ) from None


def describe_apaar_problem(raw: str) -> str | None:
    """Why an uploaded apaar_id fails ^[0-9]{12}$, or None when it is fine or empty."""
    clean = raw.replace(" ", "")
    if not clean:
        return None
    if not clean.isdigit():
        return "apaar_id contains characters other than digits"
    if len(clean) != 12:
        return f"apaar_id has {len(clean)} digits, expected 12"
    return None


def student_values(
    row: dict[str, str], institution_aicte_id: str, row_no: int
) -> tuple[dict[str, Any], str | None]:
    """Column values for `students` plus an APAAR_FORMAT message when the id is unusable.

    A malformed APAAR is treated as absent (the student gets a provisional id) so the
    enrolment still lands and Week 2 can raise INVALID_APAAR against it.
    """
    raw_apaar = (row.get("apaar_id") or "").strip()
    apaar_error = describe_apaar_problem(raw_apaar)
    apaar = "" if apaar_error else normalise(raw_apaar, "apaar")
    name = (row.get("name") or "").strip()
    dob_raw = (row.get("dob") or "").strip()
    if not name or not dob_raw:
        raise SeedError(f"row {row_no}: name and dob are required")
    try:
        dob = date.fromisoformat(dob_raw)
    except ValueError:
        raise SeedError(f"row {row_no}: dob {dob_raw!r} is not YYYY-MM-DD") from None
    mobile = (row.get("mobile") or "").strip()
    email = (row.get("email") or "").strip() or None
    address = (row.get("address") or "").strip()
    nationality = ((row.get("nationality") or "IN").strip().upper() or "IN")[:2]
    passport = (row.get("passport_no") or "").strip()
    consent_raw = (row.get("consent_status") or "").strip().upper()
    if consent_raw:
        consent = _enum(ConsentStatus, consent_raw, row_no, "consent_status")
    elif apaar:
        consent = ConsentStatus.LINKED
    elif nationality != "IN" or passport:
        consent = ConsentStatus.INTERNATIONAL
    else:
        consent = ConsentStatus.PENDING

    values: dict[str, Any] = {
        "apaar_hmac": hmac_bytes(apaar, "apaar") if apaar else None,
        "apaar_encrypted": encrypt(apaar) if apaar else None,
        "apaar_last4": last4(apaar, "apaar") if apaar else None,
        "consent_status": consent,
        "provisional_id": None
        if apaar
        else provisional_id_for(institution_aicte_id, name, dob_raw, mobile),
        "name": name,
        "name_normalized": normalise_name(name),
        "dob": dob,
        "gender": _gender(row.get("gender")),
        "mobile_hmac": hmac_bytes(mobile, "mobile") if mobile else None,
        "mobile_last4": last4(mobile, "mobile") if mobile else None,
        "email": email,
        "address_hmac": hmac_bytes(address, "address") if address else None,
        "nationality": nationality,
        "passport_hmac": hmac_bytes(passport, "passport") if passport else None,
    }
    return values, apaar_error


def masked_row(row: dict[str, str], apaar_error: str | None) -> dict[str, Any]:
    """What upload_row_errors.raw keeps: no contact details, no address, no full id."""
    raw_apaar = (row.get("apaar_id") or "").strip()
    return {
        "apaar_id": f"<{len(raw_apaar)} chars, {apaar_error}>"
        if apaar_error
        else mask_apaar(raw_apaar),
        "name": (row.get("name") or "").strip(),
        "programme_code": (row.get("programme_code") or "").strip(),
        "academic_year": (row.get("academic_year") or "").strip(),
        "admission_route": (row.get("admission_route") or "").strip(),
    }


async def _batch_for(
    session: AsyncSession, institution: Institution, year: str, filename: str, summary: Summary
) -> UploadBatch:
    """One upload_batches row per seeded file (re-used on re-run) to hang row errors on."""
    batch = (
        (
            await session.execute(
                select(UploadBatch).where(
                    UploadBatch.institution_id == institution.id,
                    UploadBatch.academic_year == year,
                    UploadBatch.filename == filename,
                )
            )
        )
        .scalars()
        .first()
    )
    if batch is not None:
        summary.bump("upload_batches", False)
        return batch
    owner = (
        (
            await session.execute(
                select(User.id).where(
                    User.institution_id == institution.id, User.role == UserRole.INSTITUTION
                )
            )
        )
        .scalars()
        .first()
    )
    if owner is None:
        owner = (
            (await session.execute(select(User.id).where(User.role == UserRole.AICTE_ADMIN)))
            .scalars()
            .first()
        )
    if owner is None:
        raise SeedError(
            f"{filename}: no INSTITUTION or AICTE_ADMIN user to own the upload batch "
            "(users.json is imported before uploads)"
        )
    now = datetime.now(UTC)
    batch = UploadBatch(
        institution_id=institution.id,
        academic_year=year,
        filename=filename,
        kind=UploadKind.INITIAL,
        status=UploadStatus.DONE,
        stage=UploadStage.DONE,
        source=UploadSource.SEED,
        uploaded_by=owner,
        started_at=now,
        finished_at=now,
    )
    session.add(batch)
    await session.flush()
    summary.bump("upload_batches", True)
    return batch


async def import_upload(session: AsyncSession, path: Path, summary: Summary) -> None:
    match = UPLOAD_NAME.match(path.name)
    if not match:
        raise SeedError(f"{path.name}: expected <aicte_id>_<year>.csv")
    aicte_id, file_year = match["aicte_id"], match["year"]
    institution = (
        await session.execute(select(Institution).where(Institution.aicte_permanent_id == aicte_id))
    ).scalar_one_or_none()
    if institution is None:
        raise SeedError(f"{path.name}: institution {aicte_id} is not in institutions.json")
    programmes: dict[str, uuid.UUID] = {}
    for programme in (
        await session.execute(
            select(Programme)
            .where(Programme.institution_id == institution.id)
            .order_by(Programme.code, Programme.shift)
        )
    ).scalars():
        programmes.setdefault(programme.code, programme.id)

    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    batch = await _batch_for(session, institution, file_year, path.name, summary)

    today = datetime.now(UTC).date()
    students: dict[bytes | str, dict[str, Any]] = {}
    enrolment_rows: list[tuple[bytes | str, dict[str, Any]]] = []
    row_errors: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):  # row 1 is the header
        values, apaar_error = student_values(row, aicte_id, index)
        if apaar_error:
            row_errors.append(
                {
                    "batch_id": batch.id,
                    "row_no": index,
                    "field": "apaar_id",
                    "code": "APAAR_FORMAT",
                    "message": apaar_error,
                    "raw": masked_row(row, apaar_error),
                }
            )
        key: bytes | str = values["apaar_hmac"] or values["provisional_id"]
        students.setdefault(key, values)
        code = (row.get("programme_code") or "").strip()
        programme_id = programmes.get(code)
        if programme_id is None:
            raise SeedError(f"{path.name} row {index}: unknown programme_code {code!r}")
        academic_year = (row.get("academic_year") or file_year).strip()
        year_of_study = int(row.get("year_of_study") or 1)
        enrolment_rows.append(
            (
                key,
                {
                    "institution_id": institution.id,
                    "programme_id": programme_id,
                    "academic_year": academic_year,
                    "year_of_study": year_of_study,
                    "cohort_year": cohort_year(academic_year, year_of_study),
                    "admission_date": today,
                    "status_date": today,
                    "admission_route": _enum(
                        AdmissionRoute, row.get("admission_route"), index, "admission_route"
                    ),
                    "counselling_ref": (row.get("counselling_ref") or "").strip() or None,
                    "category": _enum(Category, row.get("category") or "OTHER", index, "category"),
                    "seat_id": None,
                    "status": EnrolmentStatus.ACTIVE,
                    "source_row_no": index,
                    "uploaded_at": datetime.now(UTC),
                },
            )
        )

    students_created = await _bulk_insert(session, Student, list(students.values()))
    summary.bump("students", True, students_created)
    summary.bump("students", False, len(students) - students_created)

    ids = await _student_ids(session, list(students))
    enrolments: dict[tuple, dict[str, Any]] = {}
    for key, values in enrolment_rows:
        values = {"student_id": ids[key], **values}
        ekey = (
            values["student_id"],
            values["institution_id"],
            values["programme_id"],
            values["academic_year"],
        )
        enrolments.setdefault(ekey, values)
    enrolments_created = await _bulk_insert(session, Enrolment, list(enrolments.values()))
    summary.bump("enrolments", True, enrolments_created)
    summary.bump("enrolments", False, len(enrolments) - enrolments_created)

    await session.execute(delete(UploadRowError).where(UploadRowError.batch_id == batch.id))
    if row_errors:
        await session.execute(insert(UploadRowError).values(row_errors))
    summary.bump("upload_row_errors", True, len(row_errors))
    batch.total_rows = len(rows)
    batch.counts = {
        "rows": len(rows),
        "accepted": len(rows) - len(row_errors),
        "errors": len(row_errors),
    }
    summary.files.append(path.name)

    await audit.record(
        session,
        None,
        AuditAction.SEED,
        "upload_file",
        entity_id=institution.id,
        after={
            "file": path.name,
            "rows": len(rows),
            "students_created": students_created,
            "enrolments_created": enrolments_created,
            "row_errors": len(row_errors),
        },
    )


async def _bulk_insert(session: AsyncSession, model, values: list[dict[str, Any]]) -> int:
    created = 0
    for start in range(0, len(values), BATCH):
        chunk = values[start : start + BATCH]
        result = await session.execute(insert(model).values(chunk).on_conflict_do_nothing())
        created += result.rowcount or 0
    return created


async def _student_ids(
    session: AsyncSession, keys: list[bytes | str]
) -> dict[bytes | str, uuid.UUID]:
    hmacs = [k for k in keys if isinstance(k, bytes)]
    provisional = [k for k in keys if isinstance(k, str)]
    out: dict[bytes | str, uuid.UUID] = {}
    for start in range(0, len(hmacs), BATCH):
        chunk = hmacs[start : start + BATCH]
        rows = await session.execute(
            select(Student.id, Student.apaar_hmac).where(Student.apaar_hmac.in_(chunk))
        )
        for sid, h in rows:
            out[h] = sid
    for start in range(0, len(provisional), BATCH):
        chunk = provisional[start : start + BATCH]
        rows = await session.execute(
            select(Student.id, Student.provisional_id).where(Student.provisional_id.in_(chunk))
        )
        for sid, p in rows:
            out[p] = sid
    missing = [k for k in keys if k not in out]
    if missing:
        raise SeedError(f"{len(missing)} students could not be resolved after insert")
    return out


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
