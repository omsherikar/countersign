"""Wire enums (ARCHITECTURE.md §9). Values equal names so they serialise as UPPER_SNAKE."""

from __future__ import annotations

from enum import StrEnum


class InstitutionType(StrEnum):
    GOVERNMENT = "GOVERNMENT"
    GOVERNMENT_AIDED = "GOVERNMENT_AIDED"
    PRIVATE_SELF_FINANCED = "PRIVATE_SELF_FINANCED"
    UNIVERSITY_DEPARTMENT = "UNIVERSITY_DEPARTMENT"
    DEEMED = "DEEMED"


class ProgrammeLevel(StrEnum):
    DIPLOMA = "DIPLOMA"
    UG = "UG"
    PG = "PG"
    POST_DIPLOMA = "POST_DIPLOMA"


class Discipline(StrEnum):
    ENGINEERING = "ENGINEERING"
    MANAGEMENT = "MANAGEMENT"
    COMPUTER_APPLICATIONS = "COMPUTER_APPLICATIONS"
    PHARMACY = "PHARMACY"
    ARCHITECTURE = "ARCHITECTURE"
    PLANNING = "PLANNING"
    DESIGN = "DESIGN"
    HOTEL_MANAGEMENT = "HOTEL_MANAGEMENT"
    APPLIED_ARTS = "APPLIED_ARTS"


class Shift(StrEnum):
    FIRST = "FIRST"
    SECOND = "SECOND"


class ProgrammeMode(StrEnum):
    PHYSICAL = "PHYSICAL"
    ODL = "ODL"
    ONLINE = "ONLINE"


class SeatType(StrEnum):
    REGULAR = "REGULAR"
    NRI = "NRI"
    TFW = "TFW"
    LATERAL = "LATERAL"
    INTERNATIONAL = "INTERNATIONAL"


class SeatStatus(StrEnum):
    FREE = "FREE"
    ASSIGNED = "ASSIGNED"
    RELEASED = "RELEASED"


class SeatEventKind(StrEnum):
    ASSIGN = "ASSIGN"
    RELEASE = "RELEASE"


class ConsentStatus(StrEnum):
    LINKED = "LINKED"
    REFUSED = "REFUSED"
    PENDING = "PENDING"
    INTERNATIONAL = "INTERNATIONAL"


class Gender(StrEnum):
    M = "M"
    F = "F"
    O = "O"  # noqa: E741
    U = "U"


class AdmissionRoute(StrEnum):
    COUNSELLING = "COUNSELLING"
    MANAGEMENT = "MANAGEMENT"
    NRI = "NRI"
    SPOT = "SPOT"
    LATERAL = "LATERAL"
    INTERNATIONAL = "INTERNATIONAL"
    TFW = "TFW"


class Category(StrEnum):
    GENERAL = "GENERAL"
    EWS = "EWS"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"
    OTHER = "OTHER"


class EnrolmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    TRANSFERRED = "TRANSFERRED"
    GRADUATED = "GRADUATED"


class UploadKind(StrEnum):
    INITIAL = "INITIAL"
    UPDATE = "UPDATE"


