"""GET /reports and GET /reports/{name}.{format} (API_CONTRACT §A4.21, §A4.23, D46).

AICTE officers read national reports (or one region or state); a regional officer reads its
own region (or one of its states). Every download writes a READ audit entry with the report,
its format and scope; reports hold aggregates only.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from app.core import audit
from app.core.config import get_settings
from app.core.deps import RequestId, SessionDep, require_roles
from app.core.errors import ApiError
from app.models.enums import AuditAction, UserRole
from app.models.user import User
from app.reports import queries, registry, render

log = logging.getLogger("countersign.reports")

router = APIRouter(prefix="/reports", tags=["reports"])

OfficerUser = Annotated[User, Depends(require_roles(UserRole.AICTE_ADMIN, UserRole.RO_OFFICER))]
MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


class ReportInfo(BaseModel):
    name: str
    title: str
    formats: list[str]
    columns: list[str]


class ReportList(BaseModel):
    items: list[ReportInfo]


def _by(user: User) -> str:
    """Who generated the file, for the PDF footer."""
    if user.role is UserRole.RO_OFFICER and user.region is not None:
        return f"the {user.region.name} regional office"
    return "an AICTE officer"


@router.get("", response_model=ReportList)
async def list_reports(user: OfficerUser) -> ReportList:
    return ReportList(
        items=[
            ReportInfo(
                name=spec.name,
                title=spec.title,
                formats=list(spec.formats),
                columns=list(spec.columns),
            )
            for spec in registry.REPORTS.values()
        ]
    )


@router.get("/{name}.{fmt}")
async def download_report(
    name: str,
    fmt: str,
    session: SessionDep,
    user: OfficerUser,
    request_id: RequestId,
    academic_year: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    region: Annotated[str | None, Query(max_length=20)] = None,
    state: Annotated[str | None, Query(max_length=2)] = None,
) -> Response:
    spec = registry.find(name, fmt)
    if spec is None:
        raise ApiError(404, "REPORT_NOT_FOUND", "Report not found.")
    scope = await registry.scope_for(
        session,
        user,
        region=None if user.role is UserRole.RO_OFFICER else region,
        state=state,
    )
    year = academic_year or get_settings().academic_year
    if spec.name == "summary":
        data = await queries.summary(session, scope, year)
        rows = []
    else:
        rows = await spec.rows(session, scope, year)
    try:
        if spec.name == "summary":
            body = render.summary_pdf(data, scope, year, by=_by(user))
        elif fmt == "csv":
            body = render.to_csv(spec, rows)
        elif fmt == "xlsx":
            body = render.to_xlsx(spec, rows, scope, year)
        else:
            body = render.to_pdf(spec, rows, scope, year, by=_by(user))
    except Exception:
        if fmt == "csv":
            raise
        # the CSV of the same report is the fallback (copy deck err.REPORT_FAILED)
        log.exception("report render failed", extra={"report": name, "format": fmt})
        raise ApiError(500, "REPORT_FAILED", "The report could not be prepared.") from None
    await audit.record(
        session,
        user.id,
        AuditAction.READ,
        "report",
        None,
        after={"name": spec.name, "format": fmt, "scope": scope.slug},
        request_id=request_id,
    )
    filename = f"countersign_{spec.name}_{year}_{scope.slug}.{fmt}"
    return Response(
        content=body,
        media_type=MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
