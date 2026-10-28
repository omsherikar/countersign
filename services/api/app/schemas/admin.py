"""Admin endpoints: adapter ping, audit verify, audit list, chaos passthrough (A.11 to A.13)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourcePing(BaseModel):
    status: str  # OK | UNAVAILABLE | DISABLED
    latency_ms: int
    detail: str | None


class AdapterPing(BaseModel):
    adapter: str
    sources: dict[str, SourcePing]
    checked_at: str


class AuditVerify(BaseModel):
    ok: bool
    length: int
    first_broken_seq: int | None
    checked_at: str


class AuditRow(BaseModel):
    seq: int
    at: str
    actor_id: str | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str | None
    hash: str
    prev_hash: str | None


class ChaosRequest(BaseModel):
    source: str
    latency_ms: int = Field(default=0, ge=0)
    fail_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    down: bool = False


class RegionMeta(BaseModel):
    code: str
    name: str
    hq_city: str


class StateMeta(BaseModel):
    code: str
    name: str
    region: str


class ItemsOnly(BaseModel):
    items: list[Any]
