/**
 * Mock-mode evidence rows and the record status (API_CONTRACT A4.2 to A4.4,
 * copy deck §15 and §21). Rows are written with the sentences the api writes
 * (finding, source line, detail), and the status, its reason and the next
 * step follow the A4.3 rule, first match wins:
 * Disputed, Under review, Countersigned, Awaiting evidence.
 */
import { ROW_ORDER } from "@/lib/types";
import type {
  CheckDetail,
  CheckSource,
  CheckType,
  DocsKind,
  EvidenceRow,
  EvidenceRowBrief,
  EvidenceState,
  FlagStatus,
  FlagType,
  RecordFields,
  RecordStatus,
  Severity,
} from "@/lib/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const IST_MS = 330 * 60_000;

/** The calendar date in IST of a `YYYY-MM-DD` date or an ISO timestamp. */
function istParts(value: string): { y: number; m: number; d: number } {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-").map(Number);
    return { y, m, d };
  }
  const t = new Date(new Date(value).getTime() + IST_MS);
  return { y: t.getUTCFullYear(), m: t.getUTCMonth() + 1, d: t.getUTCDate() };
}

/** Dates inside row, status and next-step sentences: "12 Aug" this year, "12 Aug 2025" otherwise (A4.1). */
export function sentenceDate(value: string | null | undefined): string {
  if (!value) return "";
  const { y, m, d } = istParts(value);
  const thisYear = istParts(new Date().toISOString()).y;
  return y === thisYear ? `${d} ${MONTHS[m - 1]}` : `${d} ${MONTHS[m - 1]} ${y}`;
}

/** Today in IST as YYYY-MM-DD. */
export function todayIst(): string {
  const { y, m, d } = istParts(new Date().toISOString());
  return `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export interface RowSpec {
  state: EvidenceState;
  finding?: string | null;
  source_line: string;
  summary: string;
  basis: string;
  source: CheckSource;
  supplied_by?: string;
  observed_at?: string | null;
  independent?: boolean;
  attempts?: number;
  checked_at?: string | null;
  detail?: Partial<CheckDetail>;
}

/** One full row; `finding`, `source_line` and `summary` are stored in `detail` too, as the api stores them. */
export function makeRow(type: CheckType, spec: RowSpec, checkedAt: string): EvidenceRow {
  const finding = spec.finding ?? null;
  return {
    type,
    state: spec.state,
    finding,
    source_line: spec.source_line,
    summary: spec.summary,
    supplied_by: spec.supplied_by ?? "",
    observed_at: spec.observed_at ?? null,
    independent: spec.independent ?? false,
    resolved: null,
    source: spec.source,
    checked_at: spec.checked_at === undefined ? checkedAt : spec.checked_at,
    attempts: spec.attempts ?? 0,
    detail: { ...spec.detail, summary: spec.summary, finding, source_line: spec.source_line, basis: spec.basis },
  };
}

/** The brief form lists carry, in row order. */
export function briefOf(rows: EvidenceRow[]): EvidenceRowBrief[] {
  return ordered(rows).map((r) => ({ type: r.type, state: r.state, finding: r.finding, independent: r.independent, resolved: r.resolved !== null }));
}

export function ordered<T extends { type: CheckType }>(rows: T[]): T[] {
  return ROW_ORDER.map((t) => rows.find((r) => r.type === t)).filter((r): r is T => Boolean(r));
}

/* ---- The record status (A4.3) -------------------------------------------- */

/** What the rule reads from a case naming the record. */
export interface CaseView {
  id: string;
  type: FlagType;
  severity: Severity;
  status: FlagStatus;
  created_at: string;
  docs: { kind: DocsKind; due_on: string | null; responded_at: string | null } | null;
  escalated_at: string | null;
}

export interface RecordContext {
  /** When the latest notice reached the student, for `next_step.student`. */
  noticeSentAt: string | null;
  /** The issuer of the student's latest credits, else the affiliating university. */
  issuerName: string;
  /** The reporting deadline of the joining year, `YYYY-MM-DD`. */
  deadline: string;
  /** The next semester whose credits are expected. */
  nextSemester: number;
}

const UNRESOLVED: FlagStatus[] = ["OPEN", "DOCS_REQUESTED", "ESCALATED"];
const RANK: Record<Severity, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
const LABEL: Record<CheckType, string> = { IDENTITY: "Identity", SEAT: "Seat", ADMISSION: "Joining record", STUDYING: "Credits", STUDENT: "Student" };
const SOURCE_NAME: Partial<Record<CheckSource, string>> = {
  APAAR: "the APAAR registry",
  ADMISSION_AUTHORITY: "the state admission authority",
  ABC: "ABC",
  SII: "Study in India",
};

/** The api writes these sentences itself, with the deck's case names and document words (§5, §6). */
const CASE_NAME: Record<FlagType, string> = {
  EXCESS_ADMISSION: "Excess admission",
  QUOTA_BREACH: "Quota breach",
  LATE_REFILL: "Late refill",
  INVALID_APAAR: "APAAR not verified",
  NAME_MISMATCH: "Name or date of birth mismatch",
  DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
  DUPLICATE_WITHIN_UPLOAD: "Duplicate within institution",
  DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
  NO_ACADEMIC_ACTIVITY: "No academic activity",
  STUDENT_DENIED: "Student dispute",
  GHOST_RING: "Shared contact ring",
  ANOMALY: "Unusual pattern",
  NOT_IN_JOINING_RECORD: "Not in joining record",
  ELIGIBILITY_BREACH: "Seat category not eligible",
  MISSING_FROM_UPLOAD: "Missing from upload",
};
const DOCS_WORDS: Record<DocsKind, string> = {
  ADMISSION: "admission documents",
  JOINING: "the joining report",
  IDENTITY: "identity documents",
  ELIGIBILITY: "eligibility certificates",
  CREDITS: "semester results",
  OTHER: "documents",
};
const caseName = (type: FlagType) => CASE_NAME[type];
const docsWords = (kind: DocsKind) => DOCS_WORDS[kind];

/** The next step a case gives (A4.3, the deciding-case table). */
function caseStep(c: CaseView): string {
  if (c.status === "ESCALATED") return `Escalated to AICTE on ${sentenceDate(c.escalated_at ?? c.created_at)}; waiting for a decision.`;
  if (c.status === "DOCS_REQUESTED" && c.docs) {
    if (c.docs.responded_at) return `College responded on ${sentenceDate(c.docs.responded_at)}; waiting for an officer's decision.`;
    if (!c.docs.due_on) return `College asked for ${docsWords(c.docs.kind)}; no reply date set.`;
    if (c.docs.due_on < todayIst()) return `College was asked for ${docsWords(c.docs.kind)} by ${sentenceDate(c.docs.due_on)}; no response yet.`;
    return `College asked for ${docsWords(c.docs.kind)} by ${sentenceDate(c.docs.due_on)}.`;
  }
  if (c.type === "STUDENT_DENIED") return "Waiting for an officer to review the student's dispute.";
  return `Waiting for an officer to review the ${caseName(c.type)} case.`;
}

