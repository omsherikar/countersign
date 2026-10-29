/**
 * Mock-mode records: the record status of each enrolment with the cases that
 * name it (API_CONTRACT A4.3), record counts per college, completeness
 * against the admission authority's joinings list (A4.18), the saved column
 * mapping (A4.16), approval versions (A4.17) and the record's history (A4.7).
 */
import { ApiError, type Query } from "@/lib/api";
import { recordOf, type CaseView } from "@/lib/mock/evidence";
import { ACADEMIC_YEAR, APPROVAL_VERSIONS, BASE_PROGRAMMES, IDS, SEEDS, STATES } from "@/lib/mock/fixtures";
import { allFlags, UNRESOLVED, type StoredFlag } from "@/lib/mock/flags";
import { FIRST_UPLOAD, RECONCILED_AT, REPORTING_DEADLINE, deadlineStateOf, joinedCounts } from "@/lib/mock/joinings";
import { CHECKED_AT, recordContext, rollFor, versionsOf, type RollEntry } from "@/lib/mock/roll";
import { UPLOAD_COLUMNS } from "@/lib/types";
import type {
  ApprovalVersions,
  ColumnMapping,
  ColumnMappingPut,
  Completeness,
  CompletenessPage,
  CompletenessRow,
  DeadlineState,
  FlagStatus,
  InstitutionCompleteness,
  InstitutionRow,
  Page,
  RecordCounts,
  RecordFields,
  Role,
  UploadColumn,
  User,
} from "@/lib/types";

/** Case types that never name a record (A4.3). */
const NAME_NO_RECORD = new Set(["MISSING_FROM_UPLOAD", "ANOMALY"]);

/** Cases naming the record: its own, or a related record at the case's institution (A4.3). */
export function casesNaming(e: RollEntry, flags: StoredFlag[] = allFlags()): StoredFlag[] {
  return flags.filter(
    (f) => !NAME_NO_RECORD.has(f.type) && (f.enrolmentId === e.row.id || (f.related.includes(e.row.id) && f.institutionId === e.institutionId)),
  );
}

function view(f: StoredFlag): CaseView {
  return {
    id: f.id,
    type: f.type,
    severity: f.severity,
    status: f.status,
    created_at: f.created_at,
    docs: f.progress.docs,
    escalated_at: f.progress.escalated_at,
  };
}

/** The record for a given set of rows (the student's own view recomputes with their answer). */
export function recordFor(e: RollEntry, rows: RollEntry["checks"] = e.checks) {
  return recordOf(rows, casesNaming(e).map(view), recordContext(e));
}

const SINCE = new Map<string, { status: string; at: string }>();

/** Recomputes the record from its rows and the cases naming it, stores it on the row, and returns it. */
export function withRecord(e: RollEntry, flags?: StoredFlag[]): RecordFields {
  const r = e.row;
  if (r.status !== "ACTIVE") {
    Object.assign(r, { record_status: null, status_reason: null, next_step: null });
    return { record_status: null, status_reason: null, next_step: null, record_status_at: r.record_status_at };
  }
  const naming = casesNaming(e, flags);
  const record = recordOf(e.checks, naming.map(view), recordContext(e));
  const prior = SINCE.get(r.id);
  let at: string;
  if (!prior) {
    const student = e.checks.find((c) => c.type === "STUDENT");
    const open = naming.filter((f) => UNRESOLVED.includes(f.status)).map((f) => f.created_at).sort();
    at = record.record_status === "DISPUTED" && student?.observed_at ? student.observed_at : record.record_status === "UNDER_REVIEW" && open[0] ? open[0] : CHECKED_AT;
  } else {
    at = prior.status === record.record_status ? prior.at : new Date().toISOString().replace(/\.\d+Z$/, "Z");
  }
  SINCE.set(r.id, { status: record.record_status, at });
  Object.assign(r, record, { record_status_at: at });
  return { ...record, record_status_at: at };
}

