"""The upload spool: the uploaded bytes, Fernet-encrypted, waiting for the worker.

`<upload_spool_dir>/<batch_id>.<csv|xlsx|json>.enc`, written by the api before the batch is
committed as QUEUED and deleted when the batch is DONE or FAILED (ENGINES.md §5 rule 9).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.crypto import _fernet  # the PII_FERNET_KEY cipher; crypto has no bytes helper
from app.engine.upload.types import FileKind

KINDS: tuple[FileKind, ...] = ("csv", "xlsx", "json")


def spool_dir() -> Path:
    return Path(get_settings().upload_spool_dir)


def spool_path(batch_id: uuid.UUID, kind: FileKind) -> Path:
    return spool_dir() / f"{batch_id}.{kind}.enc"


def write_spool(batch_id: uuid.UUID, kind: FileKind, data: bytes) -> Path:
    path = spool_path(batch_id, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(_fernet().encrypt(data))
    tmp.replace(path)
    return path


def find_spool(batch_id: uuid.UUID) -> tuple[FileKind, Path] | None:
    for kind in KINDS:
        path = spool_path(batch_id, kind)
        if path.is_file():
            return kind, path
    return None


def read_spool(path: Path) -> bytes:
    return _fernet().decrypt(path.read_bytes())


def delete_spool(batch_id: uuid.UUID) -> None:
    for kind in KINDS:
        spool_path(batch_id, kind).unlink(missing_ok=True)


def canonical_rows(rows: list[dict[str, Any]]) -> bytes:
    """API rows as canonical JSON: what is spooled and hashed for POST /uploads/rows."""
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
