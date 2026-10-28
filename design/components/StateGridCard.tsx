import * as React from "react";
import { cn } from "@/lib/utils";

/** Mirrors `Region` and the `by_state` row of `DashboardSummary` in lib/types.ts. */
export type Region =
  | "NORTH" | "NORTH_WEST" | "CENTRAL" | "WEST" | "WEST_CENTRAL"
  | "SOUTH_WEST" | "SOUTH" | "SOUTH_CENTRAL" | "EAST" | "NORTH_EAST";

export interface StateRow {
  state_code: string;
  state_name: string;
  region: Region;
  institutions: number;
  programmes: number;
  approved_seats: number;
  enrolments: number;
  flags_open: number;
}

export const REGION_LABEL: Record<Region, string> = {
  NORTH: "Northern",
  NORTH_WEST: "North-Western",
  CENTRAL: "Central",
  WEST: "Western",
  WEST_CENTRAL: "Vadodara",
  SOUTH_WEST: "South-Western",
  SOUTH: "Southern",
  SOUTH_CENTRAL: "South-Central",
  EAST: "Eastern",
  NORTH_EAST: "North-Eastern",
};

const INDIAN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Integrity Index 0..100 to one of the seven sequential steps (index-1 lightest). */
export function indexStep(index: number): 1 | 2 | 3 | 4 | 5 | 6 | 7 {
  const clamped = Math.max(0, Math.min(100, index));
  return (Math.min(6, Math.floor(clamped / (100 / 7))) + 1) as 1 | 2 | 3 | 4 | 5 | 6 | 7;
}

export interface StateGridCardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onSelect"> {
  row: StateRow;
  /** Week 4: mean Integrity Index for the state, 0..100. null until then. */
  integrityIndex?: number | null;
  /** Current selection in the grid. */
  selected?: boolean;
  /** The card becomes a button when given. */
  onSelect?: (stateCode: string) => void;
}

/**
 * One state in the state grid (decision D8: a grid, never a map). The code
 * is the big element because officers know their states by code; the full
 * name is the second line. Enrolment and seats are set as tabular figures so
 * the grid scans as a table. Open flags are only coloured when non-zero.
 * The Integrity Index, when it exists, tints the left rule from the
 * sequential ramp and is also written as a number.
 */
export function StateGridCard({ row, integrityIndex = null, selected = false, onSelect, className, ...rest }: StateGridCardProps) {
  const step = integrityIndex === null ? null : indexStep(integrityIndex);
  const fill = row.approved_seats > 0 ? Math.round((row.enrolments / row.approved_seats) * 100) : null;
  const Tag: "button" | "div" = onSelect ? "button" : "div";
  return (
    <Tag
      type={onSelect ? "button" : undefined}
      onClick={onSelect ? () => onSelect(row.state_code) : undefined}
      aria-pressed={onSelect ? selected : undefined}
      className={cn(
        "flex w-full flex-col gap-2 rounded-md border border-l-[3px] bg-paper-raised p-3 text-left",
        "border-line shadow-hairline",
        onSelect && "cursor-pointer hover:border-rule-strong focus-visible:outline-2 focus-visible:outline-ring",
        selected && "border-ink-blue ring-1 ring-ink-blue",
        className,
      )}
      style={step ? { borderLeftColor: `var(--index-${step})` } : undefined}
      {...(rest as React.HTMLAttributes<HTMLDivElement> & React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-display text-xl font-semibold leading-none">{row.state_code}</span>
        <span className="truncate text-xs text-ink-muted">{REGION_LABEL[row.region]}</span>
      </div>
      <span className="truncate text-sm font-medium">{row.state_name}</span>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs" style={{ fontVariantNumeric: "tabular-nums lining-nums" }}>
        <dt className="text-ink-muted">Institutions</dt>
        <dd className="text-right">{INDIAN.format(row.institutions)}</dd>
        <dt className="text-ink-muted">Approved seats</dt>
        <dd className="text-right">{INDIAN.format(row.approved_seats)}</dd>
        <dt className="text-ink-muted">Enrolments</dt>
        <dd className="text-right">
          {INDIAN.format(row.enrolments)}
          {fill !== null && <span className="ml-1 text-ink-faint">({fill}%)</span>}
        </dd>
        <dt className="text-ink-muted">Open flags</dt>
        <dd className={cn("text-right", row.flags_open > 0 ? "font-medium text-check-fail-ink" : "text-ink-muted")}>
          {INDIAN.format(row.flags_open)}
        </dd>
        {integrityIndex !== null && (
          <>
            <dt className="text-ink-muted">Integrity Index</dt>
            <dd className="text-right font-medium">{Math.round(integrityIndex)}</dd>
          </>
        )}
      </dl>
    </Tag>
  );
}
