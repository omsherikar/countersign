"""Evidence test fixtures: the engine worlds of tests/engines, with an admission authority.

`gov` is an in-memory adapter set whose admission authority starts empty (nothing
published); `joined` adds one joining for an enrolment the way datagen writes it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.adapters.base import AdapterSet
from app.adapters.inmemory import InMemoryAdmissionAuthority
from tests.engines.conftest import World, adapters, db, session, world  # noqa: F401

__all__ = ["World", "joining_row"]


def joining_row(
    *,
    name: str,
    dob: date,
    institution_code: str,
    programme: str = "CSE",
    state: str = "MH",
    academic_year: str = "2026-27",
    joined_on: date = date(2026, 8, 2),
    round: int | None = 1,
    route: str = "COUNSELLING",
    category: str = "GENERAL",
    roll_no: str | None = None,
    apaar_id: str | None = None,
) -> dict[str, Any]:
    """One line of mockgov/admission_joinings.jsonl."""
    return {
        "state": state,
        "academic_year": academic_year,
        "name": name,
        "dob": dob.isoformat(),
        "roll_no": roll_no,
        "institution_code": institution_code,
        "programme": programme,
        "joined_on": joined_on.isoformat(),
        "round": round,
        "route": route,
        "category": category,
        "apaar_id": apaar_id,
    }


@pytest.fixture
def gov() -> AdapterSet:
    gov = adapters()
    gov.admission_authority = InMemoryAdmissionAuthority()
    return gov
