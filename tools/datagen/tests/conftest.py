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
        self._files: dict[str, list[dict]] = {}
        self._json: dict[str, object] = {}

    def json(self, name: str):
        if name not in self._json:
            with open(self.path / name, encoding="utf-8") as fh:
                self._json[name] = json.load(fh)
        return self._json[name]

    def jsonl(self, name: str) -> list[dict]:
        return self.lines(f"mockgov/{name}")

    def lines(self, relative: str) -> list[dict]:
        """Records of a JSON Lines file, by its path relative to the output directory."""
        with open(self.path / relative, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def file(self, relative: str) -> list[dict]:
        """Rows of any upload file, by its path relative to the output directory."""
        if relative not in self._files:
            with open(self.path / relative, encoding="utf-8", newline="") as fh:
                self._files[relative] = list(csv.DictReader(fh))
        return self._files[relative]

    def row(self, relative: str, row_no: int) -> dict:
        """The data row at spreadsheet row `row_no` (the header is row 1)."""
        assert row_no >= 2
        return self.file(relative)[row_no - 2]

    def upload(self, aicte_id: str, year: str = "2026-27") -> list[dict]:
        return self.file(f"uploads/{aicte_id}_{year}.csv")

    def upload_columns(self, aicte_id: str, year: str = "2026-27") -> list[str]:
        with open(self.path / "uploads" / f"{aicte_id}_{year}.csv", encoding="utf-8") as fh:
            return fh.readline().rstrip("\n").split(",")

    def all_uploads(self) -> dict[str, list[dict]]:
        inst = self.json("institutions.json")["institutions"]
        return {i["aicte_permanent_id"]: self.upload(i["aicte_permanent_id"]) for i in inst}

    def update_files(self) -> list[str]:
        return sorted(f"uploads/{p.name}" for p in (self.path / "uploads").glob("*_update*.csv"))

    def institutions(self) -> dict[str, dict]:
        return {i["aicte_permanent_id"]: i for i in self.json("institutions.json")["institutions"]}


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
