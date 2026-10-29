"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { t, tk } from "@/lib/copy";
import { admittedOf } from "@/lib/counts";
import { formatCount } from "@/lib/format";
import { useInstitutions, useRegions, useStates } from "@/lib/queries";
import { REGION_NAME } from "@/lib/roles";
import type { InstitutionListParams, InstitutionListSort, InstitutionType, Region } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { FilterSelect, SearchInput } from "@/components/common/filter-select";
import { NotComputed, TypeChip } from "@/components/common/ledger-bits";
import { Pager } from "@/components/common/pager";

const PAGE_SIZE = 25;
const TYPES: InstitutionType[] = ["GOVERNMENT", "GOVERNMENT_AIDED", "PRIVATE_SELF_FINANCED", "UNIVERSITY_DEPARTMENT", "DEEMED"];

export type InstitutionsVariant = "aicte" | "ro" | "university";

interface Column {
  key: string;
  label: string;
  num?: boolean;
  sort?: InstitutionListSort;
  tip?: string;
  /** Extra classes on the head and body cells, e.g. a breakpoint. */
  cls?: string;
}

function columnsFor(variant: InstitutionsVariant, academicYear: string, withAdmitted: boolean): Column[] {
  const cols: Column[] = [
    { key: "name", label: t("col.name"), sort: "name" },
    { key: "permanent_id", label: t("col.permanent_id") },
    { key: "state", label: t("col.state") },
  ];
  if (variant === "aicte") cols.push({ key: "region", label: t("col.region") });
  cols.push(
    { key: "type", label: t("col.type") },
    { key: "programmes", label: t("col.programmes"), num: true, cls: "hidden 2xl:table-cell" },
    { key: "approved_seats", label: t("col.approved_seats"), num: true, sort: "approved_seats", tip: t("app.hint.intake", { academic_year: academicYear }) },
  );
  if (withAdmitted) cols.push({ key: "admitted", label: t("col.admitted"), num: true, tip: t("col.admitted_tip", { academic_year: academicYear }) });
  cols.push({ key: "enrolments", label: t("col.enrolments"), num: true, sort: "enrolments", tip: t("col.enrolments_tip", { academic_year: academicYear }) });
  if (variant !== "university") {
    cols.push(
      { key: "flags_open", label: t("col.flags_open"), num: true, sort: "flags_open_desc", tip: t("table.sort_tip") },
      { key: "countersigned", label: t("kpi.countersigned"), num: true, tip: t("kpi.countersigned_tip") },
    );
  }
  return cols;
}

/**
 * "Institutions ranked": server-side search, filters, sort and pages, all
 * kept in the URL. Officers rank by open flags, then students on roll
 * (sort=flags_open_desc, A2.20); the university, which sees no flags, by
 * students on roll.
 */
