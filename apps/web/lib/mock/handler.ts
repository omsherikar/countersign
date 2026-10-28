/**
 * In-browser stand-in for the api when NEXT_PUBLIC_MOCK_API=1.
 * Routes, scoping, redaction and error envelopes follow docs/API_CONTRACT.md
 * sections A and B and Addendum 2 (A2.4 to A2.22).
 */
import { ApiError, type Query } from "@/lib/api";
import { casesDownload, casesUpload, withCases } from "@/lib/mock/cases";
import { ACADEMIC_YEAR, HEALTH, INSTITUTIONS, MOCK_PASSWORD, REGIONS, SEEDS, STATES, USERS, adapterPing, auditVerify, institutionBase, regionName, zeroChaos } from "@/lib/mock/fixtures";
import { SEVERITY_RANK, UNRESOLVED, allFlags, openFlagCount, type StoredFlag } from "@/lib/mock/flags";
import { enrolmentDetail, entryById, programmesFor, recheck, rollFor, seatsFor, studentMe, type RollEntry } from "@/lib/mock/roll";
import { readBrowserToken, tokenFor, userFromToken, writeBrowserToken } from "@/lib/mock/session";
import { allBatches, createUpload, errorsCsv, errorsOf, templateCsv } from "@/lib/mock/uploads";
import type {
  ChaosRequest,
  ChaosState,
  CheckStatus,
  CheckType,
  DashboardSummary,
  EnrolmentDetail,
  EnrolmentRecheck,
  EnrolmentRow,
  FlagDetail,
  FlagPage,
  FlagRef,
  FlagRow,
  FlagSummary,
  FlagType,
  InstitutionDetail,
  InstitutionRecheck,
  InstitutionRef,
  InstitutionRow,
  Page,
  RelatedEnrolmentRow,
  Role,
  SourceKey,
  User,
} from "@/lib/types";

let chaos: ChaosState = zeroChaos();

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

const FLAG_TYPES: FlagType[] = [
  "EXCESS_ADMISSION", "QUOTA_BREACH", "LATE_REFILL", "INVALID_APAAR", "NAME_MISMATCH", "DUPLICATE_CROSS_INSTITUTION",
  "DUPLICATE_WITHIN_UPLOAD", "DUAL_ENROLMENT_ALLOWED", "NO_ACADEMIC_ACTIVITY", "STUDENT_DENIED", "GHOST_RING", "ANOMALY",
];
const OFFICERS: Role[] = ["AICTE_ADMIN", "RO_OFFICER"];

function unauthenticated(): ApiError {
  return new ApiError(401, "UNAUTHENTICATED", "Sign in to continue.");
}
function forbidden(roles: Role[]): ApiError {
  return new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: roles });
}
function notFound(entity = "Institution"): ApiError {
  return new ApiError(404, "NOT_FOUND", `${entity} not found.`);
}

function currentUser(): User {
  const user = userFromToken(readBrowserToken());
  if (!user) throw unauthenticated();
  return user;
}

function requireRole(user: User, roles: Role[]) {
  if (!roles.includes(user.role)) throw forbidden(roles);
}

function paginate<T>(items: T[], query?: Query): Page<T> {
  const page = Math.max(1, Number(query?.page ?? 1));
  const pageSize = Math.min(200, Math.max(1, Number(query?.page_size ?? 25)));
  return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, page_size: pageSize };
}

const yes = (v: unknown) => String(v) === "true";
const no = (v: unknown) => String(v) === "false";

/* ---- Scope -------------------------------------------------------------- */

function withCounts(row: InstitutionRow): InstitutionRow {
  return { ...row, flags_open: openFlagCount(row.id) };
}

