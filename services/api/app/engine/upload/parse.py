"""PARSE: read a CSV, XLSX or JSON rows into raw rows and check the header (API_CONTRACT §A2.2).

Headers are matched after trimming, lower-casing and turning spaces and hyphens into
underscores. Unknown headers are reported in `ignored_columns`. A missing required header
or a header that appears twice rejects the file. Blank rows are skipped and not counted;
`row_no` is the spreadsheet row number (header row 1), or the 1-based position for rows.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engine.upload.types import (
    REQUIRED_COLUMNS,
    UPLOAD_COLUMNS,
    FileKind,
    ParsedUpload,
    RawRow,
    UploadFileError,
)

_KNOWN = frozenset(UPLOAD_COLUMNS)

UNREADABLE = "The file could not be read as CSV or XLSX."
NOT_UTF8 = "The file is not UTF-8 text. Save it as CSV UTF-8 and upload it again."
EMPTY = "The file has a header but no rows."


def normalise_header(text: str) -> str:
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def file_kind(filename: str) -> FileKind | None:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith(".xlsx"):
        return "xlsx"
    return None


def too_many_rows(limit: int) -> UploadFileError:
    return UploadFileError(
        "TOO_MANY_ROWS", f"The file has more than {limit:,} rows. Split it and upload each part."
    )


def cell_text(value: Any) -> str:
    """A cell or JSON value as text: dates as YYYY-MM-DD, whole numbers without a decimal point."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _check_header(cells: list[Any]) -> tuple[list[tuple[int, str]], list[str]]:
    """(column index, known column) pairs and the ignored header texts; raises on a bad header."""
    known: list[tuple[int, str]] = []
    ignored: list[str] = []
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for index, cell in enumerate(cells):
        text = cell_text(cell)
        if not text:
            continue
        key = normalise_header(text)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            duplicates.append(key)
        if key in _KNOWN:
            if seen[key] == 1:
                known.append((index, key))
        elif seen[key] == 1:
            ignored.append(text)
    present = {key for _, key in known}
    missing = [column for column in REQUIRED_COLUMNS if column not in present]
    if missing or duplicates:
        if missing:
            message = f"The file is missing required columns: {', '.join(missing)}."
        else:
            message = f"The column {duplicates[0]} appears more than once."
        raise UploadFileError(
            "UPLOAD_HEADER_INVALID",
            message,
            {"missing_columns": missing, "duplicate_columns": duplicates},
        )
    return known, ignored


def _rows(
    records: Iterable[tuple[int, list[Any]]], columns: list[tuple[int, str]], max_rows: int
) -> list[RawRow]:
    rows: list[RawRow] = []
    for row_no, cells in records:
        texts = [cell_text(c) for c in cells]
        if not any(texts):
            continue
        if len(rows) >= max_rows:
            raise too_many_rows(max_rows)
        values = dict.fromkeys(UPLOAD_COLUMNS, "")
        for index, key in columns:
            if index < len(texts):
                values[key] = texts[index]
        rows.append(RawRow(row_no=row_no, values=values))
    if not rows:
        raise UploadFileError("UPLOAD_EMPTY", EMPTY)
    return rows


def _from_records(
    records: Iterator[tuple[int, list[Any]]], kind: FileKind, max_rows: int
) -> ParsedUpload:
    first = next(records, None)
    columns, ignored = _check_header(first[1] if first else [])
    return ParsedUpload(rows=_rows(records, columns, max_rows), ignored_columns=ignored, kind=kind)


def _csv_records(data: bytes) -> Iterator[tuple[int, list[Any]]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadFileError("UNSUPPORTED_FILE_TYPE", NOT_UTF8) from None
    if "\x00" in text:
        raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE)
    try:
        records = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error:
        raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE) from None
    return enumerate(records, start=1)


def _xlsx_records(data: bytes) -> Iterator[tuple[int, list[Any]]]:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:  # not a zip, not a workbook, or a workbook openpyxl cannot open
        raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE) from None
    try:
        if not workbook.worksheets:
            raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE)
        sheet = workbook.worksheets[0]
        records = [
            (row_no, list(cells))
            for row_no, cells in enumerate(sheet.iter_rows(values_only=True), start=1)
        ]
    except UploadFileError:
        raise
    except Exception:
        raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE) from None
    finally:
        workbook.close()
    return iter(records)


def parse_upload(data: bytes | Path, filename: str, *, max_rows: int | None = None) -> ParsedUpload:
    """Read a CSV (UTF-8, BOM allowed) or XLSX (first sheet). Raises UploadFileError."""
    limit = max_rows if max_rows is not None else get_settings().upload_max_rows
    if isinstance(data, Path):
        data = data.read_bytes()
    kind = file_kind(filename)
    if kind == "csv":
        return _from_records(_csv_records(data), "csv", limit)
    if kind == "xlsx":
        return _from_records(_xlsx_records(data), "xlsx", limit)
    raise UploadFileError("UNSUPPORTED_FILE_TYPE", UNREADABLE)


def parse_rows(rows: list[dict[str, Any]], *, max_rows: int | None = None) -> ParsedUpload:
    """JSON rows from POST /uploads/rows: same columns as keys, `null` means blank."""
    limit = max_rows if max_rows is not None else get_settings().upload_max_rows
    ignored: dict[str, None] = {}
    parsed: list[RawRow] = []
    for position, row in enumerate(rows, start=1):
        values = dict.fromkeys(UPLOAD_COLUMNS, "")
        seen: set[str] = set()
        for raw_key, raw_value in row.items():
            key = normalise_header(str(raw_key))
            if key in seen:
                raise UploadFileError(
                    "UPLOAD_HEADER_INVALID",
                    f"The column {key} appears more than once.",
                    {"missing_columns": [], "duplicate_columns": [key]},
                )
            seen.add(key)
            if key in _KNOWN:
                values[key] = cell_text(raw_value)
            elif str(raw_key).strip():
                ignored.setdefault(str(raw_key).strip(), None)
        if not any(values.values()):
            continue
        if len(parsed) >= limit:
            raise too_many_rows(limit)
        parsed.append(RawRow(row_no=position, values=values))
    if not parsed:
        raise UploadFileError("UPLOAD_EMPTY", EMPTY)
    return ParsedUpload(rows=parsed, ignored_columns=list(ignored), kind="json")
