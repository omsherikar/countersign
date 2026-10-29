import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { test as base, expect, request, type APIRequestContext, type APIResponse, type BrowserContext, type Locator, type Page } from "@playwright/test";

/*
 * Shared pieces of the demo-path tests: where the stack lives, the demo
 * users and the Demo DigiLocker accounts, sign-in, Mailpit and the notice
 * links, the record card, and a small valid PDF. Every address can be moved
 * with an environment variable; the defaults are the compose ports.
 */

const trim = (url: string) => url.replace(/\/+$/, "");

export const WEB_URL = trim(process.env.E2E_BASE_URL ?? "http://localhost:3000");
export const API_URL = trim(process.env.E2E_API_URL ?? "http://localhost:8000");
export const MAILPIT_URL = trim(process.env.E2E_MAILPIT_URL ?? "http://localhost:8025");
export const MOCKGOV_URL = trim(process.env.E2E_MOCKGOV_URL ?? "http://localhost:8001");
/** The shared demo password of the seeded users; students have none. */
export const DEMO_PASSWORD = process.env.E2E_PASSWORD ?? "Countersign!2026";

/** The seeded password users (ARCHITECTURE section 7), their landing route and the name on their user menu. Students have no password. */
export const ROLES = {
  admin: { email: "admin@aicte.demo", home: "/aicte", menu: "Admin" },
  ro: { email: "ro.west@aicte.demo", home: "/ro", menu: "RO" },
  registrar: { email: "registrar@abc.edu.demo", home: "/college", menu: "Registrar" },
  university: { email: "coe@univ.demo", home: "/university", menu: "COE" },
} as const;
export type Role = keyof typeof ROLES;

export const ABC = { permanentId: "1-ABC-0001", name: "ABC College of Engineering" };

/** A Demo DigiLocker account, found on the sign-in page by its DigiLocker id or by name, and told apart by its masked APAAR. */
export interface DigiLockerAccount {
  name: string;
  digilockerId?: string;
  apaarLast4?: string | null;
}

interface ManifestAccount {
  role: string;
  digilocker_id: string;
  name: string;
  apaar_id: string | null;
}

/**
 * The datagen manifest of the running stack: `E2E_MANIFEST` names a copy of
 * it, else it is read from the compose volume through the api container.
 * Null when neither works; the cast below then falls back to the seed-42
 * defaults.
 */
function readManifest(): { demo_digilocker_accounts?: ManifestAccount[]; late_colleges?: string[]; overdue_colleges?: string[] } | null {
  try {
    if (process.env.E2E_MANIFEST) return JSON.parse(fs.readFileSync(process.env.E2E_MANIFEST, "utf8"));
    const compose = process.env.E2E_COMPOSE_FILE ?? path.resolve(__dirname, "../../../docker-compose.yml");
    const out = execFileSync("docker", ["compose", "-f", compose, "exec", "-T", "api", "cat", "/data/generated/manifest.json"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 30_000,
    });
    return JSON.parse(out);
  } catch {
    return null;
  }
}

const manifest = readManifest();
const accounts = manifest?.demo_digilocker_accounts ?? [];

/** The colleges datagen planted as late (first upload after the reporting deadline) and overdue (no upload at all), by AICTE permanent id. */
export const DEADLINES = {
  late: manifest?.late_colleges ?? ["1-7477495668", "1-9039728558"],
  overdue: manifest?.overdue_colleges ?? ["1-2440634806"],
};
function cast(role: string, fallback: { name: string; digilockerId: string; apaarId: string | null }) {
  const found = accounts.find((a) => a.role === role);
  const { name, digilockerId, apaarId } = found ? { name: found.name, digilockerId: found.digilocker_id, apaarId: found.apaar_id } : fallback;
  return { name, digilockerId, apaarId, apaarLast4: apaarId ? apaarId.slice(-4) : null };
}

/**
 * The demo cast, from the datagen manifest (`demo_digilocker_accounts`):
 * Ravi and Xavier keep their notices unanswered for the live demo, Priyanka
 * has no APAAR and claims her record by provisional ID, Jigna is "someone
 * else", and Vinayak is the deck's sample record card (`sample_card`).
 */
