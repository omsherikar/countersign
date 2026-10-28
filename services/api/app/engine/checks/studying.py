"""STUDYING: ABC credits for every completed year of study (D18)."""

from __future__ import annotations

import asyncio
from datetime import date

from app.adapters.base import AbcResult, AdapterSet
from app.core.cohort import start_year, year_label
from app.engine import evidence as ev
from app.engine.checks.base import (
    CheckSubject,
    SourceDown,
    call_source,
    flag_intent,
    pending_unavailable,
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
        credits_by_sem: dict[int, int] = {}
        for entry in result.semesters:
            credits_by_sem[entry.sem] = max(credits_by_sem.get(entry.sem, 0), entry.credits)
        semesters.extend(ev.SemesterCredits(label, sem, credits_by_sem.get(sem, 0)) for sem in sems)
    detail = ev.studying_detail(semesters)
    missing = detail["missing"]
    if missing == 0:
        return CheckOutcome(
            type=CHECK, status=CheckStatus.CONFIRMED, source=SOURCE, detail=detail, calls=calls
        )
    if missing == 1:
        return CheckOutcome(
            type=CHECK, status=CheckStatus.PENDING, source=SOURCE, detail=detail, calls=calls
        )
    flag = flag_intent(
        subject,
        FlagType.NO_ACADEMIC_ACTIVITY,
        Severity.MEDIUM,
        ev.no_academic_activity(
            year_of_study=subject.year_of_study,
            semesters=semesters,
            last_entry=_last_entry(results),
            related=[subject.enrolment_id],
        ),
    )
    return CheckOutcome(
        type=CHECK,
        status=CheckStatus.CONTRADICTED,
        source=SOURCE,
        detail=detail,
        flags=(flag,),
        calls=calls,
    )


async def evaluate(
    subject: CheckSubject, adapters: AdapterSet, gate: asyncio.Semaphore
) -> CheckOutcome:
    if subject.year_of_study <= 1:
        return CheckOutcome(
            type=CHECK,
            status=CheckStatus.NOT_APPLICABLE,
            source=SOURCE,
            detail=ev.studying_first_year(),
        )
    years = completed_years(subject)
    if not years:  # a year-2 lateral entrant
        return CheckOutcome(
            type=CHECK,
            status=CheckStatus.NOT_APPLICABLE,
            source=SOURCE,
            detail=ev.studying_lateral_entry(),
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
            return pending_unavailable(CHECK, result, calls=len(results) + 1)
        results.append(result)
    return decide(subject, years, results)
