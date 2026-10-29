"""Certificate integration for awarding bodies (D44; API_CONTRACT A3.21, §A4.15).

Countersign does not issue degrees. A university lists the graduates of its affiliates,
issues a completion attestation into a graduate's wallet, and gets for its own certificate
the masked APAAR and a QR, through the API or as a printed certificate block. The QR
carries a compact JWS signed by the issuer key over a short summary of the completion, so
a reader with a phone and no account can check the paper; the attestation id printed under
it lets a reader who cannot scan look it up in AICTE's register instead.
"""

from __future__ import annotations

import io
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import segno
from jwcrypto.jws import JWS
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas
from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.crypto import mask_apaar
from app.core.deps import scoped_institution
from app.core.errors import ApiError
from app.credentials import holder, issuer, keys, status_list
from app.credentials.issuer import display_date, iso, ist_date
from app.models.credential import Credential
from app.models.enums import AuditAction, CredentialKind, EnrolmentStatus, UserRole
from app.models.geo import University
from app.models.institution import Institution, Programme
from app.models.student import Enrolment, Student
from app.models.user import User
from app.schemas.common import Page, PageParams

SHORT_LIMIT = 28
URL_LIMIT = 400  # the QR link stays strictly under this many characters
_SIGNATURE_LENGTH = 86  # an ES256 signature, base64url
_SHORTEST = 8  # a short name is not cut below this many characters to fit the QR
_ABBREVIATIONS = (
    ("Information Technology", "IT"),
    ("Computer Science", "CS"),
    ("Engineering", "Engg."),
    ("Technology", "Tech."),
    ("Institute", "Inst."),
    ("Management", "Mgmt."),
    (" and ", " & "),
    ("University", "Univ."),
)
_DANGLING = {"of", "&", "and", "in", "for", "the", "at"}
_SHORT_ID = re.compile(r"[\s-]+")
_LOOKALIKES = str.maketrans({"O": "0", "I": "1", "L": "1"})
FOOTER = (
    "Sample certificate block generated from synthetic demo data. "
    "Countersign does not issue degrees."
)
PRINT_VIA = "certificate-print"


# ---------------------------------------------------------------- names and ids


def short_name(text: str, limit: int = SHORT_LIMIT) -> str:
    """The abbreviated name the QR carries (API_CONTRACT A3.21): common words shortened,
    then cut to at most `limit` characters at a space, without leaving a dangling `of` or
    an unclosed bracket at the end."""
    out = text
    for long, short in _ABBREVIATIONS:
        out = out.replace(long, short)
    out = " ".join(out.split())
    if len(out) <= limit:
        return out
    kept: list[str] = []
    for word in out.split(" "):
        if len(" ".join([*kept, word])) > limit:
            break
        kept.append(word)
    if not kept:
        return out[:limit]
    cut = " ".join(kept)
    opened = cut.rfind("(")
    if opened > 0 and ")" not in cut[opened:]:
        cut = cut[:opened].rstrip()
    words = cut.split(" ")
    while len(words) > 1 and words[-1].lower().rstrip(",") in _DANGLING:
        words.pop()
    return " ".join(words).rstrip(",;:-")


def mask_provisional(provisional_id: str) -> str:
    """`PRV-7Q2MK4PX` shows as `PRV-XXXXK4PX`: the one masking rule for public surfaces."""
    return f"PRV-XXXX{provisional_id.strip()[-4:]}"


def masked_id(student: Student) -> tuple[str, str]:
    """(id_kind, the id as public surfaces show it)."""
    if student.apaar_last4:
        return "APAAR", mask_apaar(student.apaar_last4) or ""
    if student.provisional_id:
        return "PROVISIONAL", mask_provisional(student.provisional_id)
    return "PROVISIONAL", ""


def normalise_short_id(raw: str) -> str | None:
    """A typed attestation id as stored, or None when it cannot be one."""
    if not isinstance(raw, str):
        return None
    text = _SHORT_ID.sub("", raw.strip().upper()).translate(_LOOKALIKES)
    if len(text) != issuer.SHORT_ID_LENGTH or any(c not in issuer.CROCKFORD for c in text):
        return None
    return text


