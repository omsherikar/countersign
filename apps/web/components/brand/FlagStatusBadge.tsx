import * as React from "react";
import { ChevronsUp, CircleCheck, CircleDot, CircleSlash, FileQuestion, PencilLine } from "lucide-react";
import { tk } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** Mirrors `FlagStatus` in lib/types.ts. */
export type FlagStatus = "OPEN" | "DOCS_REQUESTED" | "UPHELD" | "ESCALATED" | "WITHDRAWN" | "CORRECTED";

export const FLAG_STATUS_LABEL = Object.fromEntries(
  (["OPEN", "DOCS_REQUESTED", "UPHELD", "ESCALATED", "WITHDRAWN", "CORRECTED"] as const).map((s) => [s, tk(`flag_status.${s}`)]),
) as Record<FlagStatus, string>;

const STYLE: Record<FlagStatus, { chip: string; Icon: React.ComponentType<{ className?: string }> }> = {
  OPEN: { chip: "bg-flag-open-soft text-flag-open-ink border-flag-open/40", Icon: CircleDot },
  DOCS_REQUESTED: { chip: "bg-flag-docs-soft text-flag-docs-ink border-flag-docs/40", Icon: FileQuestion },
  UPHELD: { chip: "bg-flag-cleared-soft text-flag-cleared-ink border-flag-cleared/40", Icon: CircleCheck },
  ESCALATED: { chip: "bg-flag-escalated-soft text-flag-escalated-ink border-flag-escalated/40", Icon: ChevronsUp },
  CORRECTED: { chip: "bg-flag-open-soft text-flag-open-ink border-flag-open/40", Icon: PencilLine },
  WITHDRAWN: { chip: "bg-check-na-soft text-check-na-ink border-check-na/40", Icon: CircleSlash },
};

export interface FlagStatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: FlagStatus;
  /** Glyph only; the word stays in the accessible name. */
  compact?: boolean;
}

/**
 * Where a case is in its life: open, waiting on the college, sent up to
 * AICTE, or decided as Claim upheld, Claim corrected or Claim withdrawn
 * (W4 marks table). Each word travels with its icon; no decision is red.
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
