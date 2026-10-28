import * as React from "react";
import { Check, Clock, Minus, X } from "lucide-react";
import { cn } from "@/lib/utils";

/** Mirrors `CheckStatus` and `CheckType` in lib/types.ts (API_CONTRACT.md D). */
export type CheckStatus = "PASS" | "FAIL" | "PENDING" | "NA";
export type CheckType = "IDENTITY" | "ADMISSION" | "SEAT" | "STUDYING" | "STUDENT";

export const CHECK_TYPE_LABEL: Record<CheckType, string> = {
  IDENTITY: "Identity",
  ADMISSION: "Admission",
  SEAT: "Seat",
  STUDYING: "Studying",
  STUDENT: "Student",
};

export const CHECK_STATUS_LABEL: Record<CheckStatus, string> = {
  PASS: "Pass",
  FAIL: "Fail",
  PENDING: "Pending",
  NA: "Not applicable",
};

const STYLE: Record<CheckStatus, { chip: string; Icon: React.ComponentType<{ className?: string }> }> = {
  PASS: { chip: "bg-check-pass-soft text-check-pass-ink border-check-pass/40", Icon: Check },
  FAIL: { chip: "bg-check-fail-soft text-check-fail-ink border-check-fail/40", Icon: X },
  PENDING: { chip: "bg-check-pending-soft text-check-pending-ink border-check-pending/40 border-dashed", Icon: Clock },
  NA: { chip: "bg-check-na-soft text-check-na-ink border-check-na/40 border-dotted", Icon: Minus },
};

export interface CheckBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: CheckStatus;
  /** When given, the badge reads "Identity: Pass" instead of just "Pass". */
  type?: CheckType;
  /** Source system that answered, shown in a title tooltip (e.g. "APAAR"). */
  source?: string;
  /** Glyph only, label in the accessible name. For dense table cells. */
  compact?: boolean;
}

/**
 * One countersignature. Colour never carries the meaning alone: every badge
 * has a glyph and a word, and the pending/not-applicable states also differ
 * by border style so they survive greyscale print.
 */
export function CheckBadge({ status, type, source, compact = false, className, ...rest }: CheckBadgeProps) {
  const { chip, Icon } = STYLE[status];
  const label = type ? `${CHECK_TYPE_LABEL[type]}: ${CHECK_STATUS_LABEL[status]}` : CHECK_STATUS_LABEL[status];
  return (
    <span
      role="img"
      aria-label={source ? `${label} (${source})` : label}
      title={source ? `${label}. Source: ${source}` : label}
      className={cn(
        "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-chip border px-1.5 text-xs font-medium leading-none",
        compact && "w-5 justify-center px-0",
        chip,
        className,
      )}
      {...rest}
    >
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      {!compact && <span>{type ? CHECK_TYPE_LABEL[type] : CHECK_STATUS_LABEL[status]}</span>}
      {!compact && type && <span className="opacity-70">{CHECK_STATUS_LABEL[status]}</span>}
    </span>
  );
}