# ----------------------------------------------------------------- the register


@dataclass(frozen=True, slots=True)
class DegreeRecord:
    enrolment: Enrolment
    student: Student
    institution: Institution
    programme: Programme
    university: University | None


@dataclass(frozen=True, slots=True)
class GraduateQuery:
    page: PageParams
    q: str | None = None
    institution_id: uuid.UUID | None = None
    academic_year: str | None = None
    attestation: str | None = None  # issued or not_issued
    university_id: uuid.UUID | None = None  # AICTE_ADMIN only


def _record_query() -> Select:
    return (
        select(Enrolment, Student, Institution, Programme, University)
        .join(Student, Student.id == Enrolment.student_id)
        .join(Institution, Institution.id == Enrolment.institution_id)
        .join(Programme, Programme.id == Enrolment.programme_id)
        .outerjoin(University, University.id == Institution.university_id)
    )


async def record_for(session: AsyncSession, enrolment_id: uuid.UUID) -> DegreeRecord:
    row = (await session.execute(_record_query().where(Enrolment.id == enrolment_id))).one()
    return DegreeRecord(*row)


def _in_scope(user: User, institution: Institution) -> bool:
    if user.role is UserRole.AICTE_ADMIN:
        return True
    return user.role is UserRole.UNIVERSITY and institution.university_id == user.university_id


async def scoped_graduate(
    session: AsyncSession, user: User, enrolment_id: uuid.UUID
) -> DegreeRecord:
    """The enrolment's record when the user may print for it: 404 outside the university's
    affiliates, then 409 CREDENTIAL_NOT_ELIGIBLE NOT_GRADUATED for any other status."""
    row = (await session.execute(_record_query().where(Enrolment.id == enrolment_id))).first()
    if row is None or not _in_scope(user, row[2]):
        raise ApiError(404, "NOT_FOUND", "Enrolment not found.")
    record = DegreeRecord(*row)
    if record.enrolment.status is not EnrolmentStatus.GRADUATED:
        raise issuer.not_graduated()
    return record


