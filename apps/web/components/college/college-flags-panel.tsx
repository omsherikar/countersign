"use client";

import Link from "next/link";
import { Flag } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate, singular } from "@/lib/format";
import { useFlags } from "@/lib/queries";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { SectionHeader } from "@/components/common/page-header";
import { DEFAULT_STATUS } from "@/components/flags/flags-table";
import { SeverityBars } from "@/components/flags/flag-chip";

/** The five newest unresolved cases against the college, summaries verbatim (W4-3). */
export function CollegeFlagsPanel({ academicYear }: { academicYear: string }) {
  const list = useFlags({ status: DEFAULT_STATUS, academic_year: academicYear, page_size: 5, sort: "created_desc" });
  const data = list.data;
  return (
    <section aria-labelledby="flags-heading" className="mb-10">
      <SectionHeader
        id="flags-heading"
        title={t("flags.heading_college")}
        aside={
          data && data.total > 0 ? (
            <>
              <span>{singular(t("table.count.flags_one", { total: formatCount(data.total) }))}</span>
              <Link href="/college/flags">{t("flags.see_all")}</Link>
            </>
          ) : undefined
        }
      />
      {list.isLoading && <Skeleton className="h-40" />}
      {list.isError && !data && <ErrorBlock error={list.error} onRetry={() => list.refetch()} />}
      {data && data.items.length === 0 && (
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          <EmptyState icon={<Flag className="size-5" />} title={t("empty.flags_college")} />
        </div>
      )}
      {data && data.items.length > 0 && (
        <ul className="divide-y divide-rule border-y border-rule bg-paper-raised">
          {data.items.map((f) => (
            <li key={f.id} className="grid grid-cols-1 gap-x-4 gap-y-0.5 px-4 py-2.5 sm:grid-cols-[9rem_1fr_auto] sm:items-baseline">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted">
                <SeverityBars severity={f.severity} />
                {f.programme ? `${tk(`severity.${f.severity}`)}, ${f.programme.code}` : tk(`severity.${f.severity}`)}
              </span>
              <span className="min-w-0">
                <Link href={`/college/flags/${f.id}`} className="font-medium">
                  {tk(`flag.${f.type}.name`)}
                </Link>
                <span className="block text-sm text-ink">{f.summary}</span>
              </span>
              <span className="num text-xs text-ink-muted">{formatDate(f.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
