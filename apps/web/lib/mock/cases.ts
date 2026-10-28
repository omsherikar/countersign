/**
 * Mock-mode case work, student notices, the audit log and data requests
 * (API_CONTRACT A3.5, A3.7 to A3.14, A3.22 and A3.23).
 *
 * The handler sends every request through `withCases` first. Routes this
 * file owns are answered here; flag and enrolment reads go on to the Week 2
 * handler and come back decorated with case state, history and notices;
 * everything else passes straight through.
 *
 * Demo controls, from the browser console in mock mode only:
 *   countersignMock.tamperAudit(917)   the same as `make audit-tamper SEQ=917`
 *   countersignMock.restoreAudit()     the same as `make demo-reset` for the chain
 */
import { ApiError, type Query } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { IDS, INSTITUTIONS, SEEDS, USERS } from "@/lib/mock/fixtures";
import { allFlags, flagById, type StoredFact, type StoredFlag } from "@/lib/mock/flags";
import { CHECKED_AT, compact, entryById, rollFor, type RollEntry } from "@/lib/mock/roll";
import { readBrowserToken, userFromToken } from "@/lib/mock/session";
import type {
  ActorRef,
  AuditAction,
  AuditRow,
  AuditVerify,
  CaseActionRequest,
  CaseAttachment,
  CaseHistoryItem,
  Check,
  CredentialRef,
  DataRequestAdminRow,
  DataRequestResolve,
  EnrolmentDetail,
  EnrolmentNotice,
  EnrolmentRecheck,
  FlagDetail,
  FlagPage,
  FlagRow,
  FlagStatus,
  NoticeChannel,
  NoticeResendResult,
  NoticeResponse,
  NoticeState,
  OfficerAction,
  OfficerRow,
  Page,
  Region,
  ResendState,
  Role,
  StudentNoticeState,
  User,
} from "@/lib/types";

type Next = (method: string, path: string, query?: Query, body?: unknown) => Promise<unknown>;

const A: Role = "AICTE_ADMIN";
const R: Role = "RO_OFFICER";
const I: Role = "INSTITUTION";
const OFFICERS: Role[] = [A, R];

/* ---- Small helpers ------------------------------------------------------- */

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const latency = () => wait(120 + Math.round(Math.random() * 180));

function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function hex(seed: string, length = 64): string {
  let out = "";
  let x = hash(seed);
  for (let i = 0; out.length < length; i++) {
    x = hash(`${seed}:${i}:${x}`);
    out += x.toString(16).padStart(8, "0");
  }
  return out.slice(0, length);
}

