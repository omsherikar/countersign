"""A college's own column names, mapped to the upload template once (D42; API_CONTRACT
§A4.16; ENGINES §17.9).

Each header cell is normalised as §A2.2 (trimmed, lower case, spaces and hyphens as
underscores). A header whose normalised form matches a saved mapping key (normalised the
same way) is read as the mapped column; else a header that is a template column is read as
itself; else it is unknown. `apply` is pure and is what PARSE uses; `load` and `save` keep the
mapping in `institution_column_mappings`, one row per institution.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import ApiError
from app.engine.upload.types import REQUIRED_COLUMNS, UPLOAD_COLUMNS
from app.models.enums import AuditAction
from app.models.institution import InstitutionColumnMapping
from app.models.user import User

# the template's three eligibility markers (§A4.16); listed here too so a mapping to them is
# accepted whichever template the upload types carry
ELIGIBILITY_COLUMNS: tuple[str, ...] = ("tfw_income_certified", "nri_sponsored", "ciwg")
TEMPLATE_COLUMNS: tuple[str, ...] = UPLOAD_COLUMNS + tuple(
    c for c in ELIGIBILITY_COLUMNS if c not in UPLOAD_COLUMNS
)
READABLE = frozenset(UPLOAD_COLUMNS)
MAX_ENTRIES = 60
HEADER_MAX = 120
FUZZY_MIN = 85

# loose header -> template column: the synonyms of ENGINES §17.9, then the names colleges use
SYNONYMS: Mapping[str, str] = {
    "student_name": "name",
    "date_of_birth": "dob",
    "d_o_b": "dob",
    "apaar": "apaar_id",
    "apaar_no": "apaar_id",
    "course": "programme_code",
    "course_code": "programme_code",
    "branch": "programme_code",
    "year": "year_of_study",
    "admission_type": "admission_route",
    "quota": "admission_route",
    "caste_category": "category",
    "mobile_no": "mobile",
    "phone": "mobile",
    "e_mail": "email",
    "passport": "passport_no",
    "tfw": "tfw_income_certified",
    "nri": "nri_sponsored",
    # further names seen in college registers
    "name_of_student": "name",
    "candidate_name": "name",
    "birth_date": "dob",
    "apaar_number": "apaar_id",
    "contact_number": "mobile",
    "mobile_number": "mobile",
    "email_id": "email",
    "email_address": "email",
    "residential_address": "address",
    "passport_number": "passport_no",
    "programme": "programme_code",
    "program": "programme_code",
    "current_year": "year_of_study",
    "year_of_study_1_5": "year_of_study",
    "route": "admission_route",
    "allotment_no": "counselling_ref",
    "cap_allotment_ref": "counselling_ref",
    "social_category": "category",
    "reservation_category": "category",
    "apaar_consent": "consent_status",
    "date_of_admission": "admission_date",
    "admitted_on": "admission_date",
    "gender_m_f": "gender",
    "tfw_income_certificate": "tfw_income_certified",
    "nri_or_nri_sponsored": "nri_sponsored",
}

TO_TEMPLATE = "Map to a template column."
UNMAPPED = (
    "The file has columns Countersign does not recognise. Map them to the template once, "
    "then upload again."
)


def normalise_header(text: str) -> str:
    """As §A2.2 reads a header."""
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def _loose(text: str) -> str:
    """For synonyms and suggestions: every run of other characters as one underscore."""
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")


@dataclass(frozen=True, slots=True)
class HeaderMap:
    columns: dict[int, str]  # cell index -> template column
    mapped: list[tuple[str, str]]  # (their header, column) used through the saved mapping
    unknown: list[str]
    missing: list[str]  # required columns not reached
    duplicates: list[str]


def apply(headers: Sequence[str], mapping: Mapping[str, str] | None = None) -> HeaderMap:
    """Read a header row with the saved mapping (pure). A header, or a column reached twice,
    is a duplicate; a mapped column the template does not read is left unused."""
    saved = {normalise_header(k): v for k, v in (mapping or {}).items()}
    columns: dict[int, str] = {}
    mapped: list[tuple[str, str]] = []
    unknown: list[str] = []
    duplicates: list[str] = []
    seen_headers: dict[str, int] = {}
    seen_columns: set[str] = set()
    for index, text in enumerate(headers):
        text = (text or "").strip()
        if not text:
            continue
        key = normalise_header(text)
        seen_headers[key] = seen_headers.get(key, 0) + 1
        if seen_headers[key] == 2 and key not in duplicates:
            duplicates.append(key)
        if seen_headers[key] > 1:
            continue
        via_mapping = key in saved
        column = saved[key] if via_mapping else key if key in READABLE else None
        if column is None:
            unknown.append(text)
            continue
        if column not in READABLE:
            continue  # a template column this api version does not read yet
        if column in seen_columns:
            if column not in duplicates:
                duplicates.append(column)
            continue
        seen_columns.add(column)
        columns[index] = column
        if via_mapping:
            mapped.append((text, column))
    missing = [c for c in REQUIRED_COLUMNS if c not in seen_columns]
    return HeaderMap(
        columns=columns, mapped=mapped, unknown=unknown, missing=missing, duplicates=duplicates
    )


def suggest(unknown: Sequence[str], taken: Collection[str] = ()) -> list[tuple[str, str]]:
    """A template column for each unknown header that has a likely one: synonyms first, then
    a rapidfuzz ratio of FUZZY_MIN or more. A column is suggested once, and never one in
    `taken` (already in the file)."""
    used = set(taken)
    out: list[tuple[str, str]] = []
    candidates = [(c, c) for c in TEMPLATE_COLUMNS] + list(SYNONYMS.items())
    for header in unknown:
        key = _loose(header)
        column = SYNONYMS.get(key)
        if column is None:
            best, score = None, 0.0
            for name, target in candidates:
                ratio = fuzz.ratio(key, name)
                if ratio > score:
                    best, score = target, ratio
            column = best if score >= FUZZY_MIN else None
        if column is not None and column not in used:
            used.add(column)
            out.append((header, column))
    return out


def unmapped_details(header_map: HeaderMap) -> dict[str, Any]:
    """The `details` of 422 UPLOAD_HEADER_UNMAPPED."""
    suggestions = suggest(header_map.unknown, taken=set(header_map.columns.values()))
    return {
        "unknown_headers": list(header_map.unknown),
        "missing_columns": list(header_map.missing),
        "suggestions": [{"header": h, "column": c} for h, c in suggestions],
    }


def _invalid(message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"mapping: {message[:1].lower()}{message[1:]}",
        {"fields": [{"field": "mapping", "message": message}]},
    )


def validate(mapping: Mapping[str, str], headers: Sequence[str] | None = None) -> None:
    """The PUT rules of §A4.16: 422 VALIDATION_ERROR, MAPPING_DUPLICATE or MAPPING_INCOMPLETE."""
    if len(mapping) > MAX_ENTRIES:
        raise _invalid(f"Map at most {MAX_ENTRIES} columns.")
    targets: dict[str, str] = {}
    keys: dict[str, str] = {}
    for header, column in mapping.items():
        if not isinstance(header, str) or not 1 <= len(header.strip()) <= HEADER_MAX:
            raise _invalid(f"Each column name has 1 to {HEADER_MAX} characters.")
        if not isinstance(column, str) or column not in TEMPLATE_COLUMNS:
            raise _invalid(TO_TEMPLATE)
        key = normalise_header(header)
        if column in targets or key in keys:
            raise ApiError(
                422,
                "MAPPING_DUPLICATE",
                f"Each Countersign column can be chosen once. {column} is chosen more than once.",
                {"column": column},
            )
        targets[column] = header
        keys[key] = column
    if headers is not None:
        header_map = apply(headers, mapping)
        if header_map.duplicates:
            column = header_map.duplicates[0]
            raise ApiError(
                422,
                "MAPPING_DUPLICATE",
                f"Each Countersign column can be chosen once. {column} is chosen more than once.",
                {"column": column},
            )
        if header_map.missing:
            raise ApiError(
                422,
                "MAPPING_INCOMPLETE",
                f"Map every required column before you continue: {', '.join(header_map.missing)}.",
                {"missing_columns": list(header_map.missing)},
            )


# ------------------------------------------------------------------------- storage


async def load(session: AsyncSession, institution_id: uuid.UUID) -> dict[str, str]:
    """The institution's saved mapping, `{}` when none."""
    stored = (
        await session.execute(
            select(InstitutionColumnMapping.mapping).where(
                InstitutionColumnMapping.institution_id == institution_id
            )
        )
    ).scalar_one_or_none()
    return dict(stored or {})


