"""UPSERT: resolve each row to a student and upsert its enrolment (D14, ENGINES.md §5).

Identity, in order: (a) the APAAR HMAC when the row carries a usable APAAR with consent;
a provisional student of this institution with the same provisional id and no APAAR is
upgraded in place. (b) the passport HMAC (oldest match). (c) the provisional id
"PRV-" + base32(hmac(aicte_id|normalised name|dob|mobile))[:8].

Enrolments upsert on (student, institution, programme, academic year). A row that changes
none of the compared fields writes nothing, so re-uploading a file is a no-op.
"""

from __future__ import annotations

import base64
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.crypto import encrypt, hmac_bytes, normalise
from app.engine import versions
from app.engine.contracts import EngineSuite
from app.engine.upload.mask import mask_value
from app.engine.upload.types import CleanRow, RowIssue, RowOutcome, UpsertResult, upload_date
from app.engine.upload.validate import STATUS_WORDS
from app.models.enums import (
    AuditAction,
    ConsentStatus,
    EnrolmentStatus,
    Gender,
    RowErrorLevel,
    UploadSource,
    VersionSource,
)
from app.models.institution import Institution
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch
from app.privacy.service import record_apaar_link

RELEASING = (EnrolmentStatus.WITHDRAWN, EnrolmentStatus.TRANSFERRED)
# New rows are written with one multi-row INSERT per table; ids are generated here.
STUDENT_COLUMNS = (
    "id",
    "apaar_hmac",
    "apaar_encrypted",
    "apaar_last4",
    "consent_status",
    "provisional_id",
    "name",
    "name_normalized",
    "name_key",
    "dob",
    "gender",
    "mobile_hmac",
    "mobile_last4",
    "email",
    "address_hmac",
    "nationality",
    "passport_hmac",
    "passport_encrypted",
)
ENROLMENT_COLUMNS = (
    "id",
    "student_id",
    "institution_id",
    "programme_id",
    "academic_year",
    "year_of_study",
    "cohort_year",
    "admission_route",
    "counselling_ref",
    "category",
    "status",
    "admission_date",
    "status_date",
    "apaar_problem",
    "upload_batch_id",
    "source_row_no",
    "uploaded_at",
)


def provisional_id_for(aicte_id: str, normalised_name: str, dob_iso: str, mobile: str) -> str:
    """Deterministic PRV-XXXXXXXX so a re-upload finds the same APAAR-less student."""
    seed = f"{aicte_id}|{normalised_name}|{dob_iso}|{normalise(mobile, 'mobile')}"
    return "PRV-" + base64.b32encode(hmac_bytes(seed, "generic")).decode("ascii")[:8]


@dataclass(slots=True)
class _Plan:
    row: CleanRow
    name_normalised: str
    name_key: str
    provisional_id: str
    apaar_hmac: bytes | None
    passport_hmac: bytes | None
    student: Student | None = None
    student_changes: list[str] | None = None  # None: created
    # the student was created or its consent changed: an APAAR_LINK consent row is owed
    consent_changed: bool = False
    enrolment_id: uuid.UUID | None = None


def _by(rows: Sequence[Student], attr: str) -> dict[Any, Student]:
    out: dict[Any, Student] = {}
    for student in rows:  # rows arrive oldest first; keep the first per key
        out.setdefault(getattr(student, attr), student)
    return out


async def _insert(
    session: AsyncSession, model: Any, objects: list[Any], columns: tuple[str, ...]
) -> None:
    """ORM bulk INSERT: one cached statement, rows sent in batches."""
    if objects:
        await session.execute(insert(model), [{c: getattr(o, c) for c in columns} for o in objects])


async def _students(session: AsyncSession, column, keys: list[Any]) -> Sequence[Student]:
    if not keys:
        return []
    stmt = select(Student).where(column.in_(keys)).order_by(Student.created_at, Student.id)
    return (await session.execute(stmt)).scalars().all()