async def degree_for(session: AsyncSession, enrolment_id: uuid.UUID) -> Credential | None:
    """The enrolment's active Degree proof, else its latest revoked one, else None."""
    return (
        await session.execute(
            select(Credential)
            .where(
                Credential.enrolment_id == enrolment_id,
                Credential.kind == CredentialKind.COMPLETION,
            )
            .order_by(Credential.revoked, Credential.issued_at.desc(), Credential.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def graduates(session: AsyncSession, user: User, query: GraduateQuery) -> Page:
    """GET /university/graduates: GRADUATED enrolments of the university's affiliates (all
    for AICTE_ADMIN), by institution then name. A READ audit entry per student listed."""
    stmt = _record_query().where(Enrolment.status == EnrolmentStatus.GRADUATED)
    if user.role is UserRole.UNIVERSITY:
        stmt = stmt.where(Institution.university_id == user.university_id)
    elif query.university_id is not None:
        stmt = stmt.where(Institution.university_id == query.university_id)
    if query.institution_id is not None:
        institution = await scoped_institution(session, user, query.institution_id)
        stmt = stmt.where(Enrolment.institution_id == institution.id)
    if query.academic_year:
        stmt = stmt.where(Enrolment.academic_year == query.academic_year)
    q = (query.q or "").strip()
    if q:
        pattern = f"%{_escape_like(q)}%"
        stmt = stmt.where(
            or_(
                Student.name.ilike(pattern, escape="\\"),
                Student.apaar_last4 == q,
                Student.provisional_id.ilike(pattern, escape="\\"),
            )
        )
    if query.attestation in ("issued", "not_issued"):
        has_attestation = exists(
            select(Credential.id).where(
                Credential.enrolment_id == Enrolment.id,
                Credential.kind == CredentialKind.COMPLETION,
                Credential.revoked.is_(False),
            )
        )
        stmt = stmt.where(has_attestation if query.attestation == "issued" else ~has_attestation)
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(Institution.name, Student.name, Enrolment.id)
            .offset(query.page.offset)
            .limit(query.page.page_size)
        )
    ).all()
    degrees = await _latest_degrees(session, [row[0].id for row in rows])
    items = []
    for enrolment, student, institution, programme, _university in rows:
        credential = degrees.get(enrolment.id)
        items.append(
            {
                "enrolment_id": str(enrolment.id),
                "student": {
                    "id": str(student.id),
                    "name": student.name,
                    "apaar_masked": mask_apaar(student.apaar_last4),
                    # a signed-in page: the provisional id in full, as on enrolment pages
                    "provisional_id": None if student.apaar_last4 else student.provisional_id,
                },
                "institution": {
                    "id": str(institution.id),
                    "name": institution.name,
                    "aicte_permanent_id": institution.aicte_permanent_id,
                },
                "programme": {
                    "id": str(programme.id),
                    "code": programme.code,
                    "name": programme.name,
                    "level": programme.level.value,
                },
                "academic_year": enrolment.academic_year,
                "year_of_award": issuer.year_end(enrolment.academic_year),
                "attestation": (
                    {
                        "credential_id": str(credential.id),
                        "short_id": credential.short_id,
                        "status": issuer.status_of(credential),
                        "issued_at": iso(credential.issued_at),
                    }
                    if credential is not None
                    else None
                ),
            }
        )
    await audit.record_read(session, user.id, "student", [row[1].id for row in rows])
    return Page[dict[str, Any]](
        items=items, total=total, page=query.page.page, page_size=query.page.page_size
    )


async def _latest_degrees(
    session: AsyncSession, enrolment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Credential]:
    if not enrolment_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(Credential)
                .where(
                    Credential.enrolment_id.in_(enrolment_ids),
                    Credential.kind == CredentialKind.COMPLETION,
                )
                .order_by(Credential.revoked.desc(), Credential.issued_at, Credential.id)
            )
        )
        .scalars()
        .all()
    )
    # later rows win: the newest revoked one, then any active one
    return {credential.enrolment_id: credential for credential in rows}


# ------------------------------------------------------------- the compact QR


def _b64(text: str) -> str:
    return status_list.b64url(text.encode("utf-8"))


