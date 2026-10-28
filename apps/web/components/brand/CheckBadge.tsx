import * as React from "react";
import { CalendarClock, Check, Clock, CloudOff, Minus, X, type LucideIcon } from "lucide-react";
import { stateWord } from "@/lib/checks";
import { tk } from "@/lib/copy";
import type { CheckType, EvidenceState } from "@/lib/types";
import { cn } from "@/lib/utils";

export type { CheckType, EvidenceState };

/** Icon and hue per evidence state (page spec W4, the marks table). */
export const STATE_MARK: Record<EvidenceState, { chip: string; ink: string; Icon: LucideIcon }> = {
  CONFIRMED: { chip: "bg-check-pass-soft text-check-pass-ink border-check-pass/40", ink: "text-check-pass-ink", Icon: Check },
  CONTRADICTED: { chip: "bg-check-fail-soft text-check-fail-ink border-check-fail/50", ink: "text-check-fail-ink", Icon: X },
  PENDING: { chip: "bg-check-pending-soft text-check-pending-ink border-check-pending/40 border-dashed", ink: "text-check-pending-ink", Icon: Clock },
  NOT_YET_DUE: { chip: "bg-check-na-soft text-check-na-ink border-check-na/40 border-dotted", ink: "text-check-na-ink", Icon: CalendarClock },
  NOT_APPLICABLE: { chip: "bg-check-na-soft text-check-na-ink border-check-na/40 border-dotted", ink: "text-check-na-ink", Icon: Minus },
  SOURCE_UNAVAILABLE: { chip: "bg-check-pending-soft text-check-pending-ink border-check-pending/40 border-dashed", ink: "text-check-pending-ink", Icon: CloudOff },
};

export interface CheckBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: EvidenceState;
  /** When given, the badge reads "Identity: Confirmed". */
  type?: CheckType;
  /** Glyph only, the word in the accessible name. For dense table cells. */
  compact?: boolean;
  /** Overrides the state word, e.g. "Confirmed: fits approved intake". */
  word?: string;
}

/**
 * One evidence row's state (copy deck §21). Colour never carries the meaning
 * alone: every badge has a glyph and a word, and the states that hold no
 * fact also differ by border style so they survive greyscale print.
 */
export function CheckBadge({ status, type, compact = false, word, className, ...rest }: CheckBadgeProps) {
  const { chip, Icon } = STATE_MARK[status];
  const statusLabel = word ?? stateWord(status);
  const label = type ? `${tk(`check.${type}`)}: ${statusLabel}` : statusLabel;
  return (
    <span
      role="img"
      aria-label={label}
      title={tk(`evidence.tip.${status}`)}
      className={cn(
        "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-chip border px-1.5 text-xs font-medium leading-none",
        compact && "w-5 justify-center px-0",
        chip,
        className,
      )}
      {...rest}
    >
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      {!compact && <span>{type ? tk(`check.${type}`) : statusLabel}</span>}
      {!compact && type && <span className="opacity-70">{statusLabel}</span>}
    </span>
  );
}
