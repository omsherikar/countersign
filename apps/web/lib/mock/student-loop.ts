/**
 * Mock routes for the student notice, wallet, privacy, verifier and
 * university degree pages (API_CONTRACT A3.3 to A3.6 and A3.15 to A3.22).
 * State lives in sessionStorage, so answering a notice, then opening the
 * wallet, sharing a proof and checking its code all work in one tab, as the
 * demo path does against the api.
 *
 * Notice links to try (no sign-in needed):
 *   /student/notices/demo-ravi              Ravi's email notice, unanswered
 *   /student/notices/demo-ravi-digilocker   the same claim by DigiLocker
 *   /student/notices/demo-answered          answered Yes, change still open
 *   /student/notices/demo-changed           answer already changed once
 *   /student/notices/demo-closed            answered No, change window over
 *   /student/notices/demo-provisional       unanswered, provisional id
 *   /student/notices/demo-expired           410 NOTICE_EXPIRED
 *   /student/notices/demo-busy              429 RATE_LIMITED
 *   anything else                           404 NOTICE_NOT_FOUND
 * Verifier codes: a code created in the wallet, or
 *   K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF valid, R7VK-... revoked, E7XP-... expired,
 *   N7VD-... not valid, R4TE-... rate limited (same last five groups).
 * The QR images are drawn patterns, not scannable codes.
 */
import { ApiError, type Query } from "@/lib/api";
import { t } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { ACADEMIC_YEAR, IDS, INSTITUTIONS } from "@/lib/mock/fixtures";
import { studentMe } from "@/lib/mock/roll";
import { readBrowserToken, userFromToken } from "@/lib/mock/session";
import type {
  AccessLogRow,
  AccessedWhat,
  AccessorRole,
  ClaimKey,
  ConsentCurrent,
  ConsentPurpose,
  ConsentRow,
  CredentialCard,
  CredentialClaim,
  CredentialStatus,
  DataRequestCreate,
  DataRequestRow,
  DegreePrint,
  DisclosableField,
  DisclosedField,
  GraduateRow,
  IdKind,
  MyDataExport,
  NoticeChannel,
  NoticePublic,
  NoticeResponse,
  NoticeState,
  Page,
  PresentationCreated,
  PrivacyNotice,
  Role,
  StudentMe,
  StudentNotice,
  User,
  VerifyResult,
} from "@/lib/types";

export const UNHANDLED = Symbol("unhandled");

const STORE_KEY = "cs_mock_student_loop_v1";
const DAY = 86_400_000;
const MIN = 60_000;
const ISSUER = { name: "Countersign", url: "http://localhost:8000" };
const RAVI_ENROLMENT = "e0000000-0000-4666-8777-888899990000";
const ABC = INSTITUTIONS.find((i) => i.id === IDS.abc)!;
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

/* ---- Stored shapes ------------------------------------------------------- */

interface StoredNotice {
  token: string;
  id: string;
  enrolment_id: string;
  ravi: boolean;
  channel: NoticeChannel;
  institution_name: string;
  programme_code: string;
  programme_name: string;
  academic_year: string;
  year_of_study: number;
  id_kind: IdKind;
  id_masked: string;
  uploaded_at: string;
  sent_at: string;
  expires_at: string;
  response: NoticeResponse | null;
  responded_at: string | null;
  previous_response: NoticeResponse | null;
  changed_at: string | null;
  comment: string | null;
}

interface StoredCredential extends Omit<CredentialCard, "status" | "presentations" | "shares" | "last_verified_at"> {
  revoked: boolean;
  student: "ravi" | "graduate";
  claims: CredentialClaim[];
}

interface StoredPresentation {
  id: string;
  credential_id: string;
  code: string;
  created_at: string;
  expires_at: string;
  disclosed: ClaimKey[];
  verify_count: number;
  first_verified_at: string | null;
  last_verified_at: string | null;
}

interface StoredGraduate {
  row: Omit<GraduateRow, "degree">;
  universityId: string;
  credentialId: string | null;
}

interface State {
  notices: StoredNotice[];
  credentials: StoredCredential[];
  presentations: StoredPresentation[];
  consents: ConsentRow[];
  access: AccessLogRow[];
  requests: DataRequestRow[];
  graduates: StoredGraduate[];
}

/* ---- Helpers ------------------------------------------------------------- */

const iso = (ms: number) => new Date(ms).toISOString();
const now = () => Date.now();

function uid(): string {
  const hex = () => Math.floor(Math.random() * 16).toString(16);
  const part = (n: number) => Array.from({ length: n }, hex).join("");
  return `${part(8)}-${part(4)}-4${part(3)}-8${part(3)}-${part(12)}`;
}

/** Seeded PRNG so the generated graduates and QR patterns are the same on every load. */
function rng(seed: string) {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  let a = h >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let x = Math.imul(a ^ (a >>> 15), 1 | a);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

function crockford(n: number, rand: () => number = Math.random): string {
  return Array.from({ length: n }, () => CROCKFORD[Math.floor(rand() * 32)]).join("");
}

function groups(code: string): string {
  return code.match(/.{1,4}/g)!.join("-");
}

/** A3.15 input rule: trim, upper case, drop spaces and hyphens, O as 0, I and L as 1. */
function normaliseCode(raw: string): string | null {
  const s = raw.trim().toUpperCase().replace(/[\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1");
  if (s.length !== 24 || [...s].some((c) => !CROCKFORD.includes(c))) return null;
  return groups(s);
}

function b64url(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function unb64url(text: string): string | null {
  try {
    const bin = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
    return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0)));
  } catch {
    return null;
  }
}

/**
 * A QR-shaped drawing in segno's style (viewBox, quiet zone of 4, black on
 * white, no fixed size). It has the finder and timing patterns but encodes
 * nothing; mock mode cannot be scanned.
 */
export function mockQrSvg(text: string, modules = 33): string {
  const rand = rng(text);
  const n = modules;
  const dark = (x: number, y: number): boolean => {
    const finder = (fx: number, fy: number) => {
      const dx = x - fx;
      const dy = y - fy;
      if (dx < 0 || dy < 0 || dx > 6 || dy > 6) return null;
      const ring = Math.max(Math.abs(dx - 3), Math.abs(dy - 3));
      return ring !== 2;
    };
    for (const [fx, fy] of [[0, 0], [n - 7, 0], [0, n - 7]]) {
      const f = finder(fx, fy);
      if (f !== null) return f;
    }
    if ((x <= 7 && y <= 7) || (x >= n - 8 && y <= 7) || (x <= 7 && y >= n - 8)) return false;
    if (y === 6) return x % 2 === 0;
    if (x === 6) return y % 2 === 0;
    return rand() < 0.5;
  };
  let d = "";
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) if (dark(x, y)) d += `M${x + 4} ${y + 4}h1v1h-1z`;
  const size = n + 8;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}"><path fill="#fff" d="M0 0h${size}v${size}H0z"/><path fill="#000" d="${d}"/></svg>`;
}