function uuid(seed: string): string {
  const h = hex(seed, 32);
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-4${h.slice(13, 16)}-8${h.slice(17, 20)}-${h.slice(20, 32)}`;
}

const iso = (d: Date) => d.toISOString().replace(/\.\d+Z$/, "Z");
const nowIso = () => iso(new Date());
const addHours = (at: string, hours: number) => iso(new Date(new Date(at).getTime() + hours * 3_600_000));
const addDays = (at: string, days: number) => addHours(at, days * 24);

/** Today's date in IST as YYYY-MM-DD. */
function todayIst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function plusDays(date: string, n: number): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function paginate<T>(items: T[], query?: Query): Page<T> {
  const page = Math.max(1, Number(query?.page ?? 1));
  const pageSize = Math.min(200, Math.max(1, Number(query?.page_size ?? 25)));
  return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, page_size: pageSize };
}

/* ---- Errors (section B and A3.25 envelopes) ------------------------------ */

const unauthenticated = () => new ApiError(401, "UNAUTHENTICATED", "Sign in to continue.");
const forbidden = (roles: Role[]) => new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: roles });
const notFound = (message: string) => new ApiError(404, "NOT_FOUND", message);
const invalid = (field: string, message: string) => new ApiError(422, "VALIDATION_ERROR", message, { fields: [{ field, message }] });

function signedIn(): User {
  const user = userFromToken(readBrowserToken());
  if (!user) throw unauthenticated();
  return user;
}

function requireRole(user: User, roles: Role[]) {
  if (!roles.includes(user.role)) throw forbidden(roles);
}

const regionOf = (institutionId: string): Region => INSTITUTIONS.find((i) => i.id === institutionId)!.region;
const institutionName = (id: string) => SEEDS.find((s) => s.id === id)?.name ?? "";

/* ---- Officers (GET /users, A3.14) ---------------------------------------- */

const DIRECTORY: OfficerRow[] = [
  ...USERS.filter((u) => u.role === A || u.role === R).map((u) => ({
    id: u.id,
    name: u.name,
    role: u.role as OfficerRow["role"],
    region: u.scope.region,
  })),
  { id: "6f1c0a8e-0011-4c9a-9e51-1c2f1a0b7d33", name: "Deputy Director, Approvals", role: "AICTE_ADMIN" as const, region: null },
  { id: "6f1c0a8e-0012-4c9a-9e51-1c2f1a0b7d33", name: "Assistant Director, Western Region", role: "RO_OFFICER" as const, region: "WEST" as const },
].sort((a, b) => (a.role === b.role ? a.name.localeCompare(b.name) : a.role === A ? -1 : 1));

function actorOf(user: Pick<User, "id" | "name" | "role">): ActorRef {
  return { id: user.id, name: user.name, role: user.role };
}

const byEmail = (email: string) => actorOf(USERS.find((u) => u.email === email)!);

/** Officers who may hold a flag: every AICTE officer and the regional officers of its region. */
function assignable(f: StoredFlag): OfficerRow[] {
  const region = regionOf(f.institutionId);
  return DIRECTORY.filter((o) => o.role === A || o.region === region);
}

function listUsers(user: User, query?: Query): Page<OfficerRow> {
  requireRole(user, OFFICERS);
  const roles = String(query?.role ?? "").split(",").filter(Boolean);
  if (roles.length === 0 || roles.some((r) => r !== A && r !== R)) throw invalid("role", "Choose RO_OFFICER, AICTE_ADMIN or both.");
  let rows = DIRECTORY.filter((o) => roles.includes(o.role));
  if (user.role === R) rows = rows.filter((o) => o.role === A || o.region === user.scope.region);
  if (query?.flag_id) {
    const f = flagById(String(query.flag_id));
    if (!f || (user.role === R && regionOf(f.institutionId) !== user.scope.region)) throw notFound("Flag not found.");
    const ok = new Set(assignable(f).map((o) => o.id));
    rows = rows.filter((o) => ok.has(o.id));
  }
  return paginate(rows, query);
}

/* ---- Audit log (A3.23) --------------------------------------------------- */

const TAMPER_KEY = "countersign.mock.auditTamper";
const AUDIT: AuditRow[] = [];

function tamperedSeq(): number | null {
  try {
    const raw = typeof window === "undefined" ? null : window.localStorage.getItem(TAMPER_KEY);
    const n = raw ? Number(raw) : NaN;
    return Number.isInteger(n) && n >= 1 && n <= AUDIT.length ? n : null;
  } catch {
    return null;
  }
}

if (typeof window !== "undefined") {
  (window as unknown as { countersignMock?: unknown }).countersignMock = {
    tamperAudit: (seq: number) => window.localStorage.setItem(TAMPER_KEY, String(seq)),
    restoreAudit: () => window.localStorage.removeItem(TAMPER_KEY),
  };
}

function pushAudit(row: Omit<AuditRow, "seq" | "hash" | "prev_hash">) {
  const seq = AUDIT.length + 1;
  const prev = AUDIT[AUDIT.length - 1]?.hash ?? null;
  AUDIT.push({ ...row, seq, hash: hex(`audit:${seq}:${row.entity_id}:${row.action}`), prev_hash: prev });
}

function appendAudit(user: User | null, action: AuditAction, entityType: string, entityId: string, via: string | null = null) {
  pushAudit({
    at: nowIso(),
    actor_id: user?.id ?? null,
    actor_email: user?.email ?? null,
    actor_role: user?.role ?? null,
    via,
    action,
    entity_type: entityType,
    entity_id: entityId,
  });
}

/** 1,842 entries over the two seeded days: seed rows, sign-ins, uploads, flag work and views. */
function seedAudit() {
  const start = new Date("2026-10-26T04:30:00Z").getTime();
  const end = new Date("2026-10-28T12:30:00Z").getTime();
  const total = 1842;
  const people = USERS.filter((u) => u.role !== "STUDENT");
  for (let n = 1; n <= total; n++) {
    const at = iso(new Date(start + Math.round(((end - start) * (n - 1)) / (total - 1))));
    const h = hash(`audit-seed:${n}`) % 100;
    const who = people[hash(`who:${n}`) % people.length];
    const id = uuid(`entity:${n}`);
    let row: Omit<AuditRow, "seq" | "hash" | "prev_hash">;
    if (n <= 240) {
      const types = ["institution", "programme", "approval", "seat", "user"];
      row = { at, actor_id: null, actor_email: null, actor_role: null, via: "demo-seed", action: "SEED", entity_type: types[n % types.length], entity_id: id };
    } else if (h < 8) {
      row = { at, actor_id: who.id, actor_email: who.email, actor_role: who.role, via: null, action: "LOGIN", entity_type: "user", entity_id: who.id };
    } else if (h < 30) {
      const registrar = USERS[3 + (n % 2)];
      row = { at, actor_id: registrar.id, actor_email: registrar.email, actor_role: registrar.role, via: null, action: n % 5 === 0 ? "UPDATE" : "CREATE", entity_type: n % 7 === 0 ? "upload_batch" : "enrolment", entity_id: id };
    } else if (h < 48) {
      row = { at, actor_id: null, actor_email: null, actor_role: null, via: null, action: "CREATE", entity_type: n % 3 === 0 ? "flag" : "notification", entity_id: id };
    } else if (h < 70) {
      const officer = people[n % 3];
      row = { at, actor_id: officer.id, actor_email: officer.email, actor_role: officer.role, via: null, action: "READ", entity_type: "student", entity_id: id };
    } else if (h < 82) {
      row = { at, actor_id: null, actor_email: null, actor_role: null, via: "notice-link", action: "READ", entity_type: "notification", entity_id: id };
    } else if (h < 88) {
      row = { at, actor_id: null, actor_email: null, actor_role: null, via: "verifier", action: "READ", entity_type: "credential_presentation", entity_id: id };
    } else if (h < 95) {
      const officer = people[n % 3];
      row = { at, actor_id: officer.id, actor_email: officer.email, actor_role: officer.role, via: null, action: "UPDATE", entity_type: "flag", entity_id: id };
    } else {
      row = { at, actor_id: null, actor_email: null, actor_role: null, via: null, action: "UPDATE", entity_type: "check", entity_id: id };
    }
    pushAudit(row);
  }
}

function listAudit(user: User, query?: Query): Page<AuditRow> {
  requireRole(user, [A]);
  let rows = [...AUDIT].reverse();
  if (query?.entity_type) rows = rows.filter((r) => r.entity_type === query.entity_type);
  if (query?.action) rows = rows.filter((r) => r.action === query.action);
  if (query?.actor_id) rows = rows.filter((r) => r.actor_id === query.actor_id);
  if (query?.entity_id) {
    const id = String(query.entity_id).toLowerCase();
    rows = rows.filter((r) => (r.entity_id ?? "").toLowerCase().startsWith(id));
  }
  if (query?.seq_from) rows = rows.filter((r) => r.seq <= Number(query.seq_from));
  return paginate(rows, query);
}

function verifyAudit(user: User): AuditVerify {
  requireRole(user, [A]);
  const broken = tamperedSeq();
  return { ok: broken === null, length: AUDIT.length, first_broken_seq: broken, checked_at: nowIso() };
}

/* ---- Notices and the Student check (A3.5, A3.7, A3.8) -------------------- */

interface StoredNotice extends Omit<EnrolmentNotice, "state"> {
  /** When a QUEUED resend is delivered, in ms since the epoch. */
  deliverAt?: number;
}

interface NoticeFile {
  notices: StoredNotice[];
  hasEmail: boolean;
  noDigiLocker: boolean;
  resendsUsed: number;
  consentWithdrawnAt: string | null;
}

const RAVI = "e0000000-0000-4666-8777-888899990000";
const SENT_AT = "2026-10-27T09:31:40Z";
const EXPIRES_AT = "2026-11-26T09:31:31Z";
const OLD_SENT_AT = "2026-09-24T10:12:05Z";
const OLD_EXPIRES_AT = "2026-10-24T10:12:00Z";
const NOTICES = new Map<string, NoticeFile>();

const linked = (e: RollEntry) => e.row.student.consent_status === "LINKED";

function notice(e: RollEntry, channel: NoticeChannel, key: string, sentAt: string, expiresAt: string, failed = false): StoredNotice {
  return {
    id: uuid(`notice:${e.row.id}:${channel}:${key}`),
    channel,
    delivery_status: failed ? "FAILED" : "SENT",
    attempts: failed ? 3 : 1,
    last_error: failed ? "no DigiLocker account" : null,
    sent_at: sentAt,
    expires_at: expiresAt,
    response: null,
    responded_at: null,
    previous_response: null,
    changed_at: null,
    resent: false,
  };
}

/** What the seed sent each active enrolment and how the student answered (about 70% Yes). */
function seedFile(e: RollEntry): NoticeFile {
  const h = hash(e.row.id) % 1000;
  const file: NoticeFile = { notices: [], hasEmail: !(h >= 30 && h < 50), noDigiLocker: h % 10 === 7, resendsUsed: 0, consentWithdrawnAt: null };
  if (e.row.status !== "ACTIVE") return file;
  const old = h < 30 && e.row.id !== RAVI;
  const sent = old ? OLD_SENT_AT : SENT_AT;
  const expires = old ? OLD_EXPIRES_AT : EXPIRES_AT;
  if (file.hasEmail) file.notices.push(notice(e, "EMAIL", "first", sent, expires));
  if (linked(e)) file.notices.push(notice(e, "DIGILOCKER", "first", sent, expires, file.noDigiLocker));
  if (e.row.id === RAVI || file.notices.length === 0) return file;
  if (old) {
    if (h < 3) {
      file.resendsUsed = 3;
      for (const n of file.notices) n.resent = true;
    }
    if (h >= 3 && h < 6) file.consentWithdrawnAt = "2026-10-26T15:40:00Z";
    return file;
  }
  if (h >= 50 && h < 330) return file;
  const delivered = file.notices.filter((n) => n.delivery_status === "SENT");
  const answer = delivered.find((n) => n.channel === "DIGILOCKER" && h % 2 === 1) ?? delivered[0];
  if (answer) {
    answer.response = "YES";
    answer.responded_at = addHours(answer.sent_at!, 1 + (h % 40));
  }
  return file;
}

function noticesOf(e: RollEntry): NoticeFile {
  let file = NOTICES.get(e.row.id);
  if (!file) {
    file = seedFile(e);
    NOTICES.set(e.row.id, file);
  }
  for (const n of file.notices) {
    if (n.delivery_status === "QUEUED" && n.deliverAt !== undefined && Date.now() >= n.deliverAt) {
      const failed = n.channel === "DIGILOCKER" && file.noDigiLocker;
      n.delivery_status = failed ? "FAILED" : "SENT";
      n.attempts = failed ? 3 : 1;
      n.last_error = failed ? "no DigiLocker account" : null;
      n.sent_at = iso(new Date(n.deliverAt));
    }
  }
  return file;
}

function stateOf(n: StoredNotice): NoticeState {
  if (n.delivery_status === "QUEUED") return "QUEUED";
  if (n.delivery_status === "FAILED") return "FAILED";
  if (n.response) return "ANSWERED";
  return new Date(n.expires_at).getTime() < Date.now() ? "EXPIRED" : "AWAITING";
}

const isLive = (n: StoredNotice) => {
  const s = stateOf(n);
  return s === "AWAITING" || s === "QUEUED";
};

const channelWord = (c: NoticeChannel) => (c === "EMAIL" ? "email" : "DigiLocker");
const decidedAt = (n: StoredNotice) => n.changed_at ?? n.responded_at ?? "";

function studentCheck(e: RollEntry, file: NoticeFile): Check {
  const all = file.notices;
  const earliest = (resp: NoticeResponse) => all.filter((n) => n.response === resp).sort((a, b) => decidedAt(a).localeCompare(decidedAt(b)))[0];
  const make = (status: Check["status"], summary: string, state: StudentNoticeState, extra: Record<string, unknown>, at: string | null): Check => ({
    type: "STUDENT",
    status,
    source: "STUDENT_NOTICE",
    checked_at: at ?? CHECKED_AT,
    attempts: 0,
    detail: { summary, notice_state: state, ...extra },
  });
  const decided = (n: StoredNotice) => ({ channel: n.channel, sent_at: n.sent_at, responded_at: decidedAt(n), changed: Boolean(n.changed_at) });
  const no = earliest("NO");
  if (no) return make("FAIL", `Denied by the student on ${formatDate(decidedAt(no))} (${channelWord(no.channel)}).`, "DENIED", decided(no), decidedAt(no));
  const yes = earliest("YES");
  if (yes) return make("PASS", `Confirmed by the student on ${formatDate(decidedAt(yes))} (${channelWord(yes.channel)}).`, "CONFIRMED", decided(yes), decidedAt(yes));
  const delivered = all.filter((n) => n.delivery_status === "SENT").sort((a, b) => (b.sent_at ?? "").localeCompare(a.sent_at ?? ""));
  if (delivered.length === 0) {
    if (!file.hasEmail && !linked(e)) return make("PENDING", "No email or APAAR on record, so no notice can be sent.", "UNREACHABLE", {}, null);
    const extra: Record<string, unknown> = {};
    if (all.some((n) => n.delivery_status === "FAILED")) extra.delivery_failed = true;
    if (file.consentWithdrawnAt) extra.consent_withdrawn = true;
    return make("PENDING", "Notice not sent yet.", "NOT_SENT", extra, null);
  }
  const live = delivered.filter((n) => stateOf(n) === "AWAITING");
  if (live.length > 0) {
    return make("PENDING", `Notice sent on ${formatDate(live[0].sent_at)}; no reply yet.`, "SENT", { channel: live[0].channel, sent_at: live[0].sent_at }, live[0].sent_at);
  }
  return make("PENDING", "No reply (expired).", "EXPIRED", { channel: delivered[0].channel, sent_at: delivered[0].sent_at }, delivered[0].sent_at);
}

function syncEntry(e: RollEntry) {
  if (e.checks.length === 0) return;
  const check = studentCheck(e, noticesOf(e));
  e.checks = e.checks.map((c) => (c.type === "STUDENT" ? check : c));
  e.row.countersign = compact(e.checks);
}

function syncInstitution(id: string) {
  for (const e of rollFor(id)) syncEntry(e);
}

function resendState(user: User, e: RollEntry, file: NoticeFile): ResendState {
  const left = Math.max(0, 3 - file.resendsUsed);
  const block = (blocked_by: ResendState["blocked_by"]): ResendState => ({ allowed: false, blocked_by, resends_left: left });
  if (user.role === "UNIVERSITY") return block("ROLE");
  if (e.row.status !== "ACTIVE") return block("NOT_ACTIVE");
  if (file.notices.some((n) => n.response)) return block("ANSWERED");
  if (file.notices.some(isLive)) return block("LIVE");
  if (file.consentWithdrawnAt) return block("CONSENT_WITHDRAWN");
  if (!file.hasEmail && !linked(e)) return block("NO_CHANNEL");
  if (left === 0) return block("LIMIT");
  return { allowed: true, blocked_by: null, resends_left: left };
}

function toWire(n: StoredNotice): EnrolmentNotice {
  const { deliverAt: _deliverAt, ...wire } = n;
  void _deliverAt;
  return { ...wire, state: stateOf(n) };
}

/** Every notice of the enrolment, newest first. */
function wireNotices(file: NoticeFile): EnrolmentNotice[] {
  return [...file.notices]
    .sort((a, b) => (b.sent_at ?? b.expires_at).localeCompare(a.sent_at ?? a.expires_at) || a.channel.localeCompare(b.channel))
    .map(toWire);
}

/* ---- Credentials on enrolment detail (A3.7) ------------------------------ */

const REVOKED = new Map<string, string>();

function credentialsFor(e: RollEntry): CredentialRef[] {
  const student = e.checks.find((c) => c.type === "STUDENT");
  if (!student || student.status !== "PASS" || e.checks.some((c) => c.status === "FAIL")) return [];
  const highOpen = allFlags().some(
    (f) => f.severity === "HIGH" && ["OPEN", "DOCS_REQUESTED", "ESCALATED"].includes(f.status) && (f.enrolmentId === e.row.id || f.related.includes(e.row.id)),
  );
  const revokedAt = REVOKED.get(e.row.id) ?? null;
  if (highOpen && !revokedAt) return [];
  return [
    {
      id: uuid(`credential:${e.row.id}`),
      kind: "ENROLMENT",
      status: revokedAt ? "REVOKED" : "ACTIVE",
      short_id: hex(`short:${e.row.id}`, 8).toUpperCase(),
      issued_at: student.detail.responded_at ? addHours(String(student.detail.responded_at), 0.02) : CHECKED_AT,
      revoked_at: revokedAt,
      revoked_reason_code: revokedAt ? "FLAG_CONFIRMED" : null,
      revoked_reason: null,
    },
  ];
}

/* ---- Cases (A3.9 to A3.13) ----------------------------------------------- */

interface CaseState {
  assignee: { id: string; name: string } | null;
  responseReceived: boolean;
  docsDueOn: string | null;
  lastActionAt: string | null;
  history: CaseHistoryItem[];
}

const CASES = new Map<string, CaseState>();
const FILES = new Map<string, { flagId: string; blob: Blob; meta: CaseAttachment }>();
let SEQ = 60;

function caseOf(id: string): CaseState {
  let c = CASES.get(id);
  if (!c) {
    c = { assignee: null, responseReceived: false, docsDueOn: null, lastActionAt: null, history: [] };
    CASES.set(id, c);
  }
  return c;
}

const ORDER: OfficerAction[] = ["CLEAR", "REQUEST_DOCS", "ESCALATE", "CONFIRM", "NOTE", "ASSIGN", "REOPEN"];
type Rule = { to: FlagStatus | "="; roles: Role[] };
const LIVE_RULES: Partial<Record<OfficerAction, Rule>> = {
  REQUEST_DOCS: { to: "DOCS_REQUESTED", roles: [A, R] },
  ESCALATE: { to: "ESCALATED", roles: [A, R] },
  CLEAR: { to: "CLEARED", roles: [A, R] },
  CONFIRM: { to: "CONFIRMED", roles: [A, R] },
  NOTE: { to: "=", roles: [A, R] },
  ASSIGN: { to: "=", roles: [A, R] },
};
const CLOSED_RULES: Partial<Record<OfficerAction, Rule>> = { NOTE: { to: "=", roles: [A, R] }, REOPEN: { to: "OPEN", roles: [A] } };
/** The A3.9 transition table. A missing entry is 409 for everyone. */
const TABLE: Record<FlagStatus, Partial<Record<OfficerAction, Rule>>> = {
  OPEN: LIVE_RULES,
  DOCS_REQUESTED: LIVE_RULES,
  ESCALATED: {
    REQUEST_DOCS: { to: "DOCS_REQUESTED", roles: [A] },
    CLEAR: { to: "CLEARED", roles: [A] },
    CONFIRM: { to: "CONFIRMED", roles: [A] },
    NOTE: { to: "=", roles: [A, R] },
    ASSIGN: { to: "=", roles: [A] },
  },
  CLEARED: CLOSED_RULES,
  CONFIRMED: CLOSED_RULES,
};
const STATUS_WORD: Record<FlagStatus, string> = {
  OPEN: "open",
  DOCS_REQUESTED: "waiting for documents",
  ESCALATED: "escalated",
  CLEARED: "cleared",
  CONFIRMED: "confirmed",
};
const INTERNAL_NOTES: CaseHistoryItem["action"][] = ["ESCALATE", "NOTE", "REOPEN"];

function allowedActions(user: User, f: StoredFlag): OfficerAction[] {
  if (!OFFICERS.includes(user.role)) return [];
  return ORDER.filter((a) => TABLE[f.status][a]?.roles.includes(user.role));
}

function historyFor(user: User, c: CaseState): CaseHistoryItem[] {
  if (user.role !== I) return c.history;
  return c.history
    .filter((h) => h.action !== "ASSIGN")
    .map((h) => ({ ...h, note: INTERNAL_NOTES.includes(h.action) ? null : h.note, assignee: null }));
}

function decorateRow<T extends FlagRow>(user: User, row: T): T {
  const c = caseOf(row.id);
  return {
    ...row,
    assignee: user.role === I ? null : c.assignee,
    response_received: c.responseReceived,
    docs_due_on: c.docsDueOn,
    last_action_at: c.lastActionAt,
  };
}

function decorateDetail(user: User, d: FlagDetail): FlagDetail {
  const f = flagById(d.id)!;
  return {
    ...decorateRow(user, d),
    history: historyFor(user, caseOf(d.id)),
    allowed_actions: allowedActions(user, f),
    can_respond: user.role === I && f.status === "DOCS_REQUESTED",
  };
}

async function listFlags(user: User, query: Query | undefined, next: Next): Promise<FlagPage> {
  const all = (await next("GET", "/flags", { ...query, page: 1, page_size: 200 })) as FlagPage;
  let rows = all.items.map((r) => decorateRow(user, r));
  if (user.role !== I && query?.assignee) {
    const a = String(query.assignee);
    rows = rows.filter((r) => (a === "none" ? r.assignee === null : r.assignee?.id === (a === "me" ? user.id : a)));
  }
  if (query?.response_received === "true" || query?.response_received === true) rows = rows.filter((r) => r.response_received);
  if (query?.response_received === "false" || query?.response_received === false) rows = rows.filter((r) => !r.response_received);
  const page = paginate(rows, query);
  return { ...page, institutions: new Set(rows.map((r) => r.institution.id)).size };
}

async function flagDetail(user: User, id: string, next: Next): Promise<FlagDetail> {
  return decorateDetail(user, (await next("GET", `/flags/${id}`)) as FlagDetail);
}

function officerFor(f: StoredFlag, id: string): { id: string; name: string } {
  const o = assignable(f).find((x) => x.id === id);
  if (!o) throw invalid("assignee_id", "Choose an officer who can see this flag.");
  return { id: o.id, name: o.name };
}

async function act(user: User, id: string, body: unknown, next: Next): Promise<FlagDetail> {
  requireRole(user, OFFICERS);
  const req = (body ?? {}) as Partial<CaseActionRequest>;
  if (!req.action || !ORDER.includes(req.action)) throw invalid("action", "Choose an action.");
  await next("GET", `/flags/${id}`);
  const f = flagById(id)!;
  const rule = TABLE[f.status][req.action];
  if (!rule) {
    throw new ApiError(409, "FLAG_TRANSITION_INVALID", `This action is not possible while the flag is ${STATUS_WORD[f.status]}.`, {
      status: f.status,
      action: req.action,
      allowed_actions: allowedActions(user, f),
    });
  }
  if (!rule.roles.includes(user.role)) throw forbidden(rule.roles);

  const note = (req.note ?? "").trim();
  if (req.action !== "ASSIGN") {
    if (!note) throw invalid("note", "Add a note before you continue.");
    if (note.length > 2000) throw invalid("note", "Keep the note to 2,000 characters.");
  }
  let due: string | null = null;
  if (req.action === "REQUEST_DOCS" && req.due_date) {
    if (req.due_date < todayIst()) throw invalid("due_date", "Choose today or a later date.");
    if (req.due_date > plusDays(todayIst(), 90)) throw invalid("due_date", "Choose a date within 90 days of today.");
    due = req.due_date;
  }
  let assignee: { id: string; name: string } | null | undefined;
  if (req.action === "ASSIGN") {
    if (!("assignee_id" in req)) throw invalid("assignee_id", "Choose an officer who can see this flag.");
    assignee = req.assignee_id ? officerFor(f, req.assignee_id) : null;
  }
  if (req.action === "ESCALATE" && req.assignee_id) {
    const o = DIRECTORY.find((x) => x.id === req.assignee_id);
    if (!o || o.role !== A) throw invalid("assignee_id", "Escalate to an AICTE officer.");
    assignee = { id: o.id, name: o.name };
  }

  const at = nowIso();
  const from = f.status;
  const to = rule.to === "=" ? from : rule.to;
  const c = caseOf(id);
  f.status = to;
  f.updated_at = at;
  if (req.action === "REQUEST_DOCS") {
    c.docsDueOn = due;
    c.responseReceived = false;
  }
  if (req.action === "REOPEN") {
    c.docsDueOn = null;
    c.responseReceived = false;
  }
  if ((req.action === "ASSIGN" || req.action === "ESCALATE") && assignee !== undefined) c.assignee = assignee;
  if (req.action === "CONFIRM" && f.enrolmentId) {
    const e = entryById(f.enrolmentId);
    if (e && credentialsFor(e).some((x) => x.status === "ACTIVE")) REVOKED.set(f.enrolmentId, at);
  }
  c.history.push({
    seq: ++SEQ,
    at,
    action: req.action,
    from_status: from,
    to_status: to,
    actor: actorOf(user),
    note: req.action === "ASSIGN" ? null : note,
    due_date: req.action === "REQUEST_DOCS" ? due : null,
    assignee: req.action === "ASSIGN" || req.action === "ESCALATE" ? (assignee ?? null) : null,
    attachments: [],
  });
  c.lastActionAt = at;
  appendAudit(user, "UPDATE", "flag", id);
  return flagDetail(user, id, next);
}

/* ---- Attachments ---------------------------------------------------------- */

const MAX_BYTES = 5 * 1024 * 1024;
const PDF = [0x25, 0x50, 0x44, 0x46, 0x2d];
const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const JPEG = [0xff, 0xd8, 0xff];

function sniff(head: Uint8Array): CaseAttachment["content_type"] | null {
  const starts = (sig: number[]) => sig.every((b, i) => head[i] === b);
  if (starts(PDF)) return "application/pdf";
  if (starts(PNG)) return "image/png";
  if (starts(JPEG)) return "image/jpeg";
  return null;
}

function sampleBlob(type: CaseAttachment["content_type"], title: string): Blob {
  if (type === "image/png") {
    const b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
    const bin = atob(b64);
    return new Blob([Uint8Array.from(bin, (ch) => ch.charCodeAt(0))], { type });
  }
  const text = `%PDF-1.4\n1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]>> endobj\n% ${title}\ntrailer <</Root 1 0 R>>\n%%EOF\n`;
  return new Blob([text], { type: "application/pdf" });
}

function storeSample(flagId: string, filename: string, type: CaseAttachment["content_type"], size: number): CaseAttachment {
  const meta: CaseAttachment = { id: uuid(`attachment:${flagId}:${filename}`), filename, content_type: type, size_bytes: size, sha256: hex(`sha:${filename}`) };
  FILES.set(meta.id, { flagId, blob: sampleBlob(type, filename), meta });
  return meta;
}

/** POST /flags/{id}/response in mock mode (A3.11). */
export async function casesUpload(path: string, form: FormData, request: Next): Promise<unknown> {
  const m = /^\/flags\/([^/]+)\/response$/.exec(path);
  if (!m) throw new ApiError(404, "NOT_FOUND", "We could not find that.");
  const user = signedIn();
  requireRole(user, [I]);
  ensureSeeded();
  await request("GET", `/flags/${m[1]}`);
  const f = flagById(m[1])!;
  if (f.status !== "DOCS_REQUESTED") {
    throw new ApiError(409, "FLAG_TRANSITION_INVALID", `This action is not possible while the flag is ${STATUS_WORD[f.status]}.`, {
      status: f.status,
      action: "COLLEGE_RESPONSE",
      allowed_actions: [],
    });
  }
  const note = String(form.get("note") ?? "").trim();
  if (!note) throw invalid("note", "Write a reply before you send.");
  const files = form.getAll("files").filter((x): x is File => x instanceof File);
  if (files.length > 3) throw invalid("files", "Attach at most 3 files.");
  const types: CaseAttachment["content_type"][] = [];
  for (const file of files) {
    const type = sniff(new Uint8Array(await file.slice(0, 8).arrayBuffer()));
    if (!type) throw new ApiError(415, "ATTACHMENT_TYPE", "Only PDF, PNG and JPEG files can be attached.", { filename: file.name });
    types.push(type);
  }
  for (const file of files) {
    if (file.size > MAX_BYTES) throw new ApiError(413, "ATTACHMENT_TOO_LARGE", "Each file can be at most 5 MB.", { filename: file.name, max_bytes: MAX_BYTES });
  }
  const at = nowIso();
  const attachments = files.map((file, i) => {
    const meta: CaseAttachment = { id: uuid(`attachment:${f.id}:${at}:${i}:${file.name}`), filename: file.name, content_type: types[i], size_bytes: file.size, sha256: hex(`sha:${at}:${file.name}`) };
    FILES.set(meta.id, { flagId: f.id, blob: file, meta });
    appendAudit(user, "CREATE", "case_attachment", meta.id);
    return meta;
  });
  const c = caseOf(f.id);
  c.history.push({
    seq: ++SEQ,
    at,
    action: "COLLEGE_RESPONSE",
    from_status: f.status,
    to_status: f.status,
    actor: actorOf(user),
    note,
    due_date: null,
    assignee: null,
    attachments,
  });
  c.responseReceived = true;
  c.lastActionAt = at;
  appendAudit(user, "UPDATE", "flag", f.id);
  return flagDetail(user, f.id, request);
}

/** GET /flags/{id}/attachments/{attachment_id} in mock mode (A3.12). */
export async function casesDownload(path: string, request: Next): Promise<{ blob: Blob; filename: string }> {
  const m = /^\/flags\/([^/]+)\/attachments\/([^/]+)$/.exec(path);
  if (!m) throw new ApiError(404, "NOT_FOUND", "We could not find that.");
  const user = signedIn();
  requireRole(user, [A, R, I]);
  ensureSeeded();
  try {
    await request("GET", `/flags/${m[1]}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) throw notFound("Attachment not found.");
    throw err;
  }
  const file = FILES.get(m[2]);
  if (!file || file.flagId !== m[1]) throw notFound("Attachment not found.");
  appendAudit(user, "READ", "case_attachment", m[2]);
  return { blob: file.blob, filename: file.meta.filename };
}

