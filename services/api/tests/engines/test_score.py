"""Countersign score: passes over applicable checks, NA excluded, PENDING not a pass."""

from __future__ import annotations

from types import SimpleNamespace

from app.engine.score import (
    countersign,
    countersign_from_pairs,
    is_clear,
    is_countersigned,
    score,
)
from app.models.enums import CheckStatus, CheckType


def test_score_excludes_na_and_counts_pending_as_applicable() -> None:
    statuses = ["CONFIRMED", "CONFIRMED", "CONFIRMED", "NOT_APPLICABLE", "PENDING"]
    assert score(statuses) == (3, 4)
    assert score([CheckStatus.NOT_APPLICABLE, CheckStatus.NOT_APPLICABLE]) == (0, 0)
    assert score([]) is None


def test_countersigned_needs_every_applicable_check_to_pass() -> None:
    assert is_countersigned(
        ["CONFIRMED", "CONFIRMED", "NOT_APPLICABLE", "NOT_APPLICABLE", "CONFIRMED"]
    )
    assert not is_countersigned(["CONFIRMED", "PENDING", "NOT_APPLICABLE"])
    assert not is_countersigned(["NOT_APPLICABLE", "NOT_APPLICABLE"])  # nothing applicable
    assert not is_countersigned([])


def test_clear_means_no_fail() -> None:
    assert is_clear(["CONFIRMED", "PENDING", "NOT_APPLICABLE"])
    assert not is_clear(["CONFIRMED", "CONTRADICTED"])
    assert not is_clear([])


def test_countersign_block_is_in_check_order() -> None:
    checks = [
        SimpleNamespace(type=CheckType.STUDENT, status=CheckStatus.PENDING),
        SimpleNamespace(type=CheckType.SEAT, status=CheckStatus.CONFIRMED),
        SimpleNamespace(type=CheckType.IDENTITY, status=CheckStatus.CONFIRMED),
        SimpleNamespace(type=CheckType.STUDYING, status=CheckStatus.NOT_APPLICABLE),
        SimpleNamespace(type=CheckType.ADMISSION, status=CheckStatus.CONFIRMED),
    ]
    block = countersign(checks)
    assert block["score"] == {"passes": 3, "applicable": 4}
    assert [c["type"] for c in block["checks"]] == [
        "IDENTITY",
        "ADMISSION",
        "SEAT",
        "STUDYING",
        "STUDENT",
    ]
    assert block["checks"][3] == {"type": "STUDYING", "status": "NOT_APPLICABLE"}


def test_unchecked_enrolment_has_no_score() -> None:
    assert countersign([]) == {"score": None, "checks": []}
    assert countersign_from_pairs([]) == {"score": None, "checks": []}
