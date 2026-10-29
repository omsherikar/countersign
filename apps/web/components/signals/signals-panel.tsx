"use client";

import Link from "next/link";
import { t } from "@/lib/copy";
import { useSignals } from "@/lib/queries-signals";
import { ErrorBlock } from "@/components/common/query-state";
import { SectionHeader } from "@/components/common/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { NeverStatusLine, SignalStatusBadge, SignalTypeWord, countLine } from "@/components/signals/signal-bits";

/**
 * The officers' dashboard panel (W4-3, W4-6): how many signals there are,
 * the newest ones not yet handled, and the way to the full list. Only the
 * AICTE and regional dashboards render it; no other page asks for signals.
 */
export function SignalsPanel({ variant, academicYear }: { variant: "aicte" | "ro"; academicYear: string }) {
  const q = useSignals({ academic_year: academicYear, page_size: 200 });
  const base = `/${variant}/signals`;
  const fresh = q.data?.items.filter((s) => s.status === "NEW") ?? [];
  return (
    <section aria-labelledby="signals-panel-heading" className="mb-12">
      <SectionHeader
        id="signals-panel-heading"
        title={t("signal.panel_heading")}
        aside={q.data ? <span>{countLine(q.data.total, fresh.length)}</span> : undefined}
      />
      {q.isError && !q.data ? (
        <ErrorBlock error={q.error} onRetry={() => q.refetch()} compact />
      ) : !q.data ? (
        <div aria-hidden="true" className="flex flex-col gap-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : (
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          {fresh.length === 0 ? (
            <p className="px-4 py-4 text-sm text-ink-muted">{t("signal.panel_none", { academic_year: academicYear })}</p>
          ) : (
            <ul className="divide-y divide-rule">
              {fresh.slice(0, 3).map((s) => (
                <li key={s.id}>
                  <Link href={`${base}/${s.id}`} className="flex flex-col gap-1 px-4 py-3 text-ink no-underline hover:bg-paper-sunken sm:flex-row sm:items-start sm:gap-4">
                    <span className="flex shrink-0 items-center gap-2 font-medium text-ink-blue sm:w-56">
                      <SignalTypeWord type={s.type} />
                    </span>
                    <span className="min-w-0 flex-1 leading-snug">{s.summary}</span>
                    <SignalStatusBadge status={s.status} className="w-fit shrink-0" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-col gap-2 border-t border-rule px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <NeverStatusLine className="border-l-0 pl-0 text-ink-muted" />
            <Link href={base} className="inline-flex min-h-11 shrink-0 items-center font-medium sm:min-h-0">
              {t("signal.panel_more")}
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
