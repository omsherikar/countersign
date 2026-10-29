"use client";

import * as React from "react";
import Link from "next/link";
import { SlidersHorizontal } from "lucide-react";
import { ConsentBadge } from "@/components/brand/ConsentBadge";
import { EmptyState } from "@/components/brand/EmptyState";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { SeatCodePill } from "@/components/brand/SeatCodePill";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useInstitutionEnrolments } from "@/lib/queries";
import { CHECK_ORDER, STATE_ORDER, STATUS_ORDER, stateWord, statusWord } from "@/lib/checks";
import type { AdmissionRoute, CheckType, EnrolmentListParams, EnrolmentStatus, EvidenceState, ProgrammeDetail, RecordCounts, RecordStatus } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { FilterSelect, SearchInput } from "@/components/common/filter-select";
import { ReadLoggedNote, UnseatedChip } from "@/components/common/ledger-bits";
import { FlagChips } from "@/components/flags/flag-chip";
import { Pager } from "@/components/common/pager";
import { RecordStatusBadge, STATUS_MARK } from "@/components/records/record-status-badge";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;
const COLS = 10;
const STATUSES: EnrolmentStatus[] = ["ACTIVE", "WITHDRAWN", "TRANSFERRED", "GRADUATED"];
const ROUTES: AdmissionRoute[] = ["COUNSELLING", "MANAGEMENT", "NRI", "SPOT", "LATERAL", "INTERNATIONAL", "TFW"];

/** "312 Awaiting evidence · 254 Countersigned · 37 Under review · 2 Disputed", each a link that sets the Status filter. */
function StatusCounts({ counts, current, onPick }: { counts: RecordCounts; current: string; onPick: (s: RecordStatus | null) => void }) {
  return (
    <p className="mb-3 flex max-w-none flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      {STATUS_ORDER.map((s, i) => {
        const { Icon, ink } = STATUS_MARK[s];
        const on = current === s;
        return (
          <React.Fragment key={s}>
            {i > 0 && (
              <span aria-hidden="true" className="text-ink-faint">
                ·
              </span>
            )}
            <button
              type="button"
              onClick={() => onPick(on ? null : s)}
              aria-pressed={on}
              className={cn("inline-flex min-h-8 items-center gap-1 rounded-sm px-1 text-ink-blue underline-offset-4 hover:underline", on && "font-semibold")}
            >
              <Icon className={cn("size-3.5 shrink-0", ink)} aria-hidden="true" />
              {t("enrolments.status_count", { n: formatCount(counts[s]), status_word: statusWord(s) })}
            </button>
          </React.Fragment>
        );
      })}
    </p>
  );
}

/**
 * Records of one institution (page spec W4-2): masked ids only, consent,
 * route, seat code or "Unseated", the record's status and its open cases.
 * Sorted by "Needs attention first" unless the reader picks a name sort.
 * Filters live in the URL with an `e_` prefix so they survive a refresh next
 * to other tabs; on a phone they open in a sheet.
 */