const mostSevere = (cases: CaseView[]) =>
  [...cases].sort((a, b) => RANK[b.severity] - RANK[a.severity] || a.created_at.localeCompare(b.created_at))[0];

function joinAnd(words: string[]): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

/** The status, its reason and the next step, computed as the api does on every change (A4.3). */
export function recordOf(rows: EvidenceRow[], cases: CaseView[], ctx: RecordContext): Omit<RecordFields, "record_status_at"> & { record_status: RecordStatus } {
  const open = cases.filter((c) => UNRESOLVED.includes(c.status));
  const row = (t: CheckType) => rows.find((r) => r.type === t);
  const unresolvedContradiction = (r: EvidenceRow | undefined) => Boolean(r && r.state === "CONTRADICTED" && !r.resolved);

  if (rows.length === 0) {
    return { record_status: "AWAITING_EVIDENCE", status_reason: "No enrolment evidence independent of the college yet.", next_step: "Waiting for evidence independent of the college." };
  }

  const student = row("STUDENT");
  const dispute = open.find((c) => c.type === "STUDENT_DENIED");
  if (unresolvedContradiction(student) && dispute) {
    return {
      record_status: "DISPUTED",
      status_reason: `The student said they never joined, after signing in with DigiLocker on ${sentenceDate(student!.observed_at)}.`,
      next_step: caseStep(dispute),
    };
  }

  const contradicted = ordered(rows).filter(unresolvedContradiction);
  if (contradicted.length > 0 || open.length > 0) {
    const deciding = contradicted[0];
    if (deciding) {
      const named = deciding.detail.case_type ? open.find((c) => c.type === deciding.detail.case_type) : undefined;
      const caseFor = named ?? (open.length ? mostSevere(open) : undefined);
      const caseType = (deciding.detail.case_type as FlagType | undefined) ?? null;
      return {
        record_status: "UNDER_REVIEW",
        status_reason: `${LABEL[deciding.type]} is contradicted: ${deciding.finding ?? deciding.source_line}.`,
        next_step: caseFor ? caseStep(caseFor) : `Waiting for an officer to reopen the ${caseType ? caseName(caseType) : "case"} case.`,
      };
    }
    const c = mostSevere(open);
    return { record_status: "UNDER_REVIEW", status_reason: `An open ${caseName(c.type)} case names this record.`, next_step: caseStep(c) };
  }

  const identity = row("IDENTITY");
  const seat = row("SEAT");
  const identityConfirmed = Boolean(identity && (identity.state === "CONFIRMED" || (identity.state === "PENDING" && identity.detail.needs_review && identity.resolved)));
  const enrolmentRows = (["ADMISSION", "STUDYING", "STUDENT"] as CheckType[]).map(row).filter((r): r is EvidenceRow => Boolean(r));
  const independent = enrolmentRows.filter((r) => r.state === "CONFIRMED" && r.independent);
  if (identityConfirmed && seat?.state === "CONFIRMED" && independent.length > 0) {
    const words = independent.map((r) =>
      r.type === "ADMISSION" ? "the joining record" : r.type === "STUDYING" ? `credits from ${String(r.detail.issuer_name ?? ctx.issuerName)}` : "the student's own answer",
    );
    return {
      record_status: "COUNTERSIGNED",
      status_reason: `Identity, seat and ${joinAnd(words)} confirm the record, and nothing is unresolved.`,
      next_step: "None. The evidence is complete.",
    };
  }

  let reason = "No enrolment evidence independent of the college yet.";
  const upheld = rows.find((r) => r.resolved);
  if (!identityConfirmed && identity) reason = `Identity is not confirmed yet: ${identity.finding ?? identity.source_line}.`;
  else if (seat && seat.state !== "CONFIRMED") reason = `Seat is not confirmed yet: ${seat.finding ?? seat.source_line}.`;
  else if (upheld?.resolved) reason = `An officer upheld the claim on ${sentenceDate(upheld.resolved.at)}, but no evidence independent of the college confirms the record yet.`;
  else if (enrolmentRows.some((r) => r.state === "CONFIRMED" && !r.independent)) reason = "The only enrolment evidence so far comes from the college itself.";

  return { record_status: "AWAITING_EVIDENCE", status_reason: reason, next_step: nextMissing(rows, ctx) };
}

