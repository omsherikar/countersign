import * as React from "react";
import { t, tk } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** Mirrors `FlagType`, `Severity`, `FlagStatus` in lib/types.ts. */
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "CLEARED" | "ESCALATED" | "CONFIRMED";

/** The `evidence` every flag carries (API_CONTRACT A2.16): a sentence, facts with their sources, the rule. */
export interface Evidence {
  summary: string;
  facts?: { label: string; value: string | number; source?: string | null }[];
  rule_source?: string | null;
}

/** Flag names from the copy deck (flag.<TYPE>.name). */
export const FLAG_TYPE_LABEL = Object.fromEntries(
  (
    [
      "EXCESS_ADMISSION", "QUOTA_BREACH", "LATE_REFILL", "INVALID_APAAR", "NAME_MISMATCH", "DUPLICATE_CROSS_INSTITUTION",
      "DUPLICATE_WITHIN_UPLOAD", "DUAL_ENROLMENT_ALLOWED", "NO_ACADEMIC_ACTIVITY", "STUDENT_DENIED", "GHOST_RING", "ANOMALY",
    ] as const
  ).map((type) => [type, tk(`flag.${type}.name`)]),
) as Record<FlagType, string>;

const SEVERITY_RULE: Record<Severity, string> = {
  LOW: "border-l-severity-low",
  MEDIUM: "border-l-severity-medium",
  HIGH: "border-l-severity-high",
};

export interface EvidenceCardProps extends React.HTMLAttributes<HTMLElement> {
  type: FlagType;
  severity: Severity;
  evidence: Evidence;
  /** Which source produced the evidence: "Seat ledger", "APAAR", "Counselling list". */
  source?: string;
  /** ISO timestamp of when the evidence was computed. */
  checkedAt?: string | null;
  /** Rendered top-right: put a FlagStatusBadge or SeverityBadge here. */
  badges?: React.ReactNode;
  /** Rendered below the facts: action buttons (Request documents, Clear, Escalate). */
  actions?: React.ReactNode;
  /** Replaces the flag name as the card heading, where the page title already names the flag. */
  heading?: React.ReactNode;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" }) + " IST";
}

/**
 * A flag's evidence as a human would write it in the margin: one summary
 * sentence, then the facts as a ledger (fact, value, the source that gave
 * it), then the rule the flag rests on. Every sentence is printed as the api
 * wrote it. The left rule carries severity; the pink margin rule
 * frames the facts the way a ledger page does. Nothing here says "reject":
 * the card presents evidence and the officer decides.
 */
export function EvidenceCard({ type, severity, evidence, source, checkedAt, badges, actions, heading, className, ...rest }: EvidenceCardProps) {
  return (
    <article
      className={cn("rounded-md border border-line border-l-[3px] bg-paper-raised pb-3 shadow-hairline", SEVERITY_RULE[severity], className)}
      aria-label={`${FLAG_TYPE_LABEL[type]}: ${evidence.summary}`}
      {...rest}
    >
      <header className="flex items-start justify-between gap-3 px-4 pt-3">
        <div className="min-w-0">
          <h3 className="font-display text-md font-semibold leading-snug">{heading ?? FLAG_TYPE_LABEL[type]}</h3>
          <p className="mt-1 max-w-[60ch] text-sm leading-snug text-ink">{evidence.summary}</p>
        </div>
        {badges && <div className="flex shrink-0 flex-wrap justify-end gap-1">{badges}</div>}
      </header>

      {evidence.facts && evidence.facts.length > 0 && (
        <div className="mx-4 mt-3 overflow-x-auto border-l-2 border-rule-margin pl-3">
          <table className="w-full text-sm" style={{ fontVariantNumeric: "tabular-nums lining-nums" }}>
            <caption className="sr-only">{t("section.evidence")}</caption>
            <thead>
              <tr className="border-b border-rule-strong text-left text-xs text-ink-muted">
                <th scope="col" className="py-1 pr-4 font-medium">
                  {t("flag.facts.label")}
                </th>
                <th scope="col" className="py-1 pr-4 text-right font-medium">
                  {t("flag.facts.value")}
                </th>
                <th scope="col" className="py-1 font-medium">
                  {t("flag.facts.source")}
                </th>
              </tr>
            </thead>
            <tbody>
              {evidence.facts.map((f, i) => (
                <tr key={i} className="border-b border-rule align-baseline last:border-b-0">
                  <th scope="row" className="py-1.5 pr-4 text-left font-normal text-ink-muted">
                    {f.label}
                  </th>
                  <td className="py-1.5 pr-4 text-right font-medium">{typeof f.value === "number" ? new Intl.NumberFormat("en-IN").format(f.value) : f.value}</td>
                  <td className="py-1.5 text-xs text-ink-muted">{f.source ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {evidence.rule_source && <p className="mx-4 mt-2 text-xs text-ink-muted">{t("flag.rule", { rule_source: evidence.rule_source })}</p>}

      {(source || checkedAt || actions) && (
        <footer className="flex flex-wrap items-center justify-between gap-2 px-4 pt-3">
          <span className="text-xs text-ink-muted">
            {source ? `${t("col.source")}: ${source}` : ""}
            {checkedAt ? `${source ? ", " : ""}checked ${formatWhen(checkedAt)}` : ""}
          </span>
          {actions && <div className="flex gap-2">{actions}</div>}
        </footer>
      )}
    </article>
  );
}
