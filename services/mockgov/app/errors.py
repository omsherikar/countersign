"""Error envelope shared with the Countersign API: {"error": {code, message, details}}."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class MockGovError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class SourceDown(MockGovError):
    def __init__(self, message: str) -> None:
        super().__init__(503, "SOURCE_DOWN", message)


def envelope(
    status_code: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


_STATUS_CODES = {
    404: ("NOT_FOUND", "Not found."),
    405: ("METHOD_NOT_ALLOWED", "Method not allowed."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "Send application/json."),
}


def _field_name(loc: tuple) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "body"


def _clean_message(msg: str) -> str:
    # Pydantic prefixes custom validator messages with "Value error, ".
    prefix = "Value error, "
    return msg[len(prefix) :] if msg.startswith(prefix) else msg


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(MockGovError)
    async def _mockgov_error(_: Request, exc: MockGovError) -> JSONResponse:
        return envelope(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"field": _field_name(tuple(err.get("loc", ()))), "message": _clean_message(err["msg"])}
            for err in exc.errors()
        ]
        message = fields[0]["message"] if fields else "Invalid request."
        return envelope(422, "VALIDATION_ERROR", message, {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _STATUS_CODES.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
        return envelope(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        return envelope(500, "INTERNAL", "Internal error.")
