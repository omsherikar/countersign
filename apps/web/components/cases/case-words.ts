/**
 * Words shared by the case pages: who acted, which note field a sheet
 * shows, the reasons each decision offers and how a corrected value reads.
 * Notes on the three decisions and on Request documents reach the college;
 * notes on Escalate, Add note and Reopen stay with officers (A4.8).
 */
import { t, tk, type CopyId } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { REGION_NAME } from "@/lib/roles";
import type {
  CaseHistoryItem,
  CorrectableField,
  CorrectReason,
  DocsKind,
  EscalateReason,
  FlagType,
  OfficerAction,
  ReasonCode,
  Region,
  Role,
  UpholdReason,
  WithdrawReason,
} from "@/lib/types";

export const ACTION_WORD: Record<OfficerAction, CopyId> = {
  UPHOLD: "case.uphold",
  CORRECT: "case.correct",
  WITHDRAW: "case.withdraw",
  REQUEST_DOCS: "case.request_docs",
  ESCALATE: "case.escalate",
  NOTE: "case.note",
  ASSIGN: "case.assign",
  REOPEN: "case.reopen",
};

/** The three decisions, in the deck's order; none is styled as dangerous. */
export const DECISIONS = ["UPHOLD", "CORRECT", "WITHDRAW"] as const;
export type Decision = (typeof DECISIONS)[number];
export const isDecision = (a: OfficerAction): a is Decision => (DECISIONS as readonly string[]).includes(a);

/** Actions whose note the college reads; every other note stays with officers. */
export const NOTE_SHOWN_TO_COLLEGE: OfficerAction[] = ["UPHOLD", "CORRECT", "WITHDRAW", "REQUEST_DOCS"];

export function noteLabel(action: OfficerAction): string {
  return NOTE_SHOWN_TO_COLLEGE.includes(action) ? t("case.note_label") : t("case.note_label_internal");
}

/**
 * "AICTE officer", "Regional officer, Western", "Registrar". A regional
 * officer only acts on cases of its own region, so the case's region names it.
 */
export function roleWordOf(role: Role, region: Region | null): string {
  if (role === "RO_OFFICER") {
    return region ? t("shell.role.RO_OFFICER", { region_name: REGION_NAME[region] }) : t("shell.role.RO_OFFICER", { region_name: "" }).replace(/,\s*$/, "");
  }
  return tk(`shell.role.${role}`);
}

/** The latest row of one kind in a case's history. */
export function lastOf(history: CaseHistoryItem[], action: CaseHistoryItem["action"]): CaseHistoryItem | undefined {
  for (let i = history.length - 1; i >= 0; i--) if (history[i].action === action) return history[i];
  return undefined;
}

/* ---- Reasons (A4.9, copy deck section 6 reason.*) ------------------------ */

const UPHOLD_REASONS: UpholdReason[] = [
  "DOCUMENTS_SUPPORT_CLAIM", "SOURCE_RECORD_WRONG", "NAME_VARIANT", "PERMITTED_DUAL_PROGRAMME",
  "APPROVAL_VERSION_COVERS", "STUDENT_ANSWER_MISTAKEN", "MISSING_NOW_UPLOADED", "OTHER",
];
const CORRECT_REASONS: CorrectReason[] = ["UPLOAD_ERROR", "DOCUMENTS_SHOW_OTHER_VALUE", "WRONG_SEAT_CATEGORY", "OTHER"];
const WITHDRAW_REASONS: WithdrawReason[] = [
  "STUDENT_NEVER_JOINED", "NO_JOINING_EVIDENCE", "BEYOND_APPROVED_INTAKE", "NOT_ELIGIBLE_FOR_SEAT", "DUPLICATE_RECORD", "NO_RESPONSE", "OTHER",
];
const ESCALATE_REASONS: EscalateReason[] = ["NEEDS_AICTE_DECISION", "POLICY_QUESTION", "SPANS_REGIONS", "REPEATED_PATTERN", "OTHER"];

