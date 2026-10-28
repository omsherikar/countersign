/**
 * In-browser stand-in for the api when NEXT_PUBLIC_MOCK_API=1.
 * Routes, scoping and error envelopes follow docs/API_CONTRACT.md.
 */
import { ApiError, type Query } from "@/lib/api";
import {
  ACADEMIC_YEAR,
  ENROLMENTS,
  HEALTH,
  INSTITUTIONS,
  MOCK_PASSWORD,
  REGIONS,
  STATES,
  STUDENT_ME,
  USERS,
  adapterPing,
  auditVerify,
  institutionDetail,
  regionName,
  seatsFor,
  zeroChaos,
} from "@/lib/mock/fixtures";
import { readBrowserToken, tokenFor, userFromToken, writeBrowserToken } from "@/lib/mock/session";
import type {
  ChaosRequest,
  ChaosState,
  DashboardSummary,
  InstitutionRow,
  Page,
  Role,
  SourceKey,
  User,
} from "@/lib/types";

let chaos: ChaosState = zeroChaos();

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

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

function scopedInstitutions(user: User): InstitutionRow[] {
  switch (user.role) {
    case "AICTE_ADMIN":
      return INSTITUTIONS;
    case "RO_OFFICER":
      return INSTITUTIONS.filter((i) => i.region === user.scope.region);
    case "INSTITUTION":
      return INSTITUTIONS.filter((i) => i.id === user.scope.institution_id);
    case "UNIVERSITY":
      return INSTITUTIONS.filter((i) => i.university_id === user.scope.university_id);
    default:
      throw forbidden(["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
  }
}

function inScope(user: User, id: string): InstitutionRow {
  const row = scopedInstitutions(user).find((i) => i.id === id);
  if (!row) throw notFound();
  return row;
}

function summary(user: User): DashboardSummary {
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
    const s = byState.get(r.state_code) ?? { state_code: r.state_code, state_name: r.state_name, region: r.region, institutions: 0, programmes: 0, approved_seats: 0, enrolments: 0, flags_open: 0 };
    s.institutions += 1;
    s.programmes += r.programmes;
    s.approved_seats += r.approved_seats;
    s.enrolments += r.enrolments;
    byState.set(r.state_code, s);
    const g = byRegion.get(r.region) ?? { region: r.region, region_name: regionName(r.region), institutions: 0, approved_seats: 0, enrolments: 0, flags_open: 0 };
    g.institutions += 1;
    g.approved_seats += r.approved_seats;
    g.enrolments += r.enrolments;
    byRegion.set(r.region, g);
  }
  return {
    academic_year: ACADEMIC_YEAR,
    scope: { kind, label },
    kpis: {
      institutions: rows.length,
      programmes: rows.reduce((a, r) => a + r.programmes, 0),
      approved_seats: rows.reduce((a, r) => a + r.approved_seats, 0),
      enrolments: rows.reduce((a, r) => a + r.enrolments, 0),
      flags_open: 0,
      countersigned_pct: null,
    },
    by_state: [...byState.values()].sort((a, b) => a.state_name.localeCompare(b.state_name)),
    by_region: [...byRegion.values()].sort((a, b) => a.region_name.localeCompare(b.region_name)),
  };
}

function listInstitutions(user: User, q?: Query): Page<InstitutionRow> {
  let rows = [...scopedInstitutions(user)];
  const text = String(q?.q ?? "").toLowerCase();
  if (text) rows = rows.filter((r) => r.name.toLowerCase().includes(text) || r.aicte_permanent_id.toLowerCase().includes(text));
  if (q?.state) rows = rows.filter((r) => r.state_code === q.state);
  if (q?.region && user.role === "AICTE_ADMIN") rows = rows.filter((r) => r.region === q.region);
  if (q?.type) rows = rows.filter((r) => r.type === q.type);
  const sort = String(q?.sort ?? "enrolments");
  const dir = String(q?.order ?? (sort === "name" ? "asc" : "desc")) === "asc" ? 1 : -1;
  rows.sort((a, b) => {
    if (sort === "name") return dir * a.name.localeCompare(b.name);
    const key = sort === "approved_seats" ? "approved_seats" : "enrolments";
    return dir * (a[key] - b[key]) || a.name.localeCompare(b.name);
  });
  return paginate(rows, q);
}

export async function mockRequest(method: string, path: string, query?: Query, body?: unknown): Promise<unknown> {
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
    return summary(user);
  }

  if (parts[0] === "institutions") {
    requireRole(user, ["AICTE_ADMIN", "RO_OFFICER", "INSTITUTION", "UNIVERSITY"]);
    if (parts.length === 1) return listInstitutions(user, query);
    const row = inScope(user, parts[1]);
    const detail = institutionDetail(row.id);
    if (!detail) throw notFound();
    if (parts.length === 2) return detail;
    if (parts[2] === "seats") {
      let seats = seatsFor(detail);
      if (query?.programme_id) {
        const code = detail.programmes.find((p) => p.id === query.programme_id)?.code;
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
    if (parts[2] === "enrolments") {
      let rows = row.aicte_permanent_id === "1-ABC-0001" ? [...ENROLMENTS] : [];
      if (query?.programme_id) rows = rows.filter((e) => e.programme_id === query.programme_id);
      if (query?.status) rows = rows.filter((e) => e.status === query.status);
      if (query?.academic_year) rows = rows.filter((e) => e.academic_year === query.academic_year);
      if (query?.admission_route) rows = rows.filter((e) => e.admission_route === query.admission_route);
      if (query?.year_of_study) rows = rows.filter((e) => e.year_of_study === Number(query.year_of_study));
      if (query?.q) {
        const q = String(query.q).toLowerCase();
        rows = rows.filter((e) => e.student.name.toLowerCase().includes(q) || (e.student.apaar_masked ?? "").endsWith(q));
      }
      return paginate(rows, query);
    }
    throw notFound();
  }

  if (pathname === "/students/me") {
    requireRole(user, ["STUDENT"]);
    return STUDENT_ME;
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