export const DEMO = {
  ravi: cast("DEMO_STUDENT", { name: "Ravi Kumar Sharma", digilockerId: "DL-RAVI-4417", apaarId: "123456784417" }) as Cast & { apaarLast4: string },
  xavier: cast("SECOND_DEMO_NOTICE", { name: "Xavier Paul", digilockerId: "DL-8JBQ-T7KG", apaarId: "815283767032" }) as Cast & { apaarId: string; apaarLast4: string },
  priyanka: cast("PROVISIONAL_CLAIM", { name: "Priyanka Salunkhe", digilockerId: "DL-K9A5-Y8KV", apaarId: null }),
  someoneElse: cast("SOMEONE_ELSE", { name: "Jigna Mehul Bhatt", digilockerId: "DL-QXWH-ZBMM", apaarId: "268855385429" }) as Cast & { apaarLast4: string },
  sample: cast("SAMPLE_CARD", { name: "Vinayak Akshay Chavan", digilockerId: "DL-48YV-XAWA", apaarId: "274678934159" }) as Cast & { apaarLast4: string },
};
type Cast = ReturnType<typeof cast>;

/** The Demo DigiLocker's OTP, always the same (API_CONTRACT C.11). */
export const DEMO_OTP = "123456";

const AUTH_DIR = path.join(__dirname, ".auth");
export const authFile = (role: Role) => path.join(AUTH_DIR, `${role}.json`);

/** A word that marks what one run wrote, so a second run never reads the first run's notes. */
export const RUN = `run ${new Date().toISOString().slice(11, 19).replace(/:/g, "")}`;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function retryAfter(res: APIResponse): Promise<number> {
  try {
    const body = (await res.json()) as { error?: { details?: { retry_after?: number } } };
    const seconds = body.error?.details?.retry_after;
    if (typeof seconds === "number") return seconds;
  } catch {
    // Not the error envelope; fall back to a full window.
  }
  return 60;
}

/** Calls `send` again after a 429, as long as the api asks for a short wait. */
export async function withRateLimit(send: () => Promise<APIResponse>, tries = 3): Promise<APIResponse> {
  let res = await send();
  for (let i = 1; i < tries && res.status() === 429; i++) {
    await sleep((Math.min(await retryAfter(res), 65) + 1) * 1000);
    res = await send();
  }
  return res;
}

/**
 * Signs in through the api and stores the session cookie for the web host.
 * The api sets a host-only cookie, so the same cookie works on the web's
 * origin; signing in on the api's own address keeps these sign-ins apart
 * from the ones the login test makes through the web (10 a minute each).
 */
export async function signIn(role: Role): Promise<void> {
  const api = await request.newContext({ baseURL: API_URL });
  try {
    // the full address, so an api served under a path (https://host/api) keeps its prefix
    const res = await withRateLimit(() => api.post(`${API_URL}/auth/login`, { data: { email: ROLES[role].email, password: DEMO_PASSWORD } }));
    expect(res.status(), `sign in as ${ROLES[role].email}: ${await res.text()}`).toBe(200);
    const state = await api.storageState();
    const host = new URL(WEB_URL).hostname;
    const cookies = state.cookies.filter((c) => c.name === "cs_access").map((c) => ({ ...c, domain: host }));
    expect(cookies, `no session cookie for ${ROLES[role].email}`).toHaveLength(1);
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    fs.writeFileSync(authFile(role), JSON.stringify({ cookies, origins: [] }, null, 2));
  } finally {
    await api.dispose();
  }
}

/* ---- The Demo DigiLocker (mockgov /digilocker/oauth/authorize) ---- */

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** The account's radio on the Demo DigiLocker page: "Ravi Kumar Sharma DL-RAVI-4417 · APAAR XXXX XXXX 4417". */
export function accountRadio(page: Page, who: DigiLockerAccount): Locator {
  const id = who.digilockerId ? escapeRe(who.digilockerId) : "DL-[0-9A-Z]{4}-[0-9A-Z]{4}";
  const apaar = who.apaarLast4 === undefined ? ".*" : who.apaarLast4 === null ? "No APAAR linked" : `APAAR XXXX XXXX ${who.apaarLast4}`;
  return page.getByRole("radio", { name: new RegExp(`^${escapeRe(who.name)} ${id} · ${apaar}$`) });
}