/** The first missing evidence, in the order identity, seat, joining record, credits, student (A4.3). */
function nextMissing(rows: EvidenceRow[], ctx: RecordContext): string {
  for (const r of ordered(rows)) {
    if (r.state === "CONFIRMED") continue;
    if (r.type === "IDENTITY" && r.state === "NOT_APPLICABLE") return "Waiting for the student to sign in with DigiLocker and claim this record with its provisional ID.";
    if (r.state === "NOT_APPLICABLE") continue;
    if (r.state === "SOURCE_UNAVAILABLE") return `Waiting for ${SOURCE_NAME[r.source] ?? r.supplied_by}, which did not respond; it is asked again at the next recheck.`;
    if (r.type === "SEAT" && r.state === "PENDING") return "Waiting for the college to report the TFW income certificate.";
    if (r.type === "ADMISSION" && r.state === "NOT_YET_DUE") return `Waiting for the joining record; the state admission authority publishes it by ${sentenceDate(ctx.deadline)}.`;
    if (r.type === "ADMISSION" && r.state === "PENDING") return "Waiting for the joining record from the state admission authority.";
    if (r.type === "STUDYING" && (r.state === "NOT_YET_DUE" || r.state === "PENDING")) {
      return `Waiting for credits from ${ctx.issuerName} after the semester ${ctx.nextSemester} result.`;
    }
    if (r.type === "STUDENT" && r.state === "PENDING") {
      return ctx.noticeSentAt
        ? `Waiting for evidence independent of the college; the student's notice was sent on ${sentenceDate(ctx.noticeSentAt)}.`
        : "Waiting for evidence independent of the college; no notice has reached the student yet.";
    }
  }
  return "Waiting for evidence independent of the college.";
}
