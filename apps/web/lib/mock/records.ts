/**
 * Mock-mode records: the record status of each enrolment with the cases that
 * name it (API_CONTRACT A4.3), record counts per college, and completeness
 * against the admission authority's joinings list (A4.18).
 */
import { recordOf, type CaseView } from "@/lib/mock/evidence";
import { ACADEMIC_YEAR, SEEDS, STATES } from "@/lib/mock/fixtures";
import { allFlags, UNRESOLVED, type StoredFlag } from "@/lib/mock/flags";
import { FIRST_UPLOAD, RECONCILED_AT, REPORTING_DEADLINE, deadlineStateOf, joinedCounts } from "@/lib/mock/joinings";
import { CHECKED_AT, recordContext, rollFor, type RollEntry } from "@/lib/mock/roll";
import type { Completeness, FlagStatus, RecordCounts, RecordFields } from "@/lib/types";

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
