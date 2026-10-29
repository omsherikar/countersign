"""Private set intersection (API_CONTRACT §A4.26)."""

from __future__ import annotations

from pydantic import BaseModel


class PsiResult(BaseModel):
    countersign_count: int
    partner_count: int
    overlap: int
    computed_at: str
    method: str