/* ---- Enrolment detail and resend ----------------------------------------- */

async function enrolmentDetail(user: User, id: string, next: Next): Promise<EnrolmentDetail> {
  const e = entryById(id);
  if (e) syncEntry(e);
  const d = (await next("GET", `/enrolments/${id}`)) as EnrolmentDetail;
  if (!e) return d;
  const file = noticesOf(e);
  appendAudit(user, "READ", "student", e.row.student.id);
  return { ...d, notices: wireNotices(file), resend: resendState(user, e, file), credentials: credentialsFor(e) };
}

async function resend(user: User, id: string, next: Next): Promise<NoticeResendResult> {
  requireRole(user, [A, R, I]);
  await next("GET", `/enrolments/${id}`);
  const e = entryById(id)!;
  const file = noticesOf(e);
  if (e.row.status !== "ACTIVE") throw new ApiError(409, "CONFLICT", "Notices go only to active enrolments.", { reason: "NOT_ACTIVE" });
  if (file.notices.some((n) => n.response)) throw new ApiError(409, "NOTICE_LIVE", "The student has already replied.", { reason: "ANSWERED" });
  const live = file.notices.filter(isLive).sort((a, b) => (b.sent_at ?? "").localeCompare(a.sent_at ?? ""))[0];
  if (live) {
    throw new ApiError(409, "NOTICE_LIVE", `A notice sent on ${formatDate(live.sent_at ?? nowIso())} is open until ${formatDate(live.expires_at)}.`, {
      reason: "LIVE",
      expires_at: live.expires_at,
    });
  }
  if (file.consentWithdrawnAt) throw new ApiError(409, "CONFLICT", "The student has asked not to receive notices.", { reason: "CONSENT_WITHDRAWN" });
  if (!file.hasEmail && !linked(e)) {
    throw new ApiError(409, "CONFLICT", "The student has no email address or linked APAAR to send a notice to.", { reason: "NO_CHANNEL" });
  }
  if (file.resendsUsed >= 3) throw new ApiError(429, "RESEND_LIMIT", "This notice has been resent 3 times this academic year.", { limit: 3 });

  const now = Date.now();
  const at = iso(new Date(now));
  const fresh: StoredNotice[] = [];
  const channels: NoticeChannel[] = [...(file.hasEmail ? (["EMAIL"] as const) : []), ...(linked(e) ? (["DIGILOCKER"] as const) : [])];
  for (const channel of channels) {
    fresh.push({
      ...notice(e, channel, `resend:${file.resendsUsed + 1}`, at, addDays(at, 30)),
      delivery_status: "QUEUED",
      attempts: 0,
      sent_at: null,
      resent: true,
      deliverAt: now + 3000,
    });
  }
  file.notices.push(...fresh);
  file.resendsUsed += 1;
  for (const n of fresh) appendAudit(user, "CREATE", "notification", n.id);
  syncEntry(e);
  return {
    enrolment_id: id,
    notices: fresh.map(toWire),
    resend: resendState(user, e, file),
  };
}

