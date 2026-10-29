import * as React from "react";
import { Building2, Gavel, ShieldCheck } from "lucide-react";
import { STATE_MARK } from "@/components/brand/CheckBadge";
import { stateWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import { formatCardDate } from "@/lib/format";
import type { CheckType, EvidenceRow, EvidenceRowBrief, EvidenceState } from "@/lib/types";
import { cn } from "@/lib/utils";

export type AnyRow = EvidenceRow | EvidenceRowBrief;
export const isFull = (r: AnyRow): r is EvidenceRow => "source_line" in r;

/** Rows that hold a fact carry the independence marker; never the Seat row (copy deck §21). */
export function showsIndependence(r: { type: CheckType; state: EvidenceState }): boolean {
  return r.type !== "SEAT" && (r.state === "CONFIRMED" || r.state === "CONTRADICTED");
}

/** The state cell: icon and state word first, then the finding ("Confirmed: fits approved intake"). */
export function EvidenceState({ row, className }: { row: { state: EvidenceState; finding: string | null }; className?: string }) {
  const { Icon, ink } = STATE_MARK[row.state];
  const strong = row.state === "CONTRADICTED";
  return (
    <span className={cn("inline-flex items-start gap-1.5", className)} title={tk(`evidence.tip.${row.state}`)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", ink)} aria-hidden="true" />
      <span>
        <span className={cn("font-medium", ink, strong && "font-semibold")}>{stateWord(row.state)}</span>
        {row.finding && <span className="text-ink">{`: ${row.finding}`}</span>}
      </span>
    </span>
  );
}

/** "Independent of the college" or "From the college itself", with its icon and tooltip. */
export function IndependenceMarker({ row, institutionName }: { row: AnyRow; institutionName: string }) {
  const independent = row.independent;
  const Icon = independent ? ShieldCheck : Building2;
  const source = isFull(row) ? row.supplied_by : "";
  const tip = independent
    ? t("evidence.independent_tip", { source_name: source || tk(`check.${row.type}`) })
    : t("evidence.from_college_tip", { institution_name: institutionName });
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", independent ? "text-ink" : "text-ink-muted")} title={tip}>
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {independent ? t("evidence.independent") : t("evidence.from_college")}
    </span>
  );
}

/** "Claim upheld by an officer on 31 Oct": the state stays Contradicted (D43, R2). */
export function ResolvedLine({ row }: { row: AnyRow }) {
  if (!isFull(row) || !row.resolved) return null;
  const line = row.resolved.line || t("evidence.resolved.UPHELD", { date: formatCardDate(row.resolved.at) });
  return (
    <span className="mt-1 flex items-start gap-1 text-xs text-ink-muted" title={t("evidence.resolved_tip")}>
      <Gavel className="mt-px size-3.5 shrink-0 text-seal" aria-hidden="true" />
      {line}
    </span>
  );
}

/** One sentence per row for screen readers (evidence.sr_row), leaving out what does not apply. */
export function rowSentence(row: AnyRow): string {
  const check = tk(`check.${row.type}`);
  const parts = [`${check}: ${tk(`evidence.sr.${row.state}`)}.`];
  if (row.finding) parts.push(`${row.finding}.`);
  if (isFull(row) && row.source_line) parts.push(`${t("record.col.source")}: ${row.source_line}.`);
  if (showsIndependence(row)) parts.push(`${row.independent ? t("evidence.independent") : t("evidence.from_college")}.`);
  if (isFull(row) && row.resolved) parts.push(`${row.resolved.line}.`);
  return parts.join(" ");
}