class UploadStatus(StrEnum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


class UploadStage(StrEnum):
    PARSE = "PARSE"
    VALIDATE = "VALIDATE"
    FILE_DUPLICATES = "FILE_DUPLICATES"
    UPSERT = "UPSERT"
    LEDGER = "LEDGER"
    CHECKS = "CHECKS"
    DUPLICATES = "DUPLICATES"
    FLAGS = "FLAGS"
    DONE = "DONE"


class UploadSource(StrEnum):
    FILE = "FILE"
    API = "API"
    SEED = "SEED"


class RowErrorLevel(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class CheckType(StrEnum):
    IDENTITY = "IDENTITY"
    ADMISSION = "ADMISSION"
    SEAT = "SEAT"
    STUDYING = "STUDYING"
    STUDENT = "STUDENT"


class CheckStatus(StrEnum):
    """The evidence state of one row of a record (D34)."""

    CONFIRMED = "CONFIRMED"
    CONTRADICTED = "CONTRADICTED"
    PENDING = "PENDING"
    NOT_YET_DUE = "NOT_YET_DUE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class RecordStatus(StrEnum):
    """One status per ACTIVE enrolment, computed from its rows and unresolved cases (D35)."""

    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"
    COUNTERSIGNED = "COUNTERSIGNED"
    UNDER_REVIEW = "UNDER_REVIEW"
    DISPUTED = "DISPUTED"


class FlagType(StrEnum):
    EXCESS_ADMISSION = "EXCESS_ADMISSION"
    QUOTA_BREACH = "QUOTA_BREACH"
    LATE_REFILL = "LATE_REFILL"
    INVALID_APAAR = "INVALID_APAAR"
    NAME_MISMATCH = "NAME_MISMATCH"
    DUPLICATE_CROSS_INSTITUTION = "DUPLICATE_CROSS_INSTITUTION"
    DUPLICATE_WITHIN_UPLOAD = "DUPLICATE_WITHIN_UPLOAD"
    DUAL_ENROLMENT_ALLOWED = "DUAL_ENROLMENT_ALLOWED"
    NO_ACADEMIC_ACTIVITY = "NO_ACADEMIC_ACTIVITY"
    STUDENT_DENIED = "STUDENT_DENIED"
    GHOST_RING = "GHOST_RING"
    ANOMALY = "ANOMALY"
    NOT_IN_JOINING_RECORD = "NOT_IN_JOINING_RECORD"
    ELIGIBILITY_BREACH = "ELIGIBILITY_BREACH"
    MISSING_FROM_UPLOAD = "MISSING_FROM_UPLOAD"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FlagStatus(StrEnum):
    OPEN = "OPEN"
    DOCS_REQUESTED = "DOCS_REQUESTED"
    UPHELD = "UPHELD"
    ESCALATED = "ESCALATED"
    WITHDRAWN = "WITHDRAWN"
    CORRECTED = "CORRECTED"


class CaseActionKind(StrEnum):
    UPHOLD = "UPHOLD"
    REQUEST_DOCS = "REQUEST_DOCS"
    ESCALATE = "ESCALATE"
    WITHDRAW = "WITHDRAW"
    NOTE = "NOTE"
    COLLEGE_RESPONSE = "COLLEGE_RESPONSE"
    ASSIGN = "ASSIGN"
    REOPEN = "REOPEN"
    SYSTEM_NOTE = "SYSTEM_NOTE"
    CORRECT = "CORRECT"


class NoticeChannel(StrEnum):
    EMAIL = "EMAIL"
    DIGILOCKER = "DIGILOCKER"


class NoticeResponse(StrEnum):
    YES = "YES"
    NO = "NO"


class NoticeDelivery(StrEnum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class CredentialKind(StrEnum):
    ENROLMENT = "ENROLMENT"
    COMPLETION = "COMPLETION"


class EnrolmentVersionSource(StrEnum):
    UPLOAD = "UPLOAD"
    DECISION = "DECISION"
    SEED = "SEED"


class SignalType(StrEnum):
    GHOST_RING = "GHOST_RING"
    ANOMALY = "ANOMALY"


class SignalStatus(StrEnum):
    NEW = "NEW"
    CASE_OPENED = "CASE_OPENED"
    DISMISSED = "DISMISSED"


class ConsentPurpose(StrEnum):
    APAAR_LINK = "APAAR_LINK"
    NOTICE = "NOTICE"
    CREDENTIAL_SHARE = "CREDENTIAL_SHARE"


class ConsentState(StrEnum):
    GIVEN = "GIVEN"
    WITHDRAWN = "WITHDRAWN"
    REFUSED = "REFUSED"


class DataRequestKind(StrEnum):
    ACCESS = "ACCESS"
    CORRECTION = "CORRECTION"
    ERASURE = "ERASURE"


class DataRequestStatus(StrEnum):
    OPEN = "OPEN"
    DONE = "DONE"
    REJECTED = "REJECTED"


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    READ = "READ"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SEED = "SEED"


class UserRole(StrEnum):
    AICTE_ADMIN = "AICTE_ADMIN"
    RO_OFFICER = "RO_OFFICER"
    INSTITUTION = "INSTITUTION"
    STUDENT = "STUDENT"
    UNIVERSITY = "UNIVERSITY"