/**
 * On the Demo DigiLocker page: finds the account (by DigiLocker id, or by
 * name), picks it, types the demo OTP and signs in. The browser then goes
 * back to Countersign's callback.
 */
export async function digiLockerSignIn(page: Page, who: DigiLockerAccount): Promise<void> {
  await expect(page.getByRole("heading", { level: 1, name: /^Demo DigiLocker\./ })).toBeVisible();
  await page.getByLabel("Find an account by DigiLocker id or APAAR").fill(who.digilockerId ?? who.name);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const account = accountRadio(page, who);
  await expect(account, `the Demo DigiLocker lists ${who.name}`).toHaveCount(1);
  await account.check();
  await page.getByLabel("One-time password").fill(DEMO_OTP);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
}

/** Waits until the DigiLocker callback and the return page have handed the browser to `next` on the web. */
export async function backOnCountersign(page: Page, next: string): Promise<void> {
  const want = new URL(next, WEB_URL);
  await page.waitForURL((url) => url.origin === want.origin && url.pathname === want.pathname, { timeout: 60_000 });
}

/** The page a student lands on: through `/api/auth/digilocker/start?next=`, the Demo DigiLocker, and back to `next`. */
export async function studentSignIn(page: Page, who: DigiLockerAccount, next = "/student"): Promise<void> {
  await page.goto(`/api/auth/digilocker/start?next=${encodeURIComponent(next)}`);
  await digiLockerSignIn(page, who);
  await backOnCountersign(page, next);
}

type Fixtures = {
  /** A page signed in as the role: one browser context per role per test, closed afterwards. */
  pageAs: (role: Role) => Promise<Page>;
  /** A page in a new context with no cookies, as a verifier or a student opening a link. */
  freshPage: () => Promise<Page>;
  /** A page in a new context, signed in as a student through the Demo DigiLocker and left on `next`. */
  studentAs: (who: DigiLockerAccount, next?: string) => Promise<Page>;
};

export const test = base.extend<Fixtures>({
  pageAs: async ({ browser, baseURL, viewport, locale, timezoneId }, provide) => {
    const open = new Map<Role, BrowserContext>();
    await provide(async (role) => {
      let context = open.get(role);
      if (!context) {
        context = await browser.newContext({ storageState: authFile(role), baseURL, viewport, locale, timezoneId });
        open.set(role, context);
      }
      return context.pages()[0] ?? context.newPage();
    });
    for (const context of open.values()) await context.close();
  },
  freshPage: async ({ browser, baseURL, viewport, locale, timezoneId }, provide) => {
    const open: BrowserContext[] = [];
    await provide(async () => {
      const context = await browser.newContext({ baseURL, viewport, locale, timezoneId });
      open.push(context);
      return context.newPage();
    });
    for (const context of open) await context.close();
  },
  studentAs: async ({ browser, baseURL, viewport, locale, timezoneId }, provide) => {
    const open: BrowserContext[] = [];
    await provide(async (who, next = "/student") => {
      const context = await browser.newContext({ baseURL, viewport, locale, timezoneId });
      open.push(context);
      const page = await context.newPage();
      await studentSignIn(page, who, next);
      return page;
    });
    for (const context of open) await context.close();
  },
});

export { expect };

/** Records that a test took its path for a stack an earlier run already used, in the report and on the console. */
export function note(description: string): void {
  base.info().annotations.push({ type: "note", description });
  console.log(`note: ${description}`);
}

/** GET or POST on the api through the web's `/api` rewrite, with the page's own session. */
export async function apiJson<T>(page: Page, method: "GET" | "POST", url: string, data?: unknown): Promise<T> {
  // A dev stack under load can take a while on a large list; a request waits up to a minute.
  const res = await withRateLimit(() =>
    method === "GET" ? page.request.get(`/api${url}`, { timeout: 60_000 }) : page.request.post(`/api${url}`, { data: data ?? {}, timeout: 60_000 }),
  );
  expect(res.ok(), `${method} ${url}: ${res.status()} ${await res.text()}`).toBeTruthy();
  return (await res.json()) as T;
}