/* ---- Data requests (A3.22) ------------------------------------------------ */

const REQUESTS: DataRequestAdminRow[] = [];

function requestRow(
  e: RollEntry,
  kind: DataRequestAdminRow["kind"],
  details: string,
  createdAt: string,
  resolved?: { status: "DONE" | "REJECTED"; response: string; at: string },
): DataRequestAdminRow {
  const s = e.row.student;
  return {
    id: uuid(`data-request:${e.row.id}:${kind}:${createdAt}`),
    kind,
    status: resolved?.status ?? "OPEN",
    details,
    response: resolved?.response ?? null,
    enrolment: { id: e.row.id, institution_name: institutionName(e.institutionId), programme_name: e.programme.name, academic_year: e.row.academic_year },
    created_at: createdAt,
    resolved_at: resolved?.at ?? null,
    export_path: null,
    student: { id: s.id, name: s.name, apaar_masked: s.apaar_masked, provisional_id: s.provisional_id },
    resolved_by: resolved ? { id: USERS[0].id, name: USERS[0].name } : null,
  };
}

function seedRequests() {
  const ravi = entryById(RAVI)!;
  const pick = (institutionId: string, test: (e: RollEntry) => boolean, skip = 0) =>
    rollFor(institutionId).filter((e) => !e.planted && e.row.status === "ACTIVE" && test(e))[skip];
  const xyz = pick(IDS.xyz, linked, 4);
  const abcProvisional = pick(IDS.abc, (e) => e.row.student.consent_status !== "LINKED" && e.row.student.consent_status !== "INTERNATIONAL", 2);
  const karad = pick("10000000-0004-4000-8000-000000000004", linked, 9);
  const pune = pick("10000000-0010-4000-8000-000000000010", linked, 6);
  const rows = [
    requestRow(ravi, "CORRECTION", "Please unlink my APAAR from my enrolment at ABC College of Engineering. I want my college to use a provisional id for now.", "2026-10-28T06:12:00Z"),
    xyz && requestRow(xyz, "ERASURE", "Please delete my mobile number and email address from Countersign. I do not want to be contacted on them.", "2026-10-27T14:40:00Z"),
    abcProvisional &&
      requestRow(abcProvisional, "CORRECTION", "My date of birth is recorded as 4 Feb 2008. The correct date is 14 Feb 2008, as on my 10th certificate.", "2026-10-28T08:55:00Z"),
    karad &&
      requestRow(karad, "CORRECTION", "My name is spelt Shinde Prashant on the record. Please correct it to Prashant Shinde.", "2026-10-26T11:20:00Z", {
        status: "DONE",
        response: "The college uploaded your row again with the name Prashant Shinde on 27 Oct 2026. Your record now shows the corrected name.",
        at: "2026-10-27T10:05:00Z",
      }),
    pune &&
      requestRow(pune, "ERASURE", "Delete everything Countersign holds about me.", "2026-10-26T09:02:00Z", {
        status: "REJECTED",
        response:
          "We cannot erase your enrolment record, its checks or its history, because AICTE must keep them for the period the law requires. Everything shown to officers stays masked, and you can see who views your record on your Privacy page. We hold no other data about you.",
        at: "2026-10-26T16:30:00Z",
      }),
  ];
  REQUESTS.push(...rows.filter((r): r is DataRequestAdminRow => Boolean(r)));
}

