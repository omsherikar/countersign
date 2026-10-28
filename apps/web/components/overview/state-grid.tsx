"use client";

import * as React from "react";
import { EmptyState } from "@/components/brand/EmptyState";
import { StateGridCard } from "@/components/brand/StateGridCard";
import { t } from "@/lib/copy";
import { admittedOf } from "@/lib/counts";
import { formatCount } from "@/lib/format";
import { REGION_NAME } from "@/lib/roles";
import type { DashboardSummary, Region, RegionMeta, RegionSummaryRow } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * By state as a grid of state cards grouped under their regional office
 * (decision D8: a grid, never a map). Picking a card filters the
 * institutions table to that state and scrolls to it.
 */
export function StateGrid({
  summary,
  loading,
  tableAnchor = "institutions",
}: {
  summary: DashboardSummary | undefined;
  loading: boolean;
  tableAnchor?: string;
}) {
  const [params, set] = useUrlParams();
  const selected = params.get("state");

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-hidden="true">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} className="h-32 rounded-md" />
        ))}
      </div>
    );
  }
  if (!summary) return null;
  if (summary.by_state.length === 0) return <EmptyState title={t("empty.by_state")} />;

  const regionRows = new Map(summary.by_region.map((r) => [r.region, r]));
  const groups = new Map<Region, DashboardSummary["by_state"]>();
  for (const row of summary.by_state) {
    const list = groups.get(row.region) ?? [];
    list.push(row);
    groups.set(row.region, list);
  }
  const ordered = [...groups.entries()].sort((a, b) =>
    (regionRows.get(a[0])?.region_name ?? REGION_NAME[a[0]]).localeCompare(regionRows.get(b[0])?.region_name ?? REGION_NAME[b[0]]),
  );

  function pick(code: string) {
    set({ state: selected === code ? null : code, page: null });
    if (selected !== code) document.getElementById(tableAnchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="gap-8 xl:columns-2">
      {ordered.map(([region, rows]) => {
        const r = regionRows.get(region);
        const name = r?.region_name ?? REGION_NAME[region];
        return (
          <section key={region} aria-label={name} className="mb-6 break-inside-avoid">
            <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 border-b border-rule-strong pb-1.5">
              <h3 className="font-sans text-md font-semibold">{name}</h3>
              {r && (
                <p className="num text-xs text-ink-muted">
                  {formatCount(r.institutions)} institutions, {formatCount(r.enrolments)} students on roll
                </p>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(10.5rem,1fr))]">
              {rows.map((row) => (
                <StateGridCard key={row.state_code} row={row} selected={selected === row.state_code} onSelect={pick} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

/**
 * By region: all ten regional offices, sorted by name, with zero rows for
 * an office that has no institutions this year (the api drops those rows).
 */
export function RegionTable({ summary, regions }: { summary: DashboardSummary; regions?: RegionMeta[] }) {
  const byCode = new Map(summary.by_region.map((r) => [r.region, r]));
  const rows: RegionSummaryRow[] = regions?.length
    ? [...regions]
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(
          (m) =>
            byCode.get(m.code) ?? {
              region: m.code,
              region_name: `${m.name} (${m.hq_city})`,
              institutions: 0,
              approved_seats: 0,
              admitted: 0,
              enrolments: 0,
              flags_open: 0,
            },
        )
    : summary.by_region;
  const withAdmitted = summary.by_region.some((r) => admittedOf(r) !== null);
  return (
    <div className="relative overflow-x-auto bg-paper-raised">
      <table className="ledger-table">
        <caption className="sr-only">{t("section.by_region")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("col.region")}</th>
            <th scope="col" className="num">
              {t("kpi.institutions")}
            </th>
            <th scope="col" className="num" title={t("app.hint.intake", { academic_year: summary.academic_year })}>
              {t("col.approved_seats")}
            </th>
            {withAdmitted && (
              <th scope="col" className="num" title={t("col.admitted_tip", { academic_year: summary.academic_year })}>
                {t("col.admitted")}
              </th>
            )}
            <th scope="col" className="num" title={t("app.on_roll_tip")}>
              {t("app.on_roll")}
            </th>
            <th scope="col" className="num">
              {t("col.flags_open")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.region}>
              <td className={r.institutions === 0 ? "text-ink-muted" : undefined}>{r.region_name}</td>
              <td className="num">{formatCount(r.institutions)}</td>
              <td className="num">{formatCount(r.approved_seats)}</td>
              {withAdmitted && <td className="num">{formatCount(admittedOf(r) ?? 0)}</td>}
              <td className="num">{formatCount(r.enrolments)}</td>
              <td className={r.flags_open > 0 ? "num font-medium text-check-fail-ink" : "num text-ink-muted"}>{formatCount(r.flags_open)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
