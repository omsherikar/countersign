"use client";

import * as React from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { STATUS_ORDER, statusWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import { formatCount } from "@/lib/format";
import type { RecordCounts, RecordStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { STATUS_MARK } from "@/components/records/record-status-badge";

/** One decimal as sent, a trailing ".0" dropped: 49.6%, 0.2%, 100%. */
export function pctWord(n: number | null): string {
  if (n === null) return "";
  return `${String(Math.round(n * 10) / 10).replace(/\.0$/, "")}%`;
}

function shares(counts: RecordCounts): Record<RecordStatus, number | null> {
  const total = STATUS_ORDER.reduce((a, s) => a + counts[s], 0);
  return Object.fromEntries(STATUS_ORDER.map((s) => [s, total === 0 ? null : Math.round((counts[s] / total) * 1000) / 10])) as Record<
    RecordStatus,
    number | null
  >;
}

const BAR: Record<RecordStatus, string> = {
  AWAITING_EVIDENCE: "bg-check-pending",
  COUNTERSIGNED: "bg-check-pass",
  UNDER_REVIEW: "bg-flag-open",
  DISPUTED: "bg-check-fail",
};

/**
 * Records by status (page spec W4-3): four tiles in the legend's order, each
 * the icon and word, the count and share, linking to the list filtered by
 * that status; the evidence rule under them. With `chart`, a bar per status
 * sits beside a table of the same numbers (D46: every chart has its table).
 */
export function StatusPanel({
  counts,
  academicYear,
  hrefFor,
  chart = false,
  loading = false,
  failed = false,
  onRetry,
  headingId,
}: {
  counts: RecordCounts | undefined;
  academicYear: string;
  hrefFor?: (status: RecordStatus) => string | null;
  chart?: boolean;
  loading?: boolean;
  failed?: boolean;
  onRetry?: () => void;
  headingId?: string;
}) {
  const share = counts ? shares(counts) : null;
  const max = counts ? Math.max(1, ...STATUS_ORDER.map((s) => counts[s])) : 1;
  return (
    <div className="flex flex-col gap-3">
      <ul
        className="grid grid-cols-2 border-y border-rule-strong bg-paper-raised lg:grid-cols-4"
        aria-labelledby={headingId}
        title={t("kpi.status_tip", { academic_year: academicYear })}
      >
        {STATUS_ORDER.map((s, i) => {
          const { Icon, ink } = STATUS_MARK[s];
          const href = hrefFor?.(s) ?? null;
          const body = (
            <div className="flex h-full min-w-0 flex-col gap-1 px-4 py-3">
              <span className={cn("inline-flex items-center gap-1.5 text-sm font-semibold", ink)}>
                <Icon className="size-4 shrink-0" aria-hidden="true" />
                {statusWord(s)}
              </span>
              {loading ? (
                <Skeleton className="h-7 w-24" />
              ) : failed || !counts ? (
                <span className="flex items-center gap-1.5 text-sm text-ink-muted">
                  {t("err.tile_failed")}
                  {onRetry && (
                    <button type="button" onClick={onRetry} aria-label={`${t("err.retry")}: ${statusWord(s)}`} className="rounded-chip p-0.5 text-ink-blue">
                      <RefreshCw className="size-3.5" aria-hidden="true" />
                    </button>
                  )}
                </span>
              ) : (
                <>
                  <span className="font-display text-2xl leading-none font-semibold text-ink" style={{ fontVariantNumeric: "lining-nums proportional-nums" }}>
                    {formatCount(counts[s])}
                  </span>
                  <span
                    className="text-xs text-ink-muted"
                    aria-label={
                      share?.[s] === null ? undefined : t("kpi.status_value", { n: formatCount(counts[s]), pct: pctWord(share![s]).replace("%", "") })
                    }
                  >
                    {share?.[s] === null ? t("kpi.not_computed") : pctWord(share![s])}
                  </span>
                </>
              )}
            </div>
          );
          return (
            <li key={s} className={cn("min-w-0 border-rule", i % 2 === 1 && "border-l", i >= 2 && "border-t lg:border-t-0", i > 0 && "lg:border-l")}>
              {href && counts ? (
                <Link
                  href={href}
                  className="block h-full text-ink no-underline outline-offset-[-2px] hover:bg-flag-open-soft/60"
                  title={tk(`record_status.meaning.${s}`)}
                >
                  {body}
                </Link>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ul>
      <p className="max-w-[90ch] text-sm text-ink-muted">{t("record_status.rule")}</p>
      {chart && counts && (
        <div className="grid grid-cols-1 gap-x-8 gap-y-4 lg:grid-cols-2">
          <table className="ledger-table ledger-table--dense order-2 lg:order-1">
            <caption className="sr-only">{t("kpi.status_heading")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("col.record_status")}</th>
                <th scope="col" className="num">
                  {t("kpi.status_heading")}
                </th>
                <th scope="col" className="num">
                  %
                </th>
              </tr>
            </thead>
            <tbody>
              {STATUS_ORDER.map((s) => {
                const { Icon, ink } = STATUS_MARK[s];
                return (
                  <tr key={s}>
                    <th scope="row" className="px-3 text-left font-medium">
                      <span className={cn("inline-flex items-center gap-1.5", ink)}>
                        <Icon className="size-3.5 shrink-0" aria-hidden="true" />
                        {statusWord(s)}
                      </span>
                    </th>
                    <td className="num">{formatCount(counts[s])}</td>
                    <td className="num">{pctWord(share![s])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="order-1 flex flex-col gap-2 lg:order-2" aria-hidden="true">
            {STATUS_ORDER.map((s) => (
              <div key={s} className="grid grid-cols-[8.5rem_1fr_3.5rem] items-center gap-2 text-xs">
                <span className="truncate text-ink-muted">{statusWord(s)}</span>
                <span className="h-4 rounded-sm bg-paper-sunken">
                  <span className={cn("block h-full rounded-sm", BAR[s])} style={{ width: `${(counts[s] / max) * 100}%`, minWidth: counts[s] > 0 ? 2 : 0 }} />
                </span>
                <span className="num text-right text-ink">{formatCount(counts[s])}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