export const ZERO_COUNTS = (): RecordCounts => ({ AWAITING_EVIDENCE: 0, COUNTERSIGNED: 0, UNDER_REVIEW: 0, DISPUTED: 0 });

/** Active records of 2026-27 by status, for one college. */
export function countsFor(institutionId: string): RecordCounts {
  const flags = allFlags();
  const counts = ZERO_COUNTS();
  for (const e of rollFor(institutionId)) {
    if (e.row.status !== "ACTIVE" || e.row.academic_year !== ACADEMIC_YEAR) continue;
    const rec = withRecord(e, flags);
    if (rec.record_status) counts[rec.record_status] += 1;
  }
  return counts;
}

export function pct(n: number, d: number): number | null {
  return d === 0 ? null : Math.round((n / d) * 1000) / 10;
}

/** The reconciliation of one college for 2026-27 (A4.18), without the institution. */
export function completenessOf(institutionId: string): Completeness {
  const c = joinedCounts(institutionId);
  const caseFlag = allFlags().find((f) => f.type === "MISSING_FROM_UPLOAD" && f.institutionId === institutionId);
  return {
    academic_year: ACADEMIC_YEAR,
    joined: c.joined,
    uploaded_and_joined: c.matched,
    missing: c.missing.length,
    uploaded_not_joined: c.notJoined,
    completeness_pct: c.published ? pct(c.matched, c.joined) : null,
    published: c.published,
    deadline: REPORTING_DEADLINE,
    first_upload_at: FIRST_UPLOAD[institutionId] ?? null,
    deadline_state: deadlineStateOf(institutionId),
    computed_at: RECONCILED_AT,
    source_unavailable: false,
    case: caseFlag ? { id: caseFlag.id, status: caseFlag.status as FlagStatus } : null,
    missing_students: c.missing,
  };
}

export function stateNameOf(institutionId: string): string {
  const code = SEEDS.find((s) => s.id === institutionId)!.state_code;
  return STATES.find((s) => s.code === code)!.name;
}

/* ---- Column mapping (A4.16) ------------------------------------------------ */

const MAPPING_STORE = "cs-mock-column-mapping";
const REQUIRED_COLUMNS: UploadColumn[] = ["name", "dob", "programme_code", "year_of_study", "admission_route", "category"];

interface StoredMapping {
  mapping: Record<string, UploadColumn>;
  updated_at: string;
  updated_by: { id: string; name: string };
}

/** XYZ Institute's files use their own headers (A4.25 column_mappings.json); the seed saved its mapping. */
const SEEDED_MAPPINGS: Record<string, StoredMapping> = {
  [IDS.xyz]: {
    mapping: {
      "Student Name": "name",
      "D.O.B.": "dob",
      "Course Code": "programme_code",
      "Current Year": "year_of_study",
      "Admission Type": "admission_route",
      "Caste Category": "category",
      "APAAR No": "apaar_id",
      "Mobile No": "mobile",
      "Email ID": "email",
    },
    updated_at: "2026-09-17T10:20:00Z",
    updated_by: { id: "6f1c0a8e-0005-4c9a-9e51-1c2f1a0b7d33", name: "Registrar, XYZ Institute of Technology" },
  },
};

function readMappings(): Record<string, StoredMapping | null> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.sessionStorage.getItem(MAPPING_STORE) ?? "{}") as Record<string, StoredMapping | null>;
  } catch {
    return {};
  }
}

function writeMappings(all: Record<string, StoredMapping | null>) {
  try {
    window.sessionStorage.setItem(MAPPING_STORE, JSON.stringify(all));
  } catch {
    /* private mode: the mapping lives for this page only */
  }
}

export function savedMapping(institutionId: string): StoredMapping | null {
  const all = readMappings();
  return institutionId in all ? all[institutionId] : (SEEDED_MAPPINGS[institutionId] ?? null);
}