/* ---- Shapes read from the api (API_CONTRACT Addenda 2 to 4, only the fields used here) ---- */

export interface Paged<T> {
  items: T[];
  total: number;
}

export type RecordStatus = "AWAITING_EVIDENCE" | "COUNTERSIGNED" | "UNDER_REVIEW" | "DISPUTED";
export type RowType = "IDENTITY" | "SEAT" | "ADMISSION" | "STUDYING" | "STUDENT";

/** The status words of the legend (copy deck `record_status.*`). */
export const STATUS_WORD: Record<RecordStatus, string> = {
  AWAITING_EVIDENCE: "Awaiting evidence",
  COUNTERSIGNED: "Countersigned",
  UNDER_REVIEW: "Under review",
  DISPUTED: "Disputed",
};

export interface FlagRow {
  id: string;
  type: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  status: string;
  enrolment_id: string | null;
  programme: { code: string } | null;
  academic_year: string;
  summary: string;
  covers: RowType | null;
  scope: "RECORD" | "MULTI_RECORD" | "INSTITUTION";
}

export interface FlagDetail extends FlagRow {
  evidence: { summary: string; facts: { label: string; value: string | number }[] };
  enrolment: { id: string; student: { name: string } } | null;
  related_enrolments: { id: string; student: { name: string } }[];
  allowed_actions: string[];
}

export interface RowBrief {
  type: RowType;
  state: string;
  finding: string | null;
  independent: boolean;
  resolved: boolean;
}

export interface EnrolmentRow {
  id: string;
  student: { name: string; apaar_masked: string | null; provisional_id: string | null };
  programme_code: string;
  academic_year: string;
  cohort_year: string;
  year_of_study: number;
  seat_code: string | null;
  status: string;
  record_status: RecordStatus | null;
  next_step: string | null;
  checks: RowBrief[];
  flags: { id: string; type: string; status: string }[];
}

export interface EvidenceRow {
  type: RowType;
  state: string;
  finding: string | null;
  source_line: string;
  supplied_by: string;
  independent: boolean;
  resolved: { outcome: string; line: string } | null;
}

export interface EnrolmentNotice {
  id: string;
  channel: "EMAIL" | "DIGILOCKER";
  state: string;
  response: "YES" | "NO" | null;
}

export interface Credential {
  id: string;
  kind: "ENROLMENT" | "COMPLETION";
  status: "ACTIVE" | "REVOKED" | "EXPIRED";
  short_id: string;
  revoked_reason_code: string | null;
}

export interface EnrolmentDetail {
  id: string;
  status: string;
  record_status: RecordStatus | null;
  status_reason: string | null;
  next_step: string | null;
  student: { name: string; apaar_masked: string | null; provisional_id: string | null };
  programme: { code: string };
  cohort_year: string;
  seat: { seat_code: string } | null;
  claim: { claimed: boolean; claimed_at: string | null } | null;
  checks: EvidenceRow[];
  notices: EnrolmentNotice[];
  credentials: Credential[];
  flags: { id: string; type: string; status: string }[];
}

export interface NoticePublic {
  institution_name: string;
  programme_code: string;
  academic_year: string;
  id_kind: "APAAR" | "PROVISIONAL";
  id_masked: string;
  response: "YES" | "NO" | null;
}

/** ABC College of Engineering's id, read as the signed-in officer. */
export async function abcId(page: Page): Promise<string> {
  const list = await apiJson<Paged<{ id: string; aicte_permanent_id: string }>>(page, "GET", `/institutions?q=${encodeURIComponent("ABC College")}&page_size=10`);
  const abc = list.items.find((i) => i.aicte_permanent_id === ABC.permanentId);
  expect(abc, "ABC College of Engineering is seeded").toBeTruthy();
  return abc!.id;
}

/** ABC College enrolments of 2026-27 whose student name matches `q`. */
export async function abcEnrolments(page: Page, query: string): Promise<EnrolmentRow[]> {
  const institution = await abcId(page);
  const list = await apiJson<Paged<EnrolmentRow>>(page, "GET", `/institutions/${institution}/enrolments?academic_year=2026-27&${query}&page_size=100`);
  return list.items;
}

