"use client";

import * as React from "react";
import { ConsentBadge } from "@/components/brand/ConsentBadge";
import { EmptyState } from "@/components/brand/EmptyState";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { SeatCodePill } from "@/components/brand/SeatCodePill";
import { SeverityBadge } from "@/components/brand/SeverityBadge";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useInstitutionEnrolments } from "@/lib/queries";
import type { AdmissionRoute, EnrolmentStatus, ProgrammeDetail } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { Button } from "@/components/ui/button";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { FilterSelect, SearchInput } from "@/components/common/filter-select";
import { CountersignStrip, ReadLoggedNote, UnseatedChip } from "@/components/common/ledger-bits";
import { Pager } from "@/components/common/pager";

const PAGE_SIZE = 25;
const COLS = 11;
const STATUSES: EnrolmentStatus[] = ["ACTIVE", "WITHDRAWN", "TRANSFERRED", "GRADUATED"];
const ROUTES: AdmissionRoute[] = ["COUNSELLING", "MANAGEMENT", "NRI", "SPOT", "LATERAL", "INTERNATIONAL", "TFW"];

/**
 * Enrolments of one institution: masked ids only, consent, route, seat code
 * or an amber "Unseated" chip, and the countersign strip. Filters live in
 * the URL with an `e_` prefix so they survive a refresh next to other tabs.
 */
export function EnrolmentsTable({
  institutionId,
  programmes,
  academicYear,
}: {
  institutionId: string;
  programmes: ProgrammeDetail[];
  academicYear: string;
}) {
  const [params, set] = useUrlParams();
  const programmeId = params.get("e_programme") ?? "";
  const status = (params.get("e_status") ?? "ACTIVE") as EnrolmentStatus | "ALL";
  const year = params.get("e_year") ?? academicYear;
  const route = params.get("e_route") ?? "";
  const q = params.get("e_q") ?? "";
  const page = Math.max(1, Number(params.get("e_page") ?? 1) || 1);

  const list = useInstitutionEnrolments(institutionId, {
    page,
    page_size: PAGE_SIZE,
    programme_id: programmeId || undefined,
    status: status === "ALL" ? undefined : status,
    academic_year: year || undefined,
    admission_route: (route || undefined) as AdmissionRoute | undefined,
    q: q || undefined,
  });
  const onSearch = React.useCallback((value: string) => set({ e_q: value, e_page: null }), [set]);
  const data = list.data;
  const rows = data?.items ?? [];
  const filtered = Boolean(programmeId || route || q || status !== "ACTIVE");

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <FilterSelect
          label={t("app.filter.programme")}
          value={programmeId}
          options={[...programmes].sort((a, b) => a.code.localeCompare(b.code)).map((p) => ({ value: p.id, label: p.code }))}
          onChange={(v) => set({ e_programme: v, e_page: null })}
        />
        <FilterSelect
          label={t("app.filter.status")}
          value={status === "ALL" ? "" : status}
          options={STATUSES.map((s) => ({ value: s, label: tk(`enrol_status.${s}`) }))}
          onChange={(v) => set({ e_status: v === "" ? "ALL" : v === "ACTIVE" ? null : v, e_page: null })}
        />
        <FilterSelect
          label={t("app.filter.year")}
          value={year}
          options={[{ value: academicYear, label: academicYear }]}
          allLabel={null}
          onChange={(v) => set({ e_year: v === academicYear ? null : v, e_page: null })}
        />
        <FilterSelect
          label={t("app.filter.route")}
          value={route}
          options={ROUTES.map((r) => ({ value: r, label: tk(`route.${r}`) }))}
          onChange={(v) => set({ e_route: v, e_page: null })}
        />
        <SearchInput label={t("app.search_enrolments")} value={q} onChange={onSearch} className="w-full sm:w-64" />
      </div>

      <div className="overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("tab.enrolments")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("col.student")}</th>
              <th scope="col" className="code">
                {t("col.apaar")}
              </th>
              <th scope="col">{t("col.consent")}</th>
              <th scope="col" className="code">
                {t("col.programme")}
              </th>
              <th scope="col" className="num">
                {t("col.year")}
              </th>
              <th scope="col">{t("col.route")}</th>
              <th scope="col">{t("col.category")}</th>
              <th scope="col" className="code">
                {t("col.seat")}
              </th>
              <th scope="col">{t("col.countersign")}</th>
              <th scope="col">{t("col.flags")}</th>
              <th scope="col" className="num hidden 2xl:table-cell">
                {t("col.uploaded")}
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
                <EmptyState
                  title={q ? t("empty.enrolments_search", { q }) : t("empty.enrolments")}
                  action={
                    filtered ? (
                      <Button variant="outline" size="sm" onClick={() => set({ e_programme: null, e_status: null, e_route: null, e_q: null, e_page: null })}>
                        {t("empty.institutions_clear")}
                      </Button>
                    ) : undefined
                  }
                />
              </TableMessage>
            )}
            {rows.map((e) => (
              <tr key={e.id}>
                <td className="font-medium">{e.student.name}</td>
                <td className="code">
                  <MaskedApaar apaarMasked={e.student.apaar_masked} provisionalId={e.student.provisional_id} />
                </td>
                <td>
                  <ConsentBadge status={e.student.consent_status} title={tk(`consent.tip_${e.student.consent_status}`)} />
                </td>
                <td className="code">{e.programme_code}</td>
                <td className="num">{e.year_of_study}</td>
                <td>{tk(`route.${e.admission_route}`)}</td>
                <td className="text-ink-muted">{tk(`category.${e.category}`)}</td>
                <td className="code">{e.seat_code ? <SeatCodePill seatCode={e.seat_code} status="ASSIGNED" /> : <UnseatedChip />}</td>
                <td>
                  <CountersignStrip countersign={e.countersign} />
                </td>
                <td>
                  {e.flags.length === 0 ? (
                    <span className="sr-only">{t("app.none")}</span>
                  ) : (
                    <span className="flex gap-1">
                      {e.flags.slice(0, 2).map((f) => (
                        <SeverityBadge key={f.id} severity={f.severity} compact />
                      ))}
                      {e.flags.length > 2 && <span className="text-xs text-ink-muted">+{e.flags.length - 2}</span>}
                    </span>
                  )}
                </td>
                <td className="num hidden text-ink-muted 2xl:table-cell">{formatDate(e.uploaded_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ink-muted">
          {data ? <>{t("table.count.enrolments", { total: formatCount(data.total) })}. </> : null}
          <ReadLoggedNote />
        </span>
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ e_page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
    </div>
  );
}
