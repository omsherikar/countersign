/**
 * Wire types for the Countersign API.
 * Source: docs/API_CONTRACT.md section D, extended with Addendum 1
 * (region_name, rule_source, cutoff_date, last_upload, upload_batch_id,
 * source_row_no, retry_after) and the health and chaos shapes from A.1 and C.8.
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

export interface Check {
  type: CheckType;
  status: CheckStatus;
  source: string;
  checked_at: string | null;
  detail: Record<string, unknown>;
}
export interface Countersign {
  score: { passes: number; applicable: number } | null;
  checks: Check[];
}
export interface FlagRef {
  id: string;
  type: FlagType;
  severity: Severity;
  status: FlagStatus;
}

export type ScopeKind = "NATIONAL" | "REGION" | "INSTITUTION" | "UNIVERSITY";
export interface StateSummaryRow {
  state_code: string;
  state_name: string;
  region: Region;
  institutions: number;
  programmes: number;
  approved_seats: number;
  enrolments: number;
  flags_open: number;
}
export interface RegionSummaryRow {
  region: Region;
  region_name: string;
  institutions: number;
  approved_seats: number;
  enrolments: number;
  flags_open: number;
}
export interface DashboardSummary {
  academic_year: string;
  scope: { kind: ScopeKind; label: string };
  kpis: {
    institutions: number;
    programmes: number;
    approved_seats: number;
    enrolments: number;
    flags_open: number;
    countersigned_pct: number | null;
  };
  by_state: StateSummaryRow[];
  by_region: RegionSummaryRow[];
}

export interface InstitutionRow {
  id: string;
  aicte_permanent_id: string;
  name: string;
  type: InstitutionType;
  state_code: string;
  state_name: string;
  region: Region;
  /** Addendum 1.1 */
  region_name: string;
  university_id: string | null;
  university_name: string | null;
  programmes: number;
  approved_seats: number;
  enrolments: number;
  flags_open: number;
  integrity_index: number | null;
}
export interface SeatPool {
  seat_type: SeatType;
  capacity: number;
  is_supernumerary: boolean;
  assigned: number;
  free: number;
  reserved_for: string | null;
  /** Addendum 1.2: clause in rules.yaml the pool size comes from. */
  rule_source: string;
}
export interface ProgrammeDetail {
  id: string;
  code: string;
  name: string;
  level: Level;
  discipline: Discipline;
  shift: Shift;
  approval: {
    academic_year: string;
    approved_intake: number;
    /** Addendum 1.2 */
    cutoff_date: string | null;
  };
  enrolments: number;
  pools: SeatPool[];
  unseated: number;
}
export interface LastUpload {
  batch_id: string;
  uploaded_at: string;
  rows: number;
  errors: number;
}
/**
 * Section D declares this as Omit<InstitutionRow, "programmes">, but the A.7
 * example and the live api carry no approved_seats or enrolments on the
 * detail; those come from summing programmes[].
 */
export interface InstitutionDetail extends Omit<InstitutionRow, "programmes" | "approved_seats" | "enrolments"> {
  address_city: string | null;
  established_year: number | null;
  integrity_components: Record<string, number> | null;
  programmes: ProgrammeDetail[];
  /** Addendum 1.2: null in Week 1. */
  last_upload: LastUpload | null;
}
export interface SeatRow {
  id: string;
  seat_code: string;
  /** Approval year the seat belongs to; the api defaults to the current academic year. */
  academic_year: string;
  programme_code: string;
  seat_type: SeatType;
  status: SeatStatus;
  reserved_for: string | null;
  enrolment_id: string | null;
  student_name: string | null;
  assigned_at: string | null;
}
export interface StudentRef {
  id: string;
  name: string;
  apaar_masked: string | null;
  consent_status: ConsentStatus;
  provisional_id: string | null;
  nationality: string;
}
export interface EnrolmentRow {
  id: string;
  student: StudentRef;
  programme_id: string;
  programme_code: string;
  academic_year: string;
  year_of_study: number;
  admission_route: AdmissionRoute;
  counselling_ref: string | null;
  category: Category;
  seat_code: string | null;
  status: EnrolmentStatus;
  uploaded_at: string;
  /** Addendum 1.3 */
  upload_batch_id: string | null;
  /** Addendum 1.3 */
  source_row_no: number | null;
  countersign: Countersign;
  flags: FlagRef[];
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

/** Query parameters. */
export type InstitutionSort = "name" | "enrolments" | "approved_seats";
export interface InstitutionListParams {
  page?: number;
  page_size?: number;
  state?: string;
  region?: Region;
  type?: InstitutionType;
  q?: string;
  sort?: InstitutionSort;
  order?: "asc" | "desc";
}
export interface SeatListParams {
  page?: number;
  page_size?: number;
  programme_id?: string;
  seat_type?: SeatType;
  status?: SeatStatus;
  q?: string;
}
export interface EnrolmentListParams {
  page?: number;
  page_size?: number;
  programme_id?: string;
  status?: EnrolmentStatus;
  academic_year?: string;
  q?: string;
  admission_route?: AdmissionRoute;
  year_of_study?: number;
}
