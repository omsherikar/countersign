/**
 * Wire types for the Countersign API.
 * Source: docs/API_CONTRACT.md section D and Addenda 1 to 4. The Addendum 4
 * block (A4.24) is pasted verbatim at the end and replaces the earlier
 * declarations it names; the evidence rows and the record status replace the
 * countersign score. Health and chaos shapes come from A.1 and C.8.
 */

export type Role = "AICTE_ADMIN" | "RO_OFFICER" | "INSTITUTION" | "STUDENT" | "UNIVERSITY" | "VERIFIER";
export type Region =
  | "NORTH" | "NORTH_WEST" | "CENTRAL" | "WEST" | "WEST_CENTRAL"
  | "SOUTH_WEST" | "SOUTH" | "SOUTH_CENTRAL" | "EAST" | "NORTH_EAST";

export type CheckType = "IDENTITY" | "ADMISSION" | "SEAT" | "STUDYING" | "STUDENT";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
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
/** POST /psi/compute (API_CONTRACT §A4.26, D48): counts only, never members. */
export interface PsiResult {
  countersign_count: number;
  partner_count: number;
  overlap: number;
  computed_at: string;
  method: string;
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
export type FlagSort = "severity_desc" | "created_desc";

export type UploadColumn = (typeof UPLOAD_COLUMNS)[number];

// ---------- uploads ----------
export interface UploadSourceStat { source: CheckSource; calls: number; unavailable: number }
export interface UploadAccepted { batch: UploadBatch }
export interface UploadRowError {
  row_no: number; level: RowErrorLevel; field: UploadColumn | null; code: RowErrorCode; message: string; value_masked: string | null;
}
export type UploadRowInput = Partial<Record<UploadColumn, string | number | null>>;
export interface UploadRowsRequest {
  academic_year: string; institution_id?: string | null; declaration: true; label?: string; rows: UploadRowInput[];
}

// ---------- institutions and dashboard ----------
export interface SeatPool {
  seat_type: SeatType; capacity: number; is_supernumerary: boolean; assigned: number; free: number;
  reserved_for: string | null; rule_source: string;
}
export interface LastUpload { batch_id: string; uploaded_at: string; rows: number; errors: number; status: UploadStatus }
export interface SeatRow {
  id: string; seat_code: string; programme_code: string; academic_year: string; seat_type: SeatType; status: SeatStatus;
  reserved_for: string | null; enrolment_id: string | null; student_name: string | null; assigned_at: string | null;
}

// ---------- enrolments ----------
export interface InstitutionRef {
  id: string; name: string; aicte_permanent_id: string; state_code: string; state_name: string; region: Region;
}
export interface ProgrammeRef { id: string; code: string; name: string }
export interface FlagSummary extends FlagRef { summary: string; created_at: string }

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
/** The record filters plus the row and evidence-state filters of page spec W4-2, which the contract does not carry yet. */
export type EnrolmentListParams = EnrolmentListQuery & { row?: CheckType; row_state?: EvidenceState };
/** Errata 2 and A4.24: `status` also takes UNRESOLVED (OPEN, DOCS_REQUESTED, ESCALATED), the set flags_open counts, and DECIDED. */
export type FlagStatusFilter = FlagStatus | "UNRESOLVED" | "DECIDED";
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
export type OfficerRole = Extract<Role, "AICTE_ADMIN" | "RO_OFFICER">;
export type CredentialStatus = "ACTIVE" | "REVOKED" | "EXPIRED";
export type PresentationState = "LIVE" | "EXPIRED";
export type VerifyResultCode = "VALID" | "REVOKED" | "EXPIRED" | "INVALID";
export type VerifyMethod = "signature" | "register_lookup";
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

// ---------- notices ----------
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

// ---------- cases ----------
export interface ActorRef { id: string; name: string; role: Role }
export interface CaseAttachment {
  id: string; filename: string; content_type: "application/pdf" | "image/png" | "image/jpeg"; size_bytes: number; sha256: string;
}
export interface OfficerRow { id: string; name: string; role: OfficerRole; region: Region | null }
export interface UserListQuery {
  role: OfficerRole | `${OfficerRole},${OfficerRole}`; flag_id?: string; page?: number; page_size?: number;
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

// Week 4: evidence states, the record and its status (API_CONTRACT A4.24)
// ---------- Week 4 enums ----------
export type EvidenceState =
  | "CONFIRMED" | "CONTRADICTED" | "PENDING" | "NOT_YET_DUE" | "NOT_APPLICABLE" | "SOURCE_UNAVAILABLE";
export type RecordStatus = "AWAITING_EVIDENCE" | "COUNTERSIGNED" | "UNDER_REVIEW" | "DISPUTED";
export const RECORD_STATUS_ORDER: RecordStatus[] = ["AWAITING_EVIDENCE", "COUNTERSIGNED", "UNDER_REVIEW", "DISPUTED"];
export const ROW_ORDER: CheckType[] = ["IDENTITY", "SEAT", "ADMISSION", "STUDYING", "STUDENT"];
export type RecordCounts = Record<RecordStatus, number>;
/** Replaces the Week 1 FlagType. */
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY"
  | "NOT_IN_JOINING_RECORD" | "ELIGIBILITY_BREACH" | "MISSING_FROM_UPLOAD";
/** Replaces the Week 1 FlagStatus. */
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "ESCALATED" | "UPHELD" | "CORRECTED" | "WITHDRAWN";
/** Replaces the Week 3 CaseAction. */
export type CaseAction =
  | "UPHOLD" | "CORRECT" | "WITHDRAW" | "REQUEST_DOCS" | "ESCALATE" | "NOTE" | "ASSIGN" | "REOPEN"
  | "COLLEGE_RESPONSE" | "SYSTEM_NOTE";
export type OfficerAction = Exclude<CaseAction, "COLLEGE_RESPONSE" | "SYSTEM_NOTE">;
export type DecisionAction = Extract<CaseAction, "UPHOLD" | "CORRECT" | "WITHDRAW">;
export type CaseScope = "RECORD" | "MULTI_RECORD" | "INSTITUTION";
export type UpholdReason =
  | "DOCUMENTS_SUPPORT_CLAIM" | "SOURCE_RECORD_WRONG" | "NAME_VARIANT" | "PERMITTED_DUAL_PROGRAMME"
  | "APPROVAL_VERSION_COVERS" | "STUDENT_ANSWER_MISTAKEN" | "MISSING_NOW_UPLOADED" | "OTHER";
export type CorrectReason = "UPLOAD_ERROR" | "DOCUMENTS_SHOW_OTHER_VALUE" | "WRONG_SEAT_CATEGORY" | "OTHER";
export type WithdrawReason =
  | "STUDENT_NEVER_JOINED" | "NO_JOINING_EVIDENCE" | "BEYOND_APPROVED_INTAKE" | "NOT_ELIGIBLE_FOR_SEAT"
  | "DUPLICATE_RECORD" | "NO_RESPONSE" | "OTHER";
export type EscalateReason = "NEEDS_AICTE_DECISION" | "POLICY_QUESTION" | "SPANS_REGIONS" | "REPEATED_PATTERN" | "OTHER";
export type ReasonCode = UpholdReason | CorrectReason | WithdrawReason | EscalateReason;
export type DocsKind = "ADMISSION" | "JOINING" | "IDENTITY" | "ELIGIBILITY" | "CREDITS" | "OTHER";
/** Replaces the Week 3 CredentialKind. */
export type CredentialKind = "ENROLMENT" | "COMPLETION";
/** Replaces the Week 3 RevokedReasonCode. */
export type RevokedReasonCode =
  | "ENROLMENT_WITHDRAWN" | "ENROLMENT_TRANSFERRED" | "CLAIM_WITHDRAWN" | "STUDENT_DISPUTE" | "ADMIN" | "FLAG_CONFIRMED";
/** Replaces the Week 3 AccessedWhat. */
export type AccessedWhat = "RECORD" | "EXPORT" | "COMPLETION" | "NOTICE" | "CREDENTIAL" | "PROOF";
/** Replaces the A2.23 CheckSource. */
export type CheckSource =
  | "APAAR" | "ADMISSION_AUTHORITY" | "SEAT_LEDGER" | "ABC" | "SII" | "DIGILOCKER" | "STUDENT_NOTICE" | "COUNSELLING";
/** Replaces the A2.23 InstitutionSort. */
export type InstitutionSort = "flags_open_desc" | "enrolments_desc" | "name_asc" | "completeness_asc" | "countersigned_asc";
export type DeadlineState = "NOT_DUE" | "ON_TIME" | "LATE" | "OVERDUE";
export type SignalType = "GHOST_RING" | "ANOMALY";
export type SignalStatus = "NEW" | "CASE_OPENED" | "DISMISSED";
export type VersionSource = "UPLOAD" | "DECISION" | "SEED";
export type NoticeMatch = "MATCH" | "SOMEONE_ELSE" | "CLAIM_NEEDED";
export type CaseAgeBucket = "UNDER_7_DAYS" | "DAYS_7_TO_30" | "OVER_30_DAYS";
export type ReportName =
  | "by-state" | "by-institution-type" | "cases-by-type-and-outcome" | "countersign-coverage" | "completeness" | "summary";
export type ReportFormat = "csv" | "xlsx" | "pdf";
/** Replaces the Week 1 SourceKey and SOURCE_KEYS (adapter ping and chaos). */
export type SourceKey = "apaar" | "counselling" | "admission_authority" | "abc" | "digilocker" | "sii";
export const SOURCE_KEYS: SourceKey[] = ["apaar", "counselling", "admission_authority", "abc", "digilocker", "sii"];
/** Replaces the A2.23 UPLOAD_COLUMNS. */
export const UPLOAD_COLUMNS = [
  "apaar_id", "name", "dob", "gender", "mobile", "email", "address", "nationality", "passport_no",
  "programme_code", "academic_year", "year_of_study", "admission_route", "counselling_ref", "category",
  "consent_status", "status", "status_date", "admission_date", "tfw_income_certified", "nri_sponsored", "ciwg",
] as const;

// ---------- evidence rows and the record ----------
/** Replaces the A3.27 CheckDetail. */
export interface CheckDetail {
  summary: string; finding?: string | null; source_line?: string; basis: string;
  source_unavailable?: boolean; source_error?: string; needs_review?: boolean;
  name_score?: number; dob_match?: boolean; apaar_last4?: string;
  approval_id?: string; approval_version?: number; seat_code?: string; seat_type?: SeatType;
  flag_type?: FlagType; case_type?: FlagType; eligibility_rule?: "INTERNATIONAL_CIWG" | "NRI_STATUS" | "TFW_INCOME";
  reported?: Eligibility;
  joining_year?: string; joined_on?: string; round?: number | null; route?: AdmissionRoute | null; route_mismatch?: boolean;
  deadline?: string; published?: boolean;
  expected?: number; missing?: number; semesters?: { academic_year: string; sem: number; credits: number; issuer?: string }[];
  awaiting_semester?: number; issuer?: string; issuer_name?: string; self_issued?: boolean;
  claimed_at?: string; reviewed_by_officer?: boolean;
  notice_state?: StudentNoticeState; channel?: NoticeChannel; sent_at?: string; responded_at?: string; changed?: boolean;
  delivery_failed?: boolean; consent_withdrawn?: boolean;
  [key: string]: unknown;
}
export interface RowResolution {
  outcome: "UPHELD"; case_id: string; case_action_seq: number; reason_code: UpholdReason; at: string; by: ActorRef;
  line: string;
}
export interface EvidenceRow {
  type: CheckType; state: EvidenceState; finding: string | null; source_line: string; summary: string;
  supplied_by: string; observed_at: string | null; independent: boolean; resolved: RowResolution | null;
  source: CheckSource; checked_at: string | null; attempts: number; detail: CheckDetail;
}
export interface EvidenceRowBrief { type: CheckType; state: EvidenceState; finding: string | null; independent: boolean; resolved: boolean }
export interface RecordFields {
  record_status: RecordStatus | null; status_reason: string | null; next_step: string | null; record_status_at: string | null;
}
export interface Eligibility { tfw_income_certified: boolean | null; nri_sponsored: boolean | null; ciwg: boolean | null }

// ---------- enrolments ----------
/** Replaces the A2.23 EnrolmentRow. */
export interface EnrolmentRow extends RecordFields {
  id: string; student: StudentRef; programme_id: string; programme_code: string;
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category; eligibility: Eligibility;
  seat_code: string | null; status: EnrolmentStatus; admission_date: string; status_date: string;
  uploaded_at: string; upload_batch_id: string | null; source_row_no: number | null;
  checks: EvidenceRowBrief[]; flags: FlagRef[];
}
export interface EnrolmentPage extends Page<EnrolmentRow> { status_counts: RecordCounts }
/** Replaces the A2.23 EnrolmentListQuery. */
export interface EnrolmentListQuery {
  page?: number; page_size?: number; programme_id?: string; status?: EnrolmentStatus; academic_year?: string; q?: string;
  admission_route?: AdmissionRoute; year_of_study?: number; sort?: "name_asc" | "year_desc" | "route_asc" | "status_priority";
  record_status?: RecordStatus | string; flagged?: boolean; seated?: boolean;
}
export interface ApprovalRef {
  id: string; academic_year: string; version: number; approved_intake: number; effective_from: string; source: string;
}
/** Replaces the A3.27 EnrolmentDetail: the record card. */
export interface EnrolmentDetail extends RecordFields {
  id: string;
  institution: InstitutionRef;
  student: StudentRef & { dob: string; gender: "M" | "F" | "O" | "U"; mobile_masked: string | null };
  programme: ProgrammeRef & { level: Level; mode: ProgrammeMode; duration_years: number };
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category; eligibility: Eligibility;
  status: EnrolmentStatus; status_date: string; admission_date: string; uploaded_at: string;
  upload: { batch_id: string; filename: string; row_no: number | null } | null;
  seat: { id: string; seat_code: string; seat_type: SeatType; academic_year: string; assigned_at: string | null } | null;
  approval: ApprovalRef | null;
  claim: { claimed: boolean; claimed_at: string | null } | null;
  checks: EvidenceRow[];
  flags: FlagSummary[];
  notices: EnrolmentNotice[];
  resend: ResendState;
  credentials: CredentialRef[];
  versions: EnrolmentVersion[];
  history_count: number;
}
export interface FieldChange { field: string; before: unknown; after: unknown }
export interface EnrolmentVersion {
  version: number; at: string; source: VersionSource; actor: ActorRef | null;
  batch: { id: string; filename: string; row_no: number | null } | null;
  case: { id: string; type: FlagType; action: DecisionAction; case_action_seq: number; reason_code: ReasonCode } | null;
  changes: FieldChange[];
}
/** Replaces the A2.23 EnrolmentRecheck. */
export interface EnrolmentRecheck {
  enrolment_id: string; rechecked: number;
  results: { type: CheckType; before: EvidenceState; after: EvidenceState }[];
  flags_raised: number; record_status: RecordStatus | null; checks: EvidenceRowBrief[];
}
/** Replaces the A2.23 InstitutionRecheck. */
export interface InstitutionRecheck {
  institution_id: string; academic_year: string; enrolments: number; rechecked: number;
  outcomes: Record<EvidenceState, number>; flags_raised: number; duration_ms: number;
}

// ---------- the student ----------
/** Replaces the section D StudentEnrolment. */
export interface StudentEnrolment {
  id: string; institution_id: string; institution_name: string; programme_code: string; programme_name: string;
  academic_year: string; year_of_study: number; status: EnrolmentStatus;
  record_status: RecordStatus | null; status_reason: string | null; next_step: string | null;
  checks: EvidenceRowBrief[]; response: NoticeResponse | null; can_respond: boolean; claimed: boolean;
  decision: { outcome: "UPHELD" | "CORRECTED" | "WITHDRAWN" | "ESCALATED"; reason_code: ReasonCode | null; at: string } | null;
}
/** Replaces the A3.27 StudentMe. */
export interface StudentMe {
  id: string; name: string; apaar_masked: string | null; consent_status: ConsentStatus; provisional_id: string | null;
  dob: string; email: string | null; mobile_masked: string | null; signed_in_with: "DIGILOCKER";
  enrolments: StudentEnrolment[];
  notices: StudentNotice[];
  credentials: StudentCredentialBrief[];
}
/** Replaces the A3.27 NoticePublic. */
export interface NoticePublic {
  channel: NoticeChannel; institution_name: string; programme_code: string; programme_name: string;
  academic_year: string; year_of_study: number; id_kind: IdKind; id_masked: string;
  uploaded_at: string; sent_at: string | null; expires_at: string;
  response: NoticeResponse | null; responded_at: string | null;
  previous_response: NoticeResponse | null; changed_at: string | null; can_change_until: string | null;
  consent_text: string; notice_version: string;
  viewer: { signed_in: boolean; name: string | null; match: NoticeMatch | null };
  can_answer: boolean; sign_in_url: string; claim_url: string | null;
}
export interface PendingClaim { name: string; birthdate: string; next: string }
export interface ClaimRequest { provisional_id: string }
export interface ClaimResult { user: User; next: string; claimed: { student_id: string; enrolments: StudentEnrolment[] } }

// ---------- uploads ----------
/** Replaces the A2.23 UploadCounts. */
export interface UploadCounts {
  rows: number; accepted: number; errors: number; warnings: number;
  created: number; updated: number; unchanged: number; withdrawn: number; transferred: number;
  seated: number; released: number; unseated: number; flags_raised: number; flags_updated: number;
  versions: number; records: RecordCounts;
}
/** Replaces the A2.23 UploadBatch. */
export interface UploadBatch {
  id: string; institution_id: string; institution_name: string; academic_year: string; filename: string;
  source: UploadSource; kind: UploadKind; status: UploadStatus; stage: UploadStage | null;
  total_rows: number; stage_total: number; processed_rows: number; progress_pct: number;
  counts: UploadCounts; sources: UploadSourceStat[]; timings_ms: Partial<Record<UploadStage, number>>;
  error: string | null; ignored_columns: string[]; column_mapping: { header: string; column: UploadColumn }[];
  same_file_as: { batch_id: string; uploaded_at: string } | null;
  uploaded_by: { id: string; name: string };
  uploaded_at: string; started_at: string | null; finished_at: string | null;
}
export interface ColumnMapping {
  institution_id: string; mapping: Record<string, UploadColumn>; updated_at: string | null;
  updated_by: { id: string; name: string } | null; columns: { column: UploadColumn; required: boolean }[];
}
export interface ColumnMappingPut { mapping: Record<string, UploadColumn>; headers?: string[] }
export interface HeaderUnmappedDetails {
  unknown_headers: string[]; missing_columns: UploadColumn[]; suggestions: { header: string; column: UploadColumn }[];
}

// ---------- approvals and completeness ----------
export interface ApprovalVersion { version: number; approved_intake: number; effective_from: string; source: string; created_at: string }
export interface ApprovalVersions {
  approval_id: string; institution: { id: string; name: string; aicte_permanent_id: string };
  programme: ProgrammeRef; academic_year: string; current_version: number; items: ApprovalVersion[];
}
export interface ApprovalVersionCreate { approved_intake: number; effective_from: string; source: string }
export interface ApprovalVersionCreated extends ApprovalVersions {
  effects: { seats_added: number; seats_removed: number; seated: number; flags_refreshed: number; records_changed: number };
}
export interface MissingStudent {
  name: string; roll_no: string | null; programme_code: string; joined_on: string; round: number | null;
  route: AdmissionRoute; apaar_masked: string | null;
}
export interface Completeness {
  academic_year: string; joined: number; uploaded_and_joined: number; missing: number; uploaded_not_joined: number;
  completeness_pct: number | null; published: boolean;
  deadline: string; first_upload_at: string | null; deadline_state: DeadlineState;
  computed_at: string | null; source_unavailable: boolean; case: { id: string; status: FlagStatus } | null;
  missing_students?: MissingStudent[];
}
export interface InstitutionCompleteness extends Completeness { institution: InstitutionRef }
export interface CompletenessRow {
  institution: InstitutionRef; joined: number; uploaded_and_joined: number; missing: number;
  completeness_pct: number | null; published: boolean; deadline_state: DeadlineState; first_upload_at: string | null;
  case_status: FlagStatus | null;
}
export interface CompletenessPage extends Page<CompletenessRow> {
  totals: { joined: number; uploaded_and_joined: number; missing: number; completeness_pct: number | null;
            deadline_states: Record<DeadlineState, number> };
  deadline: string;
}
export interface CompletenessQuery {
  academic_year?: string; region?: Region; state?: string; deadline_state?: DeadlineState;
  sort?: "completeness_asc" | "missing_desc" | "name_asc"; page?: number; page_size?: number;
}

// ---------- institutions and dashboard ----------
/** Replaces the A2.23 DashboardSummary. */
export interface DashboardSummary {
  academic_year: string;
  scope: { kind: "NATIONAL" | "REGION" | "INSTITUTION" | "UNIVERSITY"; label: string };
  kpis: {
    institutions: number; programmes: number; approved_seats: number; admitted: number; enrolments: number;
    flags_open: number; countersigned_pct: number | null; records: RecordCounts;
    joined: number; missing_from_upload: number; completeness_pct: number | null;
    colleges_late: number; colleges_overdue: number; signals_new: number | null;
  };
  records_by_status: { status: RecordStatus; count: number; pct: number | null }[];
  flags_by_type: { type: FlagType; open: number }[];
  cases_by_age: { bucket: CaseAgeBucket; open: number }[];
  top_institutions: { institution: InstitutionRef; flags_open: number; disputed: number; under_review: number }[];
  completeness: Completeness | null;
  by_state: {
    state_code: string; state_name: string; region: Region; institutions: number; programmes: number;
    approved_seats: number; admitted: number; enrolments: number; flags_open: number;
    records: RecordCounts; countersigned_pct: number | null; completeness_pct: number | null; missing_from_upload: number;
  }[];
  by_region: {
    region: Region; region_name: string; institutions: number; approved_seats: number; admitted: number;
    enrolments: number; flags_open: number;
    records: RecordCounts; countersigned_pct: number | null; completeness_pct: number | null; missing_from_upload: number;
  }[];
}
/** Replaces the A2.23 InstitutionRow. */
export interface InstitutionRow {
  id: string; aicte_permanent_id: string; name: string; type: InstitutionType;
  state_code: string; state_name: string; region: Region; region_name: string;
  university_id: string | null; university_name: string | null;
  programmes: number; approved_seats: number; admitted: number; enrolments: number; flags_open: number;
  records: RecordCounts; countersigned_pct: number | null; completeness_pct: number | null;
  missing_from_upload: number; deadline_state: DeadlineState;
}
/** Replaces the A2.23 ProgrammeDetail. */
export interface ProgrammeDetail {
  id: string; code: string; name: string; level: Level; discipline: Discipline; shift: Shift; mode: ProgrammeMode;
  approval: {
    id: string; academic_year: string; approved_intake: number; cutoff_date: string | null;
    version: number; effective_from: string; source: string;
  };
  enrolments: number; seated: number; unseated: number; pools: SeatPool[];
}
/** Replaces the A2.23 InstitutionDetail. */
export interface InstitutionDetail extends Omit<InstitutionRow, "programmes"> {
  address_city: string | null; established_year: number | null;
  last_upload: LastUpload | null;
  completeness: Omit<Completeness, "missing_students">;
  programmes: ProgrammeDetail[];
}

// ---------- cases ----------
/** Replaces the A3.27 CaseHistoryItem. */
export interface CaseHistoryItem {
  seq: number; at: string; action: CaseAction; from_status: FlagStatus | null; to_status: FlagStatus | null;
  actor: ActorRef | null; note: string | null; due_date: string | null;
  assignee: { id: string; name: string } | null; attachments: CaseAttachment[];
  reason_code: ReasonCode | null; docs_kind: DocsKind | null; approval_version: number | null;
  correction: { enrolment_id: string; changes: FieldChange[] } | null;
  withdrawn_enrolment_ids: string[];
}
export type CorrectableField =
  | "name" | "dob" | "year_of_study" | "admission_route" | "category" | "counselling_ref" | "admission_date"
  | "tfw_income_certified" | "nri_sponsored" | "ciwg";
/** Replaces the A3.27 CaseActionRequest. */
export interface CaseActionRequest {
  action: OfficerAction; reason_code?: ReasonCode; note?: string;
  docs_kind?: DocsKind; due_date?: string | null; assignee_id?: string | null;
  withdrawn_enrolment_ids?: string[];
  correction?: { enrolment_id?: string; fields: Partial<Record<CorrectableField, string | number | boolean | null>> };
  approval_version?: number;
  dry_run?: boolean;
}
export interface DecisionEffects {
  case_status: FlagStatus;
  records: { enrolment_id: string; status: EnrolmentStatus; record_status: RecordStatus | null; status_reason: string | null }[];
  version: number | null; changes: FieldChange[];
  rows_resolved: number; rows_rerun: number;
  seats_released: { enrolment_id: string; seat_code: string }[];
  seats_assigned: { enrolment_id: string; seat_code: string }[];
  attestations_revoked: { enrolment_id: string; credential_id: string; short_id: string }[];
  attestations_issued: { enrolment_id: string; credential_id: string; short_id: string }[];
  approval: { version: number; approved_intake: number; cohort_year: string; programme_code: string } | null;
}
export interface DryRunResult { dry_run: true; effects: DecisionEffects }
/** Replaces the A3.27 FlagRow. */
export interface FlagRow {
  id: string; type: FlagType; severity: Severity; status: FlagStatus;
  institution: InstitutionRef; programme: ProgrammeRef | null; enrolment_id: string | null; academic_year: string;
  summary: string; related_count: number; assignee: { id: string; name: string } | null;
  response_received: boolean; docs_due_on: string | null; last_action_at: string | null;
  covers: CheckType | null; scope: CaseScope;
  decision: { action: DecisionAction; reason_code: ReasonCode; at: string } | null;
  signal_id: string | null;
  created_at: string; updated_at: string;
}
/** Replaces the A3.27 FlagListQuery. */
export interface FlagListQuery {
  page?: number; page_size?: number; type?: FlagType; severity?: Severity; status?: FlagStatus;
  institution_id?: string; programme_id?: string; state?: string; academic_year?: string; q?: string; sort?: FlagSort;
  assignee?: "me" | "none" | string; response_received?: boolean; signal_id?: string;
}
/** Replaces the A3.27 FlagDetail. */
export interface FlagDetail extends FlagRow {
  evidence: Evidence;
  enrolment: RelatedEnrolmentRow | null;
  related_enrolments: RelatedEnrolmentRow[];
  related_hidden: number;
  outstanding_enrolment_ids: string[];
  approval: { id: string; current_version: number; approved_intake: number; covers: boolean } | null;
  missing_students: MissingStudent[];
  history: CaseHistoryItem[];
  allowed_actions: OfficerAction[];
  can_respond: boolean;
}
export interface CaseActionResult extends FlagDetail { effects: DecisionEffects }

// ---------- signals ----------
export interface SignalRow {
  id: string; type: SignalType; academic_year: string; status: SignalStatus; summary: string;
  member_count: number; members_hidden: number; score: number | null;
  institutions: { id: string; name: string; aicte_permanent_id: string; state_code: string; region: Region }[];
  institutions_hidden: number;
  rule: string; cases: { id: string; institution_id: string; status: FlagStatus }[];
  created_at: string; updated_at: string;
}
export interface SignalFeature {
  name: "admission_growth" | "nri_share" | "management_share" | "contradiction_rate" | "contact_sharing_rate";
  value: number; peer_low: number; peer_high: number; peer_median: number; robust_z: number; stands_out: boolean;
}
export interface SignalMember {
  enrolment_id: string; student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  institution: { id: string; name: string }; programme_code: string; record_status: RecordStatus | null;
}
export interface SignalDetail extends SignalRow {
  facts: EvidenceFact[];
  shared: { kind: "MOBILE" | "EMAIL" | "ADDRESS"; masked: string; students: number }[];
  features: SignalFeature[];
  members: SignalMember[];
  dismissal: { note: string; by: { id: string; name: string }; at: string } | null;
}
export interface SignalListQuery {
  page?: number; page_size?: number; academic_year?: string; type?: SignalType; status?: SignalStatus;
  institution_id?: string; state?: string; sort?: "newest" | "score";
}
export interface SignalOpenCase { institution_ids?: string[]; note: string; severity?: Severity }
export interface SignalOpenCaseResult { cases: FlagRow[]; signal: SignalDetail }
export interface SignalDismiss { note: string }
export interface SignalRun {
  academic_year: string; rings: number; anomalies: number; created: number; updated: number; duration_ms: number;
  model: { name: "IsolationForest"; contamination: number; n_estimators: number; random_state: number; institutions: number };
}

// ---------- reports ----------
export interface ReportInfo { name: ReportName; title: string; formats: ReportFormat[]; columns: string[] }
export interface ReportQuery { academic_year?: string; region?: Region; state?: string }

// ---------- attestations and certificate integration ----------
/** Replaces the A3.27 GraduateRow. */
export interface GraduateRow {
  enrolment_id: string;
  student: { id: string; name: string; apaar_masked: string | null; provisional_id: string | null };
  institution: { id: string; name: string; aicte_permanent_id: string };
  programme: { id: string; code: string; name: string; level: Level };
  academic_year: string; year_of_award: number;
  attestation: { credential_id: string; short_id: string; status: CredentialStatus; issued_at: string } | null;
}
/** Replaces the A3.27 GraduateListQuery. */
export interface GraduateListQuery {
  page?: number; page_size?: number; q?: string; institution_id?: string; academic_year?: string;
  attestation?: "issued" | "not_issued"; university_id?: string;
}
/** Replaces the A3.27 DegreePrint. */
export interface CertificatePrint {
  enrolment_id: string;
  student: { name: string; id_kind: IdKind; id_masked: string };
  programme: { code: string; name: string; short_name: string };
  institution: { name: string; aicte_permanent_id: string; short_name: string };
  university: { code: string; name: string };
  academic_year: string; year_of_award: number;
  attestation: {
    credential_id: string; short_id: string; status: CredentialStatus; issued_at: string; revoked_at: string | null;
    jws: string; verify_url: string; lookup_url: string; qr_svg: string;
  } | null;
}

// ---------- privacy ----------
/** Replaces the A3.27 MyDataExport (enrolments carry states, the record and the history). */
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
    seat_code: string | null; record_status: RecordStatus | null; status_reason: string | null;
    checks: {
      type: CheckType; state: EvidenceState; finding: string | null; source_line: string; summary: string;
      supplied_by: string; observed_at: string | null; checked_at: string | null;
    }[];
    flags: { type: FlagType; status: FlagStatus; summary: string; created_at: string }[];
    history: Omit<EnrolmentVersion, "actor">[];
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