export function columnMapping(institutionId: string): ColumnMapping {
  const saved = savedMapping(institutionId);
  return {
    institution_id: institutionId,
    mapping: saved?.mapping ?? {},
    updated_at: saved?.updated_at ?? null,
    updated_by: saved?.updated_by ?? null,
    columns: UPLOAD_COLUMNS.map((column) => ({ column, required: REQUIRED_COLUMNS.includes(column) })),
  };
}

/** Each header cell normalised as A2.2: trimmed, lower case, spaces and hyphens to underscores. */
export function normaliseHeader(h: string): string {
  return h.trim().replace(/^﻿/, "").toLowerCase().replace(/[\s-]+/g, "_");
}

const SYNONYMS: Record<string, UploadColumn> = {
  student_name: "name", full_name: "name", name_of_student: "name", candidate_name: "name",
  "d.o.b.": "dob", "d.o.b": "dob", date_of_birth: "dob", birth_date: "dob",
  course_code: "programme_code", branch_code: "programme_code", branch: "programme_code", programme: "programme_code", program_code: "programme_code",
  current_year: "year_of_study", year: "year_of_study", class_year: "year_of_study",
  admission_type: "admission_route", quota: "admission_route", route: "admission_route",
  caste_category: "category", reservation_category: "category",
  apaar_no: "apaar_id", apaar: "apaar_id", apaar_number: "apaar_id",
  mobile_no: "mobile", phone: "mobile", contact_no: "mobile",
  email_id: "email", e_mail: "email",
  sex: "gender",
  passport: "passport_no", passport_number: "passport_no",
  allotment_no: "counselling_ref", cap_id: "counselling_ref",
  date_of_admission: "admission_date", joining_date: "admission_date",
};

/** Reads a header row with the saved mapping (A4.16): mapped, template or unknown. */
export function resolveHeaders(institutionId: string, headers: string[]) {
  const saved = savedMapping(institutionId)?.mapping ?? {};
  const byKey = new Map(Object.entries(saved).map(([k, v]) => [normaliseHeader(k), v]));
  const mapped: { header: string; column: UploadColumn }[] = [];
  const unknown: string[] = [];
  const found = new Set<UploadColumn>();
  for (const h of headers) {
    const key = normaliseHeader(h);
    if (!key) continue;
    const viaMapping = byKey.get(key);
    if (viaMapping) {
      mapped.push({ header: h, column: viaMapping });
      found.add(viaMapping);
    } else if ((UPLOAD_COLUMNS as readonly string[]).includes(key)) {
      found.add(key as UploadColumn);
    } else {
      unknown.push(h);
    }
  }
  const missing = REQUIRED_COLUMNS.filter((c) => !found.has(c));
  const suggestions = unknown
    .map((header) => ({ header, column: SYNONYMS[normaliseHeader(header)] }))
    .filter((s): s is { header: string; column: UploadColumn } => Boolean(s.column));
  return { mapped, unknown, missing, suggestions };
}

