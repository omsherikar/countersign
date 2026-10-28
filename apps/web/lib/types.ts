/**
 * Wire types for the Countersign API.
 * Source: docs/API_CONTRACT.md section D, Addendum 1 and Addendum 2. The
 * Addendum 2 block (A2.23) is pasted verbatim below and replaces the section D
 * declarations of Countersign, Check, DashboardSummary, InstitutionRow,
 * SeatPool, ProgrammeDetail, InstitutionDetail, SeatRow and EnrolmentRow.
 * Health and chaos shapes come from A.1 and C.8.
 */

export type Role = "AICTE_ADMIN" | "RO_OFFICER" | "INSTITUTION" | "STUDENT" | "UNIVERSITY" | "VERIFIER";
export type Region =
  | "NORTH" | "NORTH_WEST" | "CENTRAL" | "WEST" | "WEST_CENTRAL"
  | "SOUTH_WEST" | "SOUTH" | "SOUTH_CENTRAL" | "EAST" | "NORTH_EAST";

export type CheckType = "IDENTITY" | "ADMISSION" | "SEAT" | "STUDYING" | "STUDENT";
export type CheckStatus = "CONFIRMED" | "CONTRADICTED" | "PENDING" | "NOT_YET_DUE" | "NOT_APPLICABLE" | "SOURCE_UNAVAILABLE";
export type RecordStatus = "AWAITING_EVIDENCE" | "COUNTERSIGNED" | "UNDER_REVIEW" | "DISPUTED";
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY"
  | "NOT_IN_JOINING_RECORD" | "ELIGIBILITY_BREACH" | "MISSING_FROM_UPLOAD";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "UPHELD" | "ESCALATED" | "WITHDRAWN" | "CORRECTED";
export type ConsentStatus = "LINKED" | "REFUSED" | "PENDING" | "INTERNATIONAL";
export type AdmissionRoute = "COUNSELLING" | "MANAGEMENT" | "NRI" | "SPOT" | "LATERAL" | "INTERNATIONAL" | "TFW";
export type SeatType = "REGULAR" | "NRI" | "TFW" | "LATERAL" | "INTERNATIONAL";
export type SeatStatus = "FREE" | "ASSIGNED" | "RELEASED";
export type EnrolmentStatus = "ACTIVE" | "WITHDRAWN" | "TRANSFERRED" | "GRADUATED";
export type Category = "GENERAL" | "EWS" | "OBC" | "SC" | "ST" | "OTHER";
export type InstitutionType = "GOVERNMENT" | "GOVERNMENT_AIDED" | "PRIVATE_SELF_FINANCED" | "UNIVERSITY_DEPARTMENT" | "DEEMED";
export type Level = "DIPLOMA" | "UG" | "PG" | "POST_DIPLOMA";
export type Discipline =
  | "ENGINEERING" | "MANAGEMENT" | "COMPUTER_APPLICATIONS" | "PHARMACY" | "ARCHITECTURE"
  | "PLANNING" | "DESIGN" | "HOTEL_MANAGEMENT" | "APPLIED_ARTS";
export type Shift = "FIRST" | "SECOND";
export type SourceStatus = "OK" | "UNAVAILABLE" | "DISABLED";
export type AuditAction = "CREATE" | "UPDATE" | "DELETE" | "READ" | "LOGIN" | "LOGOUT" | "SEED";

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserScope {
  institution_id: string | null;
  institution_name: string | null;
  region: Region | null;
  student_id: string | null;
  university_id: string | null;
  university_name?: string | null;
}
export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  scope: UserScope;
}
export interface UserEnvelope {
  user: User;
}

export interface FlagRef {
  id: string;
  type: FlagType;
  severity: Severity;
  status: FlagStatus;
}

export interface StudentRef {
  id: string;
  name: string;
  apaar_masked: string | null;
  consent_status: ConsentStatus;
  provisional_id: string | null;
  nationality: string;
}
export interface StudentEnrolment {
  id: string;
  institution_id: string;
  institution_name: string;
  programme_code: string;
  programme_name: string;
  academic_year: string;
  year_of_study: number;
  status: EnrolmentStatus;
  countersign: Countersign;
}