function listRequests(user: User, query?: Query): Page<DataRequestAdminRow> {
  requireRole(user, [A]);
  let rows = REQUESTS.filter((r) => r.kind !== "ACCESS");
  if (query?.status) rows = rows.filter((r) => r.status === query.status);
  if (query?.kind) rows = rows.filter((r) => r.kind === query.kind);
  rows = [...rows].sort((a, b) => (a.status === "OPEN" ? 0 : 1) - (b.status === "OPEN" ? 0 : 1) || a.created_at.localeCompare(b.created_at));
  return paginate(rows, query);
}

function resolveRequest(user: User, id: string, body: unknown): DataRequestAdminRow {
  requireRole(user, [A]);
  const row = REQUESTS.find((r) => r.id === id);
  if (!row) throw notFound("Data request not found.");
  const req = (body ?? {}) as Partial<DataRequestResolve>;
  if (req.status !== "DONE" && req.status !== "REJECTED") throw invalid("status", "Choose Done or Decline.");
  const response = (req.response ?? "").trim();
  if (response.length < 10) throw invalid("response", "Write a reply before you resolve the request.");
  if (response.length > 2000) throw invalid("response", "Keep the reply to 2,000 characters.");
  if (row.status !== "OPEN") throw new ApiError(409, "CONFLICT", "This request is already resolved.", { reason: "ALREADY_RESOLVED" });
  row.status = req.status;
  row.response = response;
  row.resolved_at = nowIso();
  row.resolved_by = { id: user.id, name: user.name };
  appendAudit(user, "UPDATE", "data_request", row.id);
  return row;
}