export function InstitutionsTable({
  variant,
  basePath,
  region,
  academicYear = "2026-27",
  anchorId = "institutions",
}: {
  variant: InstitutionsVariant;
  basePath: string;
  /** RO scope: limits the State filter to the region's states. */
  region?: Region | null;
  /** The approval year the seats belong to, for the column tips. */
  academicYear?: string;
  anchorId?: string;
}) {
  const [params, set] = useUrlParams();
  const states = useStates();
  const regions = useRegions();

  const q = params.get("q") ?? "";
  const state = params.get("state") ?? "";
  const regionFilter = variant === "aicte" ? (params.get("region") ?? "") : "";
  const type = params.get("type") ?? "";
  const defaultSort: InstitutionListSort = variant === "university" ? "enrolments" : "flags_open_desc";
  const sort = (params.get("sort") as InstitutionListSort | null) ?? defaultSort;
  // flags_open_desc carries its own direction; the A.6 keys take `order`.
  const oneWay = sort === "flags_open_desc" || sort === "enrolments_desc" || sort === "name_asc";
  const order = oneWay ? "desc" : ((params.get("order") as "asc" | "desc" | null) ?? (sort === "name" ? "asc" : "desc"));
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);

  const query: InstitutionListParams = {
    page,
    page_size: PAGE_SIZE,
    q: q || undefined,
    state: state || undefined,
    region: (regionFilter || undefined) as Region | undefined,
    type: (type || undefined) as InstitutionType | undefined,
    sort,
    order: oneWay ? undefined : order,
  };
  const list = useInstitutions(query);
  // Admitted appears once the api sends it; until then the table shows seats and students on roll only.
  const withAdmitted = !list.data || list.data.items.length === 0 || list.data.items.some((r) => admittedOf(r) !== null);
  const cols = columnsFor(variant, academicYear, withAdmitted);
  const filtered = Boolean(q || state || regionFilter || type);

  const stateOptions = (states.data ?? [])
    .filter((s) => (region ? s.region === region : regionFilter ? s.region === regionFilter : true))
    .map((s) => ({ value: s.code, label: `${s.name} (${s.code})` }));
  const regionOptions = (regions.data ?? [])
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((r) => ({ value: r.code, label: `${r.name} (${r.hq_city})` }));

  const onSearch = React.useCallback((value: string) => set({ q: value, page: null }), [set]);

  function toggleSort(key: InstitutionListSort) {
    if (key === "flags_open_desc") {
      set({ sort: key === defaultSort ? null : key, order: null, page: null });
      return;
    }
    if (sort === key) set({ sort: key, order: order === "asc" ? "desc" : "asc", page: null });
    else set({ sort: key, order: key === "name" ? "asc" : "desc", page: null });
  }

  function clearFilters() {
    set({ q: null, state: null, region: null, type: null, page: null });
  }

  const data = list.data;
  const rows = data?.items ?? [];

  return (
    <div id={anchorId} className="scroll-mt-20">
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <SearchInput label={t("app.filter_institutions")} value={q} onChange={onSearch} className="w-full sm:w-80" />
        <FilterSelect label={t("col.state")} value={state} options={stateOptions} onChange={(v) => set({ state: v, page: null })} />
        {variant === "aicte" && (
          <FilterSelect
            label={t("col.region")}
            value={regionFilter}
            options={regionOptions}
            onChange={(v) => set({ region: v, state: null, page: null })}
          />
        )}
        <FilterSelect
          label={t("col.type")}
          value={type}
          options={TYPES.map((v) => ({ value: v, label: tk(`type.${v}`) }))}
          onChange={(v) => set({ type: v, page: null })}
        />
        {filtered && (
          <Button variant="link" size="sm" className="h-8 px-0" onClick={clearFilters}>
            {t("empty.institutions_clear")}
          </Button>
        )}
      </div>

      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("section.institutions_ranked")}</caption>
          <thead>
            <tr>
              {cols.map((c) => {
                const active = c.sort && sort === c.sort;
                const ariaSort = active ? (order === "asc" ? "ascending" : "descending") : c.sort ? "none" : undefined;
                return (
                  <th key={c.key} scope="col" className={cn(c.num && "num", c.cls)} aria-sort={ariaSort} title={c.tip}>
                    {c.sort ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.sort!)}
                        className={cn("inline-flex items-center gap-1 hover:text-ink", active && "text-ink")}
                      >
                        {c.label}
                        {active ? (
                          order === "asc" ? (
                            <ArrowUp className="size-3" aria-hidden="true" />
                          ) : (
                            <ArrowDown className="size-3" aria-hidden="true" />
                          )
                        ) : (
                          <ArrowUpDown className="size-3 opacity-40" aria-hidden="true" />
                        )}
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {list.isLoading && <SkeletonRows cols={cols.length} />}
            {list.isError && !data && (
              <TableMessage cols={cols.length}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={cols.length}>
                {filtered ? (
                  <EmptyState
                    title={t("empty.institutions_filtered")}
                    description={q ? t("search.empty", { q }) : undefined}
                    action={
                      <Button variant="outline" size="sm" onClick={clearFilters}>
                        {t("empty.institutions_clear")}
                      </Button>
                    }
                  />
                ) : (
                  <EmptyState title={variant === "university" ? t("empty.affiliates") : t("empty.by_state")} />
                )}
              </TableMessage>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="wrap min-w-[13rem] max-w-[22rem]">
                  <Link href={`${basePath}/institutions/${r.id}`} className="font-medium">
                    {r.name}
                  </Link>
                </td>
                <td className="code">{r.aicte_permanent_id}</td>
                <td>
                  <abbr title={r.state_name} className="no-underline">
                    {r.state_code}
                  </abbr>
                </td>
                {variant === "aicte" && (
                  <td className="text-ink-muted" title={r.region_name}>
                    {REGION_NAME[r.region]}
                  </td>
                )}
                <td>
                  <TypeChip type={r.type} />
                </td>
                <td className="num hidden 2xl:table-cell">{formatCount(r.programmes)}</td>
                <td className="num">{formatCount(r.approved_seats)}</td>
                {withAdmitted && <td className="num font-medium">{admittedOf(r) === null ? "" : formatCount(admittedOf(r))}</td>}
                <td className="num">{formatCount(r.enrolments)}</td>
                {variant !== "university" && (
                  <>
                    <td className={cn("num", r.flags_open > 0 ? "font-semibold text-ink" : "text-ink-muted")}>
                      {formatCount(r.flags_open)}
                    </td>
                    <td className="num">{r.countersigned_pct === null ? <NotComputed /> : `${r.countersigned_pct}%`}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ink-muted">
          {data ? t("table.count.institutions", { total: formatCount(data.total) }) : " "}
        </span>
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
    </div>
  );
}