def degree_payload(
    record: DegreeRecord,
    short_id: str,
    programme_limit: int = SHORT_LIMIT,
    institution_limit: int = SHORT_LIMIT,
) -> str:
    """The signed QR payload, keys in contract order and no spaces."""
    _kind, masked = masked_id(record.student)
    return json.dumps(
        {
            "v": 1,
            "cid": short_id,
            "n": record.student.name,
            "p": short_name(record.programme.name, programme_limit),
            "i": short_name(record.institution.name, institution_limit),
            "u": record.university.code if record.university else "",
            "y": issuer.year_end(record.enrolment.academic_year),
            "a": record.student.apaar_last4 or masked,
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )


def verify_url(jws: str) -> str:
    return f"{get_settings().web_origin}/verify/d/{jws}"


def lookup_url(short_id: str) -> str:
    return f"{get_settings().web_origin}/verify/completion/{short_id}"


def fitted_payload(record: DegreeRecord, short_id: str, header: str) -> str:
    """The payload whose QR link stays under URL_LIMIT characters.

    The contract's 28-character short names fit most graduates; when a long name, a long
    programme and a long institution meet, the longer of the two short names loses its
    last word until the link fits. The student's name is never shortened.
    """
    fixed = len(verify_url("")) + len(_b64(header)) + 2 + _SIGNATURE_LENGTH
    limits = {"p": SHORT_LIMIT, "i": SHORT_LIMIT}
    payload = degree_payload(record, short_id, limits["p"], limits["i"])
    while fixed + len(_b64(payload)) >= URL_LIMIT:
        current = json.loads(payload)
        longer = "p" if len(current["p"]) >= len(current["i"]) else "i"
        if len(current[longer]) <= _SHORTEST:
            break
        limits[longer] = len(current[longer]) - 1
        payload = degree_payload(record, short_id, limits["p"], limits["i"])
    return payload


def sign_degree(key: keys.IssuerKey, record: DegreeRecord, short_id: str) -> str:
    """ES256 over the degree summary with the issuer kid in the header (no typ, to keep the
    QR small). ES256 signatures differ on every call and every one verifies."""
    header = json.dumps({"alg": keys.ALG, "kid": key.kid}, separators=(",", ":"))
    token = JWS(payload=fitted_payload(record, short_id, header).encode("utf-8"))
    token.add_signature(key.jwk, alg=keys.ALG, protected=header)
    return token.serialize(compact=True)


async def compact_jws(session: AsyncSession, credential: Credential) -> str:
    """The degree QR's JWS, signed on each request rather than stored."""
    record = await record_for(session, credential.enrolment_id)
    return sign_degree(await keys.active_issuer_key(session), record, credential.short_id)


# ------------------------------------------------------------------ print data


async def print_body(session: AsyncSession, record: DegreeRecord) -> dict[str, Any]:
    """The print data of §A4.15 for a graduate; `attestation` is null until one is issued."""
    credential = await degree_for(session, record.enrolment.id)
    id_kind, id_masked = masked_id(record.student)
    attestation = None
    if credential is not None:
        jws = await compact_jws(session, credential)
        url = verify_url(jws)
        attestation = {
            "credential_id": str(credential.id),
            "short_id": credential.short_id,
            "status": issuer.status_of(credential),
            "issued_at": iso(credential.issued_at),
            "revoked_at": iso(credential.revoked_at),
            "jws": jws,
            "verify_url": url,
            "lookup_url": lookup_url(credential.short_id),
            "qr_svg": holder.qr_svg(url),
        }
    university = record.university
    return {
        "enrolment_id": str(record.enrolment.id),
        "student": {"name": record.student.name, "id_kind": id_kind, "id_masked": id_masked},
        "programme": {
            "code": record.programme.code,
            "name": record.programme.name,
            "short_name": short_name(record.programme.name),
        },
        "institution": {
            "name": record.institution.name,
            "aicte_permanent_id": record.institution.aicte_permanent_id,
            "short_name": short_name(record.institution.name),
        },
        "university": {
            "code": university.code if university else "",
            "name": university.name if university else "",
        },
        "academic_year": record.enrolment.academic_year,
        "year_of_award": issuer.year_end(record.enrolment.academic_year),
        "attestation": attestation,
    }


async def print_data(session: AsyncSession, user: User, enrolment_id: uuid.UUID) -> dict[str, Any]:
    """GET /university/certificates/{enrolment_id}, with its READ audit entry."""
    record = await scoped_graduate(session, user, enrolment_id)
    body = await print_body(session, record)
    await audit_print(session, user, record)
    return body


async def audit_print(session: AsyncSession, user: User, record: DegreeRecord) -> None:
    await audit.record(
        session,
        user.id,
        AuditAction.READ,
        "student",
        record.student.id,
        after={"via": PRINT_VIA},
    )


# ------------------------------------------------------------------ the insert


def _qr_rects(pdf: canvas.Canvas, url: str, x: float, y: float, width: float) -> None:
    """Draw the QR as filled squares, one run of dark modules per rectangle."""
    qr = segno.make(url, error="m", boost_error=False)
    rows = [list(row) for row in qr.matrix_iter(scale=1, border=4)]
    module = width / len(rows)
    top = y + width
    for r, row in enumerate(rows):
        c = 0
        while c < len(row):
            if row[c]:
                start = c
                while c < len(row) and row[c]:
                    c += 1
                pdf.rect(
                    x + start * module,
                    top - (r + 1) * module,
                    (c - start) * module,
                    module,
                    stroke=0,
                    fill=1,
                )
            else:
                c += 1


def _centered(pdf: canvas.Canvas, text: str, y: float, font: str, size: float) -> float:
    """Draw text centred on the page, wrapped to the text width; returns the next baseline."""
    width, _height = A4
    pdf.setFont(font, size)
    for line in simpleSplit(text, font, size, width - 50 * mm):
        pdf.drawCentredString(width / 2, y, line)
        y -= size * 1.35
    return y


def block_pdf(data: Mapping[str, Any]) -> bytes:
    """One A4 portrait page from the print data, the copy deck's certificate block: for
    whom, the programme, institution and year, the masked id, the QR about 40 mm wide with
    the attestation id and the verify address under it, and the sample footer. Black on
    white; nothing is filled but the QR. It never says degree except to say it is not one."""
    attestation = data["attestation"]
    assert attestation is not None, "print data without a completion attestation"
    university = data["university"]["name"]
    width, height = A4
    out = io.BytesIO()
    pdf = canvas.Canvas(out, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"Certificate block {attestation['short_id']}")
    pdf.setAuthor("Countersign")
    pdf.setSubject("Sample certificate block")
    pdf.setFillColorRGB(0, 0, 0)
    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.8)
    pdf.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm, stroke=1, fill=0)

    y = height - 40 * mm
    y = _centered(pdf, university, y, "Helvetica-Bold", 18)
    y -= 6 * mm
    y = _centered(pdf, f"For the certificate awarded by {university} to", y, "Helvetica", 11)
    y -= 2 * mm
    y = _centered(pdf, data["student"]["name"], y, "Helvetica-Bold", 16)
    y -= 6 * mm

    student = data["student"]
    id_line = (
        f"APAAR {student['id_masked']}"
        if student["id_kind"] == "APAAR"
        else f"Provisional ID {student['id_masked']}"
    )
    for label, value in (
        ("Programme", data["programme"]["name"]),
        ("Institution", data["institution"]["name"]),
        ("Year of completion", str(data["year_of_award"])),
    ):
        y = _centered(pdf, f"{label}: {value}", y, "Helvetica", 12)
        y -= 1 * mm
    y = _centered(pdf, id_line, y, "Helvetica-Bold", 12)

    qr_width = 40 * mm
    qr_y = y - 10 * mm - qr_width
    _qr_rects(pdf, attestation["verify_url"], (width - qr_width) / 2, qr_y, qr_width)
    y = qr_y - 7 * mm
    y = _centered(pdf, f"Attestation id {attestation['short_id']}", y, "Helvetica-Bold", 12)
    verify_at = _host_path(attestation["lookup_url"])
    y = _centered(pdf, f"Scan to verify at {verify_at}", y, "Helvetica", 10)
    y -= 6 * mm
    issued = datetime.fromisoformat(attestation["issued_at"].replace("Z", "+00:00"))
    y = _centered(
        pdf,
        f"Completion attestation issued {display_date(ist_date(issued))}",
        y,
        "Helvetica",
        10,
    )
    _centered(
        pdf,
        f"Signed by Countersign for {university}. "
        "This block is not a degree, and a changed block does not verify.",
        y,
        "Helvetica",
        10,
    )
    _centered(pdf, FOOTER, 22 * mm, "Helvetica-Oblique", 8)
    pdf.showPage()
    pdf.save()
    return out.getvalue()


def _host_path(url: str) -> str:
    """`http://localhost:3000/verify/completion/4ZK8M2QD` gives `localhost:3000/verify`."""
    return f"{urlsplit(url).netloc}/verify"


def active_degree_or_conflict(credential: Credential | None) -> Credential:
    """The completion attestation the block prints: 409 NOT_ISSUED without one,
    CREDENTIAL_REVOKED when the latest is revoked."""
    if credential is None:
        raise ApiError(
            409,
            "CREDENTIAL_NOT_ELIGIBLE",
            "Issue the completion attestation first.",
            {"reason": "NOT_ISSUED"},
        )
    if credential.revoked:
        assert credential.revoked_at is not None
        raise ApiError(
            409,
            "CREDENTIAL_REVOKED",
            f"This attestation was revoked on {display_date(ist_date(credential.revoked_at))} "
            "and cannot be shared.",
            {"revoked_at": iso(credential.revoked_at)},
        )
    return credential