/** The one ABC College 2026-27 enrolment of the named student (and APAAR ending, when given). */
export async function abcEnrolmentOf(page: Page, name: string, apaarLast4?: string | null): Promise<EnrolmentRow> {
  const rows = (await abcEnrolments(page, `q=${encodeURIComponent(name)}`)).filter(
    (e) => e.student.name === name && (apaarLast4 === undefined || (apaarLast4 === null ? e.student.apaar_masked === null : e.student.apaar_masked?.endsWith(apaarLast4))),
  );
  expect(rows, `${name} is enrolled at ${ABC.name} in 2026-27`).toHaveLength(1);
  return rows[0];
}

/* ---- Mailpit (http://localhost:8025/api/v1) ---- */

export interface MailSummary {
  ID: string;
  Subject: string;
  To: { Address: string }[];
}

export async function searchMail(api: APIRequestContext, query: string, start = 0, limit = 100): Promise<{ messages: MailSummary[]; total: number }> {
  const res = await api.get(`${MAILPIT_URL}/api/v1/search`, { params: { query, start: String(start), limit: String(limit) } });
  expect(res.ok(), `Mailpit search "${query}": ${res.status()}`).toBeTruthy();
  const body = (await res.json()) as { messages: MailSummary[] | null; messages_count?: number; total?: number };
  return { messages: body.messages ?? [], total: body.messages_count ?? body.total ?? 0 };
}

export async function mailText(api: APIRequestContext, id: string): Promise<string> {
  const res = await api.get(`${MAILPIT_URL}/api/v1/message/${id}`);
  expect(res.ok(), `Mailpit message ${id}: ${res.status()}`).toBeTruthy();
  return ((await res.json()) as { Text: string }).Text;
}

/** The notice token in a message: the link is `{WEB_ORIGIN}/student/notices/{token}` and only exists there. */
export function noticeToken(text: string): string | null {
  return text.match(/\/student\/notices\/([A-Za-z0-9_-]{20,})/)?.[1] ?? null;
}

/** The public notice as the student's link opens it, straight from the api (its own 30 a minute). */
export async function readNotice(api: APIRequestContext, token: string): Promise<{ status: number; notice: NoticePublic | null }> {
  const res = await withRateLimit(() => api.get(`${API_URL}/notices/${token}`));
  return { status: res.status(), notice: res.ok() ? ((await res.json()) as NoticePublic) : null };
}

/** The subject of every ABC College notice email (copy deck `notice.email_subject`). */
export const NOTICE_SUBJECT = `${ABC.name} has reported an enrolment in your name`;

/** An unanswered notice: its token, the record it is about and the student who may answer it. */
export interface OpenNotice {
  token: string;
  enrolmentId: string;
  student: DigiLockerAccount & { apaarLast4: string };
  programmeCode: string;
}

/**
 * The ABC College notice email of a signed-in student, read from Mailpit:
 * the student's address comes from their own home (`GET /students/me`), and
 * the notice must be about the record with this APAAR ending (the
 * "R. K. Sharma" row shares Ravi's address but carries a provisional id).
 */
export async function abcNoticeEmail(student: Page, api: APIRequestContext, apaarLast4: string): Promise<{ email: string; token: string | null; answered: boolean; text: string }> {
  const { email } = await apiJson<{ email: string }>(student, "GET", "/students/me");
  const { messages } = await searchMail(api, `to:"${email}"`);
  let answered = false;
  for (const m of messages) {
    const text = await mailText(api, m.ID);
    const token = noticeToken(text);
    if (!token) continue;
    const { notice } = await readNotice(api, token);
    if (!notice || notice.institution_name !== ABC.name || notice.id_kind !== "APAAR" || !notice.id_masked.endsWith(apaarLast4)) continue;
    if (notice.response === null) return { email, token, answered: false, text };
    answered = true;
  }
  return { email, token: null, answered, text: "" };
}

/**
 * An ABC College email notice that still asks its question, for a run after
 * the demo notices were used. Candidates come from the officer's view: ABC
 * records of the 2026-27 intake that are Countersigned, hold a seat, carry an APAAR, have
 * an email notice still awaiting an answer, and are none of the demo students
 * and in none of `skipProgrammes`. The candidate signs in through the Demo
 * DigiLocker so that their address, and so their email, can be found.
 */
