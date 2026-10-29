"""datagen's ground truth and manifest, and the rows they name resolved to enrolments.

Pure: nothing here touches the database. `snapshot.take` builds the row index from the
database; `resolve` maps each ground-truth row to the enrolment it became.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any

PERF_INSTITUTION = "9-PERF-0001"
# planted types whose case names a programme and pool, or an institution and year, not rows
POOL_TYPES = frozenset({"EXCESS_ADMISSION", "QUOTA_BREACH"})
INSTITUTION_TYPES = frozenset({"MISSING_FROM_UPLOAD"})
# planted without a case, but not legitimate controls: found by signals, or no longer active
NOT_CONTROLS = frozenset({"GHOST_RING", "ANOMALY", "WITHDRAWAL", "TRANSFER"})


@dataclass(frozen=True, slots=True)
class RowRef:
    """One row of one upload file, as ground truth names it."""

    file: str  # the file name, without the directory
    row_no: int
    institution: str
    programme_code: str | None = None
    year_of_study: int | None = None

    @property
    def key(self) -> tuple[str, int]:
        return (self.file, self.row_no)


@dataclass(frozen=True, slots=True)
class TruthRecord:
    index: int
    type: str  # anomaly_type
    expected_flag: str | None
    severity: str | None
    institution: str
    institutions: tuple[str, ...]
    programme_code: str | None
    rows: tuple[RowRef, ...]
    academic_year: str | None = None
    seat_type: str | None = None
    expected_record_status: str | None = None
    # check type -> evidence state expected on the record's rows
    expected_rows: Mapping[str, str] = field(default_factory=dict)
    expected_signal: str | None = None
    expected_deadline_state: str | None = None
    note: str = ""

    @property
    def planted_case(self) -> bool:
        return self.expected_flag is not None

    @property
    def is_control(self) -> bool:
        """Legitimate special cases that must not raise a case (refused consent, CIWG, ...)."""
        return (
            self.expected_flag is None
            and self.expected_signal is None
            and self.type not in NOT_CONTROLS
            and bool(self.rows)
        )


@dataclass(slots=True)
class Truth:
    records: list[TruthRecord]
    manifest: dict[str, Any]

    @property
    def size(self) -> str | None:
        return self.manifest.get("size")

    @property
    def seed(self) -> int | None:
        return self.manifest.get("seed")

    @property
    def perf(self) -> dict[str, Any] | None:
        return self.manifest.get("perf")

    def planted(self) -> list[TruthRecord]:
        return [r for r in self.records if r.planted_case]


def _row(raw: Mapping[str, Any]) -> RowRef:
    year = raw.get("year_of_study")
    return RowRef(
        file=PurePath(str(raw["file"])).name,
        row_no=int(raw["row_no"]),
        institution=str(raw.get("institution_aicte_id") or ""),
        programme_code=raw.get("programme_code"),
        year_of_study=int(year) if year is not None else None,
    )


def _expected_rows(raw: Mapping[str, Any]) -> dict[str, str]:
    rows = dict(raw.get("expected_rows") or {})
    check = raw.get("expected_check")
    if isinstance(check, Mapping) and check.get("type") and check.get("status"):
        rows[str(check["type"])] = str(check["status"])
    return {str(k): str(v) for k, v in rows.items()}


def parse_records(raw: Sequence[Mapping[str, Any]]) -> list[TruthRecord]:
    out: list[TruthRecord] = []
    for index, item in enumerate(raw):
        institution = str(item.get("institution_aicte_id") or "")
        institutions = tuple(
            item.get("institution_aicte_ids") or ([institution] if institution else [])
        )
        out.append(
            TruthRecord(
                index=index,
                type=str(item["anomaly_type"]),
                expected_flag=item.get("expected_flag"),
                severity=item.get("severity_expected"),
                institution=institution,
                institutions=institutions,
                programme_code=item.get("programme_code"),
                rows=tuple(_row(r) for r in item.get("rows") or ()),
                academic_year=item.get("academic_year"),
                seat_type=item.get("seat_type"),
                expected_record_status=item.get("expected_record_status"),
                expected_rows=_expected_rows(item),
                expected_signal=item.get("expected_signal"),
                expected_deadline_state=item.get("expected_deadline_state"),
                note=str(item.get("note") or ""),
            )
        )
    return out


def load(generated: Path) -> Truth:
    """ground_truth.json and manifest.json of a datagen output directory."""
    generated = Path(generated)
    truth_path = generated / "ground_truth.json"
    manifest_path = generated / "manifest.json"
    if not truth_path.is_file():
        raise FileNotFoundError(f"{truth_path} is missing; run datagen first")
    raw = json.loads(truth_path.read_text(encoding="utf-8"))
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )
    return Truth(records=parse_records(raw), manifest=manifest)


RowIndex = Mapping[tuple[str, int], str]


def resolve(records: Iterable[TruthRecord], index: RowIndex) -> dict[int, tuple[str | None, ...]]:
    """For each record, the enrolment id each of its rows became (None: no enrolment)."""
    return {r.index: tuple(index.get(row.key) for row in r.rows) for r in records}


def named_enrolments(
    records: Iterable[TruthRecord], resolved: Mapping[int, Sequence[str | None]]
) -> set[str]:
    """Every enrolment some ground-truth record names: never part of the known-clean set."""
    return {e for r in records for e in resolved.get(r.index, ()) if e is not None}
