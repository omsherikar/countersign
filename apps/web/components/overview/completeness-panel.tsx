"use client";

import * as React from "react";
import Link from "next/link";
import { t } from "@/lib/copy";
import { formatCount } from "@/lib/format";
import { useCompletenessList } from "@/lib/queries-records";
import type { DashboardSummary } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { DeadlineWord } from "@/components/records/deadline-word";
import { pctWord } from "@/components/records/status-panel";

/**
 * Completeness and deadlines (page spec W4-3): the scope's completeness
 * tile, late and overdue colleges, and the colleges with most students
 * missing from their uploads, each with its deadline word.
 */
export function CompletenessPanel({ summary, basePath, academicYear }: { summary: DashboardSummary | undefined; basePath: string; academicYear: string }) {
  const list = useCompletenessList({ academic_year: academicYear, sort: "missing_desc", page_size: 8 });
  const data = list.data;
  const k = summary?.kpis;
  return (
    <div className="flex flex-col gap-3">
      <dl className="grid grid-cols-3 border-y border-rule-strong bg-paper-raised">
        <div className="flex min-w-0 flex-col gap-1 px-3 py-2.5" title={t("completeness.tip", { academic_year: academicYear })}>
          <dt className="truncate text-xs font-medium text-ink-muted">{t("kpi.completeness")}</dt>
          <dd className="font-display text-xl leading-tight font-semibold">{k ? (k.completeness_pct === null ? <span className="text-sm font-normal text-ink-muted italic">{t("kpi.not_computed")}</span> : pctWord(k.completeness_pct)) : <Skeleton className="h-6 w-14" />}</dd>
          {k && k.completeness_pct !== null && <dd className="text-xs text-ink-muted">{t("completeness.col_missing")} {formatCount(k.missing_from_upload)}</dd>}
        </div>
        <div className="flex min-w-0 flex-col gap-1 border-l border-rule px-3 py-2.5">
          <dt className="truncate text-xs font-medium text-ink-muted">{t("deadline.LATE")}</dt>
          <dd className="font-display text-xl leading-tight font-semibold">{k ? formatCount(k.colleges_late) : <Skeleton className="h-6 w-10" />}</dd>
        </div>
        <div className="flex min-w-0 flex-col gap-1 border-l border-rule px-3 py-2.5">
          <dt className="truncate text-xs font-medium text-ink-muted">{t("deadline.OVERDUE")}</dt>
          <dd className="font-display text-xl leading-tight font-semibold">{k ? formatCount(k.colleges_overdue) : <Skeleton className="h-6 w-10" />}</dd>
        </div>
      </dl>
      {list.isError && !data ? (
        <ErrorBlock error={list.error} onRetry={() => list.refetch()} compact />
      ) : !data ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
          <table className="ledger-table ledger-table--dense">
            <caption className="sr-only">{t("completeness.panel_heading")}</caption>
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-[2] bg-paper-raised">
                  {t("completeness.col_college")}
                </th>
                <th scope="col" className="num" title={t("completeness.tip", { academic_year: academicYear })}>
                  {t("completeness.col")}
                </th>
                <th scope="col" className="num">
                  {t("completeness.col_missing")}
                </th>
                <th scope="col">{t("deadline.col")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.institution.id}>
                  <td className="sticky left-0 z-[1] max-w-[14rem] truncate bg-paper-raised" title={r.institution.name}>
                    <Link href={`${basePath}/institutions/${r.institution.id}#completeness`}>{r.institution.name}</Link>
                  </td>
                  <td className="num">
                    {r.completeness_pct === null ? (
                      <span className="text-xs whitespace-normal text-ink-muted">{r.published ? t("kpi.not_computed") : t("completeness.line_none")}</span>
                    ) : (
                      pctWord(r.completeness_pct)
                    )}
                  </td>
                  <td className={r.missing > 0 ? "num font-semibold" : "num text-ink-muted"}>{formatCount(r.missing)}</td>
                  <td>
                    <DeadlineWord state={r.deadline_state} deadline={data.deadline} firstUploadAt={r.first_upload_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
