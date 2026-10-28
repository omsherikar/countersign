"""Files a college sends with its response (D25, API_CONTRACT §A3.11).

The type is read from the file's first bytes, never from its name or declared type. Each
file is Fernet-encrypted with PII_FERNET_KEY, like the upload spool, and written to
CASE_FILES_DIR under a random name through a temporary file and a rename; the database
keeps the original name, the type, the size and the SHA-256 of the original bytes.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath

from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.core.crypto import _fernet  # the PII_FERNET_KEY cipher; crypto has no bytes helper
from app.core.errors import ApiError

MAX_FILES = 3
MAX_FILE_BYTES = 5_242_880
MAX_BODY_BYTES = 16 * 1024 * 1024
SIGNATURES = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}
FILENAME_MAX = 120
_KEY = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True, slots=True)
class StoredFile:
    storage_key: str  # uuid4 hex
    filename: str  # cleaned
    content_type: str
    size_bytes: int
    sha256: str  # of the original bytes


def files_dir() -> Path:
    return Path(get_settings().case_files_dir)


def sniff(head: bytes) -> str | None:
    """The content type the first bytes prove, or None."""
    for signature, content_type in SIGNATURES.items():
        if head.startswith(signature):
            return content_type
    return None


def clean_filename(name: str | None) -> str:
    """Base name only, control characters dropped, at most 120 characters."""
    base = PurePath((name or "").replace("\\", "/")).name
    base = "".join(ch for ch in base if unicodedata.category(ch)[0] != "C").strip()
    if not base.strip("."):
        return "attachment"
    return base[:FILENAME_MAX]


def too_large(filename: str | None = None) -> ApiError:
    details: dict[str, object] = {"max_bytes": MAX_FILE_BYTES}
    if filename is not None:
        details = {"filename": filename, **details}
    return ApiError(413, "ATTACHMENT_TOO_LARGE", "Each file can be at most 5 MB.", details)


def wrong_type(filename: str) -> ApiError:
    return ApiError(
        415,
        "ATTACHMENT_TYPE",
        "Only PDF, PNG and JPEG files can be attached.",
        {"filename": filename},
    )


async def check(upload: UploadFile) -> tuple[str, str, bytes]:
    """(clean name, content type, bytes) of a valid file; 413 or 415 otherwise."""
    filename = clean_filename(upload.filename)
    data = await upload.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise too_large(filename)
    content_type = sniff(data[:16])
    if content_type is None:
        raise wrong_type(filename)
    return filename, content_type, data


def _write(filename: str, content_type: str, data: bytes) -> StoredFile:
    key = uuid.uuid4().hex
    directory = files_dir()
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{key}.tmp"
    tmp.write_bytes(_fernet().encrypt(data))
    tmp.replace(directory / key)
    return StoredFile(
        storage_key=key,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


async def store(upload: UploadFile) -> StoredFile:
    """Check one file and write it encrypted; 413 ATTACHMENT_TOO_LARGE, 415 ATTACHMENT_TYPE."""
    return _write(*(await check(upload)))


async def store_all(uploads: Sequence[UploadFile]) -> list[StoredFile]:
    """Every file or none: each is checked before any is written."""
    checked = [await check(upload) for upload in uploads]
    stored: list[StoredFile] = []
    try:
        for item in checked:
            stored.append(_write(*item))
    except BaseException:
        discard(s.storage_key for s in stored)
        raise
    return stored


def _path(storage_key: str) -> Path:
    if not _KEY.match(storage_key):
        raise ValueError("not a storage key")
    return files_dir() / storage_key


def read(storage_key: str) -> bytes:
    """The original bytes."""
    return _fernet().decrypt(_path(storage_key).read_bytes())


def discard(storage_keys: Iterable[str]) -> None:
    for key in storage_keys:
        _path(key).unlink(missing_ok=True)