/* ---- Seed ------------------------------------------------------------------ */

const DENY_COMMENTS: (string | null)[] = [
  "I am not studying at this college. I joined a polytechnic in Nashik.",
  null,
  "I never applied here.",
  "This is not my programme. I study Mechanical Engineering at another college.",
  "I left in August and took my fee refund.",
  null,
  "I do not know this college.",
  "Someone has used my details. Please check.",
];

function deniedFlag(n: number, e: RollEntry, file: NoticeFile, comment: string | null): StoredFlag {
  const denied = file.notices.find((x) => x.response === "NO" || x.previous_response === "NO")!;
  const changed = denied.previous_response === "NO";
  const sentDate = formatDate(denied.sent_at);
  const replied = formatDate(denied.responded_at);
  const facts: StoredFact[] = [
    { label: "Channel", value: denied.channel === "EMAIL" ? "Email" : "DigiLocker", source: "Student reply" },
    { label: "Notice sent", value: sentDate, source: "Student reply" },
    { label: "Replied on", value: replied, source: "Student reply" },
    ...(changed ? [{ label: "Reply changed", value: `Yes on ${formatDate(denied.changed_at)}`, source: "Student reply" }] : []),
    { label: "Comment from the student", value: comment ?? "None", source: "Student reply", audience: "OFFICER" as const },
  ];
  return {
    id: `f${String(n).padStart(7, "0")}-7777-4888-8999-000011112222`,
    type: "STUDENT_DENIED",
    severity: "HIGH",
    status: "OPEN",
    institutionId: e.institutionId,
    programmeId: e.programme.id,
    enrolmentId: e.row.id,
    academic_year: e.row.academic_year,
    summary: changed
      ? `Student replied "not me" to the notice sent on ${sentDate}, then changed the reply to Yes on ${formatDate(denied.changed_at)}.`
      : `Student replied "not me" to the notice sent on ${sentDate}.`,
    facts,
    related: [e.row.id],
    rule_source: "Student reply",
    created_at: denied.responded_at!,
    updated_at: denied.changed_at ?? denied.responded_at!,
  };
}

