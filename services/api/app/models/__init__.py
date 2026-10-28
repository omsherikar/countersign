"""Import every model so the metadata and mapper registry are complete."""

from app.models.audit import AuditLog
from app.models.credential import (
    Consent,
    Credential,
    CredentialPresentation,
    DataRequest,
    HolderKey,
    InstitutionScore,
    SigningKey,
)
from app.models.geo import Region, State, University
from app.models.institution import Approval, Institution, Programme
from app.models.seat import Seat, SeatEvent, SeatPool
from app.models.student import Enrolment, Student
from app.models.upload import UploadBatch, UploadRowError
from app.models.user import User
from app.models.verification import CaseAction, CaseAttachment, Check, Flag, Notification

__all__ = [
    "Approval",
    "AuditLog",
    "CaseAction",
    "CaseAttachment",
    "Check",
    "Consent",
    "Credential",
    "CredentialPresentation",
    "DataRequest",
    "Enrolment",
    "Flag",
    "HolderKey",
    "Institution",
    "InstitutionScore",
    "Notification",
    "Programme",
    "Region",
    "Seat",
    "SeatEvent",
    "SeatPool",
    "SigningKey",
    "State",
    "Student",
    "University",
    "UploadBatch",
    "UploadRowError",
    "User",
]
