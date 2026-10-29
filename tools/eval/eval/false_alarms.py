"""Wrong flags on legitimate records.

The known-clean set is every ACTIVE record created from an upload that no ground-truth
record names, outside the throughput college. One of them is a false alarm when any case
names it, or when its status reads UNDER_REVIEW or DISPUTED. The planted controls (refused
consent, CIWG seats, TFW without the certificate, self-issued credits, unclaimed
provisional ids, clean independent records) are reported apart: they must not be flagged
either, but they are not part of the known-clean set.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import Any

from .detection import ratio
from .truth import TruthRecord
from .views import REVIEW_STATUSES, CaseView, RecordView

EXAMPLES = 10


def named_by_cases(cases: Iterable[CaseView]) -> dict[str, list[CaseView]]:
    out: dict[str, list[CaseView]] = {}
    for case in cases:
        for enrolment in case.enrolments:
            out.setdefault(enrolment, []).append(case)
    return out


def known_clean(
    views: Mapping[str, RecordView], named: Collection[str], exclude: Collection[str]
) -> set[str]:
    return {
        v.id
        for v in views.values()
        if v.active and v.from_upload and v.id not in named and v.institution not in exclude
    }


def _reasons(view: RecordView, cases: Sequence[CaseView]) -> list[str]:
    reasons = sorted({f"case {c.type}" for c in cases})
    if view.record_status in REVIEW_STATUSES:
        reasons.append(f"status {view.record_status}")
    return reasons


def score_false_alarms(
    clean: Collection[str], views: Mapping[str, RecordView], cases: Iterable[CaseView]
) -> dict[str, Any]:
    by_record = named_by_cases(cases)
    causes: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    flagged = 0
    for record_id in sorted(clean):
        view = views[record_id]
        reasons = _reasons(view, by_record.get(record_id, []))
        if not reasons:
            continue
        flagged += 1
        causes.update(reasons)
        if len(examples) < EXAMPLES:
            examples.append({"institution": view.institution, "reasons": reasons})
    return {
        "clean_records": len(clean),
        "flagged": flagged,
        "rate": ratio(flagged, len(clean)) if clean else None,
        "causes": dict(sorted(causes.items())),
        "examples": examples,
    }


def score_controls(
    records: Iterable[TruthRecord],
    resolved: Mapping[int, Sequence[str | None]],
    views: Mapping[str, RecordView],
    cases: Iterable[CaseView],
) -> dict[str, Any]:
    """Planted legitimate special cases named by a case. A record that some planted case
    also names (a refused-consent student who is also a duplicate) is left out."""
    records = list(records)
    expected = {
        e for r in records if r.planted_case for e in resolved.get(r.index, ()) if e is not None
    }
    by_record = named_by_cases(cases)
    by_type: dict[str, dict[str, int]] = {}
    flagged_items: list[dict[str, Any]] = []
    for record in records:
        if not record.is_control:
            continue
        ids = [
            e
            for e in resolved.get(record.index, ())
            if e is not None and e not in expected and e in views and views[e].active
        ]
        if not ids:
            continue
        tally = by_type.setdefault(record.type, {"records": 0, "flagged": 0})
        tally["records"] += 1
        reasons = sorted({r for e in ids for r in _reasons(views[e], by_record.get(e, []))})
        if reasons:
            tally["flagged"] += 1
            flagged_items.append(
                {"type": record.type, "institution": record.institution, "reasons": reasons}
            )
    return {
        "records": sum(t["records"] for t in by_type.values()),
        "flagged": sum(t["flagged"] for t in by_type.values()),
        "by_type": dict(sorted(by_type.items())),
        "flagged_items": flagged_items,
    }
