"use client";

import * as React from "react";
import { BadgeCheck } from "lucide-react";
import { t } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useApprovalVersions } from "@/lib/queries-records";
import type { ProgrammeDetail } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { EmptyState } from "@/components/brand/EmptyState";

/** One programme's versions, newest first, with the current one tagged (page spec W4-11). */
function ProgrammeVersions({ p }: { p: ProgrammeDetail }) {
  const q = useApprovalVersions(p.approval.id);
  if (q.isLoading) {
    return (
      <tr aria-hidden="true">
        <td colSpan={6}>
          <Skeleton className="h-5 w-full" />
        </td>
      </tr>
    );
  }
  if (q.isError || !q.data) {
    return (
      <tr>
        <td colSpan={6} className="wrap">
          <ErrorBlock error={q.error} onRetry={() => q.refetch()} compact />
        </td>
      </tr>
    );
  }
  const items = q.data.items;
  const lower = items.find((v, i) => i + 1 < items.length && v.approved_intake < items[i + 1].approved_intake);
  return (
    <>
      {items.map((v, i) => (
        <tr key={v.version}>
          {i === 0 && (
            <th scope="rowgroup" rowSpan={items.length + (lower ? 1 : 0)} className="code px-3 text-left align-top font-medium">
              {p.code}
            </th>
          )}
          <td className="num">v{v.version}</td>
          <td className="num">{formatCount(v.approved_intake)}</td>
          <td>{formatDate(v.effective_from)}</td>
          <td className="wrap">{v.source}</td>
          <td>
            {v.version === q.data.current_version && (
              <span className="inline-flex items-center gap-1 rounded-chip border border-check-pass/40 bg-check-pass-soft px-1.5 text-xs font-medium text-check-pass-ink">
                <BadgeCheck className="size-3" aria-hidden="true" />
                {t("approval.current")}
              </span>
            )}
          </td>
        </tr>
      ))}
      {lower && (
        <tr>
          <td colSpan={5} className="wrap text-xs text-ink-muted">
            {t("approval.change_down", {
              version: lower.version,
              before: formatCount(items[items.indexOf(lower) + 1].approved_intake),
              after: formatCount(lower.approved_intake),
              date: formatDate(lower.effective_from),
            })}
          </td>
        </tr>
      )}
    </>
  );
}

/**
 * Approval versions per programme (page spec W4-11, D41), read only. The
 * Seat rows of a cohort cite the current version. Recording a version is not
 * a web action; an api refusal reads err.APPROVAL_BELOW_ASSIGNED.
 */
export function ApprovalsTable({ programmes, academicYear }: { programmes: ProgrammeDetail[]; academicYear: string }) {
  if (programmes.length === 0) return <EmptyState title={t("empty.programmes")} />;
  return (
    <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
      <table className="ledger-table">
        <caption className="sr-only">{`${t("approval.versions_heading")}, ${academicYear}`}</caption>
        <thead>
          <tr>
            <th scope="col" className="code">
              {t("col.programme")}
            </th>
            <th scope="col" className="num">
              {t("approval.col.version")}
            </th>
            <th scope="col" className="num" title={t("approval.rule_tip")}>
              {t("approval.col.intake")}
            </th>
            <th scope="col">{t("approval.col.effective")}</th>
            <th scope="col">{t("approval.col.source")}</th>
            <th scope="col">
              <span className="sr-only">{t("approval.current")}</span>
            </th>
          </tr>
        </thead>
        {[...programmes]
          .sort((a, b) => a.code.localeCompare(b.code))
          .map((p) => (
            <tbody key={p.id}>
              <ProgrammeVersions p={p} />
            </tbody>
          ))}
      </table>
    </div>
  );
}
