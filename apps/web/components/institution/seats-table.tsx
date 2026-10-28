"use client";

import * as React from "react";
import { EmptyState } from "@/components/brand/EmptyState";
import { SeatCodePill } from "@/components/brand/SeatCodePill";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDateTime } from "@/lib/format";
import { useInstitutionSeats } from "@/lib/queries";
import type { ProgrammeDetail, SeatStatus, SeatType } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { FilterSelect, SearchInput } from "@/components/common/filter-select";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { Pager } from "@/components/common/pager";

const PAGE_SIZE = 50;
const COLS = 7;
const TYPES: SeatType[] = ["REGULAR", "NRI", "TFW", "LATERAL", "INTERNATIONAL"];
const STATUSES: SeatStatus[] = ["FREE", "ASSIGNED", "RELEASED"];

const STATUS_CHIP: Record<SeatStatus, string> = {
  FREE: "border-dashed border-seat-free/50 bg-seat-free-soft text-seat-free-ink",
  ASSIGNED: "border-seat-assigned/40 bg-seat-assigned-soft text-seat-assigned-ink",
  RELEASED: "border-seat-released/40 bg-seat-released-soft text-seat-released-ink",
};

/** Every seat row in the ledger; Week 1 shows them all Free. */
export function SeatsTable({ institutionId, programmes }: { institutionId: string; programmes: ProgrammeDetail[] }) {
  const [params, set] = useUrlParams();
  const programmeId = params.get("s_programme") ?? "";
  const seatType = params.get("s_type") ?? "";
  const status = params.get("s_status") ?? "";
  const q = params.get("s_q") ?? "";
  const page = Math.max(1, Number(params.get("s_page") ?? 1) || 1);

  const list = useInstitutionSeats(institutionId, {
    page,
    page_size: PAGE_SIZE,
    programme_id: programmeId || undefined,
    seat_type: (seatType || undefined) as SeatType | undefined,
    status: (status || undefined) as SeatStatus | undefined,
    q: q || undefined,
  });
  const onSearch = React.useCallback((value: string) => set({ s_q: value, s_page: null }), [set]);
  const data = list.data;
  const rows = data?.items ?? [];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <FilterSelect
          label={t("app.filter.programme")}
          value={programmeId}
          options={[...programmes].sort((a, b) => a.code.localeCompare(b.code)).map((p) => ({ value: p.id, label: p.code }))}
          onChange={(v) => set({ s_programme: v, s_page: null })}
        />
        <FilterSelect
          label={t("app.filter.type")}
          value={seatType}
          options={TYPES.map((v) => ({ value: v, label: tk(`seat_type.${v}`) }))}
          onChange={(v) => set({ s_type: v, s_page: null })}
        />
        <FilterSelect
          label={t("app.filter.status")}
          value={status}
          options={STATUSES.map((v) => ({ value: v, label: tk(`seat_status.${v}`) }))}
          onChange={(v) => set({ s_status: v, s_page: null })}
        />
        <SearchInput label={t("app.search_seats")} value={q} onChange={onSearch} className="w-full sm:w-56" />
      </div>
      <div className="overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table ledger-table--dense" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("tab.seats")}</caption>
          <thead>
            <tr>
              <th scope="col" className="code">
                {t("col.seat_code")}
              </th>
              <th scope="col" className="code">
                {t("col.programme")}
              </th>
              <th scope="col">{t("col.seat_type")}</th>
              <th scope="col">{t("col.reserved_for")}</th>
              <th scope="col">{t("col.status")}</th>
              <th scope="col">{t("col.holder")}</th>
              <th scope="col" className="num">
                {t("col.assigned")}
              </th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading && <SkeletonRows cols={COLS} />}
            {list.isError && !data && (
              <TableMessage cols={COLS}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={COLS}>
                <EmptyState title={t("empty.seats")} />
              </TableMessage>
            )}
            {rows.map((s) => (
              <tr key={s.id}>
                <td className="code">
                  <SeatCodePill seatCode={s.seat_code} status={s.status} />
                </td>
                <td className="code">{s.programme_code}</td>
                <td>{tk(`seat_type.${s.seat_type}`)}</td>
                <td className="text-ink-muted">{s.reserved_for ?? ""}</td>
                <td>
                  <span className={cn("inline-flex h-5 items-center rounded-chip border px-1.5 text-xs font-medium", STATUS_CHIP[s.status])}>
                    {tk(`seat_status.${s.status}`)}
                  </span>
                </td>
                <td>{s.student_name ?? ""}</td>
                <td className="num text-ink-muted">{formatDateTime(s.assigned_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ink-muted">
          {data ? <>{t("table.count.seats", { total: formatCount(data.total) })}. </> : null}
          <ReadLoggedNote />
        </span>
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ s_page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
    </div>
  );
}
