import * as React from "react";
import { t } from "@/lib/copy";
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
  /** A2.18: the intake set against approved seats; absent before the Week 2 api. */
  admitted?: number;
  enrolments: number;
  flags_open: number;
  /** A4.20: the Countersigned share of the state's active records; absent before Week 4. */
  countersigned_pct?: number | null;
}

export const REGION_LABEL: Record<Region, string> = {
  NORTH: "Northern",
  NORTH_WEST: "North-Western",
  CENTRAL: "Central",
  WEST: "Western",
  WEST_CENTRAL: "West-Central",
  SOUTH_WEST: "South-Western",
  SOUTH: "Southern",
  SOUTH_CENTRAL: "South-Central",
  EAST: "Eastern",
  NORTH_EAST: "North-Eastern",
};

const INDIAN = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

export interface StateGridCardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "onSelect"> {
  row: StateRow;
  /** Current selection in the grid. */
  selected?: boolean;
  /** The card becomes a button when given. */
  onSelect?: (stateCode: string) => void;
}

/**
 * One state in the state grid (decision D8: a grid, never a map). The code
 * is the big element because officers know their states by code; the full
 * name is the second line. Enrolment and seats are set as tabular figures so
 * the grid scans as a table. Open cases are only weighted when non-zero.
 * The Countersigned share is a share of the state's records, never a score.
 */
export function StateGridCard({ row, selected = false, onSelect, className, ...rest }: StateGridCardProps) {
  // Approved seats and admitted are one intake, shown as two counts (never a percentage); the roll covers every year.
  const admitted = typeof row.admitted === "number" ? row.admitted : null;
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
      {...(rest as React.HTMLAttributes<HTMLDivElement> & React.ButtonHTMLAttributes<HTMLButtonElement>)}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-display text-xl font-semibold leading-none">{row.state_code}</span>
        <span className="truncate text-xs text-ink-muted">{REGION_LABEL[row.region]}</span>
      </div>
      <span className="truncate text-sm font-medium">{row.state_name}</span>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs" style={{ fontVariantNumeric: "tabular-nums lining-nums" }}>
        <dt className="text-ink-muted">{t("kpi.institutions")}</dt>
        <dd className="text-right">{INDIAN.format(row.institutions)}</dd>
        <dt className="text-ink-muted">{t("kpi.programmes")}</dt>
        <dd className="text-right">{INDIAN.format(row.programmes)}</dd>
        <dt className="text-ink-muted">{t("kpi.approved_seats")}</dt>
        <dd className="text-right">{INDIAN.format(row.approved_seats)}</dd>
        {admitted !== null && (
          <>
            <dt className="text-ink-muted">{t("kpi.admitted")}</dt>
            <dd className="text-right">{INDIAN.format(admitted)}</dd>
          </>
        )}
        <dt className="text-ink-muted" title={t("app.hint.all_years")}>
          {t("kpi.enrolments")}
        </dt>
        <dd className="text-right">{INDIAN.format(row.enrolments)}</dd>
        <dt className="text-ink-muted">{t("kpi.flags_open")}</dt>
        <dd className={cn("text-right", row.flags_open > 0 ? "font-semibold text-ink" : "text-ink-muted")}>
          {INDIAN.format(row.flags_open)}
        </dd>
        {typeof row.countersigned_pct === "number" && (
          <>
            <dt className="text-ink-muted">{t("kpi.countersigned")}</dt>
            <dd className="text-right font-medium">{row.countersigned_pct}%</dd>
          </>
        )}
      </dl>
    </Tag>
  );
}
