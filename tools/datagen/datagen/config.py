"""Configuration: datagen.yaml (sizes, anomaly counts) and rules.yaml (seat pools)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
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
        # skip empty placeholders left by the compose bind mount of rules.yaml
        if candidate.is_file() and candidate.stat().st_size > 0:
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
class UpdateConfig:
    colleges: int
    withdrawals: tuple[int, int]
    transfers: tuple[int, int]
    refills: tuple[int, int]
    status_dates: tuple[str, str]


@dataclass(frozen=True)
class GraduateConfig:
    academic_year: str
    year_of_award: int
    count: int
    abc: int
    university: str
    university_share: float
    other_universities: int
    provisional: tuple[int, int]
    status_dates: tuple[str, str]


def for_size(value: Any, size: str) -> Any:
    """Resolve every `{small: .., full: ..}` mapping inside `value` to the size's entry."""
    if isinstance(value, dict):
        if set(value) == {"small", "full"}:
            return value[size]
        return {k: for_size(v, size) for k, v in value.items()}
    return value


@dataclass(frozen=True)
class Config:
    size: SizeConfig
    academic_year: str
    anomalies: dict[str, int]
    ghost_ring: dict[str, tuple[int, int]]
    updates: UpdateConfig
    graduates: GraduateConfig
    rules: dict[str, Any]
    scenarios: bool
    autonomous_share: float = 0.30
    joining: dict[str, Any] = field(default_factory=dict)
    eligibility: dict[str, Any] = field(default_factory=dict)
    signals: dict[str, Any] = field(default_factory=dict)
    statuses: dict[str, Any] = field(default_factory=dict)

    def reporting_deadline(self, academic_year: str) -> str:
        """rules.yaml `reporting.deadline` (a date, or a mapping by year), else datagen.yaml,
        else 30 September of the year's start."""
        configured = (self.rules.get("reporting") or {}).get("deadline")
        if isinstance(configured, dict) and configured.get(academic_year):
            return str(configured[academic_year])
        if isinstance(configured, str) and academic_year == self.academic_year:
            return configured
        fallback = self.joining.get("reporting_deadline", {}).get(academic_year)
        return str(fallback) if fallback else f"{academic_year[:4]}-09-30"

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
        u = raw["updates"]
        updates = UpdateConfig(
            colleges=int(u["colleges"][size]),
            withdrawals=tuple(u["withdrawals"]),
            transfers=tuple(u["transfers"]),
            refills=tuple(u["refills"]),
            status_dates=tuple(u["status_dates"]),
        )
        g = raw["graduates"]
        graduates = GraduateConfig(
            academic_year=g["academic_year"],
            year_of_award=int(g["year_of_award"]),
            count=int(g["count"][size]),
            abc=int(g["abc"][size]),
            university=g["university"],
            university_share=float(g["university_share"]),
            other_universities=int(g["other_universities"]),
            provisional=tuple(g["provisional"]),
            status_dates=tuple(g["status_dates"]),
        )
        return cls(
            size=size_cfg,
            academic_year=raw["academic_year"],
            anomalies=anomalies,
            ghost_ring=ring,
            updates=updates,
            graduates=graduates,
            rules=load_rules(rules_yaml),
            scenarios=scenarios,
            autonomous_share=float(raw.get("autonomous_share", 0.30)),
            joining=for_size(raw.get("joining", {}), size),
            eligibility=for_size(raw.get("eligibility", {}), size),
            signals=for_size(raw.get("signals", {}), size),
            statuses=for_size(raw.get("statuses", {}), size),
        )
