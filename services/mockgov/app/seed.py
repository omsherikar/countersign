"""Load the datagen registries into the mockgov database.

    python -m app.seed --from /data/generated/mockgov [--reset]

Reads apaar_registry.jsonl, counselling.jsonl, abc_credits.jsonl and sii.jsonl (file contract
in docs/API_CONTRACT.md section E) and joining_records.jsonl (the state admission authority's
joinings; tools/datagen/README.md), streams them through COPY into a staging table and merges
on each registry's natural key, so a second run with the same files changes nothing and a run
with updated rows overwrites them. A file that is missing is skipped. --reset truncates the
registries and the DigiLocker inbox first.
"""

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import asyncpg

from app.config import Settings, get_settings
from app.db import Database
from app.names import normalize_name

BATCH_SIZE = 5_000


@dataclass(frozen=True)
class RegistryFile:
    filename: str
    table: str
    columns: tuple[str, ...]
    key: tuple[str, ...]
    to_row: Callable[[dict], tuple]


def _date(value: str) -> date:
    return date.fromisoformat(str(value))


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _apaar(record: dict) -> tuple:
    return (
        str(record["apaar_id"]),
        record["name"],
        normalize_name(record["name"]),
        _date(record["dob"]),
        record.get("gender"),
    )


def _counselling(record: dict) -> tuple:
    return (
        str(record["state"]).upper(),
        int(record["year"]),
        record["name"],
        normalize_name(record["name"]),
        _date(record["dob"]),
        str(record["roll_no"]),
        str(record["programme"]),
        str(record["institution_aicte_id"]),
        int(record["round"]),
        str(record["category"]),
        str(record["allotment_ref"]),
    )


def _abc(record: dict) -> tuple:
    issuer = record.get("issuer") or {}
    return (
        str(record["apaar_id"]),
        str(record["academic_year"]),
        int(record["sem"]),
        int(record["credits"]),
        _timestamp(record["uploaded_at"]),
        str(record["result"]),
        issuer.get("type"),
        issuer.get("code"),
        issuer.get("name"),
    )


def _sii(record: dict) -> tuple:
    return (
        str(record["passport_no"]).upper(),
        record["name"],
        normalize_name(record["name"]),
        str(record["nationality"]).upper(),
        str(record["institution_aicte_id"]),
        str(record["programme"]),
        str(record["academic_year"]),
    )


def _joining(record: dict) -> tuple:
    rnd = record.get("round")
    return (
        str(record["state"]).upper(),
        str(record["academic_year"]),
        str(record["roll_no"]),
        record["name"],
        normalize_name(record["name"]),
        _date(record["dob"]),
        record.get("gender"),
        str(record["institution_code"]),
        str(record["programme"]),
        _date(record["joined_on"]),
        None if rnd is None else int(rnd),
        str(record["route"]),
        str(record["category"]),
    )


REGISTRIES: tuple[RegistryFile, ...] = (
    RegistryFile(
        "apaar_registry.jsonl",
        "apaar_registry",
        ("apaar_id", "name", "name_normalized", "dob", "gender"),
        ("apaar_id",),
        _apaar,
    ),
    RegistryFile(
        "counselling.jsonl",
        "counselling_allotments",
        (
            "state",
            "year",
            "name",
            "name_normalized",
            "dob",
            "roll_no",
            "programme",
            "institution_aicte_id",
            "round",
            "category",
            "allotment_ref",
        ),
        ("roll_no",),
        _counselling,
    ),
    RegistryFile(
        "abc_credits.jsonl",
        "abc_credits",
        (
            "apaar_id",
            "academic_year",
            "sem",
            "credits",
            "uploaded_at",
            "result",
            "issuer_type",
            "issuer_code",
            "issuer_name",
        ),
        ("apaar_id", "academic_year", "sem"),
        _abc,
    ),
    RegistryFile(
        "sii.jsonl",
        "sii_admissions",
        (
            "passport_no",
            "name",
            "name_normalized",
            "nationality",
            "institution_aicte_id",
            "programme",
            "academic_year",
        ),
        ("passport_no",),
        _sii,
    ),
    RegistryFile(
        "joining_records.jsonl",
        "admission_joinings",
        (
            "state",
            "academic_year",
            "roll_no",
            "name",
            "name_normalized",
            "dob",
            "gender",
            "institution_code",
            "programme",
            "joined_on",
            "round",
            "route",
            "category",
        ),
        ("roll_no",),
        _joining,
    ),
)