export async function findOpenAbcNotice(
  officer: Page,
  api: APIRequestContext,
  signInAs: (who: DigiLockerAccount) => Promise<Page>,
  options: { skipApaarLast4: string[]; skipProgrammes?: string[] },
): Promise<OpenNotice | null> {
  const skip = [...options.skipApaarLast4, DEMO.ravi.apaarLast4, DEMO.xavier.apaarLast4, DEMO.someoneElse.apaarLast4, DEMO.sample.apaarLast4];
  const rows = await abcEnrolments(officer, "status=ACTIVE&record_status=COUNTERSIGNED");
  let tried = 0;
  for (const row of rows) {
    const masked = row.student.apaar_masked;
    if (!masked || !row.seat_code || skip.some((d) => masked.endsWith(d))) continue;
    // The 2026-27 intake, as the demo's own students, so a withdrawal shows in that year's Seat Ledger.
    if (row.cohort_year !== "2026-27" || options.skipProgrammes?.includes(row.programme_code)) continue;
    if (row.flags.length > 0 || row.checks.find((c) => c.type === "STUDENT")?.state !== "PENDING") continue;
    const detail = await apiJson<EnrolmentDetail>(officer, "GET", `/enrolments/${row.id}`);
    if (!detail.notices.some((n) => n.channel === "EMAIL" && n.state === "AWAITING" && n.response === null)) continue;
    const student = { name: row.student.name, apaarLast4: masked.slice(-4) };
    const found = await abcNoticeEmail(await signInAs(student), api, student.apaarLast4);
    if (found.token) return { token: found.token, enrolmentId: row.id, programmeCode: row.programme_code, student };
    if (++tried >= 3) return null;
  }
  return null;
}

/* ---- The record card (W4-1) ---- */

/** The deck's record card on an enrolment page or the student's home. */
export function recordCard(page: Page): Locator {
  return page.getByRole("region", { name: /^Record card for / });
}

/**
 * One row of the card as the deck draws it: the row label, the evidence
 * state with its finding, and the source and date with the independence
 * marker. The cells are what a reader sees (the row's sentence for screen
 * readers sits in its header).
 */
export function cardRow(card: Locator, label: "Identity" | "Seat" | "Joining record" | "Credits" | "Student"): { row: Locator; state: Locator; source: Locator } {
  const row = card.locator("tbody tr").filter({ has: card.page().getByRole("rowheader", { name: new RegExp(`^${label}: `) }) });
  return { row, state: row.locator("td").nth(0), source: row.locator("td").nth(1) };
}

/** The card's footer: the status line, the reason, then the legend. */
export function cardFooter(card: Locator): Locator {
  return card.locator("footer");
}

/** The footer's first line: "Status: Disputed (priority). Next step: ...". */
export function cardStatusLine(card: Locator): Locator {
  return card.locator("footer > p").first();
}

/**
 * The status the evidence rule (API_CONTRACT §A4.3) gives a record from its
 * rows and the cases naming it. An upheld row stays Contradicted and only
 * stops counting as unresolved; it is never evidence itself.
 */
export function ruleStatus(record: EnrolmentDetail): RecordStatus {
  const row = (type: string) => record.checks.find((c) => c.type === type);
  const unresolved = (c?: { state: string; resolved: unknown }) => c?.state === "CONTRADICTED" && !c.resolved;
  const openCases = record.flags.filter((f) => ["OPEN", "DOCS_REQUESTED", "ESCALATED"].includes(f.status));
  if (unresolved(row("STUDENT")) && openCases.some((f) => f.type === "STUDENT_DENIED")) return "DISPUTED";
  if (record.checks.some(unresolved) || openCases.length > 0) return "UNDER_REVIEW";
  const identity = row("IDENTITY")?.state === "CONFIRMED";
  const seat = row("SEAT")?.state === "CONFIRMED";
  const independent = ["ADMISSION", "STUDYING", "STUDENT"].some((t) => row(t)?.state === "CONFIRMED" && row(t)?.independent);
  return identity && seat && independent ? "COUNTERSIGNED" : "AWAITING_EVIDENCE";
}

