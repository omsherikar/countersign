"""Shared wire shapes: pagination envelope, flag and institution refs."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict

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