/** Eight planted No replies (one beats a Yes on the other channel), and one No later changed to Yes. */
function seedDenials() {
  const KARAD = "10000000-0004-4000-8000-000000000004";
  const PUNE = "10000000-0010-4000-8000-000000000010";
  const KAVERI = "10000000-0006-4000-8000-000000000006";
  const LUCKNOW = "10000000-0007-4000-8000-000000000007";
  const GAYATRI = "10000000-0003-4000-8000-000000000003";
  const DURGAPUR = "10000000-0008-4000-8000-000000000008";
  const homes = [IDS.abc, IDS.abc, KARAD, PUNE, IDS.xyz, KAVERI, LUCKNOW, GAYATRI, DURGAPUR];
  const used = new Set<string>();
  const candidates = (institutionId: string) =>
    rollFor(institutionId)
      .filter((e) => !e.planted && e.row.id !== RAVI && e.row.status === "ACTIVE" && linked(e) && !used.has(e.row.id) && e.checks.length > 0)
      .sort((a, b) => hash(`deny:${a.row.id}`) - hash(`deny:${b.row.id}`));
  let n = 13;
  homes.forEach((home, i) => {
    const e = candidates(home)[0];
    if (!e) return;
    used.add(e.row.id);
    const file: NoticeFile = { notices: [], hasEmail: true, noDigiLocker: false, resendsUsed: 0, consentWithdrawnAt: null };
    const email = notice(e, "EMAIL", "first", SENT_AT, EXPIRES_AT);
    const digi = notice(e, "DIGILOCKER", "first", SENT_AT, EXPIRES_AT);
    file.notices.push(email, digi);
    if (i === 0) {
      email.response = "YES";
      email.responded_at = addHours(SENT_AT, 3);
      digi.response = "NO";
      digi.responded_at = addHours(SENT_AT, 20);
    } else if (i === homes.length - 1) {
      email.response = "YES";
      email.previous_response = "NO";
      email.responded_at = addHours(SENT_AT, 5);
      email.changed_at = addHours(SENT_AT, 26);
    } else {
      email.response = "NO";
      email.responded_at = addHours(SENT_AT, 2 + i * 3);
    }
    NOTICES.set(e.row.id, file);
    const comment = DENY_COMMENTS[i % DENY_COMMENTS.length];
    const f = deniedFlag(n++, e, file, comment);
    allFlags().push(f);
    if (email.changed_at) {
      const c = caseOf(f.id);
      c.history.push({
        seq: 59,
        at: email.changed_at,
        action: "SYSTEM_NOTE",
        from_status: "OPEN",
        to_status: "OPEN",
        actor: null,
        note: `The student changed the reply from No to Yes on ${formatDate(email.changed_at)}. The flag keeps its status until an officer decides.`,
        due_date: null,
        assignee: null,
        attachments: [],
      });
      c.lastActionAt = email.changed_at;
    }
  });
}

