import * as React from "react";
import { ChevronsUp, CircleCheck, CircleDot, FileQuestion, Stamp } from "lucide-react";
import { tk } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** Mirrors `FlagStatus` in lib/types.ts. */
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "CLEARED" | "ESCALATED" | "CONFIRMED";

export const FLAG_STATUS_LABEL = Object.fromEntries(
  (["OPEN", "DOCS_REQUESTED", "CLEARED", "ESCALATED", "CONFIRMED"] as const).map((s) => [s, tk(`flag_status.${s}`)]),
) as Record<FlagStatus, string>;

const STYLE: Record<FlagStatus, { chip: string; Icon: React.ComponentType<{ className?: string }> }> = {
  OPEN: { chip: "bg-flag-open-soft text-flag-open-ink border-flag-open/40", Icon: CircleDot },
  DOCS_REQUESTED: { chip: "bg-flag-docs-soft text-flag-docs-ink border-flag-docs/40", Icon: FileQuestion },
  CLEARED: { chip: "bg-flag-cleared-soft text-flag-cleared-ink border-flag-cleared/40", Icon: CircleCheck },
  ESCALATED: { chip: "bg-flag-escalated-soft text-flag-escalated-ink border-flag-escalated/40", Icon: ChevronsUp },
  CONFIRMED: { chip: "bg-flag-confirmed-soft text-flag-confirmed-ink border-flag-confirmed/40", Icon: Stamp },
};

export interface FlagStatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: FlagStatus;
  /** Glyph only; the word stays in the accessible name. */
  compact?: boolean;
}

/**
 * Where a flag is in its life: raised, waiting on the college, closed as
 * clear, sent up a level, or confirmed by an officer. CONFIRMED is the only
 * state that says a problem is real, and it wears the stamp glyph.
 */
export function FlagStatusBadge({ status, compact = false, className, ...rest }: FlagStatusBadgeProps) {
  const { chip, Icon } = STYLE[status];
  const label = FLAG_STATUS_LABEL[status];
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-chip border px-1.5 text-xs font-medium leading-none",
        compact && "w-5 justify-center px-0",
        chip,
        className,
      )}
      {...rest}
    >
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      {!compact && <span>{label}</span>}
    </span>
  );
}
