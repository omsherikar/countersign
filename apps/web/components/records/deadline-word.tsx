import * as React from "react";
import { Calendar, CalendarCheck, CalendarClock, CalendarX } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatCardDate } from "@/lib/format";
import type { DeadlineState } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICON = { NOT_DUE: Calendar, ON_TIME: CalendarCheck, LATE: CalendarClock, OVERDUE: CalendarX } as const;

/** deadline.tip.*: the dates behind the word, as visible text where the page has room (W4-4). */
export function deadlineTip(state: DeadlineState, deadline: string, firstUploadAt: string | null): string {
  return tk(`deadline.tip.${state}`, { deadline_date: formatCardDate(deadline), uploaded_date: formatCardDate(firstUploadAt) });
}

/**
 * On time, Late, Overdue or Due {date}, each with its icon (page spec W4,
 * marks table). Late and Overdue use the caution hue for the icon only: the
 * word stays ink, never red text.
 */
export function DeadlineWord({ state, deadline, firstUploadAt, className }: { state: DeadlineState; deadline: string; firstUploadAt?: string | null; className?: string }) {
  const Icon = ICON[state];
  const word = state === "NOT_DUE" ? t("deadline.NOT_DUE", { deadline_date: formatCardDate(deadline) }) : tk(`deadline.${state}`);
  // Without the first upload's date (institution rows do not carry it) only the tips that need none are shown.
  const needsUpload = state === "ON_TIME" || state === "LATE";
  const tip = needsUpload && !firstUploadAt ? undefined : deadlineTip(state, deadline, firstUploadAt ?? null);
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap", className)} title={tip}>
      <Icon className={cn("size-3.5 shrink-0", state === "LATE" || state === "OVERDUE" ? "text-check-pending" : "text-ink-muted")} aria-hidden="true" />
      {word}
    </span>
  );
}

/** "92% of joined students uploaded, 14 missing", the full line, or none published yet (copy deck §24). */
export function completenessLine(c: { completeness_pct: number | null; missing: number; joined: number; published: boolean }): string {
  if (c.completeness_pct === null) return c.published ? t("kpi.not_computed") : t("completeness.line_none");
  if (c.missing === 0) return t("completeness.line_full", { joined: c.joined });
  return t("completeness.line", { pct: String(Math.round(c.completeness_pct * 10) / 10).replace(/\.0$/, ""), missing: c.missing });
}
