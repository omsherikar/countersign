"""Configuration: datagen.yaml (sizes, anomaly counts) and rules.yaml (seat pools)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
DATAGEN_YAML = PROJECT_DIR / "datagen.yaml"

RULES_CANDIDATES = (
    Path("rules.yaml"),
    Path("../../rules.yaml"),
    PROJECT_DIR / "rules.yaml",
    PROJECT_DIR.parent.parent / "rules.yaml",
)


def rules_path() -> Path:
    """RULES_PATH if set, else ./rules.yaml, else ../../rules.yaml (repo root)."""
    env = os.environ.get("RULES_PATH")
    if env:
        return Path(env)
    for candidate in RULES_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("rules.yaml not found; set RULES_PATH")


def load_rules(path: Path | None = None) -> dict[str, Any]:
    with open(path or rules_path(), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_datagen_config(path: Path | None = None) -> dict[str, Any]:
    with open(path or DATAGEN_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@cache
def load_data(name: str) -> Any:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


@dataclass(frozen=True)
class SizeConfig:
    name: str
    institutions: int
    target_students: int
    programmes_per_institution: tuple[int, int]
    year1_fill: tuple[float, float]
    xlsx: bool


@dataclass(frozen=True)
class Config:
    size: SizeConfig
    academic_year: str
    anomalies: dict[str, int]
    ghost_ring: dict[str, tuple[int, int]]
    rules: dict[str, Any]
    scenarios: bool

    @classmethod
    def build(
        cls,
        size: str,
        *,
        scenarios: bool = True,
        datagen_yaml: Path | None = None,
        rules_yaml: Path | None = None,
    ) -> Config:
        raw = load_datagen_config(datagen_yaml)
        if size not in raw["sizes"]:
            raise ValueError(f"unknown size {size!r}; choose one of {sorted(raw['sizes'])}")
        s = raw["sizes"][size]
        size_cfg = SizeConfig(
            name=size,
            institutions=int(s["institutions"]),
            target_students=int(s["target_students"]),
            programmes_per_institution=tuple(s["programmes_per_institution"]),
            year1_fill=tuple(s["year1_fill"]),
            xlsx=bool(s.get("xlsx", True)),
        )
        anomalies = {
            name: (int(spec[size]) if spec.get("enabled", True) else 0)
            for name, spec in raw["anomalies"].items()
        }
        ring = {k: tuple(v) for k, v in raw["ghost_ring"].items()}
        return cls(
            size=size_cfg,
            academic_year=raw["academic_year"],
            anomalies=anomalies,
            ghost_ring=ring,
            rules=load_rules(rules_yaml),
            scenarios=scenarios,
        )
