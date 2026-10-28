"""Turning an upload into students and enrolments: parse, validate, upsert (ENGINES.md §5)."""

from app.engine.upload.parse import parse_rows, parse_upload
from app.engine.upload.types import (
    UPLOAD_COLUMNS,
    CleanRow,
    ParsedUpload,
    RowIssue,
    UploadFileError,
    UpsertResult,
    ValidationContext,
    ValidationResult,
)
from app.engine.upload.upsert import upsert_rows
from app.engine.upload.validate import file_duplicates, validate_rows

__all__ = [
    "UPLOAD_COLUMNS",
    "CleanRow",
    "ParsedUpload",
    "RowIssue",
    "UploadFileError",
    "UpsertResult",
    "ValidationContext",
    "ValidationResult",
    "file_duplicates",
    "parse_rows",
    "parse_upload",
    "upsert_rows",
    "validate_rows",
]
