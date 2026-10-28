"""Upload wire shapes (API_CONTRACT §A2.4 to §A2.8)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UploadCounts(BaseModel):
    rows: int = 0
    accepted: int = 0
    errors: int = 0
    warnings: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    withdrawn: int = 0
    transferred: int = 0
    seated: int = 0
    released: int = 0
    unseated: int = 0
    flags_raised: int = 0
    flags_updated: int = 0


class UploadSourceStat(BaseModel):
    source: str
    calls: int
    unavailable: int


class SameFile(BaseModel):
    batch_id: str
    uploaded_at: str


class Uploader(BaseModel):
    id: str
    name: str


class UploadBatchOut(BaseModel):
    id: str
    institution_id: str
    institution_name: str
    academic_year: str
    filename: str
    source: str
    kind: str
    status: str
    stage: str | None
    total_rows: int
    stage_total: int
    processed_rows: int
    progress_pct: int
    counts: UploadCounts
    sources: list[UploadSourceStat]
    timings_ms: dict[str, int]
    error: str | None
    ignored_columns: list[str]
    same_file_as: SameFile | None
    uploaded_by: Uploader
    uploaded_at: str
    started_at: str | None
    finished_at: str | None


class UploadAccepted(BaseModel):
    batch: UploadBatchOut


class UploadRowErrorOut(BaseModel):
    row_no: int
    level: str
    field: str | None
    code: str
    message: str
    value_masked: str | None


class UploadRowsIn(BaseModel):
    """POST /uploads/rows. Loosely typed so every problem gets the contract's own message."""

    academic_year: Any = None
    institution_id: Any = None
    declaration: Any = None
    label: Any = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
