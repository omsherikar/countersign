/**
 * Words and order for the five evidence rows and the four record statuses
 * (copy deck §21). Rows say Confirmed; only a record says Countersigned.
 * There is no score: a record carries one status, and one contradiction
 * outranks any number of confirmations.
 */
import { t, tk } from "@/lib/copy";
import { RECORD_STATUS_ORDER, ROW_ORDER } from "@/lib/types";
import type { CheckType, EvidenceState, RecordStatus } from "@/lib/types";

/** The deck's row order: Identity, Seat, Joining record, Credits, Student. */
export const CHECK_ORDER: CheckType[] = ROW_ORDER;

/** The six evidence states, in the order filters list them. */
export const STATE_ORDER: EvidenceState[] = ["CONFIRMED", "CONTRADICTED", "PENDING", "NOT_YET_DUE", "NOT_APPLICABLE", "SOURCE_UNAVAILABLE"];

/** The legend's order: Awaiting evidence, Countersigned, Under review, Disputed. */
export const STATUS_ORDER: RecordStatus[] = RECORD_STATUS_ORDER;

/** "Needs attention first": Disputed, Under review, Awaiting evidence, Countersigned. */
export const ATTENTION_ORDER: RecordStatus[] = ["DISPUTED", "UNDER_REVIEW", "AWAITING_EVIDENCE", "COUNTERSIGNED"];

/** Rows in the deck's order, whatever order they arrived in. */
export function ordered<T extends { type: CheckType }>(rows: T[]): T[] {
  return CHECK_ORDER.map((type) => rows.find((r) => r.type === type)).filter((r): r is T => Boolean(r));
}

/** evidence.state.* */
export function stateWord(state: EvidenceState): string {
  return tk(`evidence.state.${state}`);
}

/** "Confirmed: fits approved intake", or the state word alone when the row has no finding. */
export function stateWithFinding(row: { state: EvidenceState; finding: string | null }): string {
  const word = stateWord(row.state);
  return row.finding ? t("evidence.with_finding", { state_word: word, finding: row.finding }) : word;
}

/** Rows a recheck asks again: Pending or Source unavailable. */
export function awaitsSource(row: { state: EvidenceState }): boolean {
  return row.state === "PENDING" || row.state === "SOURCE_UNAVAILABLE";
}

/** record_status.*; a Disputed record reads "Disputed (priority)" on the card and its header. */
export function statusWord(status: RecordStatus, priority = false): string {
  if (priority && status === "DISPUTED") return t("record_status.DISPUTED_priority");
  return tk(`record_status.${status}`);
}