function mappingPut(user: User, institutionId: string, body: unknown): ColumnMapping {
  const req = (body ?? {}) as Partial<ColumnMappingPut>;
  const mapping = req.mapping ?? {};
  const entries = Object.entries(mapping);
  if (entries.length > 60) throw new ApiError(422, "VALIDATION_ERROR", "Map at most 60 columns.", { fields: [{ field: "mapping", message: "Map at most 60 columns." }] });
  for (const [header, column] of entries) {
    if (!header || header.length > 120 || !(UPLOAD_COLUMNS as readonly string[]).includes(column)) {
      throw new ApiError(422, "VALIDATION_ERROR", "Map to a template column.", { fields: [{ field: "mapping", message: "Map to a template column." }] });
    }
  }
  const seen = new Map<string, string>();
  for (const [header, column] of entries) {
    if (seen.has(column)) throw new ApiError(422, "MAPPING_DUPLICATE", `Each Countersign column can be chosen once. ${column} is chosen more than once.`, { column });
    seen.set(column, header);
  }
  const keys = new Set<string>();
  for (const [header] of entries) {
    const k = normaliseHeader(header);
    if (keys.has(k)) throw new ApiError(422, "MAPPING_DUPLICATE", `Each Countersign column can be chosen once. ${mapping[header]} is chosen more than once.`, { column: mapping[header] });
    keys.add(k);
  }
  if (req.headers) {
    const found = new Set<string>();
    for (const h of req.headers) {
      const key = normaliseHeader(h);
      const direct = Object.entries(mapping).find(([k]) => normaliseHeader(k) === key)?.[1];
      if (direct) found.add(direct);
      else if ((UPLOAD_COLUMNS as readonly string[]).includes(key)) found.add(key);
    }
    const missing = REQUIRED_COLUMNS.filter((c) => !found.has(c));
    if (missing.length) throw new ApiError(422, "MAPPING_INCOMPLETE", `Map every required column before you continue: ${missing.join(", ")}.`, { missing_columns: missing });
  }
  const all = readMappings();
  all[institutionId] = entries.length ? { mapping, updated_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"), updated_by: { id: user.id, name: user.name } } : null;
  writeMappings(all);
  return columnMapping(institutionId);
}

/* ---- Routes this file answers in mock mode -------------------------------- */

export const NOT_MINE = Symbol("not-records");

export interface RecordsContext {
  user: User;
  method: string;
  parts: string[];
  query?: Query;
  body?: unknown;
  /** The institution, or the api's 404 when it is outside the caller's scope. */
  inScope: (institutionId: string) => InstitutionRow;
  scoped: () => InstitutionRow[];
  /** The enrolment, or 403 for the role and 404 outside scope. */
  enrolmentInScope: (id: string, roles: Role[]) => RollEntry;
  paginate: <T>(items: T[], query?: Query) => Page<T>;
}

const forbidden = (roles: Role[]) => new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: roles });
const OFFICERS: Role[] = ["AICTE_ADMIN", "RO_OFFICER"];

/**
 * GET /enrolments/{id}/history (A4.7), GET /institutions/{id}/completeness and
 * GET /completeness (A4.18), GET and PUT /institutions/{id}/column-mapping
 * (A4.16), GET /approvals/{id}/versions (A4.17).
 */
