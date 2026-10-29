"""Hand-made ground truth and engine views for the scoring tests; no database."""

from __future__ import annotations

from typing import Any

from eval.truth import TruthRecord, parse_records
from eval.views import CaseView, RecordView


def row(file: str, row_no: int, inst: str = "1-AAA-0001", **extra: Any) -> dict[str, Any]:
    return {
        "file": f"uploads/{file}",
        "row_no": row_no,
        "institution_aicte_id": inst,
        "apaar_id": None,
        "name": "Synthetic Student",
        "programme_code": extra.pop("programme_code", "CSE"),
        "year_of_study": extra.pop("year_of_study", 1),
        **extra,
    }


def gt(anomaly_type: str, rows: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    inst = extra.pop("institution_aicte_id", rows[0]["institution_aicte_id"] if rows else "")
    return {
        "anomaly_type": anomaly_type,
        "expected_flag": extra.pop("expected_flag", anomaly_type),
        "severity_expected": extra.pop("severity_expected", "HIGH"),
        "institution_aicte_id": inst,
        "institution_aicte_ids": extra.pop("institution_aicte_ids", [inst]),
        "programme_code": extra.pop("programme_code", "CSE"),
        "student_refs": [],
        "rows": rows,
        "note": extra.pop("note", f"planted {anomaly_type}"),
        **extra,
    }


def records(*raw: dict[str, Any]) -> list[TruthRecord]:
    return parse_records(list(raw))


def case(
    case_id: str,
    case_type: str,
    enrolments: tuple[str, ...] = (),
    *,
    severity: str = "HIGH",
    status: str = "OPEN",
    institution: str = "1-AAA-0001",
    **extra: Any,
) -> CaseView:
    return CaseView(
        id=case_id,
        type=case_type,
        severity=severity,
        status=status,
        institution=institution,
        enrolments=frozenset(enrolments),
        **extra,
    )


def record(
    record_id: str,
    *,
    institution: str = "1-AAA-0001",
    status: str = "ACTIVE",
    record_status: str | None = "AWAITING_EVIDENCE",
    from_upload: bool = True,
    rows: dict[str, str] | None = None,
) -> RecordView:
    return RecordView(
        id=record_id,
        institution=institution,
        status=status,
        record_status=record_status,
        from_upload=from_upload,
        rows=rows or {},
    )
