import * as React from "react";
import { cn } from "@/lib/utils";

export interface MaskedApaarProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** `apaar_masked` from the wire, e.g. "XXXX XXXX 4417", or null. */
  apaarMasked: string | null;
  /** `provisional_id`, e.g. "PRV-3F9A2C1B", shown when there is no APAAR. */
  provisionalId?: string | null;
}

/**
 * The only shape of an APAAR id the web ever sees: masked, last four digits
 * visible. The mask is drawn in the mono face with the X groups dimmed so
 * the four real digits are the thing the eye lands on. When the student has
 * no APAAR (refused, pending, international) the provisional id takes its
 * place, visibly different so nobody mistakes it for a verified id.
 */
export function MaskedApaar({ apaarMasked, provisionalId, className, ...rest }: MaskedApaarProps) {
  if (!apaarMasked) {
    if (!provisionalId) {
      return (
        <span className={cn("font-mono text-xs text-ink-faint", className)} {...rest}>
          no id
        </span>
      );
    }
    return (
      <span
        className={cn("font-mono text-xs tracking-wide text-ink-muted", className)}
        title="Provisional id. The student has no linked APAAR."
        aria-label={`Provisional id ${provisionalId}`}
        {...rest}
      >
        <span className="opacity-60">PRV-</span>
        {provisionalId.replace(/^PRV-/, "")}
      </span>
    );
  }
  const groups = apaarMasked.trim().split(/\s+/);
  const last = groups[groups.length - 1];
  const masked = groups.slice(0, -1);
  return (
    <span
      className={cn("font-mono text-xs tracking-wide text-ink", className)}
      aria-label={`APAAR ending ${last}`}
      title="APAAR, masked. Only the last four digits are ever shown."
      {...rest}
    >
      {masked.map((g, i) => (
        <span key={i} className="text-ink-faint" aria-hidden="true">
          {g}{" "}
        </span>
      ))}
      <span className="font-medium">{last}</span>
    </span>
  );
}
