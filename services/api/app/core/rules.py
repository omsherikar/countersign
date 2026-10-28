"""rules.yaml loader. Every number carries its handbook source."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


class Handbook(BaseModel):
    edition: str
    verified_on: str


class RegularPool(BaseModel):
    share: float
    supernumerary: bool
    source: str


class NriPool(BaseModel):
    share: float
    carved_from: str = "REGULAR"
    supernumerary: bool
    unfilled: str | None = None
    source: str


class TfwPool(BaseModel):
    share: float
    supernumerary: bool
    condition: str | None = None
    unfilled: str | None = None
    source: str


class LateralPool(BaseModel):
    share: float
    supernumerary: bool
    plus_first_year_vacancies: bool = False
    source: str


class SlabMatch(BaseModel):
    discipline_group: list[str]
    level: list[str]

    @field_validator("discipline_group", "level", mode="before")
    @classmethod
    def _listify(cls, value: Any) -> list[str]:
        return [value] if isinstance(value, str) else list(value)


class InternationalSlab(BaseModel):
    match: SlabMatch
    share: float
    source: str


class InternationalPool(BaseModel):
    supernumerary: bool
    ciwg_reserved_fraction: float
    unfilled: str | None = None
    slabs: list[InternationalSlab]
    lateral_combined_cap: float | None = None
    lateral_combined_cap_source: str | None = None

    def slab_for(self, discipline: str, level: str) -> InternationalSlab | None:
        for slab in self.slabs:
            if discipline in slab.match.discipline_group and level in slab.match.level:
                return slab
        return None


class SeatPoolRules(BaseModel):
    REGULAR: RegularPool
    NRI: NriPool
    TFW: TfwPool
    LATERAL: LateralPool
    INTERNATIONAL: InternationalPool


class ReservationRule(BaseModel):
    share: float
    source: str


class AdmissionRouteRule(BaseModel):
    pool: str
    admission_check: str


class ApaarRules(BaseModel):
    format: str
    optional: bool = True


class NameMatching(BaseModel):
    pass_threshold: int
    review_threshold: int
    dob_must_match: bool = True


class DualEnrolment(BaseModel):
    allowed_modes: list[list[str]]


class GhostRing(BaseModel):
    min_component_cross_college: int
    min_colleges: int
    min_component_single_college: int


class IntegrityIndex(BaseModel):
    weights: dict[str, float]


class Rules(BaseModel):
    model_config = ConfigDict(extra="ignore")

    handbook: Handbook
    seat_pools: SeatPoolRules
    reservation: dict[str, ReservationRule] = Field(default_factory=dict)
    admission_routes: dict[str, AdmissionRouteRule]
    apaar: ApaarRules
    name_matching: NameMatching
    cutoff_dates: dict[str, str] = Field(default_factory=dict)
    dual_enrolment: DualEnrolment | None = None
    ghost_ring: GhostRing | None = None
    integrity_index: IntegrityIndex | None = None


def load_rules(path: str | Path | None = None) -> Rules:
    target = Path(path) if path else get_settings().resolved_rules_path()
    with open(target, encoding="utf-8") as fh:
        return Rules.model_validate(yaml.safe_load(fh))


@lru_cache
def get_rules() -> Rules:
    return load_rules()
