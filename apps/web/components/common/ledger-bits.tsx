import * as React from "react";
import { TriangleAlert } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatCount } from "@/lib/format";
import type { InstitutionType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

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

/** "Unseated" in muted text for an enrolment row with no seat code; the amber chip stays on programme counts. */
export function UnseatedChip() {
  return <span className="font-sans text-xs text-ink-muted">{t("seat.unseated")}</span>;
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
  return <span className={cn("text-xs text-ink-muted italic", className)}>{t("kpi.not_computed")}</span>;
}

/** "Viewing student records is logged." under every table with a student column. */
export function ReadLoggedNote() {
  return <span className="text-xs text-ink-muted">{t("privacy.read_logged")}</span>;
}
