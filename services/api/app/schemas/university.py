"""University graduates and degree print data (API_CONTRACT A3.21)."""

from __future__ import annotations

from pydantic import BaseModel


class GraduateStudent(BaseModel):
    id: str
    name: str
    apaar_masked: str | None
    provisional_id: str | None


class GraduateInstitution(BaseModel):
    id: str
    name: str
    aicte_permanent_id: str


class GraduateProgramme(BaseModel):
    id: str
    code: str
    name: str
    level: str


class GraduateDegree(BaseModel):
    credential_id: str
    short_id: str
    status: str
    issued_at: str


class GraduateRow(BaseModel):
    enrolment_id: str
    student: GraduateStudent
    institution: GraduateInstitution
    programme: GraduateProgramme
    academic_year: str
    year_of_award: int
    degree: GraduateDegree | None


class PrintStudent(BaseModel):
    name: str
    id_kind: str
    id_masked: str


class PrintProgramme(BaseModel):
    code: str
    name: str
    short_name: str


class PrintInstitution(BaseModel):
    name: str
    aicte_permanent_id: str
    short_name: str


class PrintUniversity(BaseModel):
    code: str
    name: str


class PrintDegree(BaseModel):
    credential_id: str
    short_id: str
    status: str
    issued_at: str
    revoked_at: str | None
    jws: str
    verify_url: str
    lookup_url: str
    qr_svg: str


class DegreePrint(BaseModel):
    enrolment_id: str
    student: PrintStudent
    programme: PrintProgramme
    institution: PrintInstitution
    university: PrintUniversity
    academic_year: str
    year_of_award: int
    degree: PrintDegree | None
