"""The seed's last step: completeness when the build has it, then the signals of the year."""

from __future__ import annotations

import json

from sqlalchemy import func, select

from app.db.session import session_factory
from app.models.signal import Signal
from app.seed import derived
from tests.signals.conftest import YEAR


def test_the_year_comes_from_the_manifest(tmp_path):
    assert derived.year_from(tmp_path, "2026-27") == "2026-27"
    (tmp_path / "manifest.json").write_text(
        json.dumps({"reporting_deadline": {"2025-26": "2025-09-30"}}), encoding="utf-8"
    )
    assert derived.year_from(tmp_path, "2026-27") == "2025-26"


async def test_signals_are_derived_once_and_found_again_unchanged(ring_world):
    first = await derived.detect(YEAR)
    assert first["rings"] == 1 and first["created"] >= 1
    again = await derived.detect(YEAR)
    assert (again["created"], again["updated"]) == (0, 0)
    async with session_factory()() as session:
        count = (await session.execute(select(func.count()).select_from(Signal))).scalar_one()
    assert count == first["created"]
