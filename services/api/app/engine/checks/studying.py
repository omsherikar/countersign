"""STUDYING, the Credits row: ABC credits for every completed year of study (D18, D38).

ABC names the body that issued each semester's credits. Credits issued by the claiming
college itself (an autonomous college) are shown Confirmed but are not independent of the
college, so they never make a record Countersigned on their own. Before the first semester
result the row is Not yet due.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from app.adapters.base import AbcResult, AdapterSet
from app.core.cohort import start_year, year_label
from app.engine import evidence as ev
from app.engine.checks.base import (
    CheckSubject,
    SourceDown,
    call_source,
    flag_intent,
    unavailable_outcome,
)
from app.engine.contracts import CheckOutcome
from app.models.enums import AdmissionRoute, CheckStatus, CheckType, FlagType, Severity

SOURCE = "ABC"
CHECK = CheckType.STUDYING


def first_year_studied(subject: CheckSubject) -> int:
    """The first year of study spent at the institution: 2 for a lateral entrant, else 1."""
    return 2 if subject.admission_route is AdmissionRoute.LATERAL else 1


def completed_years(subject: CheckSubject) -> list[tuple[str, tuple[int, int]]]:
    """[(year label, (first semester, second semester))] for each completed year of study.

    Years 1 to year_of_study - 1; a lateral entrant joined in year 2, so its years start
    at 2 (a year-3 lateral is checked on year 2 only, semesters 3 and 4).
    """
    start = start_year(subject.academic_year)
    return [
        (year_label(start - (subject.year_of_study - k)), (2 * k - 1, 2 * k))
        for k in range(first_year_studied(subject), subject.year_of_study)
    ]


def _last_entry(results: list[AbcResult]) -> date | None:
    stamps = [s.uploaded_at[:10] for r in results for s in r.semesters if s.uploaded_at]
    return date.fromisoformat(max(stamps)) if stamps else None


def _latest_upload(results: list[AbcResult]) -> datetime | None:
    """When ABC recorded the latest of the semesters read: the row's observed_at (D34)."""
    stamps: list[datetime] = []
    for result in results:
        for semester in result.semesters:
            if semester.credits > 0 and semester.uploaded_at:
                try:
                    at = datetime.fromisoformat(semester.uploaded_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                stamps.append(at if at.tzinfo else at.replace(tzinfo=UTC))
    return max(stamps) if stamps else None


def decide(
    subject: CheckSubject, years: list[tuple[str, tuple[int, int]]], results: list[AbcResult]
) -> CheckOutcome:
    calls = (SOURCE,) * len(results)
    if all(not r.apaar_id_known for r in results):
        return CheckOutcome(
            type=CHECK,
            status=CheckStatus.NOT_APPLICABLE,
            source=SOURCE,
            detail=ev.studying_unknown_apaar(),
            calls=calls,
        )
    semesters: list[ev.SemesterCredits] = []
    for (label, sems), result in zip(years, results, strict=True):
        best: dict[int, tuple[int, str | None, str | None]] = {}
        for entry in result.semesters:
            if entry.sem not in best or entry.credits > best[entry.sem][0]:
                best[entry.sem] = (entry.credits, entry.issuer, entry.issuer_name)
        for sem in sems:
            credits, issuer, issuer_name = best.get(sem, (0, None, None))
            semesters.append(ev.SemesterCredits(label, sem, credits, issuer, issuer_name))
    issuers = ev.credit_issuers(semesters, subject.institution_aicte_id, subject.institution_name)
    detail = ev.studying_detail(semesters, issuers)
    missing = detail["missing"]
    flags = ()
    if missing == 0:
        status = CheckStatus.CONFIRMED
    elif missing == 1:
        status = CheckStatus.PENDING
    else:
        status = CheckStatus.CONTRADICTED
        flags = (
            flag_intent(
                subject,
                FlagType.NO_ACADEMIC_ACTIVITY,
                Severity.MEDIUM,
                ev.no_academic_activity(
                    year_of_study=subject.year_of_study,
                    semesters=semesters,
                    last_entry=_last_entry(results),
                    related=[subject.enrolment_id],
                ),
            ),
        )
    return CheckOutcome(
        type=CHECK,
        status=status,
        source=SOURCE,
        detail=detail,
        flags=flags,
        calls=calls,
        supplied_by=issuers.supplied_by,
        observed_at=_latest_upload(results),
        # independent only when no semester read was issued by the claiming college (D38)
        independent=not issuers.self_issued,
    )


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    # no semester result exists yet, so credits are not due (R4)
    if subject.year_of_study <= 1:
        return CheckOutcome(
            type=CHECK,
            status=CheckStatus.NOT_YET_DUE,
            source=SOURCE,
            detail=ev.studying_not_yet_due(subject.affiliating_university_name),
        )
    years = completed_years(subject)
    if not years:  # a year-2 lateral entrant
        return CheckOutcome(
            type=CHECK,
            status=CheckStatus.NOT_YET_DUE,
            source=SOURCE,
            detail=ev.studying_not_yet_due_lateral(subject.affiliating_university_name),
        )
    if not subject.apaar_id:
        return CheckOutcome(
            type=CHECK,
            status=CheckStatus.NOT_APPLICABLE,
            source=SOURCE,
            detail=ev.studying_no_apaar(),
        )
    apaar_id = subject.apaar_id
    results: list[AbcResult] = []
    for label, _ in years:
        result = await call_source(
            gate, SOURCE, lambda label=label: adapters.abc.credits(apaar_id, label)
        )
        if isinstance(result, SourceDown):
            return unavailable_outcome(CHECK, result, calls=len(results) + 1)
        results.append(result)
    return decide(subject, years, results)
