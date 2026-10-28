import * as React from "react";
import { TriangleAlert } from "lucide-react";
import { CountersignScore, CHECK_ORDER } from "@/components/brand/CountersignScore";
import { t, tk } from "@/lib/copy";
import { formatCount } from "@/lib/format";
import type { Countersign, InstitutionType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * The countersign strip. With a score it is the brand CountersignScore; in
 * Week 1 (score null, no checks) it draws five hollow segments and
 * "Not yet checked", as page spec section 0 asks.
 */
export function CountersignStrip({ countersign, size = "sm" }: { countersign: Countersign; size?: "sm" | "md" | "lg" }) {
  if (countersign.score) return <CountersignScore countersign={countersign} size={size} />;
  const sizeClass = size === "sm" ? "countersign-score--sm" : size === "lg" ? "countersign-score--lg" : undefined;
  return (
    <span className={cn("countersign-score", sizeClass)} aria-label={t("strip.not_checked")} role="img">
      <span className="countersign-score__checks" aria-hidden="true">
        {CHECK_ORDER.map((c) => (
          <span key={c} className="countersign-score__check" data-status="UNCHECKED" title={`${tk(`check.${c}`)}: ${t("strip.not_checked")}`} />
        ))}
      </span>
      <span className="countersign-score__empty">{t("strip.not_checked")}</span>
    </span>
  );
}

/** "12 unseated" in amber with the ledger tooltip; zero renders a plain "0". */
export function UnseatedCount({ n }: { n: number }) {
  if (n <= 0) return <span className="text-ink-muted">0</span>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          className="inline-flex h-5 items-center gap-1 rounded-chip border border-check-pending/40 bg-check-pending-soft px-1.5 text-xs font-medium whitespace-nowrap text-check-pending-ink"
        >
          <TriangleAlert className="size-3" aria-hidden="true" />
          {t("ledger.unseated_chip", { n: formatCount(n) })}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-72">{t("ledger.unseated_tip")}</TooltipContent>
    </Tooltip>
  );
}

/** The amber "Unseated" marker for an enrolment row with no seat code. */
export function UnseatedChip() {
  return (
    <span
      title={t("ledger.unseated_tip")}
      className="inline-flex h-5 items-center rounded-chip border border-dashed border-check-pending/50 bg-check-pending-soft px-1.5 font-sans text-xs font-medium text-check-pending-ink"
    >
      {t("seat.unseated")}
    </span>
  );
}

/** Institution type in words, as a quiet outlined chip. */
export function TypeChip({ type }: { type: InstitutionType }) {
  return (
    <span className="inline-flex h-5 items-center rounded-chip border border-line bg-paper px-1.5 text-xs whitespace-nowrap text-ink-muted">
      {tk(`type.${type}`)}
    </span>
  );
}

/** Muted "Not yet computed" for Week 1 nulls (spec section 0). */
export function NotComputed({ className }: { className?: string }) {
  return <span className={cn("text-xs text-ink-faint italic", className)}>{t("kpi.not_computed")}</span>;
}

/** "Viewing student records is logged." under every table with a student column. */
export function ReadLoggedNote() {
  return <span className="text-xs text-ink-muted">{t("privacy.read_logged")}</span>;
}