def _new_student(plan: _Plan) -> Student:
    row = plan.row
    return Student(
        id=uuid.uuid4(),
        apaar_hmac=plan.apaar_hmac,
        apaar_encrypted=encrypt(row.apaar_id) if row.apaar_id else None,
        apaar_last4=row.apaar_id[-4:] if row.apaar_id else None,
        consent_status=row.consent_status,
        provisional_id=None if row.apaar_id else plan.provisional_id,
        name=row.name,
        name_normalized=plan.name_normalised,
        name_key=plan.name_key,
        dob=row.dob,
        gender=row.gender or Gender.U,
        mobile_hmac=hmac_bytes(row.mobile, "mobile") if row.mobile else None,
        mobile_last4=row.mobile[-4:] if row.mobile else None,
        email=row.email,
        address_hmac=hmac_bytes(row.address, "address") if row.address else None,
        nationality=row.effective_nationality,
        passport_hmac=plan.passport_hmac,
        passport_encrypted=encrypt(row.passport_no) if row.passport_no else None,
    )


def _update_student(student: Student, plan: _Plan, *, by_apaar: bool) -> list[str]:
    """Last writer wins for the fields the row carries; blank optional values keep what is stored.

    A row without a usable APAAR never removes or replaces a stored APAAR or its consent.
    """
    row = plan.row
    changed: dict[str, None] = {}

    def put(attr: str, value: Any, label: str) -> None:
        if getattr(student, attr) != value:
            setattr(student, attr, value)
            changed.setdefault(label, None)

    put("name", row.name, "name")
    put("name_normalized", plan.name_normalised, "name")
    put("dob", row.dob, "dob")
    put("name_key", plan.name_key, "name_key")
    if row.gender is not None:
        put("gender", row.gender, "gender")
    if row.mobile:
        put("mobile_hmac", hmac_bytes(row.mobile, "mobile"), "mobile")
        put("mobile_last4", row.mobile[-4:], "mobile")
    if row.email:
        put("email", row.email, "email")
    if row.address:
        put("address_hmac", hmac_bytes(row.address, "address"), "address")
    if row.nationality:
        put("nationality", row.nationality, "nationality")
    if row.passport_no and (
        student.passport_hmac != plan.passport_hmac or student.passport_encrypted is None
    ):
        student.passport_hmac = plan.passport_hmac
        student.passport_encrypted = encrypt(row.passport_no)
        changed.setdefault("passport", None)
    if by_apaar:
        if student.apaar_hmac is None and row.apaar_id:
            student.apaar_hmac = plan.apaar_hmac
            student.apaar_encrypted = encrypt(row.apaar_id)
            student.apaar_last4 = row.apaar_id[-4:]
            changed.setdefault("apaar", None)
        put("consent_status", ConsentStatus.LINKED, "consent_status")
    elif student.apaar_hmac is None:
        put("consent_status", row.consent_status, "consent_status")
    return list(changed)


def _created_fields(student: Student) -> list[str]:
    fields = ["name", "dob", "gender", "nationality", "consent_status"]
    optional = {
        "apaar": student.apaar_hmac,
        "mobile": student.mobile_hmac,
        "email": student.email,
        "address": student.address_hmac,
        "passport": student.passport_hmac,
    }
    return fields + [label for label, value in optional.items() if value is not None]


