import * as React from "react";
import { CircleDot, CircleSlash, FolderOpen, Network, Sigma, type LucideIcon } from "lucide-react";
import { t, tk } from "@/lib/copy";
import type { SignalStatus, SignalType } from "@/lib/types";
import { cn } from "@/lib/utils";

export const SIGNAL_TYPE_ICON: Record<SignalType, LucideIcon> = { GHOST_RING: Network, ANOMALY: Sigma };

const STATUS: Record<SignalStatus, { Icon: LucideIcon; chip: string }> = {
  NEW: { Icon: CircleDot, chip: "bg-flag-open-soft text-flag-open-ink border-flag-open/40" },
  CASE_OPENED: { Icon: FolderOpen, chip: "bg-flag-escalated-soft text-flag-escalated-ink border-flag-escalated/40" },
  DISMISSED: { Icon: CircleSlash, chip: "bg-check-na-soft text-check-na-ink border-check-na/40 border-dashed" },
};

/** New, Case opened or Dismissed: always the word with its icon (W4 marks). */
export function SignalStatusBadge({ status, className }: { status: SignalStatus; className?: string }) {
  const { Icon, chip } = STATUS[status];
  return (
    <span className={cn("inline-flex h-5 items-center gap-1 rounded-chip border px-1.5 text-xs font-medium whitespace-nowrap", chip, className)}>
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      <span>{tk(`signal.status.${status}`)}</span>
    </span>
  );
}

/** "Shared contact ring" or "Unusual pattern" with its glyph. */
export function SignalTypeWord({ type, className }: { type: SignalType; className?: string }) {
  const Icon = SIGNAL_TYPE_ICON[type];
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <Icon className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
      <span>{tk(`signal.type.${type}`)}</span>
    </span>
  );
}

/** The line every signal page carries: signals never change a record's status. */
export function NeverStatusLine({ className }: { className?: string }) {
  return <p className={cn("max-w-[68ch] border-l-2 border-rule-strong pl-3 text-sm text-ink", className)}>{t("signal.never_status")}</p>;
}

/** "40 students across 3 colleges..." count wording: "1 signal" when there is one. */
export function countLine(total: number, fresh: number): string {
  const text = t("signal.count", { total, new: fresh });
  return total === 1 ? text.replace("1 signals", "1 signal") : text;
}