export type SourceKey = "apaar" | "counselling" | "abc" | "digilocker" | "sii";
export const SOURCE_KEYS: SourceKey[] = ["apaar", "counselling", "abc", "digilocker", "sii"];

export interface SourcePing {
  status: SourceStatus;
  latency_ms: number;
  detail: string | null;
}
export interface AdapterPing {
  adapter: "inmemory" | "mockgov" | "real";
  sources: Record<SourceKey, SourcePing>;
  checked_at: string;
}
export interface AuditVerify {
  ok: boolean;
  length: number;
  first_broken_seq: number | null;
  checked_at: string;
}

export interface RegionMeta {
  code: Region;
  name: string;
  hq_city: string;
}
export interface StateMeta {
  code: string;
  name: string;
  region: Region;
}
export interface ItemsEnvelope<T> {
  items: T[];
}

/** A.1 */
export interface Health {
  status: "ok" | "degraded";
  db: string;
  redis: string;
  version: string;
}

/** C.8, proxied by the api for AICTE_ADMIN (Addendum 1.7). */
export interface ChaosSetting {
  latency_ms: number;
  fail_rate: number;
  down: boolean;
}
export type ChaosState = Record<SourceKey, ChaosSetting>;
export interface ChaosRequest extends ChaosSetting {
  source: SourceKey | "all";
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ---------- Week 2 enums ----------
export type ProgrammeMode = "PHYSICAL" | "ODL" | "ONLINE";
export type UploadStatus = "QUEUED" | "VALIDATING" | "PROCESSING" | "DONE" | "FAILED";
export type UploadStage =
  | "PARSE" | "VALIDATE" | "FILE_DUPLICATES" | "UPSERT" | "LEDGER" | "CHECKS" | "DUPLICATES" | "FLAGS" | "DONE";
export type UploadSource = "FILE" | "API" | "SEED";
export type UploadKind = "INITIAL" | "UPDATE";
export type RowErrorLevel = "ERROR" | "WARNING";
export type RowErrorCode =
  | "MISSING_REQUIRED" | "APAAR_FORMAT" | "DUPLICATE_IN_FILE" | "UNKNOWN_PROGRAMME" | "NO_APPROVAL_FOR_COHORT"
  | "DOB_FORMAT" | "DOB_IMPLAUSIBLE" | "BAD_ENUM" | "YEAR_OF_STUDY_INVALID" | "YEAR_MISMATCH" | "PASSPORT_REQUIRED"
  | "NATIONALITY_FORMAT" | "DATE_FORMAT" | "DATE_IN_FUTURE" | "MOBILE_FORMAT" | "EMAIL_FORMAT"
  | "CONSENT_CONFLICT" | "NOT_PREVIOUSLY_ENROLLED";
export type CheckSource = "APAAR" | "COUNSELLING" | "SEAT_LEDGER" | "ABC" | "SII" | "STUDENT_NOTICE";
export type FlagSort = "severity_desc" | "created_desc";
export type InstitutionSort = "flags_open_desc" | "enrolments_desc" | "name_asc";

export const UPLOAD_COLUMNS = [
  "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality", "passport_no",
  "programme_code", "academic_year", "year_of_study", "admission_route", "counselling_ref", "category",
  "consent_status", "status", "status_date", "admission_date",
] as const;
export type UploadColumn = (typeof UPLOAD_COLUMNS)[number];

// ---------- countersign ----------
export interface Score { passes: number; applicable: number }
export interface CheckBrief { type: CheckType; status: CheckStatus }
/** Replaces the Week 1 Countersign: list rows carry type and status only. */
export interface Countersign { score: Score | null; checks: CheckBrief[] }

/** Replaces the Week 1 Check. */
export interface Check {
  type: CheckType; status: CheckStatus; source: CheckSource; checked_at: string | null; attempts: number; detail: CheckDetail;
  /** Provenance (D34): who supplied the fact, when, and whether independently of the college. */
  supplied_by?: string; observed_at?: string | null; independent?: boolean;
  /** Set when an officer's decision resolved this row's contradiction (R2). */
  resolved?: { outcome: FlagStatus; case_id: string; case_action_seq: number; reason_code: string | null; at: string } | null;
}

// ---------- uploads ----------
export interface UploadCounts {
  rows: number; accepted: number; errors: number; warnings: number;
  created: number; updated: number; unchanged: number; withdrawn: number; transferred: number;
  seated: number; released: number; unseated: number; flags_raised: number; flags_updated: number;
}
export interface UploadSourceStat { source: CheckSource; calls: number; unavailable: number }
export interface UploadBatch {
  id: string; institution_id: string; institution_name: string; academic_year: string; filename: string;
  source: UploadSource; kind: UploadKind; status: UploadStatus; stage: UploadStage | null;
  total_rows: number; stage_total: number; processed_rows: number; progress_pct: number;
  counts: UploadCounts; sources: UploadSourceStat[]; timings_ms: Partial<Record<UploadStage, number>>;
  error: string | null; ignored_columns: string[];
  same_file_as: { batch_id: string; uploaded_at: string } | null;
  uploaded_by: { id: string; name: string };
  uploaded_at: string; started_at: string | null; finished_at: string | null;
}
export interface UploadAccepted { batch: UploadBatch }
export interface UploadRowError {
  row_no: number; level: RowErrorLevel; field: UploadColumn | null; code: RowErrorCode; message: string; value_masked: string | null;
}
export type UploadRowInput = Partial<Record<UploadColumn, string | number | null>>;
export interface UploadRowsRequest {
  academic_year: string; institution_id?: string | null; declaration: true; label?: string; rows: UploadRowInput[];
}

// ---------- institutions and dashboard ----------
export interface DashboardSummary {
  academic_year: string;
  scope: { kind: "NATIONAL" | "REGION" | "INSTITUTION" | "UNIVERSITY"; label: string };
  kpis: {
    institutions: number; programmes: number; approved_seats: number; admitted: number; enrolments: number;
    flags_open: number; countersigned_pct: number | null; clear_pct: number | null;
  };
  flags_by_type: { type: FlagType; open: number }[];
  by_state: {
    state_code: string; state_name: string; region: Region; institutions: number; programmes: number;
    approved_seats: number; admitted: number; enrolments: number; flags_open: number;
  }[];
  by_region: {
    region: Region; region_name: string; institutions: number; approved_seats: number; admitted: number;
    enrolments: number; flags_open: number;
  }[];
}
export interface InstitutionRow {
  id: string; aicte_permanent_id: string; name: string; type: InstitutionType;
  state_code: string; state_name: string; region: Region; region_name: string;
  university_id: string | null; university_name: string | null;
  programmes: number; approved_seats: number; admitted: number; enrolments: number;
  flags_open: number; integrity_index: number | null;
}
export interface SeatPool {
  seat_type: SeatType; capacity: number; is_supernumerary: boolean; assigned: number; free: number;
  reserved_for: string | null; rule_source: string;
}
export interface ProgrammeDetail {
  id: string; code: string; name: string; level: Level; discipline: Discipline; shift: Shift; mode: ProgrammeMode;
  approval: { academic_year: string; approved_intake: number; cutoff_date: string | null };
  enrolments: number; seated: number; unseated: number; pools: SeatPool[];
}
export interface LastUpload { batch_id: string; uploaded_at: string; rows: number; errors: number; status: UploadStatus }
export interface InstitutionDetail extends Omit<InstitutionRow, "programmes"> {
  address_city: string | null; established_year: number | null;
  integrity_components: Record<string, number> | null;
  last_upload: LastUpload | null;
  programmes: ProgrammeDetail[];
}
export interface SeatRow {
  id: string; seat_code: string; programme_code: string; academic_year: string; seat_type: SeatType; status: SeatStatus;
  reserved_for: string | null; enrolment_id: string | null; student_name: string | null; assigned_at: string | null;
}

// ---------- enrolments ----------
export interface EnrolmentRow {
  id: string; student: StudentRef; programme_id: string; programme_code: string;
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category;
  seat_code: string | null; status: EnrolmentStatus; admission_date: string; status_date: string;
  uploaded_at: string; upload_batch_id: string | null; source_row_no: number | null;
  countersign: Countersign; flags: FlagRef[];
  record_status?: RecordStatus; status_reason?: string | null;
}
export interface EnrolmentListQuery {
  page?: number; page_size?: number; programme_id?: string; status?: EnrolmentStatus; academic_year?: string; q?: string;
  admission_route?: AdmissionRoute; year_of_study?: number; sort?: "name_asc" | "year_desc" | "route_asc";
  check_status?: CheckStatus; check_type?: CheckType; flagged?: boolean; seated?: boolean;
}
export interface InstitutionRef {
  id: string; name: string; aicte_permanent_id: string; state_code: string; state_name: string; region: Region;
}
export interface ProgrammeRef { id: string; code: string; name: string }
export interface FlagSummary extends FlagRef { summary: string; created_at: string }

export interface EnrolmentRecheck {
  enrolment_id: string; rechecked: number;
  results: { type: CheckType; before: CheckStatus; after: CheckStatus }[];
  flags_raised: number; countersign: Countersign;
}
export interface InstitutionRecheck {
  institution_id: string; academic_year: string; enrolments: number; rechecked: number;
  now_pass: number; now_fail: number; now_na: number; still_pending: number; flags_raised: number; duration_ms: number;
}

// ---------- flags ----------
export interface EvidenceFact { label: string; value: string; source: string | null }
export interface Evidence { summary: string; facts: EvidenceFact[]; related_enrolment_ids: string[]; rule_source: string | null }

export interface FlagPage extends Page<FlagRow> { institutions: number }

export interface RelatedEnrolmentRow extends EnrolmentRow { institution: { id: string; name: string } }

/* ---------- Derived names used across the web ---------- */

export type ScopeKind = DashboardSummary["scope"]["kind"];
export type StateSummaryRow = DashboardSummary["by_state"][number];
export type RegionSummaryRow = DashboardSummary["by_region"][number];
export type FlagsByType = DashboardSummary["flags_by_type"];

/** Query parameters. */
/** A.6 `name|enrolments|approved_seats` with `order`, and the Addendum 1 / A2.20 single-direction keys. */
export type InstitutionListSort = InstitutionSort | "name" | "enrolments" | "approved_seats";
export interface InstitutionListParams {
  page?: number;
  page_size?: number;
  state?: string;
  region?: Region;
  type?: InstitutionType;
  q?: string;
  sort?: InstitutionListSort;
  order?: "asc" | "desc";
}
export interface SeatListParams {
  page?: number;
  page_size?: number;
  programme_id?: string;
  seat_type?: SeatType;
  status?: SeatStatus;
  q?: string;
  academic_year?: string;
}
export type EnrolmentListParams = EnrolmentListQuery;
/** Errata 2: `status` also takes UNRESOLVED (OPEN, DOCS_REQUESTED, ESCALATED), the set flags_open counts. */
export type FlagStatusFilter = FlagStatus | "UNRESOLVED";
export interface FlagListParams extends Omit<FlagListQuery, "status"> {
  status?: FlagStatusFilter;
}
export interface UploadListParams {
  page?: number;
  page_size?: number;
  institution_id?: string;
  academic_year?: string;
  status?: UploadStatus;
}
export interface UploadErrorListParams {
  page?: number;
  page_size?: number;
  level?: RowErrorLevel;
  code?: RowErrorCode;
}

// Notices, cases, credentials, verifier, degrees, privacy and audit (API_CONTRACT A3.27)
// ---------- Week 3 enums ----------
export type NoticeChannel = "EMAIL" | "DIGILOCKER";
export type NoticeResponse = "YES" | "NO";
export type NoticeDelivery = "QUEUED" | "SENT" | "FAILED";
export type NoticeState = "QUEUED" | "AWAITING" | "ANSWERED" | "EXPIRED" | "FAILED";
export type StudentNoticeState = "NOT_SENT" | "UNREACHABLE" | "SENT" | "EXPIRED" | "CONFIRMED" | "DENIED";
export type IdKind = "APAAR" | "PROVISIONAL";
export type ResendBlock = "LIVE" | "ANSWERED" | "LIMIT" | "CONSENT_WITHDRAWN" | "NO_CHANNEL" | "NOT_ACTIVE" | "ROLE";
export type CaseAction =
  | "UPHOLD" | "REQUEST_DOCS" | "ESCALATE" | "WITHDRAW" | "NOTE" | "ASSIGN" | "REOPEN" | "COLLEGE_RESPONSE" | "SYSTEM_NOTE" | "CORRECT";
// CORRECT is recorded in case history; the API does not offer it as an action yet
export type OfficerAction = Exclude<CaseAction, "COLLEGE_RESPONSE" | "SYSTEM_NOTE" | "CORRECT">;
export type OfficerRole = Extract<Role, "AICTE_ADMIN" | "RO_OFFICER">;
export type CredentialKind = "ENROLMENT" | "COMPLETION";
export type CredentialStatus = "ACTIVE" | "REVOKED" | "EXPIRED";
export type PresentationState = "LIVE" | "EXPIRED";
export type VerifyResultCode = "VALID" | "REVOKED" | "EXPIRED" | "INVALID";
export type VerifyMethod = "signature" | "register_lookup";
export type RevokedReasonCode = "ENROLMENT_WITHDRAWN" | "ENROLMENT_TRANSFERRED" | "FLAG_CONFIRMED" | "ADMIN";
export type ClaimKey =
  | "name" | "dob" | "apaar_masked" | "provisional_id" | "institution" | "programme" | "academic_year"
  | "year_of_study" | "countersigned" | "university" | "year_of_award" | "proof_id";
export type ConsentPurpose = "APAAR_LINK" | "NOTICE" | "CREDENTIAL_SHARE";
export type ConsentState = "GIVEN" | "WITHDRAWN" | "REFUSED";
export type ConsentCurrentState = ConsentState | "NONE";
export type ConsentChannel = "COLLEGE_UPLOAD" | "NOTICE_EMAIL" | "NOTICE_DIGILOCKER" | "PORTAL";
export type DataRequestKind = "ACCESS" | "CORRECTION" | "ERASURE";
export type DataRequestStatus = "OPEN" | "DONE" | "REJECTED";
export type AccessorRole = Role | "NOTICE_LINK" | "SYSTEM";
export type AccessedWhat = "RECORD" | "EXPORT" | "DEGREE" | "NOTICE" | "CREDENTIAL" | "PROOF";

// ---------- checks ----------
/** Replaces the A2.23 CheckDetail: adds the STUDENT check keys of A3.8. */
export interface CheckDetail {
  summary: string;
  source_unavailable?: boolean; source_error?: string; needs_review?: boolean;
  name_score?: number; dob_match?: boolean; apaar_last4?: string;
  round?: number; allotment_ref?: string; ref_mismatch?: boolean;
  seat_code?: string; seat_type?: SeatType; flag_type?: FlagType;
  expected?: number; missing?: number; semesters?: { academic_year: string; sem: number; credits: number }[];
  awaiting_semester?: number;
  notice_state?: StudentNoticeState; channel?: NoticeChannel; sent_at?: string; responded_at?: string; changed?: boolean;
  delivery_failed?: boolean; consent_withdrawn?: boolean;
  [key: string]: unknown;
}

// ---------- notices ----------
export interface NoticePublic {
  channel: NoticeChannel; institution_name: string; programme_code: string; programme_name: string;
  academic_year: string; year_of_study: number; id_kind: IdKind; id_masked: string;
  uploaded_at: string; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null;
  previous_response: NoticeResponse | null; changed_at: string | null; can_change_until: string | null;
  consent_text: string; notice_version: string;
}
export interface NoticeRespondRequest { response: NoticeResponse; comment?: string }
export interface StudentNotice {
  id: string; enrolment_id: string; channel: NoticeChannel;
  institution_name: string; programme_name: string; academic_year: string;
  state: NoticeState; delivery_status: NoticeDelivery; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null; changed_at: string | null; can_change_until: string | null;
}
export interface EnrolmentNotice {
  id: string; channel: NoticeChannel; state: NoticeState; delivery_status: NoticeDelivery;
  attempts: number; last_error: string | null; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null;
  previous_response: NoticeResponse | null; changed_at: string | null; resent: boolean;
}
export interface ResendState { allowed: boolean; blocked_by: ResendBlock | null; resends_left: number }
export interface NoticeResendResult { enrolment_id: string; notices: EnrolmentNotice[]; resend: ResendState }

// ---------- credentials ----------
export interface IssuerRef { name: string; url: string }
export interface CredentialRef {
  id: string; kind: CredentialKind; status: CredentialStatus; short_id: string;
  issued_at: string; revoked_at: string | null; revoked_reason_code: RevokedReasonCode | null; revoked_reason: string | null;
}
export interface StudentCredentialBrief {
  id: string; kind: CredentialKind; status: CredentialStatus; enrolment_id: string; institution_name: string; issued_at: string;
}
export interface DisclosableField { key: ClaimKey; label: string; always: boolean }
export interface PresentationBrief {
  id: string; created_at: string; expires_at: string; disclosed: ClaimKey[]; verify_count: number; last_verified_at: string | null;
}
export interface CredentialCard {
  id: string; kind: CredentialKind; status: CredentialStatus; vct: string; short_id: string; issuer: IssuerRef;
  enrolment_id: string; institution_name: string; programme_name: string; academic_year: string;
  university_name: string | null;
  issued_at: string; expires_at: string | null; revoked_at: string | null;
  revoked_reason_code: RevokedReasonCode | null; revoked_reason: string | null;
  holder_bound: boolean; disclosable: DisclosableField[]; shares: number; last_verified_at: string | null;
  presentations: PresentationBrief[];
}
export interface CredentialClaim { key: string; label: string; value: string; disclosable: boolean }
export interface CredentialDetail extends CredentialCard { claims: CredentialClaim[] }
export interface CredentialListQuery {
  page?: number; page_size?: number; student_id?: string; enrolment_id?: string; kind?: CredentialKind; status?: CredentialStatus;
}
export interface PresentRequest { fields: ClaimKey[]; consent: true }
export interface PresentationCreated {
  id: string; code: string; url: string; qr_svg: string; expires_at: string; disclosed: ClaimKey[]; total: number;
}
export interface PresentationRow {
  id: string; created_at: string; expires_at: string; state: PresentationState; disclosed: ClaimKey[];
  verify_count: number; first_verified_at: string | null; last_verified_at: string | null;
}
export interface RevokeRequest { reason: string }

// ---------- verifier ----------
export interface DisclosedField { key: ClaimKey; label: string; value: string }
export interface VerifyResult {
  result: VerifyResultCode; kind: CredentialKind | null; issuer: IssuerRef | null;
  institution_name: string | null; university_name: string | null;
  issued_at: string | null; expires_at: string | null; revoked_at: string | null;
  disclosed: DisclosedField[]; holder_bound: boolean; status_checked_at: string | null;
  method: VerifyMethod; nonce: string | null;
}
export interface VerifyPasteRequest { presentation: string }

// ---------- university ----------
export interface GraduateRow {
  enrolment_id: string;
  student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  institution: { id: string; name: string; aicte_permanent_id: string };
  programme: { id: string; code: string; name: string; level: Level };
  academic_year: string; year_of_award: number;
  degree: { credential_id: string; short_id: string; status: CredentialStatus; issued_at: string } | null;
}
export interface GraduateListQuery {
  page?: number; page_size?: number; q?: string; institution_id?: string; academic_year?: string;
  degree?: "issued" | "not_issued"; university_id?: string;
}
export interface DegreePrint {
  enrolment_id: string;
  student: { name: string; id_kind: IdKind; id_masked: string };
  programme: { code: string; name: string; short_name: string };
  institution: { name: string; aicte_permanent_id: string; short_name: string };
  university: { code: string; name: string };
  academic_year: string; year_of_award: number;
  degree: {
    credential_id: string; short_id: string; status: CredentialStatus; issued_at: string; revoked_at: string | null;
    jws: string; verify_url: string; lookup_url: string; qr_svg: string;
  } | null;
}

// ---------- cases ----------
export interface ActorRef { id: string; name: string; role: Role }
export interface CaseAttachment {
  id: string; filename: string; content_type: "application/pdf" | "image/png" | "image/jpeg"; size_bytes: number; sha256: string;
}
export interface CaseHistoryItem {
  seq: number; at: string; action: CaseAction; from_status: FlagStatus | null; to_status: FlagStatus | null;
  actor: ActorRef | null; note: string | null; due_date: string | null;
  assignee: { id: string; name: string } | null; attachments: CaseAttachment[];
}
export interface CaseActionRequest { action: OfficerAction; note?: string; due_date?: string | null; assignee_id?: string | null }
/** POST /flags/{id}/response is multipart: FormData with "note" and up to three "files". */
/** Replaces the A2.23 FlagRow. */
export interface FlagRow {
  id: string; type: FlagType; severity: Severity; status: FlagStatus;
  institution: InstitutionRef; programme: ProgrammeRef | null; enrolment_id: string | null; academic_year: string;
  summary: string; related_count: number; assignee: { id: string; name: string } | null;
  response_received: boolean; docs_due_on: string | null; last_action_at: string | null;
  created_at: string; updated_at: string;
}
/** Replaces the A2.23 FlagListQuery. */
export interface FlagListQuery {
  page?: number; page_size?: number; type?: FlagType; severity?: Severity; status?: FlagStatus;
  institution_id?: string; programme_id?: string; state?: string; academic_year?: string; q?: string; sort?: FlagSort;
  assignee?: "me" | "none" | string; response_received?: boolean;
}
/** Replaces the A2.23 FlagDetail. */
export interface FlagDetail extends FlagRow {
  evidence: Evidence;
  enrolment: RelatedEnrolmentRow | null;
  related_enrolments: RelatedEnrolmentRow[];
  related_hidden: number;
  history: CaseHistoryItem[];
  allowed_actions: OfficerAction[];
  can_respond: boolean;
}
export interface OfficerRow { id: string; name: string; role: OfficerRole; region: Region | null }
export interface UserListQuery {
  role: OfficerRole | `${OfficerRole},${OfficerRole}`; flag_id?: string; page?: number; page_size?: number;
}

// ---------- enrolments and the student ----------
/** Replaces the A2.23 EnrolmentDetail. */
export interface EnrolmentDetail {
  id: string;
  institution: InstitutionRef;
  student: StudentRef & { dob: string; gender: "M" | "F" | "O" | "U"; mobile_masked: string | null };
  programme: ProgrammeRef & { level: Level; mode: ProgrammeMode; duration_years: number };
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category;
  status: EnrolmentStatus; status_date: string; admission_date: string; uploaded_at: string;
  record_status?: RecordStatus; status_reason?: string | null; next_step?: string | null; record_status_at?: string | null;
  upload: { batch_id: string; filename: string; row_no: number | null } | null;
  seat: { id: string; seat_code: string; seat_type: SeatType; academic_year: string; assigned_at: string | null } | null;
  countersign: Countersign;
  checks: Check[];
  flags: FlagSummary[];
  notices: EnrolmentNotice[];
  resend: ResendState;
  credentials: CredentialRef[];
}
/** Replaces the section D StudentMe. */
export interface StudentMe {
  id: string; name: string; apaar_masked: string | null; consent_status: ConsentStatus; provisional_id: string | null;
  dob: string; email: string | null; mobile_masked: string | null;
  enrolments: StudentEnrolment[];
  notices: StudentNotice[];
  credentials: StudentCredentialBrief[];
}

// ---------- privacy ----------
export interface PrivacyNotice {
  version: string; effective_from: string; title: string;
  sections: { id: string; heading: string; body: string }[];
  consent_texts: Record<ConsentPurpose, string>;
}
export interface EnrolmentBrief { id: string; institution_name: string; programme_name: string; academic_year: string }
export interface ConsentRow {
  id: string; purpose: ConsentPurpose; status: ConsentState; channel: ConsentChannel;
  notice_text: string; notice_version: string; recorded_at: string; withdrawn_at: string | null;
  enrolment: EnrolmentBrief | null;
}
export interface ConsentCurrent { purpose: ConsentPurpose; status: ConsentCurrentState; since: string | null; can_withdraw: boolean }
export interface ConsentsView { current: ConsentCurrent[]; items: ConsentRow[] }
export interface ConsentWithdrawResult extends ConsentsView { presentations_expired: number }
export interface AccessLogRow { at: string; role: AccessorRole; what: AccessedWhat }
export interface DataRequestRow {
  id: string; kind: DataRequestKind; status: DataRequestStatus; details: string | null; response: string | null;
  enrolment: EnrolmentBrief | null; created_at: string; resolved_at: string | null; export_path: string | null;
}
export interface DataRequestAdminRow extends DataRequestRow {
  student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  resolved_by: { id: string; name: string } | null;
}
export interface DataRequestCreate { kind: DataRequestKind; details?: string; enrolment_id?: string }
export interface DataRequestResolve { status: Exclude<DataRequestStatus, "OPEN">; response: string }
export interface DataRequestListQuery { page?: number; page_size?: number; status?: DataRequestStatus; kind?: DataRequestKind }
export interface MyDataExport {
  generated_at: string; privacy_notice_version: string;
  student: {
    id: string; name: string; dob: string; gender: "M" | "F" | "O" | "U"; nationality: string;
    apaar_masked: string | null; provisional_id: string | null; consent_status: ConsentStatus;
    email: string | null; mobile_masked: string | null;
  };
  enrolments: {
    id: string; institution_name: string; programme_name: string; academic_year: string; year_of_study: number;
    admission_route: AdmissionRoute; category: Category; status: EnrolmentStatus; status_date: string; admission_date: string;
    seat_code: string | null;
    checks: { type: CheckType; status: CheckStatus; summary: string; checked_at: string | null }[];
    flags: { type: FlagType; status: FlagStatus; summary: string; created_at: string }[];
  }[];
  notices: {
    channel: NoticeChannel; sent_at: string | null; expires_at: string; delivery_status: NoticeDelivery;
    response: NoticeResponse | null; responded_at: string | null; changed_at: string | null; comment: string | null;
  }[];
  consents: ConsentRow[];
  credentials: {
    id: string; kind: CredentialKind; status: CredentialStatus; issued_at: string; expires_at: string | null;
    revoked_at: string | null; revoked_reason: string | null; claims: { key: string; label: string; value: string }[];
  }[];
  presentations: { credential_id: string; created_at: string; expires_at: string; disclosed: ClaimKey[]; verify_count: number }[];
  data_requests: DataRequestRow[];
  access_log: AccessLogRow[];
}

// ---------- audit ----------
/** Replaces the section D AuditRow. */
export interface AuditRow {
  seq: number; at: string; actor_id: string | null; actor_email: string | null; actor_role: Role | null; via: string | null;
  action: AuditAction; entity_type: string; entity_id: string | null; hash: string; prev_hash: string | null;
}
export interface AuditListQuery {
  page?: number; page_size?: number; actor_id?: string; entity_type?: string; entity_id?: string;
  action?: AuditAction; seq_from?: number;
}
