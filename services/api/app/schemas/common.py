"""Shared wire shapes: pagination envelope, countersign block, flag refs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 200


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams(BaseModel):
    page: int = 1
    page_size: int = PAGE_SIZE_DEFAULT

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Score(BaseModel):
    passes: int
    applicable: int


class CheckBrief(BaseModel):
    type: str
    status: str


class CheckOut(BaseModel):
    """A full check row (only in GET /enrolments/{id})."""

    type: str
    status: str
    source: str
    checked_at: str | None
    attempts: int = 0
    detail: dict[str, Any] = Field(default_factory=dict)


class Countersign(BaseModel):
    """The compact block in lists: score and [{type, status}] in check order."""

    score: Score | None = None
    checks: list[CheckBrief] = Field(default_factory=list)


class FlagRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    severity: str
    status: str


class FlagSummary(FlagRef):
    summary: str
    created_at: str


class InstitutionRef(BaseModel):
    id: str
    name: str
    aicte_permanent_id: str
    state_code: str
    state_name: str
    region: str


class ProgrammeRef(BaseModel):
    id: str
    code: str
    name: str


class IdName(BaseModel):
    id: str
    name: str
