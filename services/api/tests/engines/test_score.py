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
    statuses = ["PASS", "PASS", "PASS", "NA", "PENDING"]
    assert score(statuses) == (3, 4)
    assert score([CheckStatus.NA, CheckStatus.NA]) == (0, 0)
    assert score([]) is None


def test_countersigned_needs_every_applicable_check_to_pass() -> None:
    assert is_countersigned(["PASS", "PASS", "NA", "NA", "PASS"])
    assert not is_countersigned(["PASS", "PENDING", "NA"])
    assert not is_countersigned(["NA", "NA"])  # nothing applicable
    assert not is_countersigned([])


def test_clear_means_no_fail() -> None:
    assert is_clear(["PASS", "PENDING", "NA"])
    assert not is_clear(["PASS", "FAIL"])
    assert not is_clear([])


def test_countersign_block_is_in_check_order() -> None:
    checks = [
        SimpleNamespace(type=CheckType.STUDENT, status=CheckStatus.PENDING),
        SimpleNamespace(type=CheckType.SEAT, status=CheckStatus.PASS),
        SimpleNamespace(type=CheckType.IDENTITY, status=CheckStatus.PASS),
        SimpleNamespace(type=CheckType.STUDYING, status=CheckStatus.NA),
        SimpleNamespace(type=CheckType.ADMISSION, status=CheckStatus.PASS),
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
    assert block["checks"][3] == {"type": "STUDYING", "status": "NA"}


def test_unchecked_enrolment_has_no_score() -> None:
    assert countersign([]) == {"score": None, "checks": []}
    assert countersign_from_pairs([]) == {"score": None, "checks": []}