/** Reasons that only make sense for some case types; every other reason fits any case. */
const ONLY_FOR: Partial<Record<ReasonCode, FlagType[]>> = {
  APPROVAL_VERSION_COVERS: ["EXCESS_ADMISSION", "QUOTA_BREACH"],
  MISSING_NOW_UPLOADED: ["MISSING_FROM_UPLOAD"],
  STUDENT_ANSWER_MISTAKEN: ["STUDENT_DENIED"],
  PERMITTED_DUAL_PROGRAMME: ["DUPLICATE_CROSS_INSTITUTION", "DUAL_ENROLMENT_ALLOWED"],
  NAME_VARIANT: ["NAME_MISMATCH", "INVALID_APAAR", "DUPLICATE_CROSS_INSTITUTION", "DUPLICATE_WITHIN_UPLOAD"],
  BEYOND_APPROVED_INTAKE: ["EXCESS_ADMISSION", "QUOTA_BREACH", "GHOST_RING"],
  NOT_ELIGIBLE_FOR_SEAT: ["ELIGIBILITY_BREACH", "QUOTA_BREACH"],
  STUDENT_NEVER_JOINED: ["STUDENT_DENIED", "NOT_IN_JOINING_RECORD", "GHOST_RING"],
  WRONG_SEAT_CATEGORY: ["ELIGIBILITY_BREACH", "QUOTA_BREACH", "EXCESS_ADMISSION"],
};

/** A Missing from upload case is upheld only because the students arrived or the source was wrong (deck section 6). */
const MISSING_REASONS: UpholdReason[] = ["MISSING_NOW_UPLOADED", "SOURCE_RECORD_WRONG"];

export function reasonsFor(action: Decision | "ESCALATE", type: FlagType): ReasonCode[] {
  if (action === "ESCALATE") return ESCALATE_REASONS;
  if (action === "UPHOLD" && type === "MISSING_FROM_UPLOAD") return MISSING_REASONS;
  const all: ReasonCode[] = action === "UPHOLD" ? UPHOLD_REASONS : action === "CORRECT" ? CORRECT_REASONS : WITHDRAW_REASONS;
  return all.filter((code) => !ONLY_FOR[code] || ONLY_FOR[code]!.includes(type));
}

/** reason.<ACTION>.<CODE>, or the code itself when the deck has no word for it. */
export function reasonWord(action: OfficerAction | CaseHistoryItem["action"], code: ReasonCode): string {
  return tk(`reason.${action}.${code}`);
}

/** The reason a history row cites, whichever decision wrote it. */
export function historyReasonWord(item: Pick<CaseHistoryItem, "action" | "reason_code">): string | null {
  if (!item.reason_code) return null;
  return reasonWord(item.action, item.reason_code);
}

export const DOCS_KINDS: DocsKind[] = ["ADMISSION", "JOINING", "IDENTITY", "ELIGIBILITY", "CREDITS", "OTHER"];

/* ---- Corrections (A4.9 CORRECT fields) ----------------------------------- */

export const CORRECTABLE: CorrectableField[] = [
  "name", "dob", "year_of_study", "admission_route", "category", "counselling_ref", "admission_date",
  "tfw_income_certified", "nri_sponsored", "ciwg",
];
export const ELIGIBILITY_FIELDS: CorrectableField[] = ["tfw_income_certified", "nri_sponsored", "ciwg"];
/** Fields whose change moves the record to another seat pool (deck section 6, case.correct_change.seat). */
export const SEAT_FIELDS = ["year_of_study", "admission_route", "tfw_income_certified", "nri_sponsored", "ciwg", "programme_code"];

export function fieldWord(field: string): string {
  return tk(`field.${field}`);
}

/** How a stored value reads in "Programme: B.Tech ME to B.Tech CSE" lines. */
export function valueWord(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return t("case.correct_value.unreported");
  if (typeof value === "boolean") return t(value ? "case.correct_value.yes" : "case.correct_value.no");
  const text = String(value);
  if (field === "admission_route") return tk(`route.${text}`);
  if (field === "category") return tk(`category.${text}`);
  if (field === "status") return tk(`enrol_status.${text}`);
  if (field === "dob" || field === "admission_date" || field === "status_date") return formatDate(text);
  return text;
}

/** Up to five codes, then "and {more} more" (deck section 6). */
export function seatCodes(codes: string[]): string {
  if (codes.length <= 5) return codes.join(", ");
  return t("case.seat_codes_more", { codes: codes.slice(0, 5).join(", "), more: codes.length - 5 });
}
