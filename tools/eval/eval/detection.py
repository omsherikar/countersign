"""Detection of seeded inconsistencies, expected record statuses and deadline states.

A planted record is found when a case of its `expected_flag` type
- names every one of its rows that became an enrolment (record cases),
- is about its programme and pool (EXCESS_ADMISSION, QUOTA_BREACH), or
- is about its institution and year (MISSING_FROM_UPLOAD),
whatever the case's status. Severity matches when every such case has the planted severity.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .truth import INSTITUTION_TYPES, POOL_TYPES, TruthRecord
from .views import CaseView, RecordView


def ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


@dataclass(slots=True)
class TypeScore:
    planted: int = 0
    found: int = 0
    severity_match: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "planted": self.planted,
            "found": self.found,
            "recall": ratio(self.found, self.planted),
            "severity_match": ratio(self.severity_match, self.found),
            "severity_matched": self.severity_match,
        }


@dataclass(slots=True)
class Detection:
    by_type: dict[str, TypeScore] = field(default_factory=dict)
    misses: list[dict[str, Any]] = field(default_factory=list)
    severity_mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def planted(self) -> int:
        return sum(s.planted for s in self.by_type.values())

    @property
    def found(self) -> int:
        return sum(s.found for s in self.by_type.values())

    @property
    def severity_matched(self) -> int:
        return sum(s.severity_match for s in self.by_type.values())

    @property
    def overall_recall(self) -> float | None:
        return ratio(self.found, self.planted)

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_recall": self.overall_recall,
            "planted": self.planted,
            "found": self.found,
            "severity_match": ratio(self.severity_matched, self.found),
            "by_type": {t: s.as_dict() for t, s in sorted(self.by_type.items())},
            "misses": self.misses,
            "severity_mismatches": self.severity_mismatches,
        }


def index_cases(cases: Iterable[CaseView]) -> dict[str, list[CaseView]]:
    by_type: dict[str, list[CaseView]] = defaultdict(list)
    for case in cases:
        by_type[case.type].append(case)
    return by_type


def matching_cases(
    record: TruthRecord,
    enrolments: Sequence[str | None],
    cases_of_type: Sequence[CaseView],
) -> list[CaseView]:
    """The cases of the record's type that cover it; empty when it was not found."""
    if record.type in POOL_TYPES or record.expected_flag in POOL_TYPES:
        return [
            c
            for c in cases_of_type
            if c.institution == record.institution
            and c.programme_code == record.programme_code
            and (record.seat_type is None or c.pool is None or c.pool == record.seat_type)
        ]
    if record.type in INSTITUTION_TYPES or record.expected_flag in INSTITUTION_TYPES:
        return [
            c
            for c in cases_of_type
            if c.institution == record.institution
            and (record.academic_year is None or c.academic_year == record.academic_year)
        ]
    rows = [e for e in enrolments if e is not None]
    if not rows:
        return []
    covering = [c for c in cases_of_type if c.enrolments.intersection(rows)]
    named = set().union(*(c.enrolments for c in covering)) if covering else set()
    if not set(rows) <= named:
        return []
    return covering


def score_detection(
    records: Iterable[TruthRecord],
    resolved: Mapping[int, Sequence[str | None]],
    cases: Iterable[CaseView],
) -> Detection:
    by_type = index_cases(cases)
    result = Detection()
    for record in records:
        if not record.planted_case:
            continue
        flag = str(record.expected_flag)
        score = result.by_type.setdefault(flag, TypeScore())
        score.planted += 1
        enrolments = resolved.get(record.index, ())
        found = matching_cases(record, enrolments, by_type.get(flag, []))
        if not found:
            missing_rows = sum(1 for e in enrolments if e is None)
            result.misses.append(
                {
                    "type": flag,
                    "institution": record.institution,
                    "programme_code": record.programme_code,
                    "rows": len(record.rows),
                    "rows_without_enrolment": missing_rows,
                    "note": record.note,
                }
            )
            continue
        score.found += 1
        severities = sorted({c.severity for c in found})
        if record.severity is None or severities == [record.severity]:
            score.severity_match += 1
        else:
            result.severity_mismatches.append(
                {
                    "type": flag,
                    "institution": record.institution,
                    "expected": record.severity,
                    "found": severities,
                }
            )
    return result


def score_record_status(
    records: Iterable[TruthRecord],
    resolved: Mapping[int, Sequence[str | None]],
    views: Mapping[str, RecordView],
) -> dict[str, Any]:
    """Records planted with an expected status (and expected row states) against the engine's."""
    checked = matched = rows_checked = rows_matched = 0
    mismatches: list[dict[str, Any]] = []
    for record in records:
        if record.expected_record_status is None and not record.expected_rows:
            continue
        enrolments = [e for e in resolved.get(record.index, ()) if e is not None]
        found = [views[e] for e in enrolments if e in views]
        if record.expected_record_status is not None:
            checked += 1
            statuses = sorted({v.record_status or "NONE" for v in found})
            if found and statuses == [record.expected_record_status]:
                matched += 1
            else:
                mismatches.append(
                    {
                        "type": record.type,
                        "institution": record.institution,
                        "expected": record.expected_record_status,
                        "found": statuses or ["NO RECORD"],
                    }
                )
        for check, state in sorted(record.expected_rows.items()):
            rows_checked += 1
            states = sorted({v.rows.get(check, "NONE") for v in found})
            if found and states == [state]:
                rows_matched += 1
            else:
                mismatches.append(
                    {
                        "type": record.type,
                        "institution": record.institution,
                        "row": check,
                        "expected": state,
                        "found": states or ["NO RECORD"],
                    }
                )
    return {
        "checked": checked,
        "matched": matched,
        "rate": ratio(matched, checked),
        "rows_checked": rows_checked,
        "rows_matched": rows_matched,
        "mismatches": mismatches,
    }


def score_deadlines(
    records: Iterable[TruthRecord], states: Mapping[str, str | None] | None
) -> dict[str, Any]:
    """Planted LATE and OVERDUE colleges against the deadline state the api reports.

    `states` is None when the api has no completeness route to ask."""
    planted = [r for r in records if r.expected_deadline_state]
    if states is None:
        return {
            "checked": len(planted),
            "matched": None,
            "available": False,
            "items": [
                {"institution": r.institution, "expected": r.expected_deadline_state, "found": None}
                for r in planted
            ],
        }
    items = [
        {
            "institution": r.institution,
            "expected": r.expected_deadline_state,
            "found": states.get(r.institution),
        }
        for r in planted
    ]
    return {
        "checked": len(items),
        "matched": sum(1 for i in items if i["found"] == i["expected"]),
        "available": True,
        "items": items,
    }
