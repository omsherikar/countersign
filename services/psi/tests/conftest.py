"""Shared fixtures: a small synthetic registry file and the HMAC key the api tests use."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

KEY = "00" * 32


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    """200 synthetic APAAR registry lines, the shape datagen writes."""
    path = tmp_path / "apaar_registry.jsonl"
    lines = [
        json.dumps({"apaar_id": f"{100000000000 + i * 7919}", "name": f"Student {i}"})
        for i in range(200)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
