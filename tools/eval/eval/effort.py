"""Officer review effort: how many unresolved cases the test bed leaves, and how big they are."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any

from .views import CaseView


def review_effort(
    cases: Iterable[CaseView], active_records: int, exclude: Collection[str] = ()
) -> dict[str, Any]:
    """Unresolved cases per 1,000 ACTIVE records, evidence facts per case and records per
    case (institution-level cases name no record and count 0)."""
    open_cases = [c for c in cases if c.unresolved and c.institution not in exclude]
    n = len(open_cases)
    return {
        "unresolved_cases": n,
        "active_records": active_records,
        "cases_per_1000": round(1000 * n / active_records, 2) if active_records else None,
        "facts_per_case": round(sum(c.facts for c in open_cases) / n, 2) if n else None,
        "records_per_case": round(sum(len(c.enrolments) for c in open_cases) / n, 2) if n else None,
        "by_type": _by_type(open_cases),
    }


def _by_type(cases: list[CaseView]) -> dict[str, int]:
    out: dict[str, int] = {}
    for case in cases:
        out[case.type] = out.get(case.type, 0) + 1
    return dict(sorted(out.items()))
