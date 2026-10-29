/**
 * Mock-mode case work, student notices, the audit log and data requests
 * (API_CONTRACT A3.5, A3.7 to A3.14, A3.22 and A3.23).
 *
 * The handler sends every request through `withCases` first. Routes this
 * file owns are answered here; flag and enrolment reads go on to the base
 * handler and come back decorated with case state, history and notices;
 * everything else passes straight through.
 *
 * Demo controls, from the browser console in mock mode only:
 *   countersignMock.tamperAudit(917)   the same as `make audit-tamper SEQ=917`
 *   countersignMock.restoreAudit()     the same as `make demo-reset` for the chain
 *   countersignMock.decideFlag(id, "UPHELD")   another officer decides meanwhile (409 on a stale page)
 */
import { ApiError, type Query } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ACADEMIC_YEAR, IDS, INSTITUTIONS, SEEDS, USERS } from "@/lib/mock/fixtures";
import { makeRow, sentenceDate } from "@/lib/mock/evidence";
import { COVERS, allFlags, flagById, type StoredFact, type StoredFlag } from "@/lib/mock/flags";
import { recordFor, withRecord } from "@/lib/mock/records";
import { CHECKED_AT, LATER_VERSIONS, entryById, entryByName, evaluate, programmesFor, rollFor, seatsFor, setRows, versionsOf, type RollEntry } from "@/lib/mock/roll";
import { readBrowserToken, userFromToken } from "@/lib/mock/session";
import { listReports } from "@/lib/mock/reports";
import { allSignals, dismissSignal, featureFacts, listSignals, membersOf, ruleOf, signalDetail, signalInScope, REGION_OF, type StoredSignal } from "@/lib/mock/signals";
import type {
  ActorRef,
  AdmissionRoute,
  AuditAction,
  AuditRow,
  AuditVerify,
  CaseActionRequest,
  CaseActionResult,
  CaseAttachment,
  CaseHistoryItem,
  CaseScope,
  CredentialRef,
  DataRequestAdminRow,
  DataRequestResolve,
  DecisionAction,
  DecisionEffects,
  DocsKind,
  DryRunResult,
  EnrolmentDetail,
  EnrolmentNotice,
  EnrolmentRecheck,
  EvidenceRow,
  FieldChange,
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
  ReasonCode,
  RecordStatus,
  Region,
  Severity,
  SignalDetail,
  SignalOpenCaseResult,
  ResendState,
  Role,
  RowResolution,
  SeatRow,
  SeatType,
  StudentNoticeState,
  UpholdReason,
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
    decideFlag: (id: string, status: FlagStatus) => {
      const f = flagById(id);
      if (f) f.status = status;
    },
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

const decidedAt = (n: StoredNotice) => n.changed_at ?? n.responded_at ?? "";

/** The Student row from the notices and the answer given after DigiLocker sign-in (A4.4, copy deck §15). */
function studentCheck(e: RollEntry, file: NoticeFile): EvidenceRow {
  const all = file.notices;
  const earliest = (resp: NoticeResponse) => all.filter((n) => n.response === resp).sort((a, b) => decidedAt(a).localeCompare(decidedAt(b)))[0];
  const digilocker = { supplied_by: "Student via DigiLocker sign-in", independent: true };
  const make = (
    state: EvidenceRow["state"],
    basis: string,
    finding: string,
    sourceLine: string,
    summary: string,
    noticeState: StudentNoticeState,
    extra: Record<string, unknown>,
    observedAt: string | null,
    provenance: { supplied_by?: string; independent?: boolean } = {},
  ): EvidenceRow =>
    makeRow(
      "STUDENT",
      { state, basis, finding, source: "STUDENT_NOTICE", source_line: sourceLine, summary, observed_at: observedAt, ...provenance, detail: { notice_state: noticeState, ...extra } },
      observedAt ?? CHECKED_AT,
    );
  const decided = (n: StoredNotice) => ({ channel: n.channel, sent_at: n.sent_at, responded_at: decidedAt(n), changed: Boolean(n.changed_at) });
  const no = earliest("NO");
  if (no) {
    const at = decidedAt(no);
    return make("CONTRADICTED", "DENIED", "\"I never joined\"", `Student sign-in via DigiLocker · ${sentenceDate(at)}`, `The student signed in with DigiLocker on ${sentenceDate(at)} and said they never joined.`, "DENIED", { ...decided(no), case_type: "STUDENT_DENIED" }, at, digilocker);
  }
  const yes = earliest("YES");
  if (yes) {
    const at = decidedAt(yes);
    const changed = yes.previous_response === "NO" && yes.changed_at;
    return make(
      "CONFIRMED",
      changed ? "CONFIRMED_CHANGED" : "CONFIRMED",
      "\"I joined\"",
      `Student sign-in via DigiLocker · ${sentenceDate(at)}`,
      changed
        ? `The student said they never joined on ${sentenceDate(yes.responded_at)}, then changed the answer to Yes on ${sentenceDate(yes.changed_at)}.`
        : `The student signed in with DigiLocker on ${sentenceDate(at)} and said they joined.`,
      "CONFIRMED",
      decided(yes),
      at,
      digilocker,
    );
  }
  const delivered = all.filter((n) => n.delivery_status === "SENT").sort((a, b) => (b.sent_at ?? "").localeCompare(a.sent_at ?? ""));
  if (delivered.length === 0) {
    const unreachable = !file.hasEmail && !linked(e);
    const extra: Record<string, unknown> = {};
    if (all.some((n) => n.delivery_status === "FAILED")) extra.delivery_failed = true;
    if (file.consentWithdrawnAt) extra.consent_withdrawn = true;
    return make("PENDING", unreachable ? "UNREACHABLE" : "NOT_SENT", "notice not sent yet", "No notice sent yet", "Notice not sent yet.", unreachable ? "UNREACHABLE" : "NOT_SENT", extra, null);
  }
  const live = delivered.filter((n) => stateOf(n) === "AWAITING");
  if (live.length > 0) {
    const sent = live[0].sent_at;
    return make("PENDING", "SENT", "no answer yet", `Notice sent ${sentenceDate(sent)}`, `Notice sent on ${sentenceDate(sent)}; no answer yet.`, "SENT", { channel: live[0].channel, sent_at: sent }, null);
  }
  const expired = delivered[0];
  return make(
    "PENDING",
    "EXPIRED",
    "no answer",
    `Notice expired ${sentenceDate(expired.expires_at)}`,
    `No answer before the notice expired on ${sentenceDate(expired.expires_at)}. Silence never counts against the record.`,
    "EXPIRED",
    { channel: expired.channel, sent_at: expired.sent_at },
    null,
  );
}

function syncEntry(e: RollEntry) {
  if (e.checks.length === 0) return;
  const check = studentCheck(e, noticesOf(e));
  setRows(
    e,
    withResolutions(
      e,
      e.checks.map((c) => (c.type === "STUDENT" ? check : c)),
    ),
  );
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

/** An enrolment attestation is issued once the record is Countersigned (A4.14); an officer's revocation holds. */
function credentialsFor(e: RollEntry): CredentialRef[] {
  const revokedAt = REVOKED.get(e.row.id) ?? null;
  const record = withRecord(e);
  if (record.record_status !== "COUNTERSIGNED" && !revokedAt) return [];
  const student = e.checks.find((c) => c.type === "STUDENT");
  const issuedAt = student?.state === "CONFIRMED" && student.observed_at ? addHours(student.observed_at, 0.02) : addHours(CHECKED_AT, 0.05);
  return [
    {
      id: uuid(`credential:${e.row.id}`),
      kind: "ENROLMENT",
      status: revokedAt ? "REVOKED" : "ACTIVE",
      short_id: hex(`short:${e.row.id}`, 8).toUpperCase(),
      issued_at: issuedAt,
      revoked_at: revokedAt,
      revoked_reason_code: revokedAt ? "CLAIM_WITHDRAWN" : null,
      revoked_reason: null,
    },
  ];
}

/* ---- Cases (A3.9 to A3.13, A4.8 to A4.11) -------------------------------- */

interface CaseState {
  assignee: { id: string; name: string } | null;
  responseReceived: boolean;
  docsDueOn: string | null;
  lastActionAt: string | null;
  history: CaseHistoryItem[];
  /** Records this case withdrew or corrected; on a multi-record case they are no longer outstanding. */
  done: string[];
}

const CASES = new Map<string, CaseState>();
/** The A4.11 keys every history item carries; the decision sheets fill them. */
const EXTRA = (): Pick<CaseHistoryItem, "reason_code" | "docs_kind" | "approval_version" | "correction" | "withdrawn_enrolment_ids"> => ({
  reason_code: null,
  docs_kind: null,
  approval_version: null,
  correction: null,
  withdrawn_enrolment_ids: [],
});
const FILES = new Map<string, { flagId: string; blob: Blob; meta: CaseAttachment }>();
let SEQ = 60;

function caseOf(id: string): CaseState {
  let c = CASES.get(id);
  if (!c) {
    c = { assignee: null, responseReceived: false, docsDueOn: null, lastActionAt: null, history: [], done: [] };
    CASES.set(id, c);
  }
  return c;
}

/** The order `allowed_actions` lists them (A4.8). */
const ORDER: OfficerAction[] = ["UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS", "ESCALATE", "NOTE", "ASSIGN", "REOPEN"];
type Rule = { to: FlagStatus | "="; roles: Role[] };
const LIVE_RULES: Partial<Record<OfficerAction, Rule>> = {
  UPHOLD: { to: "UPHELD", roles: [A, R] },
  CORRECT: { to: "CORRECTED", roles: [A, R] },
  WITHDRAW: { to: "WITHDRAWN", roles: [A, R] },
  REQUEST_DOCS: { to: "DOCS_REQUESTED", roles: [A, R] },
  ESCALATE: { to: "ESCALATED", roles: [A, R] },
  NOTE: { to: "=", roles: [A, R] },
  ASSIGN: { to: "=", roles: [A, R] },
};
const CLOSED_RULES: Partial<Record<OfficerAction, Rule>> = { NOTE: { to: "=", roles: [A, R] }, REOPEN: { to: "OPEN", roles: [A] } };
/** The A4.8 transition table. A missing entry is 409 for everyone. */
const TABLE: Record<FlagStatus, Partial<Record<OfficerAction, Rule>>> = {
  OPEN: LIVE_RULES,
  DOCS_REQUESTED: LIVE_RULES,
  ESCALATED: {
    UPHOLD: { to: "UPHELD", roles: [A] },
    CORRECT: { to: "CORRECTED", roles: [A] },
    WITHDRAW: { to: "WITHDRAWN", roles: [A] },
    REQUEST_DOCS: { to: "DOCS_REQUESTED", roles: [A] },
    NOTE: { to: "=", roles: [A, R] },
    ASSIGN: { to: "=", roles: [A] },
  },
  UPHELD: CLOSED_RULES,
  WITHDRAWN: CLOSED_RULES,
  CORRECTED: CLOSED_RULES,
};
const STATUS_WORD: Record<FlagStatus, string> = {
  OPEN: "open",
  DOCS_REQUESTED: "waiting for documents",
  ESCALATED: "escalated",
  UPHELD: "claim upheld",
  WITHDRAWN: "claim withdrawn",
  CORRECTED: "claim corrected",
};
const INTERNAL_NOTES: CaseHistoryItem["action"][] = ["ESCALATE", "NOTE", "REOPEN"];
const DECIDED: FlagStatus[] = ["UPHELD", "CORRECTED", "WITHDRAWN"];

/** Reason codes per decision (A4.9). */
const REASONS: Partial<Record<OfficerAction, ReasonCode[]>> = {
  UPHOLD: ["DOCUMENTS_SUPPORT_CLAIM", "SOURCE_RECORD_WRONG", "NAME_VARIANT", "PERMITTED_DUAL_PROGRAMME", "APPROVAL_VERSION_COVERS", "STUDENT_ANSWER_MISTAKEN", "MISSING_NOW_UPLOADED", "OTHER"],
  CORRECT: ["UPLOAD_ERROR", "DOCUMENTS_SHOW_OTHER_VALUE", "WRONG_SEAT_CATEGORY", "OTHER"],
  WITHDRAW: ["STUDENT_NEVER_JOINED", "NO_JOINING_EVIDENCE", "BEYOND_APPROVED_INTAKE", "NOT_ELIGIBLE_FOR_SEAT", "DUPLICATE_RECORD", "NO_RESPONSE", "OTHER"],
  ESCALATE: ["NEEDS_AICTE_DECISION", "POLICY_QUESTION", "SPANS_REGIONS", "REPEATED_PATTERN", "OTHER"],
};
const DOCS_KINDS: DocsKind[] = ["ADMISSION", "JOINING", "IDENTITY", "ELIGIBILITY", "CREDITS", "OTHER"];

/** Which records a case names and how it is decided (A4.10). */
function scopeOf(f: StoredFlag): CaseScope {
  if (f.type === "MISSING_FROM_UPLOAD" || f.type === "ANOMALY") return "INSTITUTION";
  if (f.type === "EXCESS_ADMISSION" || f.type === "QUOTA_BREACH" || f.type === "GHOST_RING") return "MULTI_RECORD";
  return "RECORD";
}

/** Correct and Withdraw do not apply to a case that names no record. */
function decisionApplies(f: StoredFlag, action: OfficerAction): boolean {
  if (action !== "CORRECT" && action !== "WITHDRAW") return true;
  return scopeOf(f) !== "INSTITUTION";
}

/** The records a case names at its own institution. */
function namedOf(f: StoredFlag): RollEntry[] {
  const scope = scopeOf(f);
  if (scope === "INSTITUTION") return [];
  const ids = scope === "RECORD" ? [f.enrolmentId ?? f.related.find((id) => entryById(id)?.institutionId === f.institutionId)] : f.related;
  return ids
    .filter((id): id is string => Boolean(id))
    .map((id) => entryById(id))
    .filter((e): e is RollEntry => Boolean(e) && e!.institutionId === f.institutionId);
}

/** The covered row is still an unresolved contradiction (or, for a name mismatch, a review). */
function coveredOpen(f: StoredFlag, e: RollEntry): boolean {
  const covers = COVERS[f.type];
  if (!covers) return true;
  const row = e.checks.find((c) => c.type === covers);
  if (!row || row.resolved) return false;
  return row.state === "CONTRADICTED" || (f.type === "NAME_MISMATCH" && row.state === "PENDING" && Boolean(row.detail.needs_review));
}

/** A4.10 "outstanding": named, active, and still contradicted on the covered row. */
function outstandingOf(f: StoredFlag): string[] {
  if (scopeOf(f) !== "MULTI_RECORD") return [];
  const done = caseOf(f.id).done;
  return namedOf(f)
    .filter((e) => e.row.status === "ACTIVE" && !done.includes(e.row.id) && coveredOpen(f, e))
    .map((e) => e.row.id);
}

function allowedActions(user: User, f: StoredFlag): OfficerAction[] {
  if (!OFFICERS.includes(user.role)) return [];
  return ORDER.filter((a) => TABLE[f.status][a]?.roles.includes(user.role) && decisionApplies(f, a));
}

function historyFor(user: User, c: CaseState): CaseHistoryItem[] {
  if (user.role !== I) return c.history;
  return c.history
    .filter((h) => h.action !== "ASSIGN")
    .map((h) => ({ ...h, note: INTERNAL_NOTES.includes(h.action) ? null : h.note, assignee: null }));
}

/** The case each signal opened, by case id (A4.11 `signal_id`; never shown to a college). */
const SIGNAL_OF = new Map<string, string>();

function decorateRow<T extends FlagRow>(user: User, row: T): T {
  const c = caseOf(row.id);
  const f = flagById(row.id);
  const last = [...c.history].reverse().find((h) => h.action === "UPHOLD" || h.action === "CORRECT" || h.action === "WITHDRAW");
  return {
    ...row,
    assignee: user.role === I ? null : c.assignee,
    response_received: c.responseReceived,
    docs_due_on: c.docsDueOn,
    last_action_at: c.lastActionAt,
    scope: f ? scopeOf(f) : row.scope,
    decision: DECIDED.includes(row.status) && last && last.reason_code ? { action: last.action as DecisionAction, reason_code: last.reason_code, at: last.at } : null,
    signal_id: user.role === I ? null : (SIGNAL_OF.get(row.id) ?? null),
  };
}

function decorateDetail(user: User, d: FlagDetail): FlagDetail {
  const f = flagById(d.id)!;
  return {
    ...decorateRow(user, d),
    outstanding_enrolment_ids: outstandingOf(f),
    history: historyFor(user, caseOf(d.id)),
    allowed_actions: allowedActions(user, f),
    can_respond: user.role === I && f.status === "DOCS_REQUESTED",
  };
}

async function listFlags(user: User, query: Query | undefined, next: Next): Promise<FlagPage> {
  const wanted = query?.status ? String(query.status) : null;
  const status = wanted === "DECIDED" ? "UPHELD,CORRECTED,WITHDRAWN" : wanted;
  const all = (await next("GET", "/flags", { ...query, status, signal_id: undefined, page: 1, page_size: 200 })) as FlagPage;
  let rows = all.items.map((r) => decorateRow(user, r));
  if (user.role !== I && query?.assignee) {
    const a = String(query.assignee);
    rows = rows.filter((r) => (a === "none" ? r.assignee === null : r.assignee?.id === (a === "me" ? user.id : a)));
  }
  if (user.role !== I && query?.signal_id) rows = rows.filter((r) => r.signal_id === query.signal_id);
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
  if (!o) throw invalid("assignee_id", "Choose an officer who can see this case.");
  return { id: o.id, name: o.name };
}

/* ---- Decisions and what they change (A4.9, A4.10) ------------------------- */

/** Rows an officer upheld, by `enrolment:type`; the Student row is rebuilt from notices, so they are applied again on every sync. */
const RESOLVED = new Map<string, RowResolution & { caseId: string }>();

function withResolutions(e: RollEntry, rows: EvidenceRow[]): EvidenceRow[] {
  return rows.map((r) => {
    const hit = RESOLVED.get(`${e.row.id}:${r.type}`);
    if (!hit) return r.resolved ? { ...r, resolved: null } : r;
    const { caseId: _caseId, ...resolved } = hit;
    void _caseId;
    return { ...r, resolved };
  });
}

const POOL_OF: Record<AdmissionRoute, SeatType> = {
  COUNSELLING: "REGULAR", MANAGEMENT: "REGULAR", SPOT: "REGULAR", NRI: "NRI", TFW: "TFW", LATERAL: "LATERAL", INTERNATIONAL: "INTERNATIONAL",
};

const CORRECTABLE = ["name", "dob", "year_of_study", "admission_route", "category", "counselling_ref", "admission_date", "tfw_income_certified", "nri_sponsored", "ciwg"] as const;
type Correctable = (typeof CORRECTABLE)[number];
const ROUTES: AdmissionRoute[] = ["COUNSELLING", "MANAGEMENT", "NRI", "SPOT", "LATERAL", "INTERNATIONAL", "TFW"];
const CATEGORIES = ["GENERAL", "EWS", "OBC", "SC", "ST", "OTHER"];
const FIELD_WORD: Record<Correctable, string> = {
  name: "Name", dob: "Date of birth", year_of_study: "Year of study", admission_route: "Admission route", category: "Category",
  counselling_ref: "Counselling reference", admission_date: "Admission date", tfw_income_certified: "TFW income certificate",
  nri_sponsored: "NRI sponsored", ciwg: "CIWG",
};

function currentOf(e: RollEntry, field: Correctable): unknown {
  if (field === "name") return e.row.student.name;
  if (field === "dob") return e.dob;
  if (field === "tfw_income_certified" || field === "nri_sponsored" || field === "ciwg") return e.row.eligibility[field];
  return (e.row as unknown as Record<string, unknown>)[field];
}

/** The corrected fields that differ from the record, checked as an upload row would be (A4.9). */
function correctionOf(e: RollEntry, fields: Record<string, unknown>): FieldChange[] {
  const changes: FieldChange[] = [];
  for (const [field, raw] of Object.entries(fields)) {
    if (!(CORRECTABLE as readonly string[]).includes(field)) {
      throw new ApiError(422, "CORRECTION_INVALID", `${field}: this field cannot be corrected here.`, { field });
    }
    const key = field as Correctable;
    const bad = (message: string) => new ApiError(422, "CORRECTION_INVALID", `${FIELD_WORD[key]}: ${message}`, { field });
    let value: unknown = raw;
    if (key === "name" && (typeof raw !== "string" || raw.trim().length < 2)) throw bad("Enter the full name.");
    if ((key === "dob" || key === "admission_date") && (typeof raw !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(raw))) throw bad("Use a date like 2008-01-14.");
    if (key === "admission_date" && String(raw) > todayIst()) throw bad("The date is in the future.");
    if (key === "year_of_study") {
      value = Number(raw);
      if (!Number.isInteger(value) || (value as number) < 1 || (value as number) > 6) throw bad("Choose a year the programme has.");
    }
    if (key === "admission_route" && !ROUTES.includes(raw as AdmissionRoute)) throw bad("Choose an admission route.");
    if (key === "category" && !CATEGORIES.includes(String(raw))) throw bad("Choose a category.");
    if ((key === "tfw_income_certified" || key === "nri_sponsored" || key === "ciwg") && raw !== true && raw !== false && raw !== null) throw bad("Choose yes, no or not reported.");
    const before = currentOf(e, key);
    const same = typeof value === "string" && typeof before === "string" ? value.trim().toLowerCase() === before.trim().toLowerCase() : (value ?? null) === (before ?? null);
    if (!same) changes.push({ field, before: before ?? null, after: typeof value === "string" ? value.trim() : value });
  }
  return changes;
}

function cohortOf(year: number): string {
  const start = Number(ACADEMIC_YEAR.slice(0, 4)) - (year - 1);
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

/** A free seat of the pool in the record's programme, if the ledger has one. */
function freeSeat(e: RollEntry, pool: SeatType): SeatRow | undefined {
  return seatsFor(e.institutionId).find((s) => s.programme_code === e.row.programme_code && s.seat_type === pool && s.status === "FREE");
}

/** An unseated active record of the same programme and pool, first come first served: the backlog a released seat goes to. */
function backlogFor(e: RollEntry, pool: SeatType): RollEntry | undefined {
  return rollFor(e.institutionId)
    .filter((x) => x !== e && x.row.status === "ACTIVE" && !x.seat && x.programme.id === e.programme.id && x.row.cohort_year === e.row.cohort_year && x.seatType === pool)
    .sort((a, b) => a.row.admission_date.localeCompare(b.row.admission_date) || a.row.student.name.localeCompare(b.row.student.name))[0];
}

function shortIdOf(e: RollEntry): string {
  return hex(`short:${e.row.id}`, 8).toUpperCase();
}

function seatOf(row: SeatRow, at: string): RollEntry["seat"] {
  return { id: row.id, seat_code: row.seat_code, seat_type: row.seat_type, academic_year: row.academic_year, assigned_at: at };
}

function addVersion(e: RollEntry, at: string, actor: ActorRef, f: StoredFlag, action: DecisionAction, seq: number, reason: ReasonCode, changes: FieldChange[]): number {
  const version = versionsOf(e).length + 1;
  const list = LATER_VERSIONS.get(e.row.id) ?? [];
  list.push({ version, at, source: "DECISION", actor, batch: null, case: { id: f.id, type: f.type, action, case_action_seq: seq, reason_code: reason }, changes });
  LATER_VERSIONS.set(e.row.id, list);
  return version;
}

interface Snapshot {
  status: string | null;
  record: RecordStatus | null;
}

function snap(e: RollEntry): Snapshot {
  const r = withRecord(e);
  return { status: e.row.status, record: r.record_status };
}

/**
 * Works out every consequence of a decision and, unless `dryRun`, applies
 * it: one step for the case, its records, their seats and attestations, the
 * versions and the audit (A4.10). A dry run touches nothing.
 */
function decide(user: User, f: StoredFlag, req: Partial<CaseActionRequest>, to: FlagStatus, dryRun: boolean): DecisionEffects {
  const at = nowIso();
  const actor = actorOf(user);
  const action = req.action as DecisionAction;
  const reason = req.reason_code as ReasonCode;
  const seq = dryRun ? SEQ + 1 : ++SEQ;
  const effects: DecisionEffects = {
    case_status: to,
    records: [],
    version: null,
    changes: [],
    rows_resolved: 0,
    rows_rerun: 0,
    seats_released: [],
    seats_assigned: [],
    attestations_revoked: [],
    attestations_issued: [],
    approval: null,
  };
  const before = new Map<string, Snapshot>();
  const remember = (e: RollEntry) => {
    if (!before.has(e.row.id)) before.set(e.row.id, snap(e));
  };

  if (action === "WITHDRAW") {
    const named = namedOf(f);
    const scope = scopeOf(f);
    const ids = req.withdrawn_enrolment_ids ?? (scope === "RECORD" && named[0] ? [named[0].row.id] : []);
    if (scope === "MULTI_RECORD" && ids.length === 0) throw new ApiError(422, "WITHDRAW_NONE_SELECTED", "Select at least one record to withdraw.");
    const outstanding = scope === "MULTI_RECORD" ? outstandingOf(f) : named.filter((e) => e.row.status === "ACTIVE").map((e) => e.row.id);
    const notNamed = ids.filter((id) => !outstanding.includes(id));
    if (notNamed.length > 0) {
      throw new ApiError(409, "WITHDRAW_NOT_NAMED", `${notNamed.length} of the selected records are not named by this case.`, { n: notNamed.length, named_enrolment_ids: outstanding });
    }
    const entries = ids.map((id) => entryById(id)!);
    for (const e of entries) {
      remember(e);
      effects.records.push({ enrolment_id: e.row.id, status: "WITHDRAWN", record_status: null, status_reason: null });
      if (e.seat) {
        effects.seats_released.push({ enrolment_id: e.row.id, seat_code: e.seat.seat_code });
        const heir = backlogFor(e, e.seat.seat_type);
        if (heir && !entries.includes(heir)) effects.seats_assigned.push({ enrolment_id: heir.row.id, seat_code: e.seat.seat_code });
      }
      for (const c of credentialsFor(e)) if (c.status === "ACTIVE") effects.attestations_revoked.push({ enrolment_id: e.row.id, credential_id: c.id, short_id: c.short_id });
    }
    effects.version = entries[0] ? versionsOf(entries[0]).length + 1 : null;
    if (scope === "MULTI_RECORD" && outstanding.some((id) => !ids.includes(id))) effects.case_status = f.status;
    if (dryRun) return effects;
    const today = todayIst();
    for (const e of entries) {
      const released = e.seat;
      const statusBefore = e.row.status;
      const dateBefore = e.row.status_date;
      e.row.status = "WITHDRAWN";
      e.row.status_date = today;
      e.seat = null;
      e.row.seat_code = null;
      if (effects.attestations_revoked.some((x) => x.enrolment_id === e.row.id)) REVOKED.set(e.row.id, at);
      addVersion(e, at, actor, f, "WITHDRAW", seq, reason, [
        { field: "status", before: statusBefore, after: "WITHDRAWN" },
        { field: "status_date", before: dateBefore, after: today },
      ]);
      caseOf(f.id).done.push(e.row.id);
      if (released) {
        const heir = effects.seats_assigned.find((s) => s.seat_code === released.seat_code);
        const h = heir ? entryById(heir.enrolment_id) : undefined;
        if (h) {
          remember(h);
          h.seat = { ...released, assigned_at: at };
          h.row.seat_code = released.seat_code;
          evaluate(h);
          syncEntry(h);
        }
      }
      appendAudit(user, "UPDATE", "enrolment", e.row.id);
    }
  }

  if (action === "CORRECT") {
    const named = namedOf(f);
    const scope = scopeOf(f);
    const target = req.correction?.enrolment_id ?? (scope === "RECORD" ? named[0]?.row.id : undefined);
    const outstanding = scope === "MULTI_RECORD" ? outstandingOf(f) : named.filter((e) => e.row.status === "ACTIVE").map((e) => e.row.id);
    if (!target || !outstanding.includes(target)) {
      throw new ApiError(409, "WITHDRAW_NOT_NAMED", "1 of the selected records are not named by this case.", { n: 1, named_enrolment_ids: outstanding });
    }
    const e = entryById(target)!;
    const changes = correctionOf(e, (req.correction?.fields ?? {}) as Record<string, unknown>);
    if (changes.length === 0) throw new ApiError(422, "CORRECTION_EMPTY", "Change at least one field, or choose another decision.");
    remember(e);
    effects.changes = changes;
    effects.version = versionsOf(e).length + 1;
    effects.rows_rerun = 5;
    const route = (changes.find((c) => c.field === "admission_route")?.after as AdmissionRoute | undefined) ?? e.row.admission_route;
    const pool = POOL_OF[route];
    if (pool !== e.seatType || changes.some((c) => c.field === "year_of_study")) {
      if (e.seat) effects.seats_released.push({ enrolment_id: e.row.id, seat_code: e.seat.seat_code });
      const seat = freeSeat(e, pool);
      if (seat) effects.seats_assigned.push({ enrolment_id: e.row.id, seat_code: seat.seat_code });
    }
    if (scope === "MULTI_RECORD" && outstanding.some((id) => id !== target)) effects.case_status = f.status;
    effects.records.push({ enrolment_id: e.row.id, status: "ACTIVE", record_status: before.get(e.row.id)!.record, status_reason: e.row.status_reason });
    if (dryRun) return effects;
    for (const c of changes) {
      const v = c.after;
      if (c.field === "name") e.row.student.name = String(v);
      else if (c.field === "dob") e.dob = String(v);
      else if (c.field === "tfw_income_certified" || c.field === "nri_sponsored" || c.field === "ciwg") e.row.eligibility = { ...e.row.eligibility, [c.field]: v as boolean | null };
      else if (c.field === "year_of_study") {
        e.row.year_of_study = Number(v);
        e.row.cohort_year = cohortOf(Number(v));
      } else (e.row as unknown as Record<string, unknown>)[c.field] = v;
    }
    if (changes.some((c) => c.field === "name" || c.field === "dob") && e.special.identity === "NAME") e.special = { ...e.special, identity: undefined };
    e.seatType = pool;
    if (effects.seats_released.length || effects.seats_assigned.length) {
      const seat = effects.seats_assigned[0] ? freeSeat(e, pool) : undefined;
      e.seat = seat ? seatOf(seat, at) : null;
      e.row.seat_code = e.seat?.seat_code ?? null;
    }
    addVersion(e, at, actor, f, "CORRECT", seq, reason, changes);
    if (scope === "MULTI_RECORD") caseOf(f.id).done.push(e.row.id);
    evaluate(e);
    syncEntry(e);
    appendAudit(user, "UPDATE", "enrolment", e.row.id);
  }

  if (action === "UPHOLD") {
    const seatCase = f.type === "EXCESS_ADMISSION" || f.type === "QUOTA_BREACH";
    if (seatCase) {
      const p = f.programmeId ? programmesFor(f.institutionId).find((x) => x.id === f.programmeId) : undefined;
      const covers = p ? p.unseated === 0 : false;
      if (!p || !covers || req.approval_version !== p.approval.version) {
        throw new ApiError(409, "UPHOLD_NEEDS_VERSION", "This case can be upheld only when an approval version covers these admissions.", { current_version: p?.approval.version ?? null, covers: false });
      }
      effects.approval = { version: p.approval.version, approved_intake: p.approval.approved_intake, cohort_year: p.approval.academic_year, programme_code: p.code };
    }
    const covers = COVERS[f.type];
    const touched: RollEntry[] = [];
    for (const e of namedOf(f)) {
      if (e.row.status !== "ACTIVE") continue;
      remember(e);
      touched.push(e);
      if (covers && coveredOpen(f, e)) effects.rows_resolved += 1;
    }
    if (dryRun) {
      // What the records would read: the covered rows resolved and this case decided.
      const was = f.status;
      const open = new Set(touched.filter((e) => coveredOpen(f, e)).map((e) => e.row.id));
      f.status = to;
      for (const e of touched) {
        const rows = e.checks.map((r) => (r.type === covers && open.has(e.row.id) ? { ...r, resolved: { outcome: "UPHELD" as const, case_id: f.id, case_action_seq: seq, reason_code: reason as UpholdReason, at, by: actor, line: "" } } : r));
        const rec = recordFor(e, rows);
        const prior = before.get(e.row.id)!;
        if (rec.record_status !== prior.record) {
          effects.records.push({ enrolment_id: e.row.id, status: "ACTIVE", record_status: rec.record_status, status_reason: rec.status_reason });
          if (rec.record_status === "COUNTERSIGNED") effects.attestations_issued.push({ enrolment_id: e.row.id, credential_id: uuid(`credential:${e.row.id}`), short_id: shortIdOf(e) });
        }
      }
      f.status = was;
      return effects;
    }
    for (const e of touched) {
      if (!covers || !coveredOpen(f, e)) continue;
      RESOLVED.set(`${e.row.id}:${covers}`, {
        outcome: "UPHELD",
        case_id: f.id,
        case_action_seq: seq,
        reason_code: reason as UpholdReason,
        at,
        by: actor,
        line: `Claim upheld by an officer on ${sentenceDate(at)}`,
        caseId: f.id,
      });
      setRows(e, withResolutions(e, e.checks));
      appendAudit(user, "UPDATE", "check", e.row.id);
    }
  }
  return effects;
}

interface Prior {
  status: string;
  record: RecordStatus | null;
  next: string | null;
}

function priorOf(entries: RollEntry[]): Map<string, Prior> {
  return new Map(entries.map((e) => [e.row.id, { status: e.row.status, record: withRecord(e).record_status, next: e.row.next_step }]));
}

/**
 * After a real action: every record whose status, record status or next
 * step changed (A4.9 `records`), and the attestations a record that became
 * Countersigned now holds (A4.14).
 */
function settleRecords(effects: DecisionEffects, prior: Map<string, Prior>) {
  const ids = new Set([...prior.keys(), ...effects.records.map((r) => r.enrolment_id), ...effects.seats_assigned.map((s) => s.enrolment_id)]);
  const out: DecisionEffects["records"] = [];
  for (const id of ids) {
    const e = entryById(id);
    if (!e) continue;
    const rec = withRecord(e);
    const was = prior.get(id);
    if (was && was.status === e.row.status && was.record === rec.record_status && was.next === e.row.next_step) continue;
    out.push({ enrolment_id: id, status: e.row.status, record_status: rec.record_status, status_reason: rec.status_reason });
    if (rec.record_status === "COUNTERSIGNED" && was?.record !== "COUNTERSIGNED") {
      const issued = credentialsFor(e).find((c) => c.status === "ACTIVE");
      if (issued && !effects.attestations_issued.some((x) => x.enrolment_id === id)) effects.attestations_issued.push({ enrolment_id: id, credential_id: issued.id, short_id: issued.short_id });
    }
  }
  effects.records = out;
}

async function act(user: User, id: string, body: unknown, next: Next): Promise<CaseActionResult | DryRunResult> {
  requireRole(user, OFFICERS);
  const req = (body ?? {}) as Partial<CaseActionRequest>;
  if (!req.action || !ORDER.includes(req.action)) throw invalid("action", "Choose an action.");
  await next("GET", `/flags/${id}`);
  const f = flagById(id)!;
  const rule = TABLE[f.status][req.action];
  if (!rule) {
    throw new ApiError(409, "FLAG_TRANSITION_INVALID", `This action is not possible while the case is ${STATUS_WORD[f.status]}.`, {
      status: f.status,
      action: req.action,
      allowed_actions: allowedActions(user, f),
    });
  }
  if (!rule.roles.includes(user.role)) throw forbidden(rule.roles);
  if (!decisionApplies(f, req.action)) {
    throw new ApiError(409, "DECISION_NOT_AVAILABLE", `This decision does not apply to a ${f.type} case.`, { action: req.action, type: f.type, allowed_actions: allowedActions(user, f) });
  }

  const note = (req.note ?? "").trim();
  const decision = req.action === "UPHOLD" || req.action === "CORRECT" || req.action === "WITHDRAW" || req.action === "ESCALATE";
  if (decision && (!req.reason_code || !note)) {
    const fields = [...(!req.reason_code ? [{ field: "reason_code", message: "Choose a reason." }] : []), ...(!note ? [{ field: "note", message: "Add a note before you continue." }] : [])];
    throw new ApiError(422, "REASON_REQUIRED", "Choose a reason and write a note before you decide.", { fields });
  }
  if (decision && !REASONS[req.action]!.includes(req.reason_code!)) throw invalid("reason_code", "This reason does not fit this decision.");
  if (req.action !== "ASSIGN") {
    if (!note) throw invalid("note", "Add a note before you continue.");
    if (note.length > 2000) throw invalid("note", "Keep the note to 2,000 characters.");
  }
  let due: string | null = null;
  if (req.action === "REQUEST_DOCS") {
    if (!req.docs_kind || !DOCS_KINDS.includes(req.docs_kind)) throw invalid("docs_kind", "Choose what the college should send.");
    if (req.due_date) {
      if (req.due_date < todayIst()) throw invalid("due_date", "Choose today or a later date.");
      if (req.due_date > plusDays(todayIst(), 90)) throw invalid("due_date", "Choose a date within 90 days of today.");
      due = req.due_date;
    }
  }
  let assignee: { id: string; name: string } | null | undefined;
  if (req.action === "ASSIGN") {
    if (!("assignee_id" in req)) throw invalid("assignee_id", "Choose an officer who can see this case.");
    assignee = req.assignee_id ? officerFor(f, req.assignee_id) : null;
  }
  if (req.action === "ESCALATE" && req.assignee_id) {
    const o = DIRECTORY.find((x) => x.id === req.assignee_id);
    if (!o || o.role !== A) throw invalid("assignee_id", "Escalate to an AICTE officer.");
    assignee = { id: o.id, name: o.name };
  }

  const from = f.status;
  const to = rule.to === "=" ? from : rule.to;
  const empty: DecisionEffects = {
    case_status: to, records: [], version: null, changes: [], rows_resolved: 0, rows_rerun: 0,
    seats_released: [], seats_assigned: [], attestations_revoked: [], attestations_issued: [], approval: null,
  };
  const isDecision = req.action === "UPHOLD" || req.action === "CORRECT" || req.action === "WITHDRAW";
  if (req.dry_run) {
    await wait(260);
    return { dry_run: true, effects: isDecision ? decide(user, f, req, to, true) : empty };
  }

  const at = nowIso();
  const c = caseOf(id);
  const named = namedOf(f);
  const prior = priorOf(named);
  const effects = isDecision ? decide(user, f, req, to, false) : empty;
  f.status = effects.case_status;
  f.updated_at = at;
  if (req.action === "REQUEST_DOCS") {
    c.docsDueOn = due;
    c.responseReceived = false;
    f.progress.docs = { kind: req.docs_kind ?? "OTHER", due_on: due, responded_at: null };
  }
  if (req.action === "REOPEN") {
    c.docsDueOn = null;
    c.responseReceived = false;
    f.progress = { docs: null, escalated_at: null };
    for (const [key, r] of RESOLVED) if (r.caseId === f.id) RESOLVED.delete(key);
    for (const e of named) setRows(e, withResolutions(e, e.checks));
  }
  if ((req.action === "ASSIGN" || req.action === "ESCALATE") && assignee !== undefined) c.assignee = assignee;
  if (req.action === "ESCALATE") f.progress.escalated_at = at;
  const correction = req.action === "CORRECT" ? { enrolment_id: req.correction?.enrolment_id ?? named[0]?.row.id ?? "", changes: effects.changes } : null;
  c.history.push({
    ...EXTRA(),
    seq: isDecision ? SEQ : ++SEQ,
    at,
    action: req.action,
    from_status: from,
    to_status: f.status,
    actor: actorOf(user),
    note: req.action === "ASSIGN" ? null : note,
    due_date: req.action === "REQUEST_DOCS" ? due : null,
    assignee: req.action === "ASSIGN" || req.action === "ESCALATE" ? (assignee ?? null) : null,
    attachments: [],
    reason_code: decision ? (req.reason_code ?? null) : null,
    docs_kind: req.action === "REQUEST_DOCS" ? (req.docs_kind ?? "OTHER") : null,
    approval_version: req.action === "UPHOLD" && effects.approval ? effects.approval.version : null,
    correction,
    withdrawn_enrolment_ids: req.action === "WITHDRAW" ? effects.records.filter((r) => r.status === "WITHDRAWN").map((r) => r.enrolment_id) : [],
  });
  c.lastActionAt = at;
  settleRecords(effects, prior);
  appendAudit(user, "UPDATE", "flag", id);
  const detail = await flagDetail(user, id, next);
  return { ...detail, effects };
}

/* ---- Cases opened from signals (A4.19) ----------------------------------- */

const SIGNAL_SEVERITY: Record<StoredSignal["type"], Severity> = { GHOST_RING: "HIGH", ANOMALY: "MEDIUM" };

/** One case per college, citing the signal; a case that already exists for that signal and college is returned as it is. */
function caseFromSignal(user: User | null, sig: StoredSignal, institutionId: string, note: string, severity: Severity, at: string): StoredFlag {
  const id = uuid(`signal-case:${sig.id}:${institutionId}`);
  const existing = flagById(id);
  if (existing) return existing;
  const members = sig.type === "GHOST_RING" ? membersOf(sig, institutionId) : [];
  const ringFacts: StoredFact[] = [
    { label: "Students at this college", value: String(members.length), source: "Countersign signals" },
    ...sig.shared.map((x) => ({ label: x.kind === "MOBILE" ? "Shared mobile number" : x.kind === "EMAIL" ? "Shared email address" : "Shared address", value: `${x.masked} (${x.students} students)`, source: "College uploads, contact hashes" })),
    { label: "Signal", value: `Shared contact ring found on ${formatDate(sig.created_at)}`, source: "Countersign signals", audience: "OFFICER" as const },
  ];
  const f: StoredFlag = {
    id,
    type: sig.type,
    severity,
    status: "OPEN",
    institutionId,
    programmeId: null,
    enrolmentId: null,
    academic_year: sig.academic_year,
    summary:
      sig.type === "GHOST_RING"
        ? `${sig.memberIds.length} students across ${sig.institutionIds.length} institutions share ${sig.shared.length} contact details.`
        : `${institutionName(institutionId)} stands out from similar colleges on ${sig.features.filter((x) => x.stands_out).length === 1 ? "one measure" : "several measures"} (${sig.academic_year}).`,
    facts: sig.type === "GHOST_RING" ? ringFacts : featureFacts(sig),
    related: members,
    rule_source: ruleOf(sig).replace(/^(Rule|Model): /, ""),
    created_at: at,
    updated_at: at,
    progress: { docs: null, escalated_at: null },
  };
  allFlags().push(f);
  SIGNAL_OF.set(f.id, sig.id);
  const c = caseOf(f.id);
  c.history.push({ ...EXTRA(), seq: ++SEQ, at, action: "NOTE", from_status: "OPEN", to_status: "OPEN", actor: user ? actorOf(user) : null, note, due_date: null, assignee: null, attachments: [] });
  c.lastActionAt = at;
  sig.caseIds.push({ id: f.id, institution_id: institutionId });
  if (user) appendAudit(user, "CREATE", "flag", f.id);
  return f;
}

async function openSignalCase(user: User, id: string, body: unknown, next: Next): Promise<SignalOpenCaseResult> {
  const sig = signalInScope(user, id);
  const req = (body ?? {}) as { institution_ids?: string[]; note?: string; severity?: Severity };
  const note = (req.note ?? "").trim();
  if (!note) throw invalid("note", "Add a note before you continue.");
  if (note.length > 2000) throw invalid("note", "Keep the note to 2,000 characters.");
  if (sig.status === "DISMISSED") throw new ApiError(409, "SIGNAL_ALREADY_HANDLED", "This signal already has a case or was dismissed.", { status: sig.status });
  const inScope = sig.institutionIds.filter((i) => user.role === A || REGION_OF(i) === user.scope.region);
  const chosen = req.institution_ids && req.institution_ids.length > 0 ? req.institution_ids : sig.institutionIds.length === 1 ? sig.institutionIds : [];
  if (chosen.length === 0) throw invalid("institution_ids", "Choose at least one college.");
  if (chosen.some((i) => !inScope.includes(i))) throw invalid("institution_ids", "Choose colleges this signal names in your region.");
  const severity = req.severity ?? SIGNAL_SEVERITY[sig.type];
  const at = nowIso();
  const flags = chosen.map((i) => caseFromSignal(user, sig, i, note, severity, at));
  if (sig.status === "NEW") {
    sig.status = "CASE_OPENED";
    sig.note = note;
    sig.decidedBy = { id: user.id, name: user.name };
    sig.decidedAt = at;
  }
  sig.updated_at = at;
  appendAudit(user, "UPDATE", "signal", sig.id);
  const cases = await Promise.all(flags.map(async (f) => decorateRow(user, (await next("GET", `/flags/${f.id}`)) as FlagDetail)));
  return { cases, signal: signalDetail(user, sig) };
}

function dismiss(user: User, id: string, body: unknown): SignalDetail {
  const sig = signalInScope(user, id);
  const note = String((body as { note?: string } | undefined)?.note ?? "").trim();
  if (!note) throw invalid("note", "Say why you are dismissing this signal.");
  if (note.length > 2000) throw invalid("note", "Keep the note to 2,000 characters.");
  dismissSignal(user, sig, note, nowIso());
  appendAudit(user, "UPDATE", "signal", sig.id);
  return signalDetail(user, sig);
}

/** The anomaly at Lucknow already has its case, so every state of the signal pages can be seen. */
function seedSignalCases() {
  const sig = allSignals().find((x) => x.id === "5a000004-0004-4a00-8a00-000000000004");
  if (!sig || sig.caseIds.length > 0) return;
  const admin = USERS.find((u) => u.email === "admin@aicte.demo")!;
  const at = "2026-10-28T07:05:00Z";
  caseFromSignal(admin, sig, sig.institutionIds[0], "Admissions grew by nearly half while contradictions rose. Ask the college for its admission register.", "MEDIUM", at);
  sig.status = "CASE_OPENED";
  sig.note = "Admissions grew by nearly half while contradictions rose. Ask the college for its admission register.";
  sig.decidedBy = { id: admin.id, name: admin.name };
  sig.decidedAt = at;
  sig.updated_at = at;
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
    throw new ApiError(409, "FLAG_TRANSITION_INVALID", `This action is not possible while the case is ${STATUS_WORD[f.status]}.`, {
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
  if (f.progress.docs) f.progress.docs.responded_at = at;
  c.history.push({
    ...EXTRA(),
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
  const replied = sentenceDate(denied.responded_at);
  const via = "Student sign-in via DigiLocker";
  const facts: StoredFact[] = [
    { label: "Signed in with", value: "DigiLocker", source: via },
    { label: "Notice sent", value: sentDate, source: "Countersign" },
    { label: "Answered on", value: formatDate(denied.responded_at), source: via },
    ...(changed ? [{ label: "Answer changed", value: `Yes on ${formatDate(denied.changed_at)}`, source: via }] : []),
    { label: "Comment from the student", value: comment ?? "None", source: via, audience: "OFFICER" as const },
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
      ? `The student said they never joined on ${replied}, then changed the answer to Yes on ${sentenceDate(denied.changed_at)}.`
      : `The student said they never joined, after signing in with DigiLocker on ${replied}.`,
    facts,
    related: [e.row.id],
    rule_source: "Student's answer after DigiLocker sign-in",
    created_at: denied.responded_at!,
    updated_at: denied.changed_at ?? denied.responded_at!,
    progress: { docs: null, escalated_at: null },
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
        ...EXTRA(),
        seq: 59,
        at: email.changed_at,
        action: "SYSTEM_NOTE",
        from_status: "OPEN",
        to_status: "OPEN",
        actor: null,
        note: `The student changed the answer from No to Yes on ${formatDate(email.changed_at)}. The case keeps its status until an officer decides.`,
        due_date: null,
        assignee: null,
        attachments: [],
      });
      c.lastActionAt = email.changed_at;
    }
  });
}

/**
 * The deck's sample card (A4.25 sample_card): Ananya Deshmukh at ABC College,
 * B.Tech CSE 2026. Her joining record is not found, she answered No after
 * DigiLocker sign-in, and the officer asked the college for admission
 * documents: the record reads Disputed (priority).
 */
function seedSampleCard() {
  const e = entryByName(IDS.abc, "Ananya Deshmukh");
  const file: NoticeFile = { notices: [], hasEmail: true, noDigiLocker: false, resendsUsed: 0, consentWithdrawnAt: null };
  const email = notice(e, "EMAIL", "first", SENT_AT, EXPIRES_AT);
  const digi = notice(e, "DIGILOCKER", "first", SENT_AT, EXPIRES_AT);
  digi.response = "NO";
  digi.responded_at = "2026-10-28T05:40:00Z";
  file.notices.push(email, digi);
  NOTICES.set(e.row.id, file);
  const f = deniedFlag(30, e, file, "I never joined this college.");
  allFlags().push(f);
  const west = byEmail("ro.west@aicte.demo");
  const asked = "2026-10-28T07:15:00Z";
  f.status = "DOCS_REQUESTED";
  f.updated_at = asked;
  f.progress.docs = { kind: "ADMISSION", due_on: "2026-11-05", responded_at: null };
  const c = caseOf(f.id);
  c.history.push({
    ...EXTRA(),
    seq: 58,
    at: asked,
    action: "REQUEST_DOCS",
    from_status: "OPEN",
    to_status: "DOCS_REQUESTED",
    actor: west,
    note: "Send the admission form, the fee receipt and the joining report for Ananya Deshmukh.",
    due_date: "2026-11-05",
    assignee: null,
    attachments: [],
    docs_kind: "ADMISSION",
  });
  c.docsDueOn = "2026-11-05";
  c.lastActionAt = asked;
}

/** Case work already done on the seeded flags, so every state of the action bar can be seen. */
function seedCases() {
  const admin = byEmail("admin@aicte.demo");
  const west = byEmail("ro.west@aicte.demo");
  const south = byEmail("ro.south@aicte.demo");
  const abc = byEmail("registrar@abc.edu.demo");
  const puneRegistrar: ActorRef = { id: "6f1c0a8e-0021-4c9a-9e51-1c2f1a0b7d33", name: "Registrar, Pune Institute of Technology and Management", role: "INSTITUTION" };
  const id = (n: number) => (n === 1 ? "f1f1f1f1-7777-4888-8999-000011112222" : `f${String(n).padStart(7, "0")}-7777-4888-8999-000011112222`);
  const item = (seq: number, at: string, action: CaseHistoryItem["action"], from: FlagStatus, to: FlagStatus, actor: ActorRef | null, note: string | null, extra: Partial<CaseHistoryItem> = {}): CaseHistoryItem => ({
    ...EXTRA(),
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
    for (const h of history) {
      if (h.action === "REQUEST_DOCS") f.progress.docs = { kind: h.docs_kind ?? "OTHER", due_on: h.due_date, responded_at: null };
      if (h.action === "COLLEGE_RESPONSE" && f.progress.docs) f.progress.docs.responded_at = h.at;
      if (h.action === "ESCALATE") f.progress.escalated_at = h.at;
    }
    c.lastActionAt = history[history.length - 1]?.at ?? null;
    Object.assign(c, patch);
  };

  // ABC, Rahul Pawar: documents requested by AICTE, the reply date has passed.
  apply(3, "DOCS_REQUESTED", [item(36, "2026-10-27T10:02:00Z", "REQUEST_DOCS", "OPEN", "DOCS_REQUESTED", admin, "Send the APAAR card or the DigiLocker APAAR record for Rahul Pawar.", { due_date: "2026-10-27", docs_kind: "IDENTITY" })], {
    docsDueOn: "2026-10-27",
  });

  // ABC, Mohd. Faizan Shaikh: documents requested by the regional officer, the college responded.
  const form = storeSample(id(4), "admission_form.pdf", "application/pdf", 421_888);
  const idCopy = storeSample(id(4), "id_copy.png", "image/png", 186_112);
  apply(
    4,
    "DOCS_REQUESTED",
    [
      item(41, "2026-10-27T10:35:00Z", "REQUEST_DOCS", "OPEN", "DOCS_REQUESTED", west, "Send the admission form and an ID copy for Mohd. Faizan Shaikh.", { due_date: "2026-11-04", docs_kind: "IDENTITY" }),
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
    "WITHDRAWN",
    [
      item(47, "2026-10-26T16:10:00Z", "REQUEST_DOCS", "OPEN", "DOCS_REQUESTED", west, "Send the NRI admission register for CSE, 2026-27, and any supernumerary approval.", { due_date: "2026-10-28", docs_kind: "ADMISSION" }),
      item(49, "2026-10-27T07:25:00Z", "COLLEGE_RESPONSE", "DOCS_REQUESTED", "DOCS_REQUESTED", puneRegistrar, "Register attached. We have no supernumerary approval for NRI seats this year.", {
        attachments: [storeSample(id(11), "nri_register_cse_2026-27.pdf", "application/pdf", 1_887_436)],
      }),
      item(55, "2026-10-27T13:45:00Z", "WITHDRAW", "DOCS_REQUESTED", "WITHDRAWN", admin, "Three NRI admissions beyond the 5% carve-out with no supernumerary approval. Their claims do not stand.", {
        reason_code: "BEYOND_APPROVED_INTAKE",
        withdrawn_enrolment_ids: flagById(id(11))?.related ?? [],
      }),
    ],
    { docsDueOn: "2026-10-28", responseReceived: true },
  );
  // The withdrawal took effect: each named record is withdrawn by decision, with its version (A4.10).
  const quota = flagById(id(11));
  if (quota) {
    for (const rid of quota.related) {
      const e = entryById(rid);
      if (!e || e.row.status !== "ACTIVE") continue;
      const dateBefore = e.row.status_date;
      e.row.status = "WITHDRAWN";
      e.row.status_date = "2026-10-27";
      addVersion(e, "2026-10-27T13:45:00Z", admin, quota, "WITHDRAW", 55, "BEYOND_APPROVED_INTAKE", [
        { field: "status", before: "ACTIVE", after: "WITHDRAWN" },
        { field: "status_date", before: dateBefore, after: "2026-10-27" },
      ]);
      caseOf(quota.id).done.push(rid);
    }
  }

  // GCE Karad, late refill: cleared, then the engines refreshed the evidence.
  apply(12, "UPHELD", [
    item(52, "2026-10-28T09:05:00Z", "UPHOLD", "OPEN", "UPHELD", west, "The seat was released on 28 Sep and refilled on 5 Oct with the state counselling authority's written approval, which is on file.", {
      reason_code: "DOCUMENTS_SUPPORT_CLAIM",
    }),
    item(57, "2026-10-28T09:40:00Z", "SYSTEM_NOTE", "UPHELD", "UPHELD", null, "Evidence updated after the decision."),
  ]);
}

let seeded = false;

function ensureSeeded() {
  if (seeded) return;
  seeded = true;
  for (const s of SEEDS) rollFor(s.id);
  seedAudit();
  seedDenials();
  seedSampleCard();
  seedCases();
  seedRequests();
  seedSignalCases();
  for (const s of SEEDS) syncInstitution(s.id);
}

/* ---- Router ---------------------------------------------------------------- */

/**
 * Answers the officer routes above, decorates flag and enrolment reads, and
 * hands everything else to `next` (the base handler).
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
        result.checks = e.row.checks;
        result.record_status = withRecord(e).record_status;
      }
      return result;
    }
  }

  if (parts[0] === "institutions" && parts[2] === "recheck" && method === "POST") {
    const result = await next(method, path, query, body);
    syncInstitution(parts[1]);
    return result;
  }

  if (pathname === "/dashboard/summary" && method === "GET") {
    // Officers see how many signals are new (A4.20); everyone else gets null.
    const summary = (await next(method, path, query, body)) as { kpis: { signals_new: number | null } };
    const user = signedIn();
    if (OFFICERS.includes(user.role)) summary.kpis.signals_new = listSignals(user, { status: "NEW", page_size: 200 }).total;
    return summary;
  }

  if (pathname === "/reports" && method === "GET") {
    await latency();
    return listReports(signedIn());
  }

  if (parts[0] === "signals") {
    await latency();
    if (parts.length === 1 && method === "GET") return listSignals(signedIn(), query);
    if (parts.length === 2 && method === "GET") {
      const user = signedIn();
      const detail = signalDetail(user, signalInScope(user, parts[1]));
      for (const m of detail.members) appendAudit(user, "READ", "student", m.student.id);
      return detail;
    }
    if (parts.length === 3 && parts[2] === "open-case" && method === "POST") return openSignalCase(signedIn(), parts[1], body, next);
    if (parts.length === 3 && parts[2] === "dismiss" && method === "POST") return dismiss(signedIn(), parts[1], body);
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
