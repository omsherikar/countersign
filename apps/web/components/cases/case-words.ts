/**
 * Words shared by the case pages: who acted, and which note field a sheet
 * shows. Notes on Clear, Request documents and Confirm reach the college;
 * notes on Escalate, Add note and Reopen stay with officers (A3.9).
 */
import { t, tk, type CopyId } from "@/lib/copy";
import { REGION_NAME } from "@/lib/roles";
import type { CaseHistoryItem, OfficerAction, Region, Role } from "@/lib/types";

export const ACTION_WORD: Record<OfficerAction, CopyId> = {
  UPHOLD: "case.clear",
  REQUEST_DOCS: "case.request_docs",
  ESCALATE: "case.escalate",
  WITHDRAW: "case.confirm",
  NOTE: "case.note",
  ASSIGN: "case.assign",
  REOPEN: "case.reopen",
};

/** Actions whose note the college reads; every other note stays with officers. */
export const NOTE_SHOWN_TO_COLLEGE: OfficerAction[] = ["UPHOLD", "REQUEST_DOCS", "WITHDRAW"];

export function noteLabel(action: OfficerAction): string {
  return NOTE_SHOWN_TO_COLLEGE.includes(action) ? t("case.note_label") : t("case.note_label_internal");
}

/**
 * "AICTE officer", "Regional officer, Western", "Registrar". A regional
 * officer only acts on flags of its own region, so the flag's region names it.
 */
export function roleWordOf(role: Role, region: Region | null): string {
  if (role === "RO_OFFICER") {
    return region ? t("shell.role.RO_OFFICER", { region_name: REGION_NAME[region] }) : t("shell.role.RO_OFFICER", { region_name: "" }).replace(/,\s*$/, "");
  }
  return tk(`shell.role.${role}`);
}

/** The latest row of one kind in a flag's history. */
export function lastOf(history: CaseHistoryItem[], action: CaseHistoryItem["action"]): CaseHistoryItem | undefined {
  for (let i = history.length - 1; i >= 0; i--) if (history[i].action === action) return history[i];
  return undefined;
}
