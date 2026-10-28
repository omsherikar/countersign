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
export type CheckStatus = "PASS" | "FAIL" | "PENDING" | "NA";
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "CLEARED" | "ESCALATED" | "CONFIRMED";
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
export interface StudentMe {
  id: string;
  name: string;
  apaar_masked: string | null;
  consent_status: ConsentStatus;
  provisional_id: string | null;
  dob: string;
  email: string | null;
  mobile_masked: string | null;
  enrolments: StudentEnrolment[];
  notices: unknown[];
  credentials: unknown[];
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
export interface AuditRow {
  seq: number;
  at: string;
  actor_id: string | null;
  actor_email: string | null;
  action: AuditAction;
  entity_type: string;
  entity_id: string | null;
  hash: string;
  prev_hash: string | null;
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
export interface CheckDetail {
  summary: string;
  source_unavailable?: boolean; source_error?: string; needs_review?: boolean;
  name_score?: number; dob_match?: boolean; apaar_last4?: string;
  round?: number; allotment_ref?: string; ref_mismatch?: boolean;
  seat_code?: string; seat_type?: SeatType; flag_type?: FlagType;
  expected?: number; missing?: number; semesters?: { academic_year: string; sem: number; credits: number }[];
  awaiting_semester?: number;
  [key: string]: unknown;
}
/** Replaces the Week 1 Check. */
export interface Check { type: CheckType; status: CheckStatus; source: CheckSource; checked_at: string | null; attempts: number; detail: CheckDetail }

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
export interface EnrolmentDetail {
  id: string;
  institution: InstitutionRef;
  student: StudentRef & { dob: string; gender: "M" | "F" | "O" | "U"; mobile_masked: string | null };
  programme: ProgrammeRef & { level: Level; mode: ProgrammeMode; duration_years: number };
  academic_year: string; cohort_year: string; year_of_study: number;
  admission_route: AdmissionRoute; counselling_ref: string | null; category: Category;
  status: EnrolmentStatus; status_date: string; admission_date: string; uploaded_at: string;
  upload: { batch_id: string; filename: string; row_no: number | null } | null;
  seat: { id: string; seat_code: string; seat_type: SeatType; academic_year: string; assigned_at: string | null } | null;
  countersign: Countersign;
  checks: Check[];
  flags: FlagSummary[];
}
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
export interface FlagRow {
  id: string; type: FlagType; severity: Severity; status: FlagStatus;
  institution: InstitutionRef; programme: ProgrammeRef | null; enrolment_id: string | null; academic_year: string;
  summary: string; related_count: number; assignee: { id: string; name: string } | null;
  created_at: string; updated_at: string;
}
export interface FlagPage extends Page<FlagRow> { institutions: number }
export interface FlagListQuery {
  page?: number; page_size?: number; type?: FlagType; severity?: Severity; status?: FlagStatus;
  institution_id?: string; programme_id?: string; state?: string; academic_year?: string; q?: string; sort?: FlagSort;
}
export interface RelatedEnrolmentRow extends EnrolmentRow { institution: { id: string; name: string } }
export interface FlagDetail extends FlagRow {
  evidence: Evidence;
  enrolment: RelatedEnrolmentRow | null;
  related_enrolments: RelatedEnrolmentRow[];
  related_hidden: number;
  history: unknown[]; // always [] in Week 2
}

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
