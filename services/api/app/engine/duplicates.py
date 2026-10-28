"""Duplicate detection (docs/ENGINES.md section 9, DECISIONS D19).

Only ACTIVE enrolments of the academic year take part. Candidates are blocked on
`students.name_key` (date of birth, first initial, metaphone of the surname).

- Rule A, within the institution: a different student, at least one of the two without
  an APAAR, whose name scores 90 or more or who shares the mobile HMAC:
  DUPLICATE_WITHIN_UPLOAD (MEDIUM), one flag.
- Rule B, the same student (same APAAR or passport) ACTIVE at another institution:
  DUAL_ENROLMENT_ALLOWED (LOW) when the two modes are an allowed pair, otherwise
  DUPLICATE_CROSS_INSTITUTION (HIGH). One flag per institution.
- Rule C, no APAAR across institutions: name 90 or more and the same mobile HMAC; the
  same mode rule with DUPLICATE_CROSS_INSTITUTION at MEDIUM. One flag per institution.

The repeated APAAR inside one file is not here: it is the pipeline's DUPLICATE_IN_FILE.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit import AuditEntry
from app.core.rules import get_rules
from app.engine import evidence as ev
from app.engine.contracts import DuplicatesResult
from app.engine.flags import pair_key, raise_flag
from app.engine.matching import match_names
from app.models.enums import EnrolmentStatus, FlagType, ProgrammeMode, Severity
from app.models.geo import State
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch


@dataclass(frozen=True, slots=True)
class _Row:
    enrolment: Enrolment
    student: Student
    institution: Institution
    state_name: str
    programme: Programme
    filename: str | None

    @property
    def has_apaar(self) -> bool:
        return self.student.apaar_hmac is not None

    @property
    def order(self) -> tuple:
        e = self.enrolment
        return (
            e.uploaded_at,
            e.source_row_no if e.source_row_no is not None else 1 << 30,
            str(e.id),
        )

    def side(self) -> ev.DuplicateSide:
        return ev.DuplicateSide(
            enrolment_id=self.enrolment.id,
            institution_name=self.institution.name,
            state_name=self.state_name,
            programme_name=self.programme.name,
            mode=self.programme.mode,
            name=self.student.name,
            filename=self.filename,
            row_no=self.enrolment.source_row_no,
            uploaded_on=self.enrolment.uploaded_at.date(),
        )


def _base_query(academic_year: str):
    return (
        select(Enrolment, Student, Institution, State.name, Programme, UploadBatch.filename)
        .join(Student, Student.id == Enrolment.student_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(State, State.id == Institution.state_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .outerjoin(UploadBatch, UploadBatch.id == Enrolment.upload_batch_id)
        .where(Enrolment.academic_year == academic_year, Enrolment.status == EnrolmentStatus.ACTIVE)
    )


async def _rows(session: AsyncSession, stmt) -> list[_Row]:
    return [_Row(*row) for row in (await session.execute(stmt)).all()]


def dual_allowed(mode_a: ProgrammeMode, mode_b: ProgrammeMode) -> bool:
    """Whether the two modes are an allowed pair in rules.yaml dual_enrolment (unordered)."""
    rules = get_rules().dual_enrolment
    if rules is None:
        return False
    pair = {mode_a.value, mode_b.value}
    return any(set(allowed) == pair for allowed in rules.allowed_modes)


def _mobile_match(a: Student, b: Student) -> bool:
    return a.mobile_hmac is not None and a.mobile_hmac == b.mobile_hmac


async def detect_duplicates(
    session: AsyncSession,
    institution_id: uuid.UUID,
    academic_year: str,
    enrolment_ids: Sequence[uuid.UUID],
    *,
    actor_id: uuid.UUID | None = None,
) -> DuplicatesResult:
    result = DuplicatesResult()
    ids = list(dict.fromkeys(enrolment_ids))
    if not ids:
        return result
    inputs = await _rows(session, _base_query(academic_year).where(Enrolment.id.in_(ids)))
    if not inputs:
        return result
    position = {enrolment_id: n for n, enrolment_id in enumerate(ids)}
    inputs.sort(key=lambda r: position[r.enrolment.id])

    keys = {r.student.name_key for r in inputs if r.student.name_key}
    blocks: dict[str, list[_Row]] = defaultdict(list)
    if keys:
        for row in await _rows(
            session, _base_query(academic_year).where(Student.name_key.in_(keys))
        ):
            blocks[row.student.name_key].append(row)
    same_student: dict[uuid.UUID, list[_Row]] = defaultdict(list)
    for row in await _rows(
        session,
        _base_query(academic_year).where(Enrolment.student_id.in_({r.student.id for r in inputs})),
    ):
        same_student[row.student.id].append(row)

    sink: list[AuditEntry] = []
    seen: set[frozenset[uuid.UUID]] = set()
    for row in inputs:
        # Rule B: the same student ACTIVE at another institution.
        for other in same_student[row.student.id]:
            if other.institution.id == row.institution.id:
                continue
            pair = frozenset({row.enrolment.id, other.enrolment.id})
            if pair in seen:
                continue
            seen.add(pair)
            words = ev.match_words(
                same_apaar=row.has_apaar,
                same_passport=not row.has_apaar and row.student.passport_hmac is not None,
                name_score=None,
                mobile=False,
            )
            await _cross_pair(
                session, row, other, words, Severity.HIGH, academic_year, actor_id, sink, result
            )

        for other in blocks.get(row.student.name_key or "", []):
            if other.student.id == row.student.id:
                continue
            if row.has_apaar and other.has_apaar:
                continue  # two different APAARs are two different people
            pair = frozenset({row.enrolment.id, other.enrolment.id})
            if pair in seen:
                continue
            match = match_names(row.student.name, other.student.name)
            mobile = _mobile_match(row.student, other.student)
            if other.institution.id == row.institution.id:
                # Rule A
                if match.score < 90 and not mobile:
                    continue
                seen.add(pair)
                words = ev.match_words(
                    same_apaar=False,
                    same_passport=False,
                    name_score=match.score if match.score >= 90 else None,
                    mobile=mobile,
                )
                await _within_pair(session, row, other, words, actor_id, sink, result)
            else:
                # Rule C
                if match.score < 90 or not mobile:
                    continue
                seen.add(pair)
                words = ev.match_words(
                    same_apaar=False, same_passport=False, name_score=match.score, mobile=True
                )
                await _cross_pair(
                    session,
                    row,
                    other,
                    words,
                    Severity.MEDIUM,
                    academic_year,
                    actor_id,
                    sink,
                    result,
                )
    await audit.record_many(session, sink)
    return result


async def _within_pair(
    session: AsyncSession,
    a: _Row,
    b: _Row,
    words: str,
    actor_id: uuid.UUID | None,
    sink: list[AuditEntry],
    result: DuplicatesResult,
) -> None:
    """One DUPLICATE_WITHIN_UPLOAD naming the suspected copy: the record without an APAAR,
    or the later one when neither has an APAAR."""
    if a.has_apaar != b.has_apaar:
        original, copy = (a, b) if a.has_apaar else (b, a)
    else:
        original, copy = sorted((a, b), key=lambda r: r.order)
    shared = a.programme.id if a.programme.id == b.programme.id else None
    raised = await raise_flag(
        session,
        type=FlagType.DUPLICATE_WITHIN_UPLOAD,
        severity=Severity.MEDIUM,
        institution_id=copy.institution.id,
        programme_id=shared,
        enrolment_id=copy.enrolment.id,
        academic_year=copy.enrolment.academic_year,
        dedupe_key=pair_key(FlagType.DUPLICATE_WITHIN_UPLOAD, a.enrolment.id, b.enrolment.id),
        evidence=ev.duplicate_within_upload(
            original=original.side(), copy=copy.side(), words=words
        ),
        actor_id=actor_id,
        audit_sink=sink,
    )
    result.within += 1
    result.flags.count(raised)


async def _cross_pair(
    session: AsyncSession,
    a: _Row,
    b: _Row,
    words: str,
    severity: Severity,
    academic_year: str,
    actor_id: uuid.UUID | None,
    sink: list[AuditEntry],
    result: DuplicatesResult,
) -> None:
    """Two flags, one per institution, each from its own side's point of view."""
    allowed = dual_allowed(a.programme.mode, b.programme.mode)
    flag_type = FlagType.DUAL_ENROLMENT_ALLOWED if allowed else FlagType.DUPLICATE_CROSS_INSTITUTION
    for own, other in ((a, b), (b, a)):
        if allowed:
            evidence = ev.dual_enrolment_allowed(own=own.side(), other=other.side())
        else:
            evidence = ev.duplicate_cross_institution(
                own=own.side(), other=other.side(), words=words, academic_year=academic_year
            )
        raised = await raise_flag(
            session,
            type=flag_type,
            severity=Severity.LOW if allowed else severity,
            institution_id=own.institution.id,
            programme_id=own.programme.id,
            enrolment_id=own.enrolment.id,
            academic_year=academic_year,
            dedupe_key=pair_key(flag_type, a.enrolment.id, b.enrolment.id, own.institution.id),
            evidence=evidence,
            actor_id=actor_id,
            audit_sink=sink,
        )
        result.flags.count(raised)
    if allowed:
        result.dual += 1
    else:
        result.cross += 1