async def upsert_rows(
    session: AsyncSession,
    batch: UploadBatch,
    rows: Sequence[CleanRow],
    *,
    engines: EngineSuite,
    actor_id: uuid.UUID | None,
) -> UpsertResult:
    """Upsert one chunk of accepted rows. Flushes, never commits."""
    result = UpsertResult()
    if not rows:
        return result
    institution = await session.get(Institution, batch.institution_id)
    if institution is None:
        raise LookupError("the batch's institution does not exist")
    day = upload_date(batch.created_at)

    aicte_id = institution.aicte_permanent_id
    plans: list[_Plan] = []
    for row in rows:
        normalised = engines.normalise_name(row.name)
        plans.append(
            _Plan(
                row=row,
                name_normalised=normalised,
                name_key=engines.name_key(row.name, row.dob),
                provisional_id=provisional_id_for(
                    aicte_id, normalised, row.dob.isoformat(), row.mobile or ""
                ),
                apaar_hmac=hmac_bytes(row.apaar_id, "apaar") if row.apaar_id else None,
                passport_hmac=hmac_bytes(row.passport_no, "passport") if row.passport_no else None,
            )
        )

    by_apaar = _by(
        await _students(
            session, Student.apaar_hmac, list({p.apaar_hmac for p in plans if p.apaar_hmac})
        ),
        "apaar_hmac",
    )
    by_passport = _by(
        await _students(
            session,
            Student.passport_hmac,
            list({p.passport_hmac for p in plans if p.passport_hmac}),
        ),
        "passport_hmac",
    )
    by_provisional = _by(
        await _students(session, Student.provisional_id, list({p.provisional_id for p in plans})),
        "provisional_id",
    )

    entries: list[audit.AuditEntry] = []
    new_students: list[Student] = []  # not added to the session: inserted in bulk below
    # the versioned student fields as stored before this chunk changed them (D42)
    student_before: dict[uuid.UUID, dict[str, Any]] = {}
    new_enrolments: list[Enrolment] = []
    for plan in plans:
        student: Student | None
        if plan.apaar_hmac:
            student = by_apaar.get(plan.apaar_hmac)
            if student is None:
                candidate = by_provisional.get(plan.provisional_id)
                if candidate is not None and candidate.apaar_hmac is None:
                    student = candidate  # the college's provisional student gains its APAAR
        else:
            student = by_passport.get(plan.passport_hmac) if plan.passport_hmac else None
            if student is None:
                student = by_provisional.get(plan.provisional_id)

        if student is None:
            student = _new_student(plan)
            new_students.append(student)
            plan.consent_changed = True
            result.students_created += 1
            entries.append(
                audit.AuditEntry(
                    action=AuditAction.CREATE,
                    entity_type="student",
                    entity_id=student.id,
                    actor_id=actor_id,
                    after=_student_after(student, _created_fields(student)),
                )
            )
        else:
            student_before.setdefault(student.id, versions.student_fields(student))
            changes = _update_student(student, plan, by_apaar=plan.apaar_hmac is not None)
            plan.consent_changed = "consent_status" in changes
            if changes:
                result.students_updated += 1
                entries.append(
                    audit.AuditEntry(
                        action=AuditAction.UPDATE,
                        entity_type="student",
                        entity_id=student.id,
                        actor_id=actor_id,
                        after=_student_after(student, changes),
                    )
                )
        plan.student = student
        if student.apaar_hmac:
            by_apaar[student.apaar_hmac] = student
        if student.passport_hmac:
            by_passport.setdefault(student.passport_hmac, student)
        if student.provisional_id:
            by_provisional[student.provisional_id] = student

    student_ids = list({p.student.id for p in plans if p.student is not None})
    existing = (
        (
            await session.execute(
                select(Enrolment).where(
                    Enrolment.institution_id == batch.institution_id,
                    Enrolment.academic_year == batch.academic_year,
                    Enrolment.student_id.in_(student_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    enrolments = {(e.student_id, e.programme_id): e for e in existing}
    source = VersionSource.SEED if batch.source is UploadSource.SEED else VersionSource.UPLOAD
    version_writes: list[versions.VersionWrite] = []

    for plan in plans:
        row, student = plan.row, plan.student
        assert student is not None
        enrolment = enrolments.get((student.id, row.programme_id))
        released = False
        before: dict[str, Any] | None = None
        if enrolment is None:
            status = row.status or EnrolmentStatus.ACTIVE
            enrolment = Enrolment(
                id=uuid.uuid4(),
                student_id=student.id,
                institution_id=batch.institution_id,
                programme_id=row.programme_id,
                academic_year=batch.academic_year,
                year_of_study=row.year_of_study,
                cohort_year=row.cohort_year,
                admission_route=row.admission_route,
                counselling_ref=row.counselling_ref,
                category=row.category,
                status=status,
                admission_date=row.admission_date or day,
                status_date=row.status_date or day,
                apaar_problem=row.apaar_problem,
                upload_batch_id=batch.id,
                source_row_no=row.row_no,
                uploaded_at=batch.created_at,
            )
            new_enrolments.append(enrolment)
            enrolments[(student.id, row.programme_id)] = enrolment
            outcome = "created"
            result.created += 1
            if status in RELEASING:
                result.issues.append(_not_previously_enrolled(row, status))
            _count_status(result, None, status)
        else:
            before = {
                **(student_before.get(student.id) or versions.student_fields(student)),
                **versions.enrolment_fields(enrolment),
            }
            status = row.status or enrolment.status
            admission_date = row.admission_date or enrolment.admission_date
            wanted = (
                row.year_of_study,
                row.admission_route,
                row.counselling_ref,
                row.category,
                status,
                admission_date,
                row.apaar_problem,
            )
            current = (
                enrolment.year_of_study,
                enrolment.admission_route,
                enrolment.counselling_ref,
                enrolment.category,
                enrolment.status,
                enrolment.admission_date,
                enrolment.apaar_problem,
            )
            if wanted == current:
                outcome = "unchanged"
                result.unchanged += 1
            else:
                previous = enrolment.status
                status_changed = status != previous
                enrolment.year_of_study = row.year_of_study
                enrolment.cohort_year = row.cohort_year
                enrolment.admission_route = row.admission_route
                enrolment.counselling_ref = row.counselling_ref
                enrolment.category = row.category
                enrolment.status = status
                enrolment.admission_date = admission_date
                enrolment.apaar_problem = row.apaar_problem
                if row.status_date is not None:
                    enrolment.status_date = row.status_date
                elif status_changed:
                    enrolment.status_date = day
                enrolment.upload_batch_id = batch.id
                enrolment.source_row_no = row.row_no
                outcome = "updated"
                result.updated += 1
                released = status_changed and status in RELEASING
                if status_changed:
                    _count_status(result, previous, status)
        if outcome != "unchanged":
            entries.append(
                audit.AuditEntry(
                    action=AuditAction.CREATE if outcome == "created" else AuditAction.UPDATE,
                    entity_type="enrolment",
                    entity_id=enrolment.id,
                    actor_id=actor_id,
                    after={
                        "student_id": str(student.id),
                        "programme_id": str(enrolment.programme_id),
                        "academic_year": enrolment.academic_year,
                        "year_of_study": enrolment.year_of_study,
                        "admission_route": enrolment.admission_route.value,
                        "status": enrolment.status.value,
                        "batch_id": str(batch.id),
                        "row_no": row.row_no,
                    },
                )
            )
        changed = versions.diff(before, versions.snapshot(enrolment, student))
        if changed:
            version_writes.append(
                versions.VersionWrite(
                    enrolment_id=enrolment.id,
                    changes=changed,
                    source=source,
                    batch_id=batch.id,
                    actor_id=actor_id,
                    at=batch.created_at,
                )
            )
        plan.enrolment_id = enrolment.id
        result.outcomes.append(
            RowOutcome(
                row_no=row.row_no,
                enrolment_id=enrolment.id,
                student_id=student.id,
                outcome=outcome,
                status=enrolment.status,
                released=released,
            )
        )

    await _insert(session, Student, new_students, STUDENT_COLUMNS)
    await _insert(session, Enrolment, new_enrolments, ENROLMENT_COLUMNS)
    # after the inserts, so each version finds its enrolment
    result.versions += await versions.record_many(session, version_writes)
    # after the inserts, so each consent row finds its student and enrolment
    for plan in plans:
        if plan.consent_changed and plan.student is not None and plan.enrolment_id is not None:
            await record_apaar_link(
                session,
                student_id=plan.student.id,
                enrolment_id=plan.enrolment_id,
                consent_status=plan.student.consent_status,
                institution_name=institution.name,
                actor_id=actor_id,
                audit_sink=entries,
            )
    await session.flush()
    await audit.record_many(session, entries)
    return result


def _count_status(
    result: UpsertResult, previous: EnrolmentStatus | None, status: EnrolmentStatus
) -> None:
    if status == previous:
        return
    if status is EnrolmentStatus.WITHDRAWN:
        result.withdrawn += 1
    elif status is EnrolmentStatus.TRANSFERRED:
        result.transferred += 1


def _student_after(student: Student, changed: list[str]) -> dict[str, Any]:
    return {
        "apaar_last4": student.apaar_last4,
        "provisional_id": student.provisional_id,
        "consent_status": student.consent_status.value,
        "changed": changed,
    }


def _not_previously_enrolled(row: CleanRow, status: EnrolmentStatus) -> RowIssue:
    return RowIssue(
        row_no=row.row_no,
        level=RowErrorLevel.WARNING,
        field="status",
        code="NOT_PREVIOUSLY_ENROLLED",
        message=(
            "No earlier enrolment matches this student; recorded as "
            f"{STATUS_WORDS[status]} with no seat"
        ),
        value_masked=mask_value("status", row.status_raw),
        raw=row.raw,
    )