function origin(): string {
  return typeof window === "undefined" ? "http://localhost:3000" : window.location.origin;
}

function currentUser(): User {
  const user = userFromToken(readBrowserToken());
  if (!user) throw new ApiError(401, "UNAUTHENTICATED", "Sign in to continue.");
  return user;
}

function requireRole(user: User, roles: Role[]) {
  if (!roles.includes(user.role)) throw new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: roles });
}

function paginate<T>(items: T[], query?: Query): Page<T> {
  const page = Math.max(1, Number(query?.page ?? 1));
  const pageSize = Math.min(200, Math.max(1, Number(query?.page_size ?? 25)));
  return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, page_size: pageSize };
}

function validation(field: string, message: string): ApiError {
  return new ApiError(422, "VALIDATION_ERROR", message, { fields: [{ field, message }] });
}

/** "Identity, Admission, Seat and Student" */
function joinAnd(words: string[]): string {
  return words.length <= 1 ? words.join("") : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/* ---- Seed ---------------------------------------------------------------- */

const ENROLMENT_FIELDS: DisclosableField[] = [
  { key: "name", label: "Name", always: false },
  { key: "dob", label: "Date of birth", always: false },
  { key: "apaar_masked", label: "APAAR (masked)", always: false },
  { key: "institution", label: "Institution", always: true },
  { key: "programme", label: "Programme", always: true },
  { key: "academic_year", label: "Academic year", always: false },
  { key: "year_of_study", label: "Year of study", always: false },
  { key: "countersigned", label: "Countersigned by", always: false },
];

const DEGREE_FIELDS: DisclosableField[] = [
  { key: "name", label: "Name", always: false },
  { key: "apaar_masked", label: "APAAR (masked)", always: false },
  { key: "institution", label: "Institution", always: true },
  { key: "programme", label: "Programme", always: true },
  { key: "university", label: "University", always: false },
  { key: "year_of_award", label: "Year of award", always: false },
];

const FIRST = ["Aarav", "Ananya", "Vihaan", "Diya", "Aditya", "Isha", "Arjun", "Kavya", "Rohan", "Meera", "Siddharth", "Pooja", "Nikhil", "Sneha", "Kunal", "Tanvi", "Harsh", "Riya", "Omkar", "Shruti"];
const LAST = ["Patil", "Deshmukh", "Kulkarni", "Joshi", "Pawar", "Jadhav", "Shinde", "Gaikwad", "More", "Chavan", "Kale", "Bhosale"];
const PROGRAMMES = [
  { code: "CSE", name: "B.Tech Computer Science and Engineering" },
  { code: "MECH", name: "B.Tech Mechanical Engineering" },
  { code: "ECE", name: "B.Tech Electronics and Communication Engineering" },
  { code: "CIVIL", name: "B.Tech Civil Engineering" },
  { code: "IT", name: "B.Tech Information Technology" },
];

function seedGraduates(): StoredGraduate[] {
  const rand = rng("graduates-2025-26");
  const affiliates = INSTITUTIONS.filter((i) => i.university_id === IDS.mstu);
  const out: StoredGraduate[] = [];
  affiliates.forEach((inst, ii) => {
    for (let k = 0; k < 18; k++) {
      const p = PROGRAMMES[Math.floor(rand() * PROGRAMMES.length)];
      const provisional = rand() < 0.12;
      const last4 = String(1000 + Math.floor(rand() * 9000));
      const name = `${FIRST[Math.floor(rand() * FIRST.length)]} ${LAST[Math.floor(rand() * LAST.length)]}`;
      out.push({
        universityId: IDS.mstu,
        credentialId: null,
        row: {
          enrolment_id: `90000000-${String(ii).padStart(4, "0")}-4000-8000-${String(k).padStart(12, "0")}`,
          student: {
            id: `91000000-${String(ii).padStart(4, "0")}-4000-8000-${String(k).padStart(12, "0")}`,
            name,
            apaar_masked: provisional ? null : `XXXX XXXX ${last4}`,
            provisional_id: provisional ? `PRV-${crockford(8, rand)}` : null,
          },
          institution: { id: inst.id, name: inst.name, aicte_permanent_id: inst.aicte_permanent_id },
          programme: { id: `92000000-0000-4000-8000-${p.code.padStart(12, "0")}`, code: p.code, name: p.name, level: "UG" },
          academic_year: "2025-26",
          year_of_award: 2026,
        },
      });
    }
  });
  // The first graduate is Asha Patil of the contract examples.
  out[0].row.student = { ...out[0].row.student, name: "Asha Patil", apaar_masked: "XXXX XXXX 0011", provisional_id: null };
  return out.sort((a, b) => a.row.institution.name.localeCompare(b.row.institution.name) || a.row.student.name.localeCompare(b.row.student.name));
}

function raviNotice(token: string, channel: NoticeChannel, t0: number): StoredNotice {
  return {
    token,
    id: uid(),
    enrolment_id: RAVI_ENROLMENT,
    ravi: true,
    channel,
    institution_name: ABC.name,
    programme_code: "CSE",
    programme_name: "B.Tech Computer Science and Engineering",
    academic_year: ACADEMIC_YEAR,
    year_of_study: 1,
    id_kind: "APAAR",
    id_masked: "XXXX XXXX 4417",
    uploaded_at: iso(t0 - 3 * 60 * MIN),
    sent_at: iso(t0 - 2 * 60 * MIN + (channel === "DIGILOCKER" ? 1000 : 0)),
    expires_at: iso(t0 - 2 * 60 * MIN + 30 * DAY),
    response: null,
    responded_at: null,
    previous_response: null,
    changed_at: null,
    comment: null,
  };
}

function otherNotice(token: string, patch: Partial<StoredNotice>, t0: number): StoredNotice {
  return {
    ...raviNotice(token, "EMAIL", t0),
    ravi: false,
    enrolment_id: uid(),
    programme_code: "MECH",
    programme_name: "B.Tech Mechanical Engineering",
    id_masked: "XXXX XXXX 7302",
    ...patch,
  };
}

function seed(): State {
  const t0 = now();
  const graduates = seedGraduates();
  const state: State = {
    notices: [
      raviNotice("demo-ravi", "EMAIL", t0),
      raviNotice("demo-ravi-digilocker", "DIGILOCKER", t0),
      otherNotice("demo-answered", { response: "YES", responded_at: iso(t0 - 2 * DAY) }, t0),
      otherNotice("demo-changed", { response: "YES", responded_at: iso(t0 - 3 * DAY), previous_response: "NO", changed_at: iso(t0 - 2 * DAY) }, t0),
      otherNotice("demo-closed", { response: "NO", responded_at: iso(t0 - 9 * DAY), uploaded_at: iso(t0 - 12 * DAY), sent_at: iso(t0 - 11 * DAY) }, t0),
      otherNotice("demo-provisional", { id_kind: "PROVISIONAL", id_masked: "PRV-XXXXK4PX", programme_code: "ECE", programme_name: "B.Tech Electronics and Communication Engineering" }, t0),
    ],
    credentials: [],
    presentations: [],
    consents: [
      {
        id: uid(),
        purpose: "APAAR_LINK",
        status: "GIVEN",
        channel: "COLLEGE_UPLOAD",
        notice_text: t("consent.apaar_link", { institution_name: ABC.name }),
        notice_version: "v1",
        recorded_at: iso(t0 - 3 * 60 * MIN),
        withdrawn_at: null,
        enrolment: { id: RAVI_ENROLMENT, institution_name: ABC.name, programme_name: "B.Tech Computer Science and Engineering", academic_year: ACADEMIC_YEAR },
      },
    ],
    access: seedAccess(t0),
    requests: [
      {
        id: uid(),
        kind: "CORRECTION",
        status: "DONE",
        details: "My mobile number ends in 4521, the college had an older number.",
        response: "Your college uploaded the corrected mobile number on 22 Oct 2026. Nothing else needed changing.",
        enrolment: { id: RAVI_ENROLMENT, institution_name: ABC.name, programme_name: "B.Tech Computer Science and Engineering", academic_year: ACADEMIC_YEAR },
        created_at: iso(t0 - 8 * DAY),
        resolved_at: iso(t0 - 6 * DAY),
        export_path: null,
      },
    ],
    graduates,
  };
  // Two degree proofs already issued, one of them since revoked.
  for (const [i, revoked] of [[0, false], [4, true]] as const) {
    const g = graduates[i];
    const cred = degreeCredential(g, t0 - (revoked ? 5 : 1) * DAY);
    if (revoked) Object.assign(cred, { revoked: true, revoked_at: iso(t0 - 2 * DAY), revoked_reason_code: "ADMIN", revoked_reason: "Degree withdrawn by the university." });
    state.credentials.push(cred);
    g.credentialId = cred.id;
  }
  return state;
}

function seedAccess(t0: number): AccessLogRow[] {
  const rows: AccessLogRow[] = [];
  const roles: [AccessorRole, AccessedWhat][] = [
    ["INSTITUTION", "RECORD"],
    ["RO_OFFICER", "RECORD"],
    ["AICTE_ADMIN", "RECORD"],
    ["INSTITUTION", "RECORD"],
    ["UNIVERSITY", "RECORD"],
  ];
  for (let i = 0; i < 27; i++) {
    const [role, what] = roles[i % roles.length];
    rows.push({ at: iso(t0 - (i * 7 + 3) * 60 * MIN), role, what });
  }
  return rows;
}

/* ---- Store --------------------------------------------------------------- */

let memory: State | null = null;

function load(): State {
  if (memory) return memory;
  try {
    const raw = typeof sessionStorage === "undefined" ? null : sessionStorage.getItem(STORE_KEY);
    memory = raw ? (JSON.parse(raw) as State) : seed();
  } catch {
    memory = seed();
  }
  return memory;
}

function save() {
  try {
    if (memory && typeof sessionStorage !== "undefined") sessionStorage.setItem(STORE_KEY, JSON.stringify(memory));
  } catch {
    // Private windows may refuse storage; the state then lasts for this page only.
  }
}

/* ---- Notices (A3.3, A3.4, A3.6) ------------------------------------------ */

const NOTICE_TEXT = (institution: string) => t("consent.notice", { institution_name: institution });

function noticePublic(n: StoredNotice): NoticePublic {
  const until = n.responded_at && !n.changed_at ? Date.parse(n.responded_at) + 7 * DAY : null;
  return {
    channel: n.channel,
    institution_name: n.institution_name,
    programme_code: n.programme_code,
    programme_name: n.programme_name,
    academic_year: n.academic_year,
    year_of_study: n.year_of_study,
    id_kind: n.id_kind,
    id_masked: n.id_masked,
    uploaded_at: n.uploaded_at,
    sent_at: n.sent_at,
    expires_at: n.expires_at,
    response: n.response,
    responded_at: n.responded_at,
    previous_response: n.previous_response,
    changed_at: n.changed_at,
    can_change_until: until && until > now() ? iso(until) : null,
    consent_text: NOTICE_TEXT(n.institution_name),
    notice_version: "v1",
  };
}

function findNotice(token: string): StoredNotice {
  if (token === "demo-busy") throw new ApiError(429, "RATE_LIMITED", "Too many requests.", { retry_after: 12 });
  if (token === "demo-expired") throw new ApiError(410, "NOTICE_EXPIRED", "This link has expired. Ask your college to resend the notice.");
  const n = load().notices.find((x) => x.token === token);
  if (!n) throw new ApiError(404, "NOTICE_NOT_FOUND", "This link is not valid.");
  if (!n.response && Date.parse(n.expires_at) < now()) throw new ApiError(410, "NOTICE_EXPIRED", "This link has expired. Ask your college to resend the notice.");
  return n;
}

function respond(n: StoredNotice, body: { response?: string; comment?: string }): NoticePublic {
  const response = body.response;
  if (response !== "YES" && response !== "NO") throw validation("response", "Choose YES or NO.");
  if (typeof body.comment === "string" && body.comment.length > 500) throw validation("comment", "At most 500 characters.");
  const at = iso(now());
  if (!n.response) {
    Object.assign(n, { response, responded_at: at, comment: response === "NO" ? (body.comment ?? null) : null });
  } else if (n.response === response) {
    return noticePublic(n);
  } else if (n.changed_at) {
    throw new ApiError(409, "NOTICE_ALREADY_CHANGED", "You have already changed your answer once.", { reason: "CHANGED_ONCE" });
  } else if (Date.parse(n.responded_at!) + 7 * DAY < now()) {
    throw new ApiError(409, "NOTICE_ALREADY_CHANGED", "Answers can be changed only within 7 days of the first reply.", { reason: "WINDOW_CLOSED" });
  } else {
    Object.assign(n, { previous_response: n.response, response, changed_at: at, comment: response === "NO" ? (body.comment ?? null) : n.comment });
  }
  const state = load();
  if (response === "YES") {
    state.consents.unshift({
      id: uid(),
      purpose: "NOTICE",
      status: "GIVEN",
      channel: n.channel === "EMAIL" ? "NOTICE_EMAIL" : "NOTICE_DIGILOCKER",
      notice_text: NOTICE_TEXT(n.institution_name),
      notice_version: "v1",
      recorded_at: at,
      withdrawn_at: null,
      enrolment: n.ravi ? { id: n.enrolment_id, institution_name: n.institution_name, programme_name: n.programme_name, academic_year: n.academic_year } : null,
    });
  }
  if (n.ravi) settleRaviProof();
  save();
  return noticePublic(n);
}

/** The Student check of Ravi's claim: a No on any channel beats a Yes (D24). */
function raviReply(): NoticeResponse | null {
  const answers = load().notices.filter((n) => n.ravi && n.response).map((n) => n.response);
  if (answers.includes("NO")) return "NO";
  if (answers.includes("YES")) return "YES";
  return null;
}

/** Issue Ravi's Enrolment proof once his Student check is countersigned; revoke-free otherwise (a pending check never revokes). */
function settleRaviProof() {
  const state = load();
  const active = state.credentials.find((c) => c.student === "ravi" && c.kind === "ENROLMENT" && !c.revoked);
  if (raviReply() === "YES" && !active) state.credentials.unshift(enrolmentCredential());
}

function enrolmentCredential(): StoredCredential {
  const issued = now();
  const issuedDate = formatDate(iso(issued));
  return {
    id: uid(),
    kind: "ENROLMENT",
    revoked: false,
    student: "ravi",
    vct: "countersign:enrolment:v1",
    short_id: crockford(8),
    issuer: ISSUER,
    enrolment_id: RAVI_ENROLMENT,
    institution_name: ABC.name,
    programme_name: "B.Tech Computer Science and Engineering",
    academic_year: ACADEMIC_YEAR,
    university_name: null,
    issued_at: iso(issued),
    expires_at: "2027-08-31T18:29:59Z",
    revoked_at: null,
    revoked_reason_code: null,
    revoked_reason: null,
    holder_bound: true,
    disclosable: ENROLMENT_FIELDS,
    claims: [
      { key: "name", label: "Name", value: "Ravi Kumar Sharma", disclosable: true },
      { key: "dob", label: "Date of birth", value: "21 Mar 2007", disclosable: true },
      { key: "apaar_masked", label: "APAAR (masked)", value: "XXXX XXXX 4417", disclosable: true },
      { key: "institution", label: "Institution", value: `${ABC.name} (${ABC.aicte_permanent_id})`, disclosable: true },
      { key: "programme", label: "Programme", value: "B.Tech Computer Science and Engineering (UG)", disclosable: true },
      { key: "academic_year", label: "Academic year", value: ACADEMIC_YEAR, disclosable: true },
      { key: "year_of_study", label: "Year of study", value: "1", disclosable: true },
      { key: "countersigned", label: "Countersigned by", value: `${joinAnd(["Identity", "Admission", "Seat", "Student"])}, as of ${issuedDate}`, disclosable: true },
      { key: "issued", label: "Issued", value: issuedDate, disclosable: false },
      { key: "expires", label: "Valid until", value: "31 Aug 2027", disclosable: false },
    ],
  };
}

function studentNotices(): StudentNotice[] {
  return load()
    .notices.filter((n) => n.ravi)
    .map((n) => {
      const pub = noticePublic(n);
      const state: NoticeState = n.response ? "ANSWERED" : Date.parse(n.expires_at) < now() ? "EXPIRED" : "AWAITING";
      return {
        id: n.id,
        enrolment_id: n.enrolment_id,
        channel: n.channel,
        institution_name: n.institution_name,
        programme_name: n.programme_name,
        academic_year: n.academic_year,
        state,
        delivery_status: "SENT" as const,
        sent_at: n.sent_at,
        expires_at: n.expires_at,
        response: n.response,
        responded_at: n.responded_at,
        changed_at: n.changed_at,
        can_change_until: pub.can_change_until,
      };
    })
    .sort((a, b) => (b.sent_at ?? "").localeCompare(a.sent_at ?? ""));
}

/** GET /students/me with the Week 3 lists filled and the Student check following Ravi's reply. */
function studentMeLive(): StudentMe {
  const me = studentMe();
  const reply = raviReply();
  const enrolments = me.enrolments.map((e) => {
    if (e.id !== RAVI_ENROLMENT || !reply) return e;
    const checks = e.countersign.checks.map((c) => (c.type === "STUDENT" ? { ...c, status: reply === "YES" ? ("CONFIRMED" as const) : ("CONTRADICTED" as const) } : c));
    const applicable = checks.filter((c) => c.status !== "NOT_APPLICABLE" && c.status !== "NOT_YET_DUE").length;
    const passes = checks.filter((c) => c.status === "CONFIRMED").length;
    return { ...e, countersign: { score: { passes, applicable }, checks } };
  });
  const credentials = load()
    .credentials.filter((c) => c.student === "ravi")
    .map((c) => ({ id: c.id, kind: c.kind, status: credentialStatus(c), enrolment_id: c.enrolment_id, institution_name: c.institution_name, issued_at: c.issued_at }));
  return { ...me, enrolments, notices: studentNotices(), credentials };
}

/* ---- Credentials (A3.16, A3.17) ------------------------------------------ */

function credentialStatus(c: StoredCredential): CredentialStatus {
  if (c.revoked) return "REVOKED";
  if (c.expires_at && Date.parse(c.expires_at) < now()) return "EXPIRED";
  return "ACTIVE";
}

function card(c: StoredCredential): CredentialCard {
  const shares = load()
    .presentations.filter((p) => p.credential_id === c.id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const verified = shares.map((p) => p.last_verified_at).filter((x): x is string => Boolean(x)).sort();
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const { revoked, student, claims, ...rest } = c;
  return {
    ...rest,
    status: credentialStatus(c),
    shares: shares.length,
    last_verified_at: verified[verified.length - 1] ?? null,
    presentations: shares.slice(0, 5).map((p) => ({
      id: p.id,
      created_at: p.created_at,
      expires_at: p.expires_at,
      disclosed: p.disclosed,
      verify_count: p.verify_count,
      last_verified_at: p.last_verified_at,
    })),
  };
}

function ownCredential(id: string): StoredCredential {
  const c = load().credentials.find((x) => x.id === id && x.student === "ravi");
  if (!c) throw new ApiError(404, "NOT_FOUND", "Credential not found.");
  return c;
}

function present(c: StoredCredential, body: { fields?: unknown; consent?: unknown }): PresentationCreated {
  if (body.consent !== true) throw validation("consent", "Agree to the share text to create a proof.");
  const fields = Array.isArray(body.fields) ? (body.fields as string[]) : [];
  const known = c.disclosable.map((d) => d.key as string);
  const unknown = fields.find((f) => !known.includes(f));
  if (unknown) throw validation("fields", `Unknown field: ${unknown}.`);
  const status = credentialStatus(c);
  if (status === "REVOKED") {
    throw new ApiError(409, "CREDENTIAL_REVOKED", `This proof was revoked on ${formatDate(c.revoked_at)} and cannot be shared.`, { revoked_at: c.revoked_at });
  }
  if (status === "EXPIRED") {
    throw new ApiError(409, "CREDENTIAL_NOT_ELIGIBLE", `This proof expired on ${formatDate(c.expires_at)} and cannot be shared.`, { reason: "EXPIRED" });
  }
  const chosen = new Set([...fields, "institution", "programme"]);
  const disclosed = c.disclosable.map((d) => d.key).filter((k) => chosen.has(k));
  const code = groups(crockford(24));
  const created = now();
  const state = load();
  const p: StoredPresentation = {
    id: uid(),
    credential_id: c.id,
    code,
    created_at: iso(created),
    expires_at: iso(created + 10 * MIN),
    disclosed,
    verify_count: 0,
    first_verified_at: null,
    last_verified_at: null,
  };
  state.presentations.unshift(p);
  state.consents.unshift({
    id: uid(),
    purpose: "CREDENTIAL_SHARE",
    status: "GIVEN",
    channel: "PORTAL",
    notice_text: t("consent.credential_share"),
    notice_version: "v1",
    recorded_at: p.created_at,
    withdrawn_at: null,
    enrolment: null,
  });
  save();
  const url = `${origin()}/verify/${code}`;
  return { id: p.id, code, url, qr_svg: mockQrSvg(url), expires_at: p.expires_at, disclosed, total: c.disclosable.length };
}

/* ---- Verifier (A3.20) ---------------------------------------------------- */

const INVALID: VerifyResult = {
  result: "INVALID",
  kind: null,
  issuer: null,
  institution_name: null,
  university_name: null,
  issued_at: null,
  expires_at: null,
  revoked_at: null,
  disclosed: [],
  holder_bound: false,
  status_checked_at: null,
  method: "signature",
  nonce: null,
};

function verifyResult(c: StoredCredential, disclosedKeys: ClaimKey[], expiresAt: string | null, method: VerifyResult["method"]): VerifyResult {
  const status = credentialStatus(c);
  const checkedAt = iso(now() - 20_000);
  const base: VerifyResult = {
    result: "VALID",
    kind: c.kind,
    issuer: ISSUER,
    institution_name: null,
    university_name: c.university_name,
    issued_at: c.issued_at,
    expires_at: expiresAt,
    revoked_at: null,
    disclosed: [],
    holder_bound: c.holder_bound,
    status_checked_at: checkedAt,
    method,
    nonce: null,
  };
  if (status === "REVOKED") return { ...base, result: "REVOKED", revoked_at: c.revoked_at };
  if (status === "EXPIRED" || (expiresAt && Date.parse(expiresAt) < now())) return { ...base, result: "EXPIRED" };
  const disclosed: DisclosedField[] = c.claims
    .filter((cl) => disclosedKeys.includes(cl.key as ClaimKey))
    .map((cl) => ({ key: cl.key as ClaimKey, label: cl.label, value: cl.value }));
  return { ...base, institution_name: c.institution_name, disclosed };
}

/** Fixed demo codes so every result state can be seen without creating a share first. */
function demoCode(code: string): VerifyResult | null {
  const tail = "3M2X-9ZAB-4TNE-W8RC-6HDF";
  const lead = code.slice(0, 4);
  if (code.slice(5) !== tail) return null;
  if (lead === "R4TE") throw new ApiError(429, "RATE_LIMITED", "Too many requests.", { retry_after: 15 });
  const issued = iso(now() - 3 * MIN);
  const valid: VerifyResult = {
    ...INVALID,
    result: "VALID",
    kind: "ENROLMENT",
    issuer: ISSUER,
    institution_name: ABC.name,
    issued_at: issued,
    expires_at: iso(now() + 7 * MIN),
    holder_bound: true,
    status_checked_at: iso(now() - 20_000),
    disclosed: [
      { key: "institution", label: "Institution", value: `${ABC.name} (${ABC.aicte_permanent_id})` },
      { key: "programme", label: "Programme", value: "B.Tech Computer Science and Engineering (UG)" },
      { key: "year_of_study", label: "Year of study", value: "1" },
    ],
  };
  switch (lead) {
    case "K7PQ":
      return valid;
    case "R7VK":
      return { ...valid, result: "REVOKED", institution_name: null, disclosed: [], revoked_at: iso(now() - DAY) };
    case "E7XP":
      return { ...valid, result: "EXPIRED", institution_name: null, disclosed: [], expires_at: iso(now() - 2 * MIN) };
    case "N7VD":
      return INVALID;
    default:
      return null;
  }
}

function verifyCode(raw: string): VerifyResult {
  const code = normaliseCode(raw);
  if (!code) throw new ApiError(404, "PRESENTATION_NOT_FOUND", "This code is not a Countersign proof.");
  const demo = demoCode(code);
  if (demo) return demo;
  const state = load();
  const p = state.presentations.find((x) => x.code === code);
  const c = p && state.credentials.find((x) => x.id === p.credential_id);
  if (!p || !c) throw new ApiError(404, "PRESENTATION_NOT_FOUND", "This code is not a Countersign proof.");
  const at = iso(now());
  p.verify_count += 1;
  p.first_verified_at ??= at;
  p.last_verified_at = at;
  state.access.unshift({ at, role: "VERIFIER", what: "PROOF" });
  save();
  return verifyResult(c, p.disclosed, p.expires_at, "signature");
}

function verifyPaste(body: { presentation?: unknown }): VerifyResult {
  const text = typeof body.presentation === "string" ? body.presentation.trim() : "";
  if (text.length < 1 || text.length > 16384) throw validation("presentation", "Paste the proof text.");
  if (!/^eyJ[\w-]+\.[\w-]+\.[\w-]+~/.test(text)) return INVALID;
  const valid = demoCode("K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF")!;
  return { ...valid, expires_at: "2027-08-31T18:29:59Z", nonce: "K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF" };
}

/* ---- Degrees (A3.21, A3.20) ---------------------------------------------- */

function shortName(name: string): string {
  const s = name
    .replace(/Engineering/g, "Engg.")
    .replace(/Technology/g, "Tech.")
    .replace(/Institute/g, "Inst.")
    .replace(/Management/g, "Mgmt.")
    .replace(/Computer Science/g, "CS")
    .replace(/Information Technology/g, "IT")
    .replace(/ and /g, " & ")
    .replace(/University/g, "Univ.");
  if (s.length <= 28) return s;
  const cut = s.slice(0, 29);
  return cut.slice(0, cut.lastIndexOf(" "));
}

function maskProvisional(id: string): string {
  return `PRV-XXXX${id.slice(-4)}`;
}

function degreeCredential(g: StoredGraduate, issued: number): StoredCredential {
  const r = g.row;
  const apaar = r.student.apaar_masked;
  return {
    id: uid(),
    kind: "COMPLETION",
    revoked: false,
    student: "graduate",
    vct: "countersign:degree:v1",
    short_id: crockford(8),
    issuer: ISSUER,
    enrolment_id: r.enrolment_id,
    institution_name: r.institution.name,
    programme_name: r.programme.name,
    academic_year: r.academic_year,
    university_name: "Maharashtra State Technical University",
    issued_at: iso(issued),
    expires_at: null,
    revoked_at: null,
    revoked_reason_code: null,
    revoked_reason: null,
    holder_bound: false,
    disclosable: DEGREE_FIELDS,
    claims: [
      { key: "name", label: "Name", value: r.student.name, disclosable: true },
      ...(apaar ? [{ key: "apaar_masked", label: "APAAR (masked)", value: apaar, disclosable: true }] : []),
      { key: "institution", label: "Institution", value: `${r.institution.name} (${r.institution.aicte_permanent_id})`, disclosable: true },
      { key: "programme", label: "Programme", value: `${r.programme.name} (UG)`, disclosable: true },
      { key: "university", label: "University", value: "Maharashtra State Technical University (MSTU)", disclosable: true },
      { key: "year_of_award", label: "Year of award", value: String(r.year_of_award), disclosable: true },
    ],
  };
}

function graduateScope(user: User): StoredGraduate[] {
  requireRole(user, ["UNIVERSITY", "AICTE_ADMIN"]);
  const all = load().graduates;
  return user.role === "AICTE_ADMIN" ? all : all.filter((g) => g.universityId === user.scope.university_id);
}

function graduateRow(g: StoredGraduate): GraduateRow {
  const c = g.credentialId ? load().credentials.find((x) => x.id === g.credentialId) : undefined;
  return { ...g.row, degree: c ? { credential_id: c.id, short_id: c.short_id, status: credentialStatus(c), issued_at: c.issued_at } : null };
}

function degreeJws(g: StoredGraduate, c: StoredCredential): string {
  const r = g.row;
  const header = b64url(JSON.stringify({ alg: "ES256", kid: "mock-issuer-key" }));
  const payload = b64url(
    JSON.stringify({
      v: 1,
      cid: c.short_id,
      n: r.student.name,
      p: shortName(r.programme.name),
      i: shortName(r.institution.name),
      u: "MSTU",
      y: r.year_of_award,
      a: r.student.apaar_masked ? r.student.apaar_masked.slice(-4) : maskProvisional(r.student.provisional_id ?? ""),
    }),
  );
  return `${header}.${payload}.mock${crockford(40).toLowerCase()}`;
}

function degreePrint(g: StoredGraduate): DegreePrint {
  const r = g.row;
  const c = g.credentialId ? load().credentials.find((x) => x.id === g.credentialId) : undefined;
  const jws = c ? degreeJws(g, c) : null;
  const verifyUrl = jws ? `${origin()}/verify/d/${jws}` : "";
  return {
    enrolment_id: r.enrolment_id,
    student: r.student.apaar_masked
      ? { name: r.student.name, id_kind: "APAAR", id_masked: r.student.apaar_masked }
      : { name: r.student.name, id_kind: "PROVISIONAL", id_masked: maskProvisional(r.student.provisional_id ?? "") },
    programme: { code: r.programme.code, name: r.programme.name, short_name: shortName(r.programme.name) },
    institution: { name: r.institution.name, aicte_permanent_id: r.institution.aicte_permanent_id, short_name: shortName(r.institution.name) },
    university: { code: "MSTU", name: "Maharashtra State Technical University" },
    academic_year: r.academic_year,
    year_of_award: r.year_of_award,
    degree:
      c && jws
        ? {
            credential_id: c.id,
            short_id: c.short_id,
            status: credentialStatus(c),
            issued_at: c.issued_at,
            revoked_at: c.revoked_at,
            jws,
            verify_url: verifyUrl,
            lookup_url: `${origin()}/verify/degree/${c.short_id}`,
            qr_svg: mockQrSvg(verifyUrl, 45),
          }
        : null,
  };
}

function degreeFields(c: StoredCredential, g: StoredGraduate | undefined, fromPayload?: Record<string, unknown>): DisclosedField[] {
  const r = g?.row;
  const fields: DisclosedField[] = [{ key: "proof_id", label: "Proof id", value: c.short_id }];
  const name = String(fromPayload?.n ?? r?.student.name ?? "");
  fields.push({ key: "name", label: "Name", value: name });
  fields.push({ key: "programme", label: "Programme", value: String(fromPayload?.p ?? c.programme_name) });
  fields.push({ key: "institution", label: "Institution", value: String(fromPayload?.i ?? c.institution_name) });
  fields.push({ key: "university", label: "University", value: "Maharashtra State Technical University (MSTU)" });
  fields.push({ key: "year_of_award", label: "Year of award", value: String(fromPayload?.y ?? r?.year_of_award ?? "") });
  const a = fromPayload ? String(fromPayload.a ?? "") : (r?.student.apaar_masked?.slice(-4) ?? maskProvisional(r?.student.provisional_id ?? ""));
  if (a.startsWith("PRV-")) fields.push({ key: "provisional_id", label: "Provisional id", value: a });
  else fields.push({ key: "apaar_masked", label: "APAAR (masked)", value: `XXXX XXXX ${a}` });
  return fields;
}

function verifyDegreeJws(jws: string): VerifyResult {
  const [, payload, signature] = jws.split(".");
  const json = payload ? unb64url(payload) : null;
  if (!json || !signature?.startsWith("mock")) return INVALID;
  let claims: Record<string, unknown>;
  try {
    claims = JSON.parse(json) as Record<string, unknown>;
  } catch {
    return INVALID;
  }
  const state = load();
  const c = state.credentials.find((x) => x.kind === "COMPLETION" && x.short_id === claims.cid);
  if (claims.v !== 1 || !c) return INVALID;
  const g = state.graduates.find((x) => x.credentialId === c.id);
  const base = verifyResult(c, [], null, "signature");
  if (base.result !== "VALID") return base;
  return { ...base, institution_name: String(claims.i), disclosed: degreeFields(c, g, claims) };
}

function verifyDegreeLookup(raw: string): VerifyResult {
  const id = raw.trim().toUpperCase().replace(/O/g, "0").replace(/[IL]/g, "1");
  const state = load();
  const c = state.credentials.find((x) => x.kind === "COMPLETION" && x.short_id === id);
  if (!c) throw new ApiError(404, "PRESENTATION_NOT_FOUND", "This code is not a Countersign proof.");
  const g = state.graduates.find((x) => x.credentialId === c.id);
  const base = verifyResult(c, [], null, "register_lookup");
  base.status_checked_at = iso(now());
  if (base.result !== "VALID") return base;
  const fields = degreeFields(c, g).map((f) => {
    if (f.key === "programme") return { ...f, value: c.programme_name };
    if (f.key === "institution") return { ...f, value: c.institution_name };
    if (f.key === "provisional_id" && g?.row.student.provisional_id) return { ...f, value: maskProvisional(g.row.student.provisional_id) };
    return f;
  });
  return { ...base, institution_name: c.institution_name, disclosed: fields };
}

/* ---- Privacy (A3.22) ----------------------------------------------------- */

const PRIVACY_NOTICE: PrivacyNotice = {
  version: "v1",
  effective_from: "2026-10-28",
  title: "How Countersign uses your data",
  sections: [
    {
      id: "what_we_hold",
      heading: "What we hold",
      body: "Your name, date of birth and gender as your college uploaded them, your masked APAAR or a provisional id, your enrolment (institution, programme, academic year, year of study, admission route and seat), the result of each check, your replies to notices, and the proofs you share.",
    },
    {
      id: "why",
      heading: "Why we hold it",
      body: "To check that every enrolment a college reports is real: against the APAAR registry, the counselling allotment list, the seat ledger, the Academic Bank of Credits and your own reply. Nothing is decided about you without an AICTE officer looking at it.",
    },
    {
      id: "who_sees",
      heading: "Who sees it",
      body: "AICTE officers, your regional office, your college and its affiliating university, each only for the institutions they are responsible for. They see your APAAR masked to its last four digits. Your email and mobile are shown only to you.",
    },
    {
      id: "how_long",
      heading: "How long we keep it",
      body: "As long as the law requires AICTE to keep admission records. A record that must be kept is not erased on request; the reply to an erasure request says what can be removed.",
    },
    {
      id: "your_rights",
      heading: "Your rights",
      body: "You can see who viewed your record, download a copy of everything held about you, ask for a correction or an erasure, and withdraw the consents you gave on this page. Withdrawing never affects your admission.",
    },
  ],
  consent_texts: {
    APAAR_LINK: t("consent.apaar_link"),
    NOTICE: t("consent.notice"),
    CREDENTIAL_SHARE: t("consent.credential_share"),
  },
};

const PURPOSES: ConsentPurpose[] = ["APAAR_LINK", "NOTICE", "CREDENTIAL_SHARE"];

function consentsView() {
  const items = load().consents.slice().sort((a, b) => b.recorded_at.localeCompare(a.recorded_at));
  const current: ConsentCurrent[] = PURPOSES.map((purpose) => {
    const latest = items.find((r) => r.purpose === purpose);
    const status = latest ? (latest.withdrawn_at ? "WITHDRAWN" : latest.status) : "NONE";
    const can = purpose === "NOTICE" ? status !== "WITHDRAWN" : purpose === "CREDENTIAL_SHARE" ? status === "GIVEN" : false;
    return { purpose, status, since: latest ? (latest.withdrawn_at ?? latest.recorded_at) : null, can_withdraw: can };
  });
  return { current, items };
}

function withdraw(purpose: string) {
  if (purpose === "APAAR_LINK") {
    throw validation("purpose", "To unlink your APAAR, send a correction request. Your college must upload your record again; your admission is not affected.");
  }
  if (purpose !== "NOTICE" && purpose !== "CREDENTIAL_SHARE") throw validation("purpose", "Unknown purpose.");
  const state = load();
  const at = iso(now());
  const given = state.consents.filter((r) => r.purpose === purpose && r.status === "GIVEN" && !r.withdrawn_at);
  given.forEach((r) => (r.withdrawn_at = at));
  if (purpose === "NOTICE" && given.length === 0 && consentsView().current[1].status !== "WITHDRAWN") {
    state.consents.unshift({
      id: uid(),
      purpose: "NOTICE",
      status: "WITHDRAWN",
      channel: "PORTAL",
      notice_text: t("consent.withdraw.NOTICE"),
      notice_version: "v1",
      recorded_at: at,
      withdrawn_at: at,
      enrolment: null,
    });
  }
  let expired = 0;
  if (purpose === "CREDENTIAL_SHARE") {
    for (const p of state.presentations) {
      if (Date.parse(p.expires_at) > now()) {
        p.expires_at = at;
        expired += 1;
      }
    }
  }
  save();
  return { ...consentsView(), presentations_expired: expired };
}

function createRequest(body: DataRequestCreate): DataRequestRow {
  if (!["ACCESS", "CORRECTION", "ERASURE"].includes(body.kind)) throw validation("kind", "Choose what you want.");
  const details = (body.details ?? "").trim();
  if (body.kind !== "ACCESS" && details.length < 10) throw validation("details", "Write at least 10 characters.");
  if (details.length > 2000) throw validation("details", "At most 2,000 characters.");
  const at = iso(now());
  const row: DataRequestRow = {
    id: uid(),
    kind: body.kind,
    status: body.kind === "ACCESS" ? "DONE" : "OPEN",
    details: details || null,
    response: body.kind === "ACCESS" ? "Your data is ready to download." : null,
    enrolment: body.enrolment_id
      ? { id: RAVI_ENROLMENT, institution_name: ABC.name, programme_name: "B.Tech Computer Science and Engineering", academic_year: ACADEMIC_YEAR }
      : null,
    created_at: at,
    resolved_at: body.kind === "ACCESS" ? at : null,
    export_path: body.kind === "ACCESS" ? "/students/me/export.json" : null,
  };
  load().requests.unshift(row);
  save();
  return row;
}

function exportData(): MyDataExport {
  const state = load();
  const me = studentMeLive();
  const access = state.access;
  state.access.unshift({ at: iso(now()), role: "STUDENT", what: "EXPORT" });
  save();
  return {
    generated_at: iso(now()),
    privacy_notice_version: "v1",
    student: {
      id: me.id,
      name: me.name,
      dob: me.dob,
      gender: "M",
      nationality: "IN",
      apaar_masked: me.apaar_masked,
      provisional_id: me.provisional_id,
      consent_status: me.consent_status,
      email: me.email,
      mobile_masked: me.mobile_masked,
    },
    enrolments: me.enrolments.map((e) => ({
      id: e.id,
      institution_name: e.institution_name,
      programme_name: e.programme_name,
      academic_year: e.academic_year,
      year_of_study: e.year_of_study,
      admission_route: "COUNSELLING",
      category: "GENERAL",
      status: e.status,
      status_date: "2026-10-28",
      admission_date: "2026-08-02",
      seat_code: "CSE-R-001",
      checks: e.countersign.checks.map((c) => ({ type: c.type, status: c.status, summary: "", checked_at: null })),
      flags: [],
    })),
    notices: state.notices
      .filter((n) => n.ravi)
      .map((n) => ({
        channel: n.channel,
        sent_at: n.sent_at,
        expires_at: n.expires_at,
        delivery_status: "SENT" as const,
        response: n.response,
        responded_at: n.responded_at,
        changed_at: n.changed_at,
        comment: n.comment,
      })),
    consents: consentsView().items,
    credentials: state.credentials
      .filter((c) => c.student === "ravi")
      .map((c) => ({
        id: c.id,
        kind: c.kind,
        status: credentialStatus(c),
        issued_at: c.issued_at,
        expires_at: c.expires_at,
        revoked_at: c.revoked_at,
        revoked_reason: c.revoked_reason,
        claims: c.claims.filter((cl) => cl.disclosable).map(({ key, label, value }) => ({ key, label, value })),
      })),
    presentations: state.presentations.map((p) => ({
      credential_id: p.credential_id,
      created_at: p.created_at,
      expires_at: p.expires_at,
      disclosed: p.disclosed,
      verify_count: p.verify_count,
    })),
    data_requests: state.requests,
    access_log: access.filter((a) => a.role !== "STUDENT"),
  };
}

/* ---- A small PDF for the insert ------------------------------------------ */

function insertPdf(print: DegreePrint): Blob {
  const id = print.student.id_kind === "APAAR" ? `APAAR ${print.student.id_masked}` : `Provisional id ${print.student.id_masked}`;
  const lines: [number, number, number, string][] = [
    [18, 72, 760, print.university.name],
    [11, 72, 730, "This insert accompanies the degree awarded to"],
    [11, 72, 700, `Name            ${print.student.name}`],
    [11, 72, 682, `Programme       ${print.programme.name}`],
    [11, 72, 664, `Institution     ${print.institution.name}`],
    [11, 72, 646, `Year of award   ${print.year_of_award}`],
    [11, 72, 628, id],
    [11, 72, 590, `Proof id ${print.degree?.short_id ?? ""}`],
    [11, 72, 572, `Scan to verify at ${origin().replace(/^https?:\/\//, "")}/verify`],
    [9, 72, 80, "Sample degree insert generated from synthetic demo data. Not a degree certificate."],
  ];
  const esc = (s: string) => s.replace(/[\\()]/g, (m) => `\\${m}`);
  const stream = lines.map(([size, x, y, text]) => `BT /F1 ${size} Tf ${x} ${y} Td (${esc(text)}) Tj ET`).join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((o, i) => {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("")}`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return new Blob([pdf], { type: "application/pdf" });
}

/* ---- Routing ------------------------------------------------------------- */

/**
 * Answers the routes above, or UNHANDLED so the main mock handler carries on.
 * Public routes (notices, verify, privacy notice) never ask who is signed in.
 */
export async function studentLoopRequest(method: string, pathname: string, query?: Query, body?: unknown): Promise<unknown> {
  const parts = pathname.split("/").filter(Boolean);
  const data = (body ?? {}) as Record<string, unknown>;

  if (parts[0] === "notices" && parts[1]) {
    const n = findNotice(decodeURIComponent(parts[1]));
    if (parts.length === 2 && method === "GET") {
      if (n.ravi) {
        load().access.unshift({ at: iso(now()), role: "NOTICE_LINK", what: "NOTICE" });
        save();
      }
      return noticePublic(n);
    }
    if (parts[2] === "respond" && method === "POST") return respond(n, data as { response?: string; comment?: string });
  }

  if (parts[0] === "verify") {
    if (parts.length === 1 && method === "POST") return verifyPaste(data);
    if (parts[1] === "d" && parts[2]) return verifyDegreeJws(parts.slice(2).join("/"));
    if (parts[1] === "degree" && parts[2]) return verifyDegreeLookup(decodeURIComponent(parts[2]));
    if (parts.length === 2) return verifyCode(decodeURIComponent(parts[1]));
  }

  if (pathname === "/privacy/notice") return PRIVACY_NOTICE;

  if (pathname === "/students/me") {
    requireRole(currentUser(), ["STUDENT"]);
    return studentMeLive();
  }

  if (parts[0] === "students" && parts[1] === "me") {
    requireRole(currentUser(), ["STUDENT"]);
    const rest = parts.slice(2).join("/");
    if (rest === "consents" && method === "GET") return consentsView();
    if (parts[2] === "consents" && parts[4] === "withdraw" && method === "POST") return withdraw(parts[3]);
    if (rest === "access-log") return paginate(load().access.filter((a) => a.role !== "STUDENT"), query);
    if (rest === "data-requests" && method === "GET") return paginate(load().requests, query);
    if (rest === "data-requests" && method === "POST") return createRequest(data as unknown as DataRequestCreate);
    return UNHANDLED;
  }

  if (parts[0] === "credentials") {
    const user = currentUser();
    requireRole(user, ["STUDENT", "AICTE_ADMIN"]);
    const mine = load().credentials.filter((c) => c.student === "ravi");
    if (parts.length === 1) return paginate(mine.map(card), query);
    const c = ownCredential(parts[1]);
    if (parts.length === 2) return { ...card(c), claims: c.claims };
    if (parts[2] === "present" && method === "POST") {
      requireRole(user, ["STUDENT"]);
      return present(c, data);
    }
    if (parts[2] === "presentations") {
      const rows = load()
        .presentations.filter((p) => p.credential_id === c.id)
        .map((p) => ({
          id: p.id,
          created_at: p.created_at,
          expires_at: p.expires_at,
          state: Date.parse(p.expires_at) > now() ? "LIVE" : "EXPIRED",
          disclosed: p.disclosed,
          verify_count: p.verify_count,
          first_verified_at: p.first_verified_at,
          last_verified_at: p.last_verified_at,
        }));
      return paginate(rows, query);
    }
  }

  if (parts[0] === "university") {
    const user = currentUser();
    const scope = graduateScope(user);
    if (parts[1] === "graduates") {
      let rows = scope;
      const q = String(query?.q ?? "").trim().toLowerCase();
      if (q) {
        rows = rows.filter(
          (g) =>
            g.row.student.name.toLowerCase().includes(q) ||
            (g.row.student.apaar_masked ?? "").endsWith(q) ||
            (g.row.student.provisional_id ?? "").toLowerCase().includes(q),
        );
      }
      if (query?.degree === "issued") rows = rows.filter((g) => g.credentialId);
      if (query?.degree === "not_issued") rows = rows.filter((g) => !g.credentialId);
      return paginate(rows.map(graduateRow), query);
    }
    if (parts[1] === "degrees" && parts[2]) {
      const g = scope.find((x) => x.row.enrolment_id === parts[2]);
      if (!g) throw new ApiError(404, "NOT_FOUND", "Enrolment not found.");
      if (parts[3] === "issue" && method === "POST") {
        const existing = g.credentialId ? load().credentials.find((c) => c.id === g.credentialId) : undefined;
        if (!existing || existing.revoked) {
          const cred = degreeCredential(g, now());
          load().credentials.push(cred);
          g.credentialId = cred.id;
          save();
        }
        return degreePrint(g);
      }
      if (parts.length === 3) return degreePrint(g);
    }
  }

  return UNHANDLED;
}

/** File downloads for these pages: the student's export and the degree insert PDF. */
export async function studentLoopDownload(path: string): Promise<{ blob: Blob; filename: string } | null> {
  if (path === "/students/me/export.json") {
    requireRole(currentUser(), ["STUDENT"]);
    return { blob: new Blob([JSON.stringify(exportData(), null, 2)], { type: "application/json" }), filename: "countersign-my-data.json" };
  }
  const m = /^\/university\/degrees\/([^/]+)\/insert\.pdf$/.exec(path);
  if (m) {
    const g = graduateScope(currentUser()).find((x) => x.row.enrolment_id === m[1]);
    if (!g) throw new ApiError(404, "NOT_FOUND", "Enrolment not found.");
    const print = degreePrint(g);
    if (!print.degree) throw new ApiError(409, "CREDENTIAL_NOT_ELIGIBLE", "Issue the degree proof first.", { reason: "NOT_ISSUED" });
    if (print.degree.status === "REVOKED") throw new ApiError(409, "CREDENTIAL_REVOKED", "This proof is already revoked.", { revoked_at: print.degree.revoked_at });
    return { blob: insertPdf(print), filename: `degree-insert-${print.degree.short_id}.pdf` };
  }
  return null;
}