RESET_TABLES = (
    "apaar_registry",
    "counselling_allotments",
    "abc_credits",
    "sii_admissions",
    "admission_joinings",
    "digilocker_inbox",
)


def read_rows(path: Path, to_row: Callable[[dict], tuple]) -> Iterator[tuple]:
    """Parse one JSONL file into table rows, naming the line on any bad record."""
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_no}: invalid JSON ({exc.msg})") from exc
            try:
                yield to_row(record)
            except KeyError as exc:
                raise ValueError(f"{path.name}:{line_no}: missing field {exc}") from exc
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path.name}:{line_no}: {exc}") from exc


def _batches(rows: Iterable[tuple], size: int) -> Iterator[list[tuple]]:
    batch: list[tuple] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


async def load_registry(conn: asyncpg.Connection, spec: RegistryFile, path: Path) -> int:
    """COPY the file into a staging table and merge it into the registry. Returns rows read."""
    stage = f"_stage_{spec.table}"
    cols = ", ".join(spec.columns)
    key = ", ".join(spec.key)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in spec.columns if c not in spec.key)

    read = 0
    async with conn.transaction():
        # Same column types as the registry, none of its constraints or serial defaults.
        await conn.execute(
            f"CREATE TEMP TABLE {stage} ON COMMIT DROP AS "
            f"SELECT {cols} FROM {spec.table} WITH NO DATA"
        )
        for batch in _batches(read_rows(path, spec.to_row), BATCH_SIZE):
            await conn.copy_records_to_table(stage, records=batch, columns=list(spec.columns))
            read += len(batch)
        # DISTINCT ON keeps the last occurrence of a duplicated key within one file.
        await conn.execute(
            f"INSERT INTO {spec.table} ({cols}) "
            f"SELECT DISTINCT ON ({key}) {cols} FROM {stage} ORDER BY {key}, ctid DESC "
            f"ON CONFLICT ({key}) DO UPDATE SET {updates}"
        )
    return read


async def count_rows(conn: asyncpg.Connection, table: str) -> int:
    return await conn.fetchval(f"SELECT count(*) FROM {table}")


async def run(from_dir: Path, reset: bool, settings: Settings | None = None) -> dict[str, dict]:
    """Seed every registry file found under from_dir. Returns {table: {read, total}}."""
    settings = settings or get_settings()
    if not from_dir.is_dir():
        raise FileNotFoundError(f"{from_dir} is not a directory")

    db = Database(settings.database_url())
    try:
        await db.create_all()
    finally:
        await db.dispose()

    summary: dict[str, dict] = {}
    conn = await asyncpg.connect(settings.asyncpg_dsn())
    try:
        if reset:
            tables = ", ".join(RESET_TABLES)
            await conn.execute(f"TRUNCATE {tables} RESTART IDENTITY")
        for spec in REGISTRIES:
            path = from_dir / spec.filename
            read = await load_registry(conn, spec, path) if path.exists() else None
            summary[spec.table] = {"read": read, "total": await count_rows(conn, spec.table)}
    finally:
        await conn.close()
    return summary


def print_summary(summary: dict[str, dict], elapsed: float) -> None:
    print(f"{'table':<24}{'read':>10}{'total':>10}")
    for table, counts in summary.items():
        read = "missing" if counts["read"] is None else counts["read"]
        print(f"{table:<24}{read:>10}{counts['total']:>10}")
    print(f"done in {elapsed:.1f}s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.seed", description="Load datagen registries into mockgov."
    )
    parser.add_argument("--from", dest="from_dir", required=True, type=Path)
    parser.add_argument("--reset", action="store_true", help="truncate the registries first")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    try:
        summary = asyncio.run(run(args.from_dir, args.reset))
    except (FileNotFoundError, ValueError) as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1
    print_summary(summary, time.perf_counter() - started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
