import * as React from "react";
import { Clock, Globe, Link2, Link2Off } from "lucide-react";
import { cn } from "@/lib/utils";

/** Mirrors `ConsentStatus` in lib/types.ts. */
export type ConsentStatus = "LINKED" | "REFUSED" | "PENDING" | "INTERNATIONAL";

export const CONSENT_LABEL: Record<ConsentStatus, string> = {
  LINKED: "APAAR linked",
  REFUSED: "APAAR refused",
  PENDING: "Consent pending",
  INTERNATIONAL: "International",
};

const STYLE: Record<ConsentStatus, { chip: string; Icon: React.ComponentType<{ className?: string }> }> = {
  LINKED: { chip: "bg-consent-linked-soft text-consent-linked-ink border-consent-linked/40", Icon: Link2 },
  // Neutral on purpose: refusing APAAR is lawful and never blocks admission.
  REFUSED: { chip: "bg-consent-refused-soft text-consent-refused-ink border-consent-refused/40", Icon: Link2Off },
  PENDING: { chip: "bg-consent-pending-soft text-consent-pending-ink border-consent-pending/40 border-dashed", Icon: Clock },
  INTERNATIONAL: {
    chip: "bg-consent-international-soft text-consent-international-ink border-consent-international/40",
    Icon: Globe,
  },
};

export interface ConsentBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: ConsentStatus;
  /** Glyph only; the word stays in the accessible name. */
  compact?: boolean;
}

/**
 * Whether the student's APAAR is linked. REFUSED is grey, not red: the
 * Supreme Court order and the DPDP Act make APAAR optional, so a refusal is
 * a fact about identity checks, not a mark against the student.
 */
export function ConsentBadge({ status, compact = false, className, ...rest }: ConsentBadgeProps) {
  const { chip, Icon } = STYLE[status];
  const label = CONSENT_LABEL[status];
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
