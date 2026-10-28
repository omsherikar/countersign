"use client";

import * as React from "react";
import { ChevronRight } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { t, tk } from "@/lib/copy";
import { seatedOf } from "@/lib/counts";
import { formatCount, formatDate } from "@/lib/format";
import type { ProgrammeDetail, SeatPool } from "@/lib/types";
import { cn } from "@/lib/utils";
import { UnseatedCount } from "@/components/common/ledger-bits";

const COLS = 8;

/** "Regular 114 of 114", "TFW 4 of 6 (supernumerary)", "International 1 of 18 (6 reserved for CIWG)". */
export function poolLine(pool: SeatPool): string {
  let line = t("pools.line", { type: tk(`seat_type.${pool.seat_type}`), assigned: formatCount(pool.assigned), capacity: formatCount(pool.capacity) });
  if (pool.is_supernumerary && !pool.reserved_for?.includes("CIWG")) line += ` ${t("pools.supernumerary")}`;
  if (pool.reserved_for && pool.reserved_for.includes("CIWG")) line += ` ${t("pools.ciwg", { n: formatCount(Math.round(pool.capacity / 3)) })}`;
  return line;
}

/** Seat pools for one programme, each with the rules.yaml clause it comes from. */
function PoolsPanel({ programme }: { programme: ProgrammeDetail }) {
  return (
    <div className="border-l-2 border-rule-margin bg-paper py-2 pr-3 pl-4">
      <table className="ledger-table ledger-table--dense">
        <caption className="sr-only">Seat pools for {programme.code}</caption>
        <thead>
          <tr>
            <th scope="col">{t("app.pools_col.pool")}</th>
            <th scope="col" className="num">
              {t("app.pools_col.seats")}
            </th>
            <th scope="col" className="num">
              {t("app.pools_col.free")}
            </th>
            <th scope="col">{t("app.pools_col.kind")}</th>
            <th scope="col">{t("col.reserved_for")}</th>
            <th scope="col">{t("app.pools_col.rule")}</th>
          </tr>
        </thead>
        <tbody>
          {programme.pools.map((pool) => (
            <tr key={pool.seat_type}>
              <td className="font-medium">{tk(`seat_type.${pool.seat_type}`)}</td>
              <td className="num">
                {formatCount(pool.assigned)} <span className="text-ink-muted">of</span> {formatCount(pool.capacity)}
              </td>
              <td className="num">{formatCount(pool.free)}</td>
              <td className="text-ink-muted">{pool.is_supernumerary ? t("app.pools.super") : t("app.pools.within")}</td>
              <td className="text-ink-muted">
                {pool.reserved_for ? (pool.reserved_for.includes("CIWG") ? t("pools.ciwg", { n: Math.round(pool.capacity / 3) }).replace(/[()]/g, "") : pool.reserved_for) : ""}
              </td>
              <td className="wrap max-w-[28rem] text-xs text-ink-muted">{pool.rule_source}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {programme.approval.cutoff_date && (
        <p className="mt-1.5 text-xs text-ink-muted">{t("app.pools.cutoff", { date: formatDate(programme.approval.cutoff_date) })}</p>
      )}
    </div>
  );
}

/**
 * Programmes with approved, admitted, seated and unseated, one expander
 * per row for the seat pools. `openWhen` decides which rows start open
 * (the registrar's ledger opens every row with unseated enrolments).
 */
export function ProgrammesTable({
  programmes,
  academicYear,
  openWhen,
  emptyText = t("empty.programmes"),
}: {
  programmes: ProgrammeDetail[];
  academicYear: string;
  openWhen?: (p: ProgrammeDetail) => boolean;
  emptyText?: string;
}) {
  const sorted = React.useMemo(() => [...programmes].sort((a, b) => a.code.localeCompare(b.code)), [programmes]);
  const [open, setOpen] = React.useState<Set<string>>(() => new Set(sorted.filter((p) => openWhen?.(p)).map((p) => p.id)));

  function toggle(id: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (programmes.length === 0) return <EmptyState title={emptyText} />;

  return (
    <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
      <table className="ledger-table">
        <caption className="sr-only">{t("section.programmes")}</caption>
        <thead>
          <tr>
            <th scope="col" className="code">
              {t("col.code")}
            </th>
            <th scope="col">{t("col.programme")}</th>
            <th scope="col">{t("col.level")}</th>
            <th scope="col">{t("col.shift")}</th>
            <th scope="col" className="num" title={t("col.approved_tip", { academic_year: academicYear })}>
              {t("col.approved")}
            </th>
            <th scope="col" className="num" title={t("col.admitted_tip", { academic_year: academicYear })}>
              {t("col.admitted")}
            </th>
            <th scope="col" className="num">
              {t("col.seated")}
            </th>
            <th scope="col" className="num">
              {t("col.unseated")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p) => {
            const isOpen = open.has(p.id);
            const panelId = `pools-${p.id}`;
            return (
              <React.Fragment key={p.id}>
                <tr data-state={isOpen ? "selected" : undefined}>
                  <td className="code">
                    <button
                      type="button"
                      aria-expanded={isOpen}
                      aria-controls={panelId}
                      onClick={() => toggle(p.id)}
                      className="inline-flex items-center gap-1 font-medium text-ink"
                    >
                      <ChevronRight className={cn("size-3.5 text-ink-muted transition-transform", isOpen && "rotate-90")} aria-hidden="true" />
                      {p.code}
                      <span className="sr-only">{isOpen ? t("pools.hide") : t("pools.show")}</span>
                    </button>
                  </td>
                  <td className="wrap min-w-[16rem]">{p.name}</td>
                  <td>{tk(`level.${p.level}`)}</td>
                  <td>{tk(`shift.${p.shift}`)}</td>
                  <td className="num">{formatCount(p.approval.approved_intake)}</td>
                  <td className={cn("num font-medium", p.enrolments > p.approval.approved_intake && "text-check-pending-ink")}>
                    {formatCount(p.enrolments)}
                  </td>
                  <td className="num">{formatCount(seatedOf(p))}</td>
                  <td className="num">
                    <UnseatedCount n={p.unseated} />
                  </td>
                </tr>
                {isOpen && (
                  <tr id={panelId}>
                    <td colSpan={COLS} className="!h-auto !p-0 !whitespace-normal">
                      <div className="px-3 py-2">
                        <p className="mb-1.5 text-xs text-ink-muted">{p.pools.map(poolLine).join(" · ")}</p>
                        <PoolsPanel programme={p} />
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
