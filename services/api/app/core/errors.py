"""The error envelope: every non-2xx body is {"error": {code, message, details}}."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("countersign.errors")

_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "SOURCE_UNAVAILABLE",
}

_STATUS_MESSAGES = {
    401: "Sign in to continue.",
    403: "Your role cannot access this resource.",
    404: "Not found.",
    405: "Method not allowed.",
    415: "Request bodies must be application/json.",
    429: "Too many requests. Try again shortly.",
}


class ApiError(StarletteHTTPException):
    """An HTTP error that already knows its envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.message = message
        self.details = details or {}


def envelope(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
        headers=headers,
    )


def unauthenticated() -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", "Sign in to continue.")


def forbidden(required_roles: list[str]) -> ApiError:
    return ApiError(
        403,
        "FORBIDDEN",
        "Your role cannot access this resource.",
        {"required_roles": required_roles},
    )


def not_found(what: str = "Resource") -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} not found.")


async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return envelope(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _STATUS_CODES.get(exc.status_code, "INTERNAL")
    message = _STATUS_MESSAGES.get(exc.status_code) or (
        exc.detail if isinstance(exc.detail, str) else "Request failed."
    )
    return envelope(exc.status_code, code, message, {}, exc.headers)


async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        fields.append({"field": ".".join(loc) or "body", "message": err.get("msg", "invalid")})
    return envelope(422, "VALIDATION_ERROR", "Request is not valid.", {"fields": fields})


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = 60
    return envelope(
        429,
        "RATE_LIMITED",
        "Too many requests. Try again shortly.",
        {"retry_after": retry_after, "limit": str(exc.detail)},
        {"Retry-After": str(retry_after)},
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", extra={"path": request.url.path})
    return envelope(500, "INTERNAL", "Something went wrong on our side.")


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
