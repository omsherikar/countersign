import * as React from "react";
import { tk } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** Mirrors `Severity` in lib/types.ts. */
export type Severity = "LOW" | "MEDIUM" | "HIGH";

export const SEVERITY_LABEL = Object.fromEntries((["LOW", "MEDIUM", "HIGH"] as const).map((s) => [s, tk(`severity.${s}`)])) as Record<Severity, string>;

/** Ordinal: slate, ochre, red. The bar count repeats the level without colour. */
const STYLE: Record<Severity, { chip: string; bars: number }> = {
  LOW: { chip: "bg-severity-low-soft text-severity-low-ink border-severity-low/40", bars: 1 },
  MEDIUM: { chip: "bg-severity-medium-soft text-severity-medium-ink border-severity-medium/40", bars: 2 },
  HIGH: { chip: "bg-severity-high-soft text-severity-high-ink border-severity-high/40", bars: 3 },
};

export interface SeverityBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  severity: Severity;
  /** Glyph only; the word stays in the accessible name. */
  compact?: boolean;
}

/**
 * Flag severity as a three-step meter: one, two or three bars plus the word.
 * Severity is how urgent a flag is, never whether the college is at fault;
 * see DESIGN.md for the distinction from CONFIRMED.
 */
export function SeverityBadge({ severity, compact = false, className, ...rest }: SeverityBadgeProps) {
  const { chip, bars } = STYLE[severity];
  const label = `Severity ${SEVERITY_LABEL[severity].toLowerCase()}`;
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-chip border px-1.5 text-xs font-medium leading-none",
        compact && "px-1",
        chip,
        className,
      )}
      {...rest}
    >
      <span className="inline-flex items-end gap-px" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={cn("w-[3px] rounded-[1px] bg-current", i <= bars ? "opacity-100" : "opacity-25")}
            style={{ height: 4 + i * 2.5 }}
          />
        ))}
      </span>
      {!compact && <span>{SEVERITY_LABEL[severity]}</span>}
    </span>
  );
}
