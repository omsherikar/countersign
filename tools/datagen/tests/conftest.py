import csv
import json
from pathlib import Path

import pytest

from datagen.cli import generate


class Generated:
    """A generated directory with lazy, cached readers for the files under test."""

    def __init__(self, path: Path, summary: dict):
        self.path = path
        self.summary = summary
        self._uploads: dict[str, list[dict]] = {}

    def json(self, name: str):
        with open(self.path / name, encoding="utf-8") as fh:
            return json.load(fh)

    def jsonl(self, name: str) -> list[dict]:
        with open(self.path / "mockgov" / name, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def upload(self, aicte_id: str, year: str = "2026-27") -> list[dict]:
        key = f"{aicte_id}_{year}"
        if key not in self._uploads:
            with open(self.path / "uploads" / f"{key}.csv", encoding="utf-8", newline="") as fh:
                self._uploads[key] = list(csv.DictReader(fh))
        return self._uploads[key]

    def upload_columns(self, aicte_id: str, year: str = "2026-27") -> list[str]:
        with open(self.path / "uploads" / f"{aicte_id}_{year}.csv", encoding="utf-8") as fh:
            return fh.readline().rstrip("\n").split(",")

    def all_uploads(self) -> dict[str, list[dict]]:
        inst = self.json("institutions.json")["institutions"]
        return {i["aicte_permanent_id"]: self.upload(i["aicte_permanent_id"]) for i in inst}


@pytest.fixture(scope="session")
def small(tmp_path_factory) -> Generated:
    out = tmp_path_factory.mktemp("small")
    summary = generate("small", 42, out, scenarios=True)
    return Generated(out, summary)


@pytest.fixture(scope="session")
def small_no_scenarios(tmp_path_factory) -> Generated:
    out = tmp_path_factory.mktemp("small_plain")
    summary = generate("small", 42, out, scenarios=False, xlsx=False)
    return Generated(out, summary)