function scopedInstitutions(user: User): InstitutionRow[] {
  let rows: InstitutionRow[];
  switch (user.role) {
    case "AICTE_ADMIN":
      rows = INSTITUTIONS;
      break;
    case "RO_OFFICER":
      rows = INSTITUTIONS.filter((i) => i.region === user.scope.region);
      break;
    case "INSTITUTION":
      rows = INSTITUTIONS.filter((i) => i.id === user.scope.institution_id);
      break;
    case "UNIVERSITY":
      rows = INSTITUTIONS.filter((i) => i.university_id === user.scope.university_id);
      break;
    default:
      throw forbidden(["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
  }
  return rows.map(withCounts);
}

function inScope(user: User, id: string, entity = "Institution"): InstitutionRow {
  const row = scopedInstitutions(user).find((i) => i.id === id);
  if (!row) throw notFound(entity);
  return row;
}

function institutionRef(id: string): InstitutionRef {
  const row = INSTITUTIONS.find((r) => r.id === id)!;
  return { id: row.id, name: row.name, aicte_permanent_id: row.aicte_permanent_id, state_code: row.state_code, state_name: row.state_name, region: row.region };
}

/** Flags the caller may see (A2.15 roles). */
function flagScope(user: User): StoredFlag[] {
  requireRole(user, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION"]);
  const all = allFlags();
  if (user.role === "AICTE_ADMIN") return all;
  if (user.role === "RO_OFFICER") return all.filter((f) => INSTITUTIONS.find((i) => i.id === f.institutionId)?.region === user.scope.region);
  return all.filter((f) => f.institutionId === user.scope.institution_id);
}

const bySeverity = (a: { severity: StoredFlag["severity"]; created_at: string }, b: typeof a) =>
  SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] || a.created_at.localeCompare(b.created_at);

/** Unresolved flags naming an enrolment, as list rows carry them (A2.10). Out-of-scope callers see none. */
function flagRefs(user: User, enrolmentId: string): FlagRef[] {
  if (!["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"].includes(user.role)) return [];
  const visible = user.role === "UNIVERSITY" ? allFlags().filter((f) => scopedInstitutions(user).some((i) => i.id === f.institutionId)) : flagScope(user);
  return visible
    .filter((f) => UNRESOLVED.includes(f.status) && (f.enrolmentId === enrolmentId || f.related.includes(enrolmentId)))
    .sort(bySeverity)
    .map((f) => ({ id: f.id, type: f.type, severity: f.severity, status: f.status }));
}

function listRow(user: User, e: RollEntry): EnrolmentRow {
  return { ...e.row, flags: flagRefs(user, e.row.id) };
}

/* ---- Dashboard ---------------------------------------------------------- */

const STATS = new Map<string, { checked: number; countersigned: number; clear: number }>();
function rollStats(id: string) {
  const hit = STATS.get(id);
  if (hit) return hit;
  const rows = rollFor(id).filter((e) => e.row.status === "ACTIVE" && e.checks.length > 0);
  const s = {
    checked: rows.length,
    countersigned: rows.filter((e) => e.checks.every((c) => c.status === "PASS" || c.status === "NA")).length,
    clear: rows.filter((e) => e.checks.every((c) => c.status !== "FAIL")).length,
  };
  STATS.set(id, s);
  return s;
}
const pct = (n: number, d: number) => (d === 0 ? null : Math.round((n / d) * 1000) / 10);

function summary(user: User, academicYear?: string): DashboardSummary {
  const rows = scopedInstitutions(user);
  const label =
    user.role === "AICTE_ADMIN"
      ? "All India"
      : user.role === "RO_OFFICER"
        ? `${REGIONS.find((r) => r.code === user.scope.region)?.name ?? ""} Region`
        : user.role === "INSTITUTION"
          ? (user.scope.institution_name ?? "")
          : (user.scope.university_name ?? "");
  const kind = user.role === "AICTE_ADMIN" ? "NATIONAL" : user.role === "RO_OFFICER" ? "REGION" : user.role === "INSTITUTION" ? "INSTITUTION" : "UNIVERSITY";
  const byState = new Map<string, DashboardSummary["by_state"][number]>();
  const byRegion = new Map<string, DashboardSummary["by_region"][number]>();
  for (const r of rows) {
    const s = byState.get(r.state_code) ?? { state_code: r.state_code, state_name: r.state_name, region: r.region, institutions: 0, programmes: 0, approved_seats: 0, admitted: 0, enrolments: 0, flags_open: 0 };
    s.institutions += 1;
    s.programmes += r.programmes;
    s.approved_seats += r.approved_seats;
    s.admitted += r.admitted;
    s.enrolments += r.enrolments;
    s.flags_open += r.flags_open;
    byState.set(r.state_code, s);
    const g = byRegion.get(r.region) ?? { region: r.region, region_name: regionName(r.region), institutions: 0, approved_seats: 0, admitted: 0, enrolments: 0, flags_open: 0 };
    g.institutions += 1;
    g.approved_seats += r.approved_seats;
    g.admitted += r.admitted;
    g.enrolments += r.enrolments;
    g.flags_open += r.flags_open;
    byRegion.set(r.region, g);
  }
  const ids = new Set(rows.map((r) => r.id));
  const open = allFlags().filter((f) => ids.has(f.institutionId) && UNRESOLVED.includes(f.status));
  const stats = rows.map((r) => rollStats(r.id));
  const checked = stats.reduce((a, s) => a + s.checked, 0);
  return {
    academic_year: academicYear || ACADEMIC_YEAR,
    scope: { kind, label },
    kpis: {
      institutions: rows.length,
      programmes: rows.reduce((a, r) => a + r.programmes, 0),
      approved_seats: rows.reduce((a, r) => a + r.approved_seats, 0),
      admitted: rows.reduce((a, r) => a + r.admitted, 0),
      enrolments: rows.reduce((a, r) => a + r.enrolments, 0),
      flags_open: open.length,
      countersigned_pct: pct(stats.reduce((a, s) => a + s.countersigned, 0), checked),
      clear_pct: pct(stats.reduce((a, s) => a + s.clear, 0), checked),
    },
    flags_by_type: FLAG_TYPES.map((type) => ({ type, open: open.filter((f) => f.type === type).length })),
    by_state: [...byState.values()].sort((a, b) => a.state_name.localeCompare(b.state_name)),
    by_region: [...byRegion.values()].sort((a, b) => a.region_name.localeCompare(b.region_name)),
  };
}

/* ---- Institutions ------------------------------------------------------- */

function listInstitutions(user: User, q?: Query): Page<InstitutionRow> {
  let rows = [...scopedInstitutions(user)];
  const text = String(q?.q ?? "").toLowerCase();
  if (text) rows = rows.filter((r) => r.name.toLowerCase().includes(text) || r.aicte_permanent_id.toLowerCase().includes(text));
  if (q?.state) rows = rows.filter((r) => r.state_code === q.state);
  if (q?.region && user.role === "AICTE_ADMIN") rows = rows.filter((r) => r.region === q.region);
  if (q?.type) rows = rows.filter((r) => r.type === q.type);
  const sort = String(q?.sort ?? "flags_open_desc");
  if (sort === "flags_open_desc") {
    rows.sort((a, b) => b.flags_open - a.flags_open || b.enrolments - a.enrolments || a.name.localeCompare(b.name));
  } else if (sort === "name" || sort === "name_asc") {
    const dir = String(q?.order ?? "asc") === "desc" ? -1 : 1;
    rows.sort((a, b) => dir * a.name.localeCompare(b.name));
  } else {
    const key = sort === "approved_seats" ? "approved_seats" : "enrolments";
    const dir = String(q?.order ?? "desc") === "asc" ? 1 : -1;
    rows.sort((a, b) => dir * (a[key] - b[key]) || a.name.localeCompare(b.name));
  }
  return paginate(rows, q);
}

function institutionDetail(row: InstitutionRow): InstitutionDetail {
  const base = institutionBase(row.id)!;
  const last = allBatches().find((b) => b.institution_id === row.id && b.academic_year === ACADEMIC_YEAR);
  return {
    ...base,
    flags_open: row.flags_open,
    last_upload: last ? { batch_id: last.id, uploaded_at: last.uploaded_at, rows: last.counts.rows, errors: last.counts.errors, status: last.status } : null,
    programmes: programmesFor(row.id),
  };
}

function listEnrolments(user: User, row: InstitutionRow, q?: Query): Page<EnrolmentRow> {
  let rows = rollFor(row.id);
  if (q?.programme_id) rows = rows.filter((e) => e.row.programme_id === q.programme_id);
  if (q?.status) rows = rows.filter((e) => e.row.status === q.status);
  if (q?.academic_year) rows = rows.filter((e) => e.row.academic_year === q.academic_year);
  if (q?.admission_route) rows = rows.filter((e) => e.row.admission_route === q.admission_route);
  if (q?.year_of_study) rows = rows.filter((e) => e.row.year_of_study === Number(q.year_of_study));
  if (q?.check_status) {
    const status = q.check_status as CheckStatus;
    const type = q.check_type as CheckType | undefined;
    rows = rows.filter((e) => e.row.countersign.checks.some((c) => c.status === status && (!type || c.type === type)));
  }
  if (q?.seated !== undefined && q?.seated !== null && q?.seated !== "") {
    if (yes(q.seated)) rows = rows.filter((e) => e.seat);
    if (no(q.seated)) rows = rows.filter((e) => !e.seat);
  }
  if (q?.q) {
    const text = String(q.q).toLowerCase();
    rows = rows.filter((e) => e.row.student.name.toLowerCase().includes(text) || (e.row.student.apaar_masked ?? "").endsWith(text));
  }
  let list = rows.map((e) => listRow(user, e));
  if (q?.flagged !== undefined && q?.flagged !== null && q?.flagged !== "") {
    if (yes(q.flagged)) list = list.filter((r) => r.flags.length > 0);
    if (no(q.flagged)) list = list.filter((r) => r.flags.length === 0);
  }
  const sort = String(q?.sort ?? "name_asc");
  list.sort((a, b) => {
    if (sort === "year_desc") return b.year_of_study - a.year_of_study || a.student.name.localeCompare(b.student.name);
    if (sort === "route_asc") return a.admission_route.localeCompare(b.admission_route) || a.student.name.localeCompare(b.student.name);
    return a.student.name.localeCompare(b.student.name);
  });
  return paginate(list, q);
}

/* ---- Enrolments --------------------------------------------------------- */

function enrolmentInScope(user: User, id: string, roles: Role[]): RollEntry {
  requireRole(user, roles);
  const entry = entryById(id);
  if (!entry || !scopedInstitutions(user).some((i) => i.id === entry.institutionId)) throw notFound("Enrolment");
  return entry;
}

/** Errata 5: every role except the two officer roles gets the wording that names no other institution. */
const isOfficer = (user: User) => OFFICERS.includes(user.role);
function redactedSummary(user: User, f: StoredFlag): string {
  return !isOfficer(user) && f.summaryForInstitution ? f.summaryForInstitution : f.summary;
}

function getEnrolment(user: User, id: string): EnrolmentDetail {
  const entry = enrolmentInScope(user, id, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
  const visible = user.role === "UNIVERSITY" ? allFlags().filter((f) => f.institutionId === entry.institutionId) : flagScope(user);
  const flags: FlagSummary[] = visible
    .filter((f) => f.enrolmentId === id || f.related.includes(id))
    .sort(bySeverity)
    .map((f) => ({ id: f.id, type: f.type, severity: f.severity, status: f.status, summary: redactedSummary(user, f), created_at: f.created_at }));
  return { ...enrolmentDetail(entry), flags };
}

function recheckEnrolment(user: User, id: string): EnrolmentRecheck {
  const entry = enrolmentInScope(user, id, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION"]);
  const results = recheck(entry);
  STATS.delete(entry.institutionId);
  return { enrolment_id: id, rechecked: results.length, results, flags_raised: 0, countersign: entry.row.countersign };
}

function recheckInstitution(user: User, row: InstitutionRow, academicYear: string): InstitutionRecheck {
  requireRole(user, OFFICERS);
  const started = Date.now();
  const active = rollFor(row.id).filter((e) => e.row.status === "ACTIVE" && e.row.academic_year === academicYear);
  let rechecked = 0;
  const after: Record<CheckStatus, number> = { PASS: 0, FAIL: 0, NA: 0, PENDING: 0 };
  for (const e of active) {
    if (!e.checks.some((c) => c.status === "PENDING" && c.type !== "STUDENT")) continue;
    rechecked += 1;
    for (const r of recheck(e)) after[r.after] += 1;
  }
  STATS.delete(row.id);
  return {
    institution_id: row.id,
    academic_year: academicYear,
    enrolments: active.length,
    rechecked,
    now_pass: after.PASS,
    now_fail: after.FAIL,
    now_na: after.NA,
    still_pending: after.PENDING,
    flags_raised: 0,
    duration_ms: Date.now() - started + 240,
  };
}

/* ---- Flags (A2.15, A2.16) ----------------------------------------------- */

function visibleRelated(user: User, f: StoredFlag): string[] {
  if (user.role !== "INSTITUTION") return f.related;
  return f.related.filter((id) => entryById(id)?.institutionId === user.scope.institution_id);
}

function programmeRef(f: StoredFlag) {
  if (!f.programmeId) return null;
  const p = programmesFor(f.institutionId).find((x) => x.id === f.programmeId);
  return p ? { id: p.id, code: p.code, name: p.name } : null;
}

function flagRow(user: User, f: StoredFlag): FlagRow {
  return {
    id: f.id,
    type: f.type,
    severity: f.severity,
    status: f.status,
    institution: institutionRef(f.institutionId),
    programme: programmeRef(f),
    enrolment_id: f.enrolmentId,
    academic_year: f.academic_year,
    summary: redactedSummary(user, f),
    related_count: visibleRelated(user, f).length,
    assignee: null,
    response_received: false,
    docs_due_on: null,
    last_action_at: null,
    created_at: f.created_at,
    updated_at: f.updated_at,
  };
}

function relatedRow(user: User, id: string): RelatedEnrolmentRow | null {
  const e = entryById(id);
  if (!e) return null;
  const seed = SEEDS.find((s) => s.id === e.institutionId)!;
  return { ...listRow(user, e), institution: { id: seed.id, name: seed.name } };
}

function listFlags(user: User, q?: Query): FlagPage {
  let flags = flagScope(user);
  if (q?.type) flags = flags.filter((f) => f.type === q.type);
  if (q?.severity) flags = flags.filter((f) => f.severity === q.severity);
  if (q?.status) {
    // Errata 2: one status, a comma-separated list, or UNRESOLVED (OPEN, DOCS_REQUESTED, ESCALATED).
    const wanted = String(q.status) === "UNRESOLVED" ? UNRESOLVED : String(q.status).split(",");
    flags = flags.filter((f) => wanted.includes(f.status));
  }
  if (q?.institution_id) flags = flags.filter((f) => f.institutionId === q.institution_id);
  if (q?.programme_id) flags = flags.filter((f) => f.programmeId === q.programme_id);
  if (q?.state) flags = flags.filter((f) => institutionRef(f.institutionId).state_code === q.state);
  if (q?.academic_year) flags = flags.filter((f) => f.academic_year === q.academic_year);
  if (q?.q) {
    const text = String(q.q).toLowerCase();
    flags = flags.filter((f) => {
      const inst = institutionRef(f.institutionId);
      return redactedSummary(user, f).toLowerCase().includes(text) || inst.name.toLowerCase().includes(text) || inst.aicte_permanent_id.toLowerCase().includes(text);
    });
  }
  flags = [...flags].sort(String(q?.sort ?? "severity_desc") === "created_desc" ? (a, b) => b.created_at.localeCompare(a.created_at) : bySeverity);
  const page = paginate(flags.map((f) => flagRow(user, f)), q);
  return { ...page, institutions: new Set(flags.map((f) => f.institutionId)).size };
}

function getFlag(user: User, id: string): FlagDetail {
  const f = flagScope(user).find((x) => x.id === id) ?? null;
  if (!f) throw notFound("Flag");
  const related = visibleRelated(user, f);
  const audience = isOfficer(user) ? "OFFICER" : "INSTITUTION";
  return {
    ...flagRow(user, f),
    evidence: {
      summary: redactedSummary(user, f),
      facts: f.facts.filter((x) => !x.audience || x.audience === audience).map(({ label, value, source }) => ({ label, value, source })),
      related_enrolment_ids: related,
      rule_source: f.rule_source,
    },
    enrolment: f.enrolmentId ? relatedRow(user, f.enrolmentId) : null,
    related_enrolments: related.map((rid) => relatedRow(user, rid)).filter((r): r is RelatedEnrolmentRow => r !== null),
    related_hidden: f.related.length - related.length,
    history: [],
    allowed_actions: [],
    can_respond: false,
  };
}

/* ---- Uploads (A2.4 to A2.9) --------------------------------------------- */

function uploadScope(user: User) {
  requireRole(user, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION"]);
  const ids = new Set(scopedInstitutions(user).map((r) => r.id));
  return allBatches().filter((b) => ids.has(b.institution_id));
}

function uploadInScope(user: User, id: string) {
  const batch = uploadScope(user).find((b) => b.id === id);
  if (!batch) throw notFound("Upload");
  return batch;
}

/* ---- Router ------------------------------------------------------------- */

/** Week 3 case, notice, audit and data request routes sit in front of the Week 2 routes (lib/mock/cases.ts). */
export async function mockRequest(method: string, path: string, query?: Query, body?: unknown): Promise<unknown> {
  return withCases(method, path, query, body, weekTwoRequest);
}

async function weekTwoRequest(method: string, path: string, query?: Query, body?: unknown): Promise<unknown> {
  await wait(120 + Math.round(Math.random() * 180));
  const [pathname] = path.split("?");
  const parts = pathname.split("/").filter(Boolean);

  if (method === "POST" && pathname === "/auth/login") {
    const { email, password } = (body ?? {}) as { email?: string; password?: string };
    const fields = [];
    if (!email || email.length < 3) fields.push({ field: "email", message: "Enter your email." });
    if (!password) fields.push({ field: "password", message: "Enter your password." });
    if (fields.length) throw new ApiError(422, "VALIDATION_ERROR", fields[0].message, { fields });
    const user = USERS.find((u) => u.email === email?.trim().toLowerCase());
    if (!user || password !== MOCK_PASSWORD) throw new ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.");
    writeBrowserToken(tokenFor(user.email));
    return { user };
  }
  if (method === "POST" && pathname === "/auth/logout") {
    writeBrowserToken(null);
    return undefined;
  }
  if (pathname === "/healthz") return HEALTH;

  const user = currentUser();

  if (pathname === "/me") return { user };
  if (pathname === "/meta/regions") return { items: REGIONS };
  if (pathname === "/meta/states") return { items: STATES };

  if (pathname === "/dashboard/summary") {
    requireRole(user, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    return summary(user, query?.academic_year ? String(query.academic_year) : undefined);
  }

  if (parts[0] === "institutions") {
    requireRole(user, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    if (parts.length === 1) return listInstitutions(user, query);
    if (parts[2] === "recheck" && method === "POST") {
      requireRole(user, OFFICERS);
      const row = inScope(user, parts[1]);
      const year = (body as { academic_year?: string } | undefined)?.academic_year ?? ACADEMIC_YEAR;
      await wait(900);
      return recheckInstitution(user, row, year);
    }
    const row = inScope(user, parts[1]);
    if (parts.length === 2) return institutionDetail(row);
    if (parts[2] === "seats") {
      let seats = seatsFor(row.id);
      if (query?.programme_id) {
        const code = programmesFor(row.id).find((p) => p.id === query.programme_id)?.code;
        seats = seats.filter((s) => s.programme_code === code);
      }
      if (query?.seat_type) seats = seats.filter((s) => s.seat_type === query.seat_type);
      if (query?.status) seats = seats.filter((s) => s.status === query.status);
      if (query?.q) {
        const q = String(query.q).toUpperCase();
        seats = seats.filter((s) => s.seat_code.startsWith(q) || (s.student_name ?? "").toUpperCase().includes(q));
      }
      return paginate(seats, query);
    }
    if (parts[2] === "enrolments") return listEnrolments(user, row, query);
    throw notFound();
  }

  if (parts[0] === "enrolments" && parts[1]) {
    if (user.role === "STUDENT") throw forbidden(["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    if (parts[2] === "recheck" && method === "POST") {
      await wait(500);
      return recheckEnrolment(user, parts[1]);
    }
    if (parts.length === 2) return getEnrolment(user, parts[1]);
  }

  if (parts[0] === "flags") {
    if (parts.length === 1) return listFlags(user, query);
    if (parts.length === 2) return getFlag(user, parts[1]);
  }

  if (parts[0] === "uploads") {
    if (parts.length === 1) {
      let batches = uploadScope(user);
      if (query?.institution_id && user.role !== "INSTITUTION") batches = batches.filter((b) => b.institution_id === query.institution_id);
      if (query?.academic_year) batches = batches.filter((b) => b.academic_year === query.academic_year);
      if (query?.status) batches = batches.filter((b) => b.status === query.status);
      return paginate(batches, query);
    }
    const batch = uploadInScope(user, parts[1]);
    if (parts.length === 2) return batch;
    if (parts[2] === "errors") {
      let errors = errorsOf(batch);
      if (query?.level) errors = errors.filter((e) => e.level === query.level);
      if (query?.code) errors = errors.filter((e) => e.code === query.code);
      return paginate(errors, query);
    }
  }

  if (pathname === "/students/me") {
    requireRole(user, ["STUDENT"]);
    return studentMe();
  }

  if (parts[0] === "admin") {
    requireRole(user, ["AICTE_ADMIN"]);
    if (pathname === "/admin/adapters/ping") {
      const slowest = Math.max(...Object.values(chaos).map((c) => (c.down ? 600 : c.latency_ms)));
      await wait(Math.min(slowest, 1500));
      return adapterPing(chaos);
    }
    if (pathname === "/admin/audit/verify") return auditVerify();
    if (pathname === "/admin/chaos" && method === "GET") return chaos;
    if (pathname === "/admin/chaos" && method === "POST") {
      const req = body as ChaosRequest;
      const setting = { latency_ms: req.latency_ms, fail_rate: req.fail_rate, down: req.down };
      const keys: SourceKey[] = req.source === "all" ? (Object.keys(chaos) as SourceKey[]) : [req.source];
      chaos = { ...chaos };
      for (const k of keys) chaos[k] = { ...setting };
      return Object.fromEntries(keys.map((k) => [k, chaos[k]]));
    }
    if (pathname === "/admin/chaos/reset" && method === "POST") {
      chaos = zeroChaos();
      return chaos;
    }
    if (pathname === "/admin/demo/reset") throw new ApiError(501, "NOT_IMPLEMENTED", "Run make demo-reset.");
  }

  throw new ApiError(404, "NOT_FOUND", "We could not find that.");
}

/** POST /uploads (multipart) in mock mode. */
export async function mockUpload(path: string, form: FormData): Promise<unknown> {
  await wait(150);
  if (path.startsWith("/flags/")) return casesUpload(path, form, mockRequest);
  if (path !== "/uploads") throw new ApiError(404, "NOT_FOUND", "We could not find that.");
  return createUpload(currentUser(), form);
}

/** File downloads in mock mode: errors.csv and the templates. */
export async function mockDownload(path: string): Promise<{ blob: Blob; filename: string }> {
  await wait(150);
  if (path.startsWith("/flags/")) return casesDownload(path, mockRequest);
  const user = currentUser();
  if (path === "/uploads/template.csv" || path === "/uploads/template.xlsx") {
    requireRole(user, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION"]);
    // No XLSX writer in the browser mock; both buttons save the CSV header row.
    return templateCsv();
  }
  const m = /^\/uploads\/([^/]+)\/errors\.csv$/.exec(path);
  if (m) return errorsCsv(uploadInScope(user, m[1]));
  throw new ApiError(404, "NOT_FOUND", "We could not find that.");
}