export function EnrolmentsTable({
  institutionId,
  programmes,
  academicYear,
  enrolmentHref,
  flagHref,
}: {
  institutionId: string;
  programmes: ProgrammeDetail[];
  academicYear: string;
  /** Enrolment detail route for this role, e.g. (id) => `/aicte/enrolments/${id}`. */
  enrolmentHref?: (id: string) => string;
  /** Case detail route for this role; the university has none. */
  flagHref?: (id: string) => string;
}) {
  const [params, set] = useUrlParams();
  const programmeId = params.get("e_programme") ?? "";
  const status = (params.get("e_enrol") ?? "ACTIVE") as EnrolmentStatus | "ALL";
  const year = params.get("e_year") ?? academicYear;
  const route = params.get("e_route") ?? "";
  const q = params.get("e_q") ?? "";
  const recordStatus = (params.get("e_status") ?? "") as RecordStatus | "";
  const row = (params.get("e_row") ?? "") as CheckType | "";
  const rowState = (params.get("e_state") ?? "") as EvidenceState | "";
  const flagged = params.get("e_flagged") ?? "";
  const seated = params.get("e_seated") ?? "";
  const sort = (params.get("e_sort") ?? "status_priority") as NonNullable<EnrolmentListParams["sort"]>;
  const page = Math.max(1, Number(params.get("e_page") ?? 1) || 1);

  const list = useInstitutionEnrolments(institutionId, {
    page,
    page_size: PAGE_SIZE,
    programme_id: programmeId || undefined,
    status: status === "ALL" ? undefined : status,
    academic_year: year || undefined,
    admission_route: (route || undefined) as AdmissionRoute | undefined,
    q: q || undefined,
    record_status: recordStatus || undefined,
    // Row and Evidence state together mean "this row in this state" (W4-2); pending in the contract.
    row_state: rowState || undefined,
    row: rowState && row ? row : undefined,
    flagged: flagged === "" ? undefined : flagged === "true",
    seated: seated === "" ? undefined : seated === "true",
    sort,
  });
  const onSearch = React.useCallback((value: string) => set({ e_q: value, e_page: null }), [set]);
  const data = list.data;
  const rows = data?.items ?? [];
  const filterCount = [programmeId, route, status !== "ACTIVE" ? status : "", recordStatus, row, rowState, flagged, seated].filter(Boolean).length;
  const filtered = Boolean(filterCount || q);
  const clearAll = () =>
    set({
      e_programme: null,
      e_enrol: null,
      e_route: null,
      e_q: null,
      e_status: null,
      e_row: null,
      e_state: null,
      e_flagged: null,
      e_seated: null,
      e_page: null,
    });

  const filters = (
    <>
      <FilterSelect
        label={t("enrolments.filter.status")}
        value={recordStatus}
        options={STATUS_ORDER.map((s) => ({ value: s, label: statusWord(s) }))}
        allLabel={t("enrolments.filter.status_all")}
        onChange={(v) => set({ e_status: v, e_page: null })}
      />
      <FilterSelect
        label={t("enrolments.filter.check")}
        value={row}
        options={CHECK_ORDER.map((c) => ({ value: c, label: tk(`check.${c}`) }))}
        allLabel={t("enrolments.filter.any")}
        onChange={(v) => set({ e_row: v, e_page: null })}
      />
      <FilterSelect
        label={t("enrolments.filter.result")}
        value={rowState}
        options={STATE_ORDER.map((s) => ({ value: s, label: stateWord(s) }))}
        allLabel={t("enrolments.filter.any")}
        onChange={(v) => set({ e_state: v, e_page: null })}
      />
      <FilterSelect
        label={t("enrolments.filter.flagged")}
        value={flagged}
        options={[
          { value: "true", label: t("enrolments.filter.flagged_yes") },
          { value: "false", label: t("enrolments.filter.flagged_no") },
        ]}
        allLabel={t("enrolments.filter.any")}
        onChange={(v) => set({ e_flagged: v, e_page: null })}
      />
      <FilterSelect
        label={t("enrolments.filter.seated")}
        value={seated}
        options={[
          { value: "true", label: t("enrolments.filter.seated_yes") },
          { value: "false", label: t("enrolments.filter.seated_no") },
        ]}
        allLabel={t("enrolments.filter.any")}
        onChange={(v) => set({ e_seated: v, e_page: null })}
      />
      <FilterSelect
        label={t("app.filter.programme")}
        value={programmeId}
        options={[...programmes].sort((a, b) => a.code.localeCompare(b.code)).map((p) => ({ value: p.id, label: p.code }))}
        onChange={(v) => set({ e_programme: v, e_page: null })}
      />
      <FilterSelect
        label={t("app.filter.route")}
        value={route}
        options={ROUTES.map((r) => ({ value: r, label: tk(`route.${r}`) }))}
        onChange={(v) => set({ e_route: v, e_page: null })}
      />
      <FilterSelect
        label={t("app.filter.enrolment_status")}
        value={status === "ALL" ? "" : status}
        options={STATUSES.map((s) => ({ value: s, label: tk(`enrol_status.${s}`) }))}
        onChange={(v) => set({ e_enrol: v === "" ? "ALL" : v === "ACTIVE" ? null : v, e_page: null })}
      />
      <FilterSelect
        label={t("app.filter.year")}
        value={year}
        options={[{ value: academicYear, label: academicYear }]}
        allLabel={null}
        onChange={(v) => set({ e_year: v === academicYear ? null : v, e_page: null })}
      />
      <FilterSelect
        label={t("app.filter.sort")}
        value={sort}
        options={[
          { value: "status_priority", label: t("record_status.sort.attention") },
          { value: "name_asc", label: t("enrolments.sort.name") },
        ]}
        allLabel={null}
        onChange={(v) => set({ e_sort: v === "status_priority" ? null : v, e_page: null })}
      />
    </>
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <SearchInput label={t("app.search_enrolments")} value={q} onChange={onSearch} className="w-full sm:w-64" />
        <div className="hidden flex-wrap items-center gap-x-4 gap-y-2 md:flex">{filters}</div>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" className="h-11 md:hidden">
              <SlidersHorizontal className="size-4" aria-hidden="true" />
              {t("app.filters")}
              {filterCount > 0 && <span className="rounded-chip bg-ink-blue px-1.5 text-xs text-on-ink-blue">{filterCount}</span>}
            </Button>
          </SheetTrigger>
          <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto bg-paper-raised">
            <SheetHeader>
              <SheetTitle>{t("app.filters")}</SheetTitle>
              <SheetDescription className="sr-only">{t("tab.enrolments")}</SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-3 px-4 pb-6 [&_select]:h-11 [&_select]:max-w-none [&>div]:justify-between">{filters}</div>
          </SheetContent>
        </Sheet>
        {filtered && (
          <Button variant="link" size="sm" className="h-8 px-0" onClick={clearAll}>
            {t("empty.clear_filters")}
          </Button>
        )}
      </div>

      {data?.status_counts && <StatusCounts counts={data.status_counts} current={recordStatus} onPick={(s) => set({ e_status: s, e_page: null })} />}

      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("tab.enrolments")}</caption>
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-[2] bg-paper-raised">
                {t("col.student")}
              </th>
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
              <th scope="col" className="code">
                {t("col.seat")}
              </th>
              <th scope="col" aria-sort={sort === "status_priority" ? "other" : "none"} title={t("record_status.sort_tip")}>
                {t("col.record_status")}
              </th>
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
                  title={
                    q
                      ? t("empty.enrolments_search", { q })
                      : recordStatus && filterCount === 1
                        ? t("empty.status_filtered")
                        : filtered
                          ? t("empty.enrolments_filtered")
                          : t("empty.enrolments")
                  }
                  action={
                    filtered ? (
                      <Button variant="outline" size="sm" onClick={clearAll}>
                        {t("empty.clear_filters")}
                      </Button>
                    ) : undefined
                  }
                />
              </TableMessage>
            )}
            {rows.map((e) => (
              <tr key={e.id}>
                <td className="sticky left-0 z-[1] bg-paper-raised font-medium">
                  {enrolmentHref ? <Link href={enrolmentHref(e.id)}>{e.student.name}</Link> : e.student.name}
                </td>
                <td className="code">
                  <MaskedApaar apaarMasked={e.student.apaar_masked} provisionalId={e.student.provisional_id} />
                </td>
                <td>
                  <ConsentBadge status={e.student.consent_status} compact title={tk(`consent.tip_${e.student.consent_status}`)} />
                </td>
                <td className="code">{e.programme_code}</td>
                <td className="num">{e.year_of_study}</td>
                <td>{tk(`route.${e.admission_route}`)}</td>
                <td className="code">{e.seat_code ? <SeatCodePill seatCode={e.seat_code} status="ASSIGNED" /> : <UnseatedChip />}</td>
                <td>
                  {e.record_status ? (
                    <RecordStatusBadge status={e.record_status} tip={e.status_reason} />
                  ) : (
                    <span className="text-xs text-ink-muted">{tk(`enrol_status.${e.status}`)}</span>
                  )}
                </td>
                <td>
                  <FlagChips flags={e.flags} hrefFor={flagHref} />
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
