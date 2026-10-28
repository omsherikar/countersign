/**
 * Words for checks, shared by the strip, the badges and enrolment detail
 * (copy deck §3, "Pending words"). Lists carry type and status only, so a
 * pending check there reads "Pending" unless it is the Student check;
 * enrolment detail has `detail` and can say why it is pending.
 */
import { t, tk } from "@/lib/copy";
import { formatDateTime } from "@/lib/format";
import type { Check, CheckBrief, CheckStatus, CheckType, Countersign } from "@/lib/types";

export const CHECK_ORDER: CheckType[] = ["IDENTITY", "ADMISSION", "SEAT", "STUDYING", "STUDENT"];

type AnyCheck = CheckBrief | Check;
const hasDetail = (c: AnyCheck): c is Check => "detail" in c && typeof c.detail === "object" && c.detail !== null;

/** The status word a reader sees: check.status.*, or for PENDING the first pending word that applies. */
export function statusWord(c: AnyCheck): string {
  if (c.status === "SOURCE_UNAVAILABLE") return t("check.pending.unavailable");
  if (c.status !== "PENDING") return tk(`check.status.${c.status}`);
  if (c.type === "STUDENT") {
    // Enrolment detail knows where the notice stands (A3.8); lists say "No reply yet".
    const state = hasDetail(c) ? c.detail.notice_state : undefined;
    if (state === "NOT_SENT" || state === "UNREACHABLE") return t("check.pending.student_not_sent");
    if (state === "EXPIRED") return t("check.pending.student_expired");
    return t("check.pending.student");
  }
  if (hasDetail(c)) {
    if (c.detail.source_unavailable) return t("check.pending.unavailable");
    if (c.detail.needs_review) return t("check.pending.review");
    if (c.detail.awaiting_semester) return t("check.pending.results");
  }
  return t("check.status.PENDING");
}

/** Rows a recheck asks again: PENDING or SOURCE_UNAVAILABLE. */
export function awaitsSource(c: { status: CheckStatus }): boolean {
  return c.status === "PENDING" || c.status === "SOURCE_UNAVAILABLE";
}

/** Pending checks other than Student: the {pending} of strip.score_pending. */
export function pendingCount(countersign: Countersign): number {
  return countersign.checks.filter((c) => awaitsSource(c) && c.type !== "STUDENT").length;
}

/** "3 of 4", or "2 of 4, 1 pending" when a check other than Student waits. */
export function scoreText(countersign: Countersign): string {
  const s = countersign.score;
  if (!s) return t("strip.not_checked");
  const pending = pendingCount(countersign);
  return pending > 0 ? t("strip.score_pending", { passes: s.passes, applicable: s.applicable, pending }) : t("strip.score", { passes: s.passes, applicable: s.applicable });
}

/** checks in display order, whatever order they arrived in. */
export function ordered<T extends AnyCheck>(checks: T[]): T[] {
  return CHECK_ORDER.map((type) => checks.find((c) => c.type === type)).filter((c): c is T => Boolean(c));
}

/** strip.aria with the same words as the popover lines. */
export function stripAria(countersign: Countersign, full?: Check[]): string {
  const s = countersign.score;
  if (!s) return t("strip.not_checked");
  const list = ordered<AnyCheck>(full && full.length ? full : countersign.checks);
  const word = (type: CheckType) => {
    const c = list.find((x) => x.type === type);
    return c ? statusWord(c).toLowerCase() : t("check.never").toLowerCase();
  };
  return t("strip.aria", {
    passes: s.passes,
    applicable: s.applicable,
    s1: word("IDENTITY"),
    s2: word("ADMISSION"),
    s3: word("SEAT"),
    s4: word("STUDYING"),
    s5: word("STUDENT"),
  });
}

/** One popover line: strip.segment_tip in lists, strip.segment_tip_full with source and time on detail. */
export function segmentTip(c: AnyCheck): string {
  const check = tk(`check.${c.type}`);
  if (hasDetail(c)) {
    return t("strip.segment_tip_full", {
      check,
      status_word: statusWord(c),
      source_name: tk(`source.${c.source}`),
      checked_at: c.checked_at ? formatDateTime(c.checked_at) : t("check.never"),
    });
  }
  return t("strip.segment_tip", { check, status_word: statusWord(c) });
}
