import fs from "node:fs";
import path from "node:path";
import { test as base, expect, request, type APIRequestContext, type APIResponse, type BrowserContext, type Locator, type Page } from "@playwright/test";

/*
 * Shared pieces of the demo-path tests: where the stack lives, the demo
 * users, sign-in, Mailpit and the notice links, and a small valid PDF.
 * Every address can be moved with an environment variable; the defaults
 * are the compose ports.
 */

const trim = (url: string) => url.replace(/\/+$/, "");

export const WEB_URL = trim(process.env.E2E_BASE_URL ?? "http://localhost:3000");
export const API_URL = trim(process.env.E2E_API_URL ?? "http://localhost:8000");
export const MAILPIT_URL = trim(process.env.E2E_MAILPIT_URL ?? "http://localhost:8025");
export const MOCKGOV_URL = trim(process.env.E2E_MOCKGOV_URL ?? "http://localhost:8001");
const PASSWORD = process.env.E2E_PASSWORD ?? "Countersign!2026";

/** The seeded demo users (ARCHITECTURE section 7), their landing route and the name on their user menu. */
export const ROLES = {
  admin: { email: "admin@aicte.demo", home: "/aicte", menu: "Admin" },
  ro: { email: "ro.west@aicte.demo", home: "/ro", menu: "RO" },
  registrar: { email: "registrar@abc.edu.demo", home: "/college", menu: "Registrar" },
  student: { email: "student@demo", home: "/student", menu: "Ravi" },
  university: { email: "coe@univ.demo", home: "/university", menu: "COE" },
} as const;
export type Role = keyof typeof ROLES;

export const ABC = { permanentId: "1-ABC-0001", name: "ABC College of Engineering" };

/**
 * The notices the seed leaves unanswered for the live demo (datagen
 * manifest `demo_unanswered_notices`): Ravi answers Yes, the second student
 * answers No through the DigiLocker inbox.
 */
export const DEMO = {
  ravi: { name: "Ravi Kumar Sharma", apaarLast4: "4417" },
  second: {
    name: process.env.E2E_SECOND_NOTICE_NAME ?? "Xavier Paul",
    apaarId: process.env.E2E_SECOND_NOTICE_APAAR ?? "815283767032",
  },
};

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
    const res = await withRateLimit(() => api.post("/auth/login", { data: { email: ROLES[role].email, password: PASSWORD } }));
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

type Fixtures = {
  /** A page signed in as the role: one browser context per role per test, closed afterwards. */
  pageAs: (role: Role) => Promise<Page>;
  /** A page in a new context with no cookies, as a verifier or a student opening a link. */
  freshPage: () => Promise<Page>;
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
});

export { expect };

/** Records that a test took its path for a stack an earlier run already used, in the report and on the console. */
export function note(description: string): void {
  base.info().annotations.push({ type: "note", description });
  console.log(`note: ${description}`);
}

/** GET or POST on the api through the web's `/api` rewrite, with the page's own session. */
export async function apiJson<T>(page: Page, method: "GET" | "POST", url: string, data?: unknown): Promise<T> {
  const res = await withRateLimit(() => (method === "GET" ? page.request.get(`/api${url}`) : page.request.post(`/api${url}`, { data: data ?? {} })));
  expect(res.ok(), `${method} ${url}: ${res.status()} ${await res.text()}`).toBeTruthy();
  return (await res.json()) as T;
}

/* ---- Shapes read from the api (API_CONTRACT Addenda 2 and 3, only the fields used here) ---- */

export interface Paged<T> {
  items: T[];
  total: number;
}

export interface FlagRow {
  id: string;
  type: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  status: string;
  enrolment_id: string | null;
  summary: string;
}

export interface FlagDetail extends FlagRow {
  evidence: { summary: string; facts: { label: string; value: string | number }[] };
  enrolment: { id: string; student: { name: string } } | null;
  related_enrolments: { id: string; student: { name: string } }[];
}

export interface EnrolmentRow {
  id: string;
  student: { name: string; apaar_masked: string | null };
  programme_code: string;
  academic_year: string;
  status: string;
}

export interface EnrolmentNotice {
  id: string;
  channel: "EMAIL" | "DIGILOCKER";
  state: string;
  response: "YES" | "NO" | null;
}

export interface EnrolmentDetail {
  id: string;
  student: { name: string; apaar_masked: string | null };
  checks: { type: string; status: string; detail: { summary: string } }[];
  notices: EnrolmentNotice[];
  credentials: { id: string; kind: string; status: string }[];
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

export async function mailHeader(api: APIRequestContext, id: string, name: string): Promise<string | null> {
  const res = await api.get(`${MAILPIT_URL}/api/v1/message/${id}/headers`);
  expect(res.ok(), `Mailpit headers ${id}: ${res.status()}`).toBeTruthy();
  const headers = (await res.json()) as Record<string, string[]>;
  const key = Object.keys(headers).find((k) => k.toLowerCase() === name.toLowerCase());
  return key ? (headers[key][0] ?? null) : null;
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

export const NOTICE_SUBJECT = `${ABC.name} says you joined`;

/**
 * An ABC College email notice that still asks its question, for a run after
 * the demo notices were used. Candidates come from the officer's view (ABC
 * enrolments whose Student check is pending, with an APAAR, none of the demo
 * students); their email is found through its X-Countersign-Notice header,
 * and its link must still open an unanswered notice.
 */
export async function findOpenAbcNotice(
  officer: Page,
  api: APIRequestContext,
  options: { skipApaarLast4: string[] },
): Promise<{ enrolmentId: string; apaarMasked: string; token: string } | null> {
  const institution = await abcId(officer);
  const list = await apiJson<Paged<EnrolmentRow>>(
    officer,
    "GET",
    `/institutions/${institution}/enrolments?academic_year=2026-27&status=ACTIVE&check_type=STUDENT&check_status=PENDING&page_size=60`,
  );
  const wanted = new Map<string, { enrolmentId: string; apaarMasked: string }>();
  for (const row of list.items) {
    const masked = row.student.apaar_masked;
    if (!masked || options.skipApaarLast4.some((d) => masked.endsWith(d))) continue;
    const detail = await apiJson<EnrolmentDetail>(officer, "GET", `/enrolments/${row.id}`);
    for (const n of detail.notices) {
      if (n.channel === "EMAIL" && n.state === "AWAITING" && n.response === null) wanted.set(n.id, { enrolmentId: row.id, apaarMasked: masked });
    }
    if (wanted.size >= 8) break;
  }
  if (wanted.size === 0) return null;
  for (let start = 0; ; start += 100) {
    const { messages } = await searchMail(api, `subject:"${NOTICE_SUBJECT}"`, start, 100);
    if (messages.length === 0) return null;
    for (const m of messages) {
      const noticeId = await mailHeader(api, m.ID, "X-Countersign-Notice");
      const hit = noticeId ? wanted.get(noticeId) : undefined;
      if (!hit) continue;
      const token = noticeToken(await mailText(api, m.ID));
      if (!token) continue;
      const { notice } = await readNotice(api, token);
      if (notice && notice.response === null) return { ...hit, token };
    }
  }
}

/* ---- Tables ---- */

/** A body cell of `row`, found by its column heading in `table`. */
export async function cellIn(table: Locator, row: Locator, heading: string): Promise<Locator> {
  const headings = (await table.locator("thead th").allInnerTexts()).map((h) => h.trim());
  const index = headings.indexOf(heading);
  expect(index, `column "${heading}" in ${headings.join(", ")}`).toBeGreaterThanOrEqual(0);
  return row.locator("td").nth(index);
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
