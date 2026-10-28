"""Masked echoes of uploaded values (API_CONTRACT §A2.3 `value_masked`)."""

from __future__ import annotations

from typing import Any

MAX_ECHO = 64


def _length(value: str) -> str:
    n = len(value)
    return f"<{n} character{'' if n == 1 else 's'}>"


def mask_value(field: str | None, value: str | None) -> str | None:
    """The offending value as the registrar may see it; None when blank or never shown."""
    value = (value or "").strip()
    if not value:
        return None
    if field == "apaar_id":
        digits = value.replace(" ", "")
        if len(digits) == 12 and digits.isdigit():
            return f"XXXX XXXX {digits[-4:]}"
        return _length(value)
    if field == "passport_no":
        clean = value.replace(" ", "").upper()
        if len(clean) <= 3:
            return _length(value)
        return "X" * (len(clean) - 3) + clean[-3:]
    if field == "mobile":
        if len(value) < 4:
            return _length(value)
        return f"XXXXXX{value[-4:]}"
    if field == "email":
        local, at, domain = value.partition("@")
        return f"{local[:1]}***@{domain}" if at else f"{value[:1]}***"
    if field == "address":
        return None
    return value[:MAX_ECHO]


def masked_row(values: dict[str, str]) -> dict[str, Any]:
    """What upload_row_errors.raw keeps of a row: no contact details, no full ids."""
    return {
        "apaar_id": mask_value("apaar_id", values.get("apaar_id")),
        "name": (values.get("name") or "").strip()[:200],
        "programme_code": (values.get("programme_code") or "").strip()[:MAX_ECHO],
        "academic_year": (values.get("academic_year") or "").strip()[:MAX_ECHO],
        "admission_route": (values.get("admission_route") or "").strip()[:MAX_ECHO],
    }
