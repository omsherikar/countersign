import * as React from "react";
import { BadgeCheck, FileSearch, Hourglass, OctagonAlert, type LucideIcon } from "lucide-react";
import { statusWord } from "@/lib/checks";
import { tk } from "@/lib/copy";
import type { RecordStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Icon and hue per status (page spec W4, the marks table). The word always travels with them. */
export const STATUS_MARK: Record<RecordStatus, { Icon: LucideIcon; chip: string; ink: string }> = {
  AWAITING_EVIDENCE: { Icon: Hourglass, chip: "bg-check-pending-soft text-check-pending-ink border-check-pending/50 border-dashed", ink: "text-check-pending-ink" },
  COUNTERSIGNED: { Icon: BadgeCheck, chip: "bg-check-pass-soft text-check-pass-ink border-check-pass/50", ink: "text-check-pass-ink" },
  UNDER_REVIEW: { Icon: FileSearch, chip: "bg-flag-open-soft text-flag-open-ink border-flag-open/50", ink: "text-flag-open-ink" },
  DISPUTED: { Icon: OctagonAlert, chip: "bg-check-fail-soft text-check-fail-ink border-check-fail/60 border-2", ink: "text-check-fail-ink" },
};

const SIZE = {
  sm: "h-5 gap-1 px-1.5 text-xs [&_svg]:size-3",
  md: "h-7 gap-1.5 px-2.5 text-sm [&_svg]:size-4",
  lg: "min-h-10 gap-2 px-3.5 py-1.5 text-lg font-semibold [&_svg]:size-5",
} as const;

export interface RecordStatusBadgeProps extends Omit<React.HTMLAttributes<HTMLSpanElement>, "title"> {
  status: RecordStatus | null;
  size?: keyof typeof SIZE;
  /** "Disputed (priority)": the record card's footer and header only. */
  priority?: boolean;
  /** Tooltip; defaults to record_status.meaning.* for officers and registrars. */
  tip?: string | null;
}

/**
 * A record's one status: icon and word, colour as a second cue only
 * (copy deck §21). Awaiting evidence is dashed so it survives greyscale;
 * Disputed carries the heavier border so it outranks every other mark.
 */
export function RecordStatusBadge({ status, size = "sm", priority = false, tip, className, ...rest }: RecordStatusBadgeProps) {
  if (!status) return null;
  const { Icon, chip } = STATUS_MARK[status];
  const word = statusWord(status, priority);
  const title = tip === undefined ? tk(`record_status.meaning.${status}`) : (tip ?? undefined);
  return (
    <span
      className={cn("inline-flex items-center whitespace-nowrap rounded-chip border font-medium leading-none", SIZE[size], chip, className)}
      title={title}
      {...rest}
    >
      <Icon className="shrink-0" aria-hidden="true" />
      <span>{word}</span>
    </span>
  );
}