export function recordsRequest(ctx: RecordsContext): unknown {
  const { user, method, parts, query } = ctx;
  const need = (roles: Role[]) => {
    if (!roles.includes(user.role)) throw forbidden(roles);
  };

  if (parts[0] === "enrolments" && parts[1] && parts[2] === "history" && method === "GET") {
    const e = ctx.enrolmentInScope(parts[1], ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    return ctx.paginate(versionsOf(e), query);
  }

  if (parts[0] === "institutions" && parts[1] && parts[2] === "completeness" && parts.length === 3 && method === "GET") {
    need(["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    const row = ctx.inScope(parts[1]);
    const c = completenessOf(row.id);
    const institution = { id: row.id, name: row.name, aicte_permanent_id: row.aicte_permanent_id, state_code: row.state_code, state_name: row.state_name, region: row.region };
    const body: InstitutionCompleteness = { institution, ...c, missing_students: user.role === "UNIVERSITY" ? [] : c.missing_students };
    return body;
  }

  if (parts[0] === "completeness" && parts.length === 1 && method === "GET") {
    need(OFFICERS);
    let rows = ctx.scoped();
    if (query?.region && user.role === "AICTE_ADMIN") rows = rows.filter((r) => r.region === query.region);
    if (query?.state) rows = rows.filter((r) => r.state_code === query.state);
    const items: CompletenessRow[] = rows.map((r) => {
      const c = completenessOf(r.id);
      return {
        institution: { id: r.id, name: r.name, aicte_permanent_id: r.aicte_permanent_id, state_code: r.state_code, state_name: r.state_name, region: r.region },
        joined: c.joined,
        uploaded_and_joined: c.uploaded_and_joined,
        missing: c.missing,
        completeness_pct: c.completeness_pct,
        published: c.published,
        deadline_state: c.deadline_state,
        first_upload_at: c.first_upload_at,
        case_status: c.case?.status ?? null,
      };
    });
    const filtered = query?.deadline_state ? items.filter((i) => i.deadline_state === query.deadline_state) : items;
    const sort = String(query?.sort ?? "completeness_asc");
    const nullsLast = (v: number | null) => (v === null ? Number.POSITIVE_INFINITY : v);
    filtered.sort((a, b) =>
      sort === "missing_desc"
        ? b.missing - a.missing || a.institution.name.localeCompare(b.institution.name)
        : sort === "name_asc"
          ? a.institution.name.localeCompare(b.institution.name)
          : nullsLast(a.completeness_pct) - nullsLast(b.completeness_pct) || a.institution.name.localeCompare(b.institution.name),
    );
    const joined = filtered.reduce((a, r) => a + r.joined, 0);
    const matched = filtered.reduce((a, r) => a + r.uploaded_and_joined, 0);
    const states: Record<DeadlineState, number> = { NOT_DUE: 0, ON_TIME: 0, LATE: 0, OVERDUE: 0 };
    for (const r of filtered) states[r.deadline_state] += 1;
    const page: CompletenessPage = {
      ...ctx.paginate(filtered, query),
      totals: { joined, uploaded_and_joined: matched, missing: filtered.reduce((a, r) => a + r.missing, 0), completeness_pct: pct(matched, joined), deadline_states: states },
      deadline: REPORTING_DEADLINE,
    };
    return page;
  }

  if (parts[0] === "institutions" && parts[1] && parts[2] === "column-mapping") {
    if (method === "GET") {
      need(["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION"]);
      return columnMapping(ctx.inScope(parts[1]).id);
    }
    if (method === "PUT") {
      need(["AICTE_ADMIN", "INSTITUTION"]);
      return mappingPut(user, ctx.inScope(parts[1]).id, ctx.body);
    }
  }

  if (parts[0] === "approvals" && parts[1] && parts[2] === "versions" && method === "GET") {
    need(["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    for (const row of ctx.scoped()) {
      const p = (BASE_PROGRAMMES[row.id] ?? []).find((x) => x.approval.id === parts[1]);
      if (!p) continue;
      const body: ApprovalVersions = {
        approval_id: p.approval.id,
        institution: { id: row.id, name: row.name, aicte_permanent_id: row.aicte_permanent_id },
        programme: { id: p.id, code: p.code, name: p.name },
        academic_year: p.approval.academic_year,
        current_version: p.approval.version,
        items: (APPROVAL_VERSIONS.get(p.id) ?? []).map(({ version, approved_intake, effective_from, source, created_at }) => ({ version, approved_intake, effective_from, source, created_at })),
      };
      return body;
    }
    throw new ApiError(404, "NOT_FOUND", "Approval not found.");
  }

  return NOT_MINE;
}

/** GET /institutions/{id}/completeness.csv: the missing list, masked (A4.18). */
export function completenessCsv(institutionId: string): { blob: Blob; filename: string } {
  const c = completenessOf(institutionId);
  const seed = SEEDS.find((s) => s.id === institutionId)!;
  const quote = (v: string | number | null) => {
    const s = v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    "name,roll_no,programme_code,joined_on,round,route,apaar_masked",
    ...(c.missing_students ?? []).map((m) => [m.name, m.roll_no, m.programme_code, m.joined_on, m.round, m.route, m.apaar_masked].map(quote).join(",")),
  ];
  return { blob: new Blob(["﻿" + lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" }), filename: `missing_${seed.aicte_permanent_id}_${ACADEMIC_YEAR}.csv` };
}
