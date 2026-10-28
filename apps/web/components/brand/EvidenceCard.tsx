import * as React from "react";
import { cn } from "@/lib/utils";

/** Mirrors `FlagType`, `Severity`, `FlagStatus` in lib/types.ts. */
export type FlagType =
  | "EXCESS_ADMISSION" | "QUOTA_BREACH" | "LATE_REFILL" | "INVALID_APAAR" | "NAME_MISMATCH"
  | "DUPLICATE_CROSS_INSTITUTION" | "DUPLICATE_WITHIN_UPLOAD" | "DUAL_ENROLMENT_ALLOWED"
  | "NO_ACADEMIC_ACTIVITY" | "STUDENT_DENIED" | "GHOST_RING" | "ANOMALY";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "CLEARED" | "ESCALATED" | "CONFIRMED";

/** The `evidence` JSON every flag carries (ARCHITECTURE.md section 9). */
export interface Evidence {
  summary: string;
  facts?: { label: string; value: string | number }[];
}

export const FLAG_TYPE_LABEL: Record<FlagType, string> = {
  EXCESS_ADMISSION: "Excess admission",
  QUOTA_BREACH: "Quota breach",
  LATE_REFILL: "Late refill",
  INVALID_APAAR: "Invalid APAAR",
  NAME_MISMATCH: "Name mismatch",
  DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
  DUPLICATE_WITHIN_UPLOAD: "Duplicate within upload",
  DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
  NO_ACADEMIC_ACTIVITY: "No academic activity",
  STUDENT_DENIED: "Student denied enrolment",
  GHOST_RING: "Ghost ring",
  ANOMALY: "Anomaly",
};

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
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" }) + " IST";
}

/**
 * A flag's evidence as a human would write it in the margin: one summary
 * sentence, then the facts as a ledger (label on the left, value right,
 * tabular figures). The left rule carries severity; the pink margin rule
 * frames the facts the way a ledger page does. Nothing here says "reject":
 * the card presents evidence and the officer decides.
 */
export function EvidenceCard({ type, severity, evidence, source, checkedAt, badges, actions, className, ...rest }: EvidenceCardProps) {
  return (
    <article
      className={cn("rounded-md border border-line border-l-[3px] bg-paper-raised shadow-hairline", SEVERITY_RULE[severity], className)}
      aria-label={`${FLAG_TYPE_LABEL[type]}: ${evidence.summary}`}
      {...rest}
    >
      <header className="flex items-start justify-between gap-3 px-4 pt-3">
        <div className="min-w-0">
          <h3 className="font-display text-md font-semibold leading-snug">{FLAG_TYPE_LABEL[type]}</h3>
          <p className="mt-1 max-w-[60ch] text-sm leading-snug text-ink">{evidence.summary}</p>
        </div>
        {badges && <div className="flex shrink-0 flex-wrap justify-end gap-1">{badges}</div>}
      </header>

      {evidence.facts && evidence.facts.length > 0 && (
        <dl className="mx-4 mt-3 border-l-2 border-rule-margin pl-3 text-sm" style={{ fontVariantNumeric: "tabular-nums lining-nums" }}>
          {evidence.facts.map((f, i) => (
            <div key={i} className="flex items-baseline justify-between gap-4 border-b border-rule py-1 last:border-b-0">
              <dt className="text-ink-muted">{f.label}</dt>
              <dd className="text-right font-medium">{typeof f.value === "number" ? new Intl.NumberFormat("en-IN").format(f.value) : f.value}</dd>
            </div>
          ))}
        </dl>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
        <span className="text-xs text-ink-muted">
          {source ? `Source: ${source}` : "Evidence"}
          {checkedAt ? `, checked ${formatWhen(checkedAt)}` : ""}
        </span>
        {actions && <div className="flex gap-2">{actions}</div>}
      </footer>
    </article>
  );
}
