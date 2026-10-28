import * as React from "react";
import { cn } from "@/lib/utils";

const INDIAN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Indian digit grouping: 18,960 and 1,89,600, the way the panel reads numbers. */
export function formatCount(n: number): string {
  return INDIAN.format(n);
}

export interface KpiTileProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Sentence case, no trailing colon: "Approved seats". */
  label: string;
  /** null renders as "not yet" rather than a misleading zero (Week 1 integrity index). */
  value: number | string | null;
  /** Appended to a numeric value, e.g. "%". */
  unit?: string;
  /** One short line under the value: "across 50 institutions". */
  hint?: string;
  /** Tone of the value. Only "alert" colours the number; use it for flags_open > 0. */
  tone?: "default" | "alert" | "muted";
  /** Pass a custom formatter for non-count numbers. */
  format?: (n: number) => string;
}

/**
 * One cell of the KPI strip. Tiles are not cards: put several inside
 * `<div className="kpi-strip">` and the feint rules between them come from
 * globals.css. Big numbers use proportional figures (tabular is for columns).
 */
export function KpiTile({ label, value, unit, hint, tone = "default", format = formatCount, className, ...rest }: KpiTileProps) {
  const display = value === null ? "not yet" : typeof value === "number" ? format(value) : value;
  const isNumber = typeof value === "number";
  return (
    <div className={cn("flex min-w-0 flex-col gap-1 px-4 py-3", className)} {...rest}>
      <span className="truncate text-xs font-medium text-ink-muted">{label}</span>
      <span
        className={cn(
          "font-display text-2xl font-semibold leading-none tracking-display",
          value === null && "italic font-normal text-ink-faint text-lg",
          tone === "alert" && isNumber && "text-check-fail-ink",
          tone === "muted" && "text-ink-muted",
        )}
        style={{ fontVariantNumeric: "lining-nums proportional-nums" }}
      >
        {display}
        {unit && isNumber && <span className="ml-0.5 text-base font-normal text-ink-muted">{unit}</span>}
      </span>
      {hint && <span className="line-clamp-2 text-xs text-ink-muted">{hint}</span>}
    </div>
  );
}