/** Case work already done on the Week 2 flags, so every state of the action bar can be seen. */
function seedCases() {
  const admin = byEmail("admin@aicte.demo");
  const west = byEmail("ro.west@aicte.demo");
  const south = byEmail("ro.south@aicte.demo");
  const abc = byEmail("registrar@abc.edu.demo");
  const puneRegistrar: ActorRef = { id: "6f1c0a8e-0021-4c9a-9e51-1c2f1a0b7d33", name: "Registrar, Pune Institute of Technology and Management", role: "INSTITUTION" };
  const id = (n: number) => (n === 1 ? "f1f1f1f1-7777-4888-8999-000011112222" : `f${String(n).padStart(7, "0")}-7777-4888-8999-000011112222`);
  const item = (seq: number, at: string, action: CaseHistoryItem["action"], from: FlagStatus, to: FlagStatus, actor: ActorRef | null, note: string | null, extra: Partial<CaseHistoryItem> = {}): CaseHistoryItem => ({
    seq,
    at,
    action,
    from_status: from,
    to_status: to,
    actor,
    note,
    due_date: null,
    assignee: null,
    attachments: [],
    ...extra,
  });
  const apply = (n: number, status: FlagStatus, history: CaseHistoryItem[], patch: Partial<CaseState> = {}) => {
    const f = flagById(id(n));
    if (!f) return;
    f.status = status;
    const c = caseOf(f.id);
    c.history.push(...history);
    c.lastActionAt = history[history.length - 1]?.at ?? null;
    Object.assign(c, patch);
  };

  // ABC, Rahul Pawar: documents requested by AICTE, the reply date has passed.
  apply(3, "DOCS_REQUESTED", [item(36, "2026-10-27T10:02:00Z", "REQUEST_DOCS", "OPEN", "DOCS_REQUESTED", admin, "Send the APAAR card or the DigiLocker APAAR record for Rahul Pawar.", { due_date: "2026-10-27" })], {
    docsDueOn: "2026-10-27",
  });

  // ABC, Mohd. Faizan Shaikh: documents requested by the regional officer, the college responded.
  const form = storeSample(id(4), "admission_form.pdf", "application/pdf", 421_888);
  const idCopy = storeSample(id(4), "id_copy.png", "image/png", 186_112);
  apply(
    4,
    "DOCS_REQUESTED",
    [
      item(41, "2026-10-27T10:35:00Z", "REQUEST_DOCS", "OPEN", "DOCS_REQUESTED", west, "Send the admission form and an ID copy for Mohd. Faizan Shaikh.", { due_date: "2026-11-04" }),
      item(44, "2026-10-28T04:50:00Z", "COLLEGE_RESPONSE", "DOCS_REQUESTED", "DOCS_REQUESTED", abc, "The student's full name on the 10th certificate is Mohammed Faizan Shaikh. Admission form and ID copy attached.", {
        attachments: [form, idCopy],
      }),
    ],
    { docsDueOn: "2026-11-04", responseReceived: true },
  );

  // ABC, Kunal Bhosale: escalated by the regional officer to AICTE.
  apply(
    5,
    "ESCALATED",
    [
      item(38, "2026-10-27T11:10:00Z", "ASSIGN", "OPEN", "OPEN", west, null, { assignee: { id: west.id, name: west.name } }),
      item(39, "2026-10-27T11:12:00Z", "ESCALATE", "OPEN", "ESCALATED", west, "Two semesters with no credits and the university has not replied. This needs a decision at AICTE.", {
        assignee: { id: admin.id, name: admin.name },
      }),
    ],
    { assignee: { id: admin.id, name: admin.name } },
  );

  // XYZ and Kaveri, Arjun Iyer: assigned to the southern regional officer.
  apply(9, "OPEN", [item(33, "2026-10-27T12:00:00Z", "ASSIGN", "OPEN", "OPEN", admin, null, { assignee: { id: south.id, name: south.name } })], {
    assignee: { id: south.id, name: south.name },
  });

  // Pune ITM, NRI quota: documents, a response, then confirmed by AICTE.
  apply(
    11,
    "CONFIRMED",
    [
      item(47, "2026-10-26T16:10:00Z", "REQUEST_DOCS", "OPEN", "DOCS_REQUESTED", west, "Send the NRI admission register for CSE, 2026-27, and any supernumerary approval.", { due_date: "2026-10-28" }),
      item(49, "2026-10-27T07:25:00Z", "COLLEGE_RESPONSE", "DOCS_REQUESTED", "DOCS_REQUESTED", puneRegistrar, "Register attached. We have no supernumerary approval for NRI seats this year.", {
        attachments: [storeSample(id(11), "nri_register_cse_2026-27.pdf", "application/pdf", 1_887_436)],
      }),
      item(55, "2026-10-27T13:45:00Z", "CONFIRM", "DOCS_REQUESTED", "CONFIRMED", admin, "Three NRI admissions beyond the 5% carve-out with no supernumerary approval. Recorded as a confirmed irregularity."),
    ],
    { docsDueOn: "2026-10-28", responseReceived: true },
  );

  // GCE Karad, late refill: cleared, then the engines refreshed the evidence.
  apply(12, "CLEARED", [
    item(52, "2026-10-28T09:05:00Z", "CLEAR", "OPEN", "CLEARED", west, "The seat was released on 28 Sep and refilled on 5 Oct with the state counselling authority's written approval, which is on file."),
    item(57, "2026-10-28T09:40:00Z", "SYSTEM_NOTE", "CLEARED", "CLEARED", null, "Evidence updated after the decision."),
  ]);
}

let seeded = false;

function ensureSeeded() {
  if (seeded) return;
  seeded = true;
  for (const s of SEEDS) rollFor(s.id);
  seedAudit();
  seedDenials();
  seedCases();
  seedRequests();
  for (const s of SEEDS) syncInstitution(s.id);
}

/* ---- Router ---------------------------------------------------------------- */

/**
 * Answers the Week 3 officer routes, decorates flag and enrolment reads, and
 * hands everything else to `next` (the Week 2 handler).
 */
export async function withCases(method: string, path: string, query: Query | undefined, body: unknown, next: Next): Promise<unknown> {
  const [pathname] = path.split("?");
  if (pathname.startsWith("/auth/") || pathname === "/healthz") return next(method, path, query, body);
  ensureSeeded();
  const parts = pathname.split("/").filter(Boolean);

  if (parts[0] === "flags") {
    if (parts.length === 1 && method === "GET") return listFlags(signedIn(), query, next);
    if (parts.length === 2 && method === "GET") return flagDetail(signedIn(), parts[1], next);
    if (parts.length === 3 && parts[2] === "actions" && method === "POST") return act(signedIn(), parts[1], body, next);
  }

  if (parts[0] === "enrolments" && parts[1]) {
    if (parts.length === 2 && method === "GET") return enrolmentDetail(signedIn(), parts[1], next);
    if (parts[2] === "notices" && parts[3] === "resend" && method === "POST") return resend(signedIn(), parts[1], next);
    if (parts[2] === "recheck" && method === "POST") {
      const result = (await next(method, path, query, body)) as EnrolmentRecheck;
      const e = entryById(parts[1]);
      if (e) {
        syncEntry(e);
        result.countersign = e.row.countersign;
      }
      return result;
    }
  }

  if (parts[0] === "institutions" && parts[2] === "recheck" && method === "POST") {
    const result = await next(method, path, query, body);
    syncInstitution(parts[1]);
    return result;
  }

  if (pathname === "/users" && method === "GET") {
    await latency();
    return listUsers(signedIn(), query);
  }

  if (pathname === "/admin/audit" && method === "GET") {
    await latency();
    return listAudit(signedIn(), query);
  }
  if (pathname === "/admin/audit/verify" && method === "GET") {
    await wait(700);
    return verifyAudit(signedIn());
  }

  if (parts[0] === "data-requests") {
    await latency();
    if (parts.length === 1 && method === "GET") return listRequests(signedIn(), query);
    if (parts.length === 3 && parts[2] === "resolve" && method === "POST") return resolveRequest(signedIn(), parts[1], body);
  }

  return next(method, path, query, body);
}