def columns() -> list[dict[str, Any]]:
    """The template columns in order, each with whether it is required."""
    return [{"column": c, "required": c in REQUIRED_COLUMNS} for c in TEMPLATE_COLUMNS]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


async def read(session: AsyncSession, institution_id: uuid.UUID) -> dict[str, Any]:
    """The GET body of §A4.16."""
    row = (
        await session.execute(
            select(InstitutionColumnMapping, User.id, User.name)
            .outerjoin(User, User.id == InstitutionColumnMapping.updated_by_id)
            .where(InstitutionColumnMapping.institution_id == institution_id)
            .execution_options(populate_existing=True)
        )
    ).first()
    stored, user_id, user_name = row if row is not None else (None, None, None)
    return {
        "institution_id": str(institution_id),
        "mapping": dict(stored.mapping) if stored is not None else {},
        "updated_at": _iso(stored.updated_at) if stored is not None else None,
        "updated_by": {"id": str(user_id), "name": user_name} if user_id is not None else None,
        "columns": columns(),
    }


async def save(
    session: AsyncSession,
    institution_id: uuid.UUID,
    mapping: Mapping[str, str],
    user: User,
    *,
    request_id: str | None = None,
    seed: bool = False,
) -> dict[str, Any]:
    """Replace the institution's mapping (`{}` clears it) and audit it; returns the GET
    body. The caller has validated it. The seed saves it in the college registrar's name and
    audits it as a SEED entry with no actor. Flushes, never commits."""
    clean = {header.strip(): column for header, column in mapping.items()}
    now = datetime.now(UTC)
    await session.execute(
        pg_insert(InstitutionColumnMapping)
        .values(institution_id=institution_id, mapping=clean, updated_at=now, updated_by_id=user.id)
        .on_conflict_do_update(
            index_elements=[InstitutionColumnMapping.institution_id],
            set_={"mapping": clean, "updated_at": now, "updated_by_id": user.id},
        )
    )
    await audit.record(
        session,
        None if seed else user.id,
        AuditAction.SEED if seed else AuditAction.UPDATE,
        "institution_column_mapping",
        institution_id,
        after={"headers": len(clean)},
        request_id=request_id,
    )
    return await read(session, institution_id)
