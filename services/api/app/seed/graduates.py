"""graduates.jsonl -> students with GRADUATED enrolments of an earlier academic year (D28).

The university degree proof needs students who have finished. datagen lists them in
graduates.jsonl (tools/datagen/README.md): final-year students of 2025-26 who are not on the
current roll. Each becomes a student, stored as an upload stores one (APAAR as HMAC, Fernet
copy and last four; a provisional id when there is no APAAR), with one enrolment of status
GRADUATED: no seat, no upload batch, no checks and no flags. Every current-year figure counts
ACTIVE enrolments of that year only, so graduates never appear in it, and a file that puts a
graduate in the current academic year is refused.

Safe to re-run: a student is found again by APAAR HMAC or provisional id, an enrolment by
(student, institution, programme, academic year), and nothing found is changed. One SEED
audit entry per run with counts only, never PII.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.cohort import cohort_year, start_year
from app.core.config import get_settings
from app.core.crypto import encrypt, hmac_bytes, normalise
from app.engine import matching
from app.models.enums import (
    AdmissionRoute,
    AuditAction,
    Category,
    ConsentStatus,
    EnrolmentStatus,
    Gender,
    Shift,
)
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.seed.importer import SeedError, Summary

APAAR_DIGITS = re.compile(r"[0-9]{12}")


def read_graduates(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _apaar(row: dict[str, Any]) -> str | None:
    """The APAAR used as identity: 12 digits with consent LINKED, as an upload uses it."""
    value = normalise(str(row.get("apaar_id") or ""), "apaar")
    if row.get("consent_status") == ConsentStatus.LINKED.value and APAAR_DIGITS.fullmatch(value):
        return value
    return None


async def _programmes(
    session: AsyncSession, rows: list[dict[str, Any]], where: str
) -> dict[tuple[str, str], tuple[Institution, Programme]]:
    """(aicte_id, programme code) -> its institution and programme, FIRST shift preferred."""
    aicte_ids = {row["institution_aicte_id"] for row in rows}
    institutions = {
        i.aicte_permanent_id: i
        for i in (
            await session.execute(
                select(Institution).where(Institution.aicte_permanent_id.in_(aicte_ids))
            )
        ).scalars()
    }
    out: dict[tuple[str, str], tuple[Institution, Programme]] = {}
    for aicte_id in sorted(aicte_ids):
        institution = institutions.get(aicte_id)
        if institution is None:
            raise SeedError(f"{where}: institution {aicte_id} is not in institutions.json")
        programmes = (
            await session.execute(
                select(Programme).where(Programme.institution_id == institution.id)
            )
        ).scalars()
        for programme in sorted(programmes, key=lambda p: p.shift is not Shift.FIRST):
            out.setdefault((aicte_id, programme.code), (institution, programme))
    return out


def _new_student(row: dict[str, Any], apaar: str | None) -> Student:
    dob = date.fromisoformat(row["dob"])
    mobile = normalise(str(row.get("mobile") or ""), "mobile")
    return Student(
        id=uuid.uuid4(),
        apaar_hmac=hmac_bytes(apaar, "apaar") if apaar else None,
        apaar_encrypted=encrypt(apaar) if apaar else None,
        apaar_last4=apaar[-4:] if apaar else None,
        consent_status=ConsentStatus(row["consent_status"]),
        provisional_id=None if apaar else row["provisional_id"],
        name=row["name"],
        name_normalized=matching.normalise_name(row["name"]),
        name_key=matching.name_key(row["name"], dob),
        dob=dob,
        gender=Gender(row.get("gender") or Gender.U.value),
        mobile_hmac=hmac_bytes(mobile, "mobile") if mobile else None,
        mobile_last4=mobile[-4:] if mobile else None,
        email=row.get("email") or None,
        nationality=row.get("nationality") or "IN",
    )


def _new_enrolment(
    row: dict[str, Any], student: Student, institution: Institution, programme: Programme
) -> Enrolment:
    year = row["academic_year"]
    year_of_study = int(row["year_of_study"])
    cohort = cohort_year(year, year_of_study)
    admitted = row.get("admission_date")
    graduated = row.get("status_date")
    return Enrolment(
        id=uuid.uuid4(),
        student_id=student.id,
        institution_id=institution.id,
        programme_id=programme.id,
        academic_year=year,
        year_of_study=year_of_study,
        cohort_year=cohort,
        admission_route=AdmissionRoute(row.get("admission_route") or "COUNSELLING"),
        counselling_ref=None,
        category=Category(row.get("category") or "GENERAL"),
        seat_id=None,
        status=EnrolmentStatus.GRADUATED,
        upload_batch_id=None,
        source_row_no=None,
        admission_date=(
            date.fromisoformat(admitted) if admitted else date(start_year(cohort), 7, 1)
        ),
        status_date=(
            date.fromisoformat(graduated)
            if graduated
            else date(int(row.get("year_of_award") or start_year(year) + 1), 6, 30)
        ),
    )


async def import_graduates(session: AsyncSession, path: Path, summary: Summary) -> None:
    """Every line of graduates.jsonl as a student and a GRADUATED enrolment. Flushes, never
    commits."""
    rows = read_graduates(path)
    current = get_settings().academic_year
    places = await _programmes(session, rows, path.name)

    students_created = enrolments_created = 0
    for n, row in enumerate(rows, start=1):
        where = f"{path.name} line {n}"
        if row["academic_year"] == current:
            raise SeedError(
                f"{where}: {current} is the current academic year; graduates belong to an "
                "earlier one"
            )
        place = places.get((row["institution_aicte_id"], row["programme_code"]))
        if place is None:
            raise SeedError(
                f"{where}: programme {row['programme_code']} is not offered by "
                f"{row['institution_aicte_id']}"
            )
        institution, programme = place
        apaar = _apaar(row)
        if apaar is None and not row.get("provisional_id"):
            raise SeedError(f"{where}: a graduate needs an APAAR with consent or a provisional id")

        key = (
            Student.apaar_hmac == hmac_bytes(apaar, "apaar")
            if apaar
            else Student.provisional_id == row["provisional_id"]
        )
        student = (await session.execute(select(Student).where(key))).scalars().first()
        summary.bump("graduate_students", student is None)
        if student is None:
            student = _new_student(row, apaar)
            session.add(student)
            await session.flush()
            students_created += 1

        enrolment = (
            await session.execute(
                select(Enrolment.id).where(
                    Enrolment.student_id == student.id,
                    Enrolment.institution_id == institution.id,
                    Enrolment.programme_id == programme.id,
                    Enrolment.academic_year == row["academic_year"],
                )
            )
        ).first()
        if enrolment is None:
            session.add(_new_enrolment(row, student, institution, programme))
            enrolments_created += 1
        summary.bump("graduates", enrolment is None)
    await session.flush()

    await audit.record(
        session,
        None,
        AuditAction.SEED,
        "graduates_file",
        after={
            "file": path.name,
            "graduates": len(rows),
            "students_created": students_created,
            "enrolments_created": enrolments_created,
        },
    )
