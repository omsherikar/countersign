import * as React from "react";
import Link from "next/link";
import { t, tk } from "@/lib/copy";
import type { FlagRef, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE: Record<Severity, string> = {
  LOW: "bg-severity-low-soft text-severity-low-ink border-severity-low/40",
  MEDIUM: "bg-severity-medium-soft text-severity-medium-ink border-severity-medium/40",
  HIGH: "bg-severity-high-soft text-severity-high-ink border-severity-high/40",
};
const BARS: Record<Severity, number> = { LOW: 1, MEDIUM: 2, HIGH: 3 };

/** The severity meter: one, two or three bars, so the level reads without colour. */
export function SeverityBars({ severity }: { severity: Severity }) {
  return (
    <span className="inline-flex items-end gap-px" aria-hidden="true">
      {[1, 2, 3].map((i) => (
        <span key={i} className={cn("w-[3px] rounded-[1px] bg-current", i <= BARS[severity] ? "opacity-100" : "opacity-25")} style={{ height: 4 + i * 2.5 }} />
      ))}
    </span>
  );
}

/**
 * One unresolved flag on an enrolment row: severity meter and the flag's
 * name, accessible name "Excess admission, High" (flag.chip). With `href`
 * the chip opens the flag.
 */
export function FlagChip({ flag, href, className }: { flag: Pick<FlagRef, "type" | "severity">; href?: string; className?: string }) {
  const label = t("flag.chip", { type_name: tk(`flag.${flag.type}.name`), severity_word: tk(`severity.${flag.severity}`) });
  const body = (
    <>
      <SeverityBars severity={flag.severity} />
      <span className="max-w-32 truncate">{tk(`flag.${flag.type}.name`)}</span>
    </>
  );
  const cls = cn(
    "inline-flex h-5 items-center gap-1.5 rounded-chip border px-1.5 font-sans text-xs font-medium whitespace-nowrap no-underline",
    TONE[flag.severity],
    className,
  );
  if (href) {
    return (
      <Link href={href} aria-label={label} title={label} className={cn(cls, "hover:underline")}>
        {body}
      </Link>
    );
  }
  return (
    <span role="img" aria-label={label} title={label} className={cls}>
      {body}
    </span>
  );
}

/** At most two chips, then "+n" (flags.more). */
export function FlagChips({ flags, hrefFor }: { flags: FlagRef[]; hrefFor?: (id: string) => string }) {
  if (flags.length === 0) return <span className="sr-only">{t("app.none")}</span>;
  return (
    <span className="flex items-center gap-1">
      {flags.slice(0, 2).map((f) => (
        <FlagChip key={f.id} flag={f} href={hrefFor?.(f.id)} />
      ))}
      {flags.length > 2 && <span className="text-xs text-ink-muted">{t("flags.more", { n: flags.length - 2 })}</span>}
    </span>
  );
}