/* ---- Attestations (W3-2, W3-4) ---- */

/** Six groups of four Crockford base32 characters (A3.15). */
export const SHARE_CODE = /^[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){5}$/;

/**
 * Shares three fields of the wallet's active enrolment attestation: the two
 * that are always shared and the academic year. Returns the share code and
 * the attestation's id.
 */
export async function shareThreeFields(wallet: Page): Promise<{ code: string; credentialId: string }> {
  const attestation = wallet.getByRole("region", { name: "Enrolment attestation" }).filter({ has: wallet.getByRole("button", { name: "Share attestation" }) });
  await expect(attestation).toHaveCount(1);
  await expect(attestation.getByText("Active", { exact: true })).toBeVisible();
  await attestation.getByRole("button", { name: "Share attestation" }).click();

  const sheet = wallet.getByRole("dialog", { name: "Share this attestation" });
  await expect(sheet.getByRole("checkbox", { name: "Institution (always shared)" })).toBeChecked();
  await expect(sheet.getByRole("checkbox", { name: "Programme (always shared)" })).toBeChecked();
  await expect(sheet.getByText("Shares 2 of 8 fields")).toBeVisible();
  await sheet.getByRole("checkbox", { name: "Academic year", exact: true }).check();
  await expect(sheet.getByText("Shares 3 of 8 fields")).toBeVisible();
  await sheet.getByRole("checkbox", { name: "I agree" }).check();

  const created = wallet.waitForResponse((r) => /^\/api\/credentials\/[^/]+\/present$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
  await sheet.getByRole("button", { name: "Create QR" }).click();
  const response = await created;
  expect(response.status()).toBe(201);
  const body = (await response.json()) as { code: string; disclosed: string[] };
  expect(body.disclosed).toEqual(["institution", "programme", "academic_year"]);

  await expect(sheet.getByRole("img", { name: /^QR code for your attestation/ })).toBeVisible();
  const code = sheet.getByText(SHARE_CODE).first();
  await expect(code).toHaveText(body.code);
  return { code: body.code, credentialId: new URL(response.url()).pathname.split("/")[3] };
}

/** A verifier with no account opens the share code and sees a valid attestation with exactly these fields, and nothing about the student. */
export async function expectValidShare(verifier: Page, code: string, fields: [string, string | RegExp][], hidden: string[]): Promise<void> {
  await verifier.goto(`/verify/${code}`);
  const result = verifier.getByRole("region", { name: "Valid attestation" });
  await expect(result.getByRole("heading", { level: 1 })).toHaveText("Valid attestation");
  await expect(result.getByRole("term")).toHaveText(fields.map(([term]) => term));
  await expect(result.getByRole("definition")).toHaveText(fields.map(([, value]) => value));
  for (const text of hidden) await expect(verifier.getByText(text)).toHaveCount(0);
}

/* ---- Tables ---- */

/** A body cell of `row`, found by its column heading in `table`. */
export async function cellIn(table: Locator, row: Locator, heading: string): Promise<Locator> {
  const headings = (await table.locator("thead th").allInnerTexts()).map((h) => h.trim());
  const index = headings.indexOf(heading);
  expect(index, `column "${heading}" in ${headings.join(", ")}`).toBeGreaterThanOrEqual(0);
  return row.locator("td").nth(index);
}

/** A whole number from a cell such as "132", "12 unseated" or "120v2". */
export async function numberIn(cell: Locator): Promise<number> {
  const text = (await cell.innerText()).replace(/,/g, "");
  const match = text.match(/\d+/);
  expect(match, `a number in "${text}"`).not.toBeNull();
  return Number(match![0]);
}

/* ---- A small, valid PDF ---- */

/** One A4 page with a line of Helvetica text; the byte offsets in the xref table are exact. */
export function minimalPdf(line: string): Buffer {
  const text = line.replace(/[()\\]/g, "");
  const stream = `BT /F1 14 Tf 72 770 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream, "latin1")} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, i) => {
    offsets.push(Buffer.byteLength(pdf, "latin1"));
    pdf += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = Buffer.byteLength(pdf, "latin1");
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, "latin1");
}
