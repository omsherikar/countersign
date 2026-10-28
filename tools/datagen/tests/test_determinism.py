"""Same seed, same bytes. Different seed, different data."""

import hashlib
import json
from pathlib import Path

from datagen.cli import generate, main

VOLATILE = {"manifest.json", "summary.json"}


def digests(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def stable_part(root: Path, name: str) -> dict:
    data = json.loads((root / name).read_text(encoding="utf-8"))
    data.pop("generated_at", None)
    data.pop("timings_seconds", None)
    return data


def test_two_runs_with_the_same_seed_are_byte_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate("small", 42, a)
    generate("small", 42, b)
    da, db = digests(a), digests(b)
    assert set(da) == set(db)
    for name in da:
        if Path(name).name in VOLATILE:
            continue
        assert da[name] == db[name], name
    for name in VOLATILE:
        assert stable_part(a, name) == stable_part(b, name)
    assert any(name.endswith(".xlsx") for name in da)


def test_different_seed_changes_the_data(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    generate("small", 1, a, xlsx=False)
    generate("small", 2, b, xlsx=False)
    da, db = digests(a), digests(b)
    assert da["uploads/1-ABC-0001_2026-27.csv"] != db["uploads/1-ABC-0001_2026-27.csv"]
    assert da["institutions.json"] != db["institutions.json"]


def test_cli_generate_and_summary(tmp_path, capsys):
    out = tmp_path / "cli"
    assert main(["generate", "--size", "small", "--seed", "7", "--out", str(out), "--no-xlsx"]) == 0
    assert main(["summary", str(out)]) == 0
    text = capsys.readouterr().out
    assert "datagen small seed=7" in text
    assert "ground truth by type" in text
    assert "XLSX uploads skipped" in text
