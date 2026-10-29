"""Signals against the planted ghost rings and anomalous colleges.

A planted ring is found when one GHOST_RING signal holds at least 80% of its members; a ring
signal is correct when it is the finding of some planted ring. An anomaly is found when an
ANOMALY signal names its institution; an ANOMALY signal is correct when it names a planted one.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import Any

from .detection import ratio
from .truth import TruthRecord
from .views import SignalView

RING_SHARE = 0.8


def holds(signal: Collection[str], members: Collection[str], share: float = RING_SHARE) -> bool:
    return bool(members) and len(set(signal) & set(members)) >= share * len(members)


def score_rings(
    planted: Sequence[frozenset[str]], signals: Sequence[frozenset[str]]
) -> dict[str, Any]:
    found = sum(1 for ring in planted if any(holds(s, ring) for s in signals))
    correct = sum(1 for s in signals if any(holds(s, ring) for ring in planted))
    return {
        "planted": len(planted),
        "found": found,
        "recall": ratio(found, len(planted)),
        "signals": len(signals),
        "correct": correct,
        "precision": ratio(correct, len(signals)),
    }


def score_anomalies(planted: Collection[str], signals: Sequence[frozenset[str]]) -> dict[str, Any]:
    planted = set(planted)
    found = sum(1 for inst in planted if any(inst in s for s in signals))
    correct = sum(1 for s in signals if s & planted)
    return {
        "planted": len(planted),
        "found": found,
        "recall": ratio(found, len(planted)),
        "signals": len(signals),
        "correct": correct,
        "precision": ratio(correct, len(signals)),
    }


def score_signals(
    records: Iterable[TruthRecord],
    resolved: Mapping[int, Sequence[str | None]],
    signals: Iterable[SignalView],
) -> dict[str, Any]:
    records = list(records)
    signals = list(signals)
    rings = [
        frozenset(e for e in resolved.get(r.index, ()) if e is not None)
        for r in records
        if r.expected_signal == "GHOST_RING"
    ]
    anomalies = {r.institution for r in records if r.expected_signal == "ANOMALY"}
    ring_result = score_rings(
        [ring for ring in rings if ring], [s.enrolments for s in signals if s.type == "GHOST_RING"]
    )
    anomaly_result = score_anomalies(
        anomalies, [s.institutions for s in signals if s.type == "ANOMALY"]
    )
    total_planted = ring_result["planted"] + anomaly_result["planted"]
    total_signals = ring_result["signals"] + anomaly_result["signals"]
    return {
        "rings": ring_result,
        "anomalies": anomaly_result,
        "signals_run": bool(signals),
        "recall": ratio(ring_result["found"] + anomaly_result["found"], total_planted),
        "precision": ratio(ring_result["correct"] + anomaly_result["correct"], total_signals),
    }
