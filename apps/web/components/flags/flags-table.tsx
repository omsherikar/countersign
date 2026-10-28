"use client";

import * as React from "react";
import Link from "next/link";
import { Flag, Inbox } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { FlagStatusBadge } from "@/components/brand/FlagStatusBadge";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useFlags, useInstitution, useInstitutions, useStates } from "@/lib/queries";
import type { FlagListParams, FlagSort, FlagStatusFilter, FlagType, Region, Severity } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { FilterSelect, SearchInput } from "@/components/common/filter-select";
import { Pager } from "@/components/common/pager";
import { SeverityBars } from "@/components/flags/flag-chip";

const PAGE_SIZE = 25;
export const FLAG_TYPES: FlagType[] = [
  "EXCESS_ADMISSION", "QUOTA_BREACH", "LATE_REFILL", "INVALID_APAAR", "NAME_MISMATCH", "DUPLICATE_CROSS_INSTITUTION",
  "DUPLICATE_WITHIN_UPLOAD", "DUAL_ENROLMENT_ALLOWED", "NO_ACADEMIC_ACTIVITY", "STUDENT_DENIED", "GHOST_RING", "ANOMALY",
];
const SEVERITIES: Severity[] = ["HIGH", "MEDIUM", "LOW"];
const STATUSES: FlagStatusFilter[] = ["UNRESOLVED", "OPEN", "DOCS_REQUESTED", "ESCALATED", "CLEARED", "CONFIRMED"];
/** The default list matches the Open flags tile: every flag still waiting on someone (errata 2). */
export const DEFAULT_STATUS: FlagStatusFilter = "UNRESOLVED";

const SEVERITY_INK: Record<Severity, string> = {
  HIGH: "text-severity-high-ink",
  MEDIUM: "text-severity-medium-ink",
  LOW: "text-severity-low-ink",
};

/** Severity as the three-bar meter and the word, coloured on the chip only. */
function SeverityCell({ severity }: { severity: Severity }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium", SEVERITY_INK[severity])}>
      <SeverityBars severity={severity} />
      {tk(`severity.${severity}`)}
    </span>
  );
}

export type FlagsTableVariant = "cases" | "tab" | "college";

/**
 * The shared flags list (page spec W2-7): the officers' case queue, an
 * institution's Flags tab and the registrar's /college/flags. Read only.
 * Filters live in the URL with the `f_` prefix; rows link to flag detail and
 * `j` / `k` move between them.
 */
export function FlagsTable({
  variant,
  detailBase,
  institutionId,
  region,
  academicYear = "2026-27",
  showState = false,
}: {
  variant: FlagsTableVariant;
  /** Flag detail route base, e.g. "/aicte/cases". */
  detailBase: string;
  /** Fixed institution for the Flags tab. */
  institutionId?: string;
  /** RO scope, so the State filter lists the region's states. */
  region?: Region | null;
  academicYear?: string;
  /** The State filter is for AICTE officers. */
  showState?: boolean;
}) {
  const [params, set] = useUrlParams();
  const status = (params.get("f_status") ?? DEFAULT_STATUS) as FlagStatusFilter | "ALL";
  const severity = (params.get("f_severity") ?? "") as Severity | "";
  const type = (params.get("f_type") ?? "") as FlagType | "";
  const chosenInstitution = variant === "cases" ? (params.get("f_institution") ?? "") : (institutionId ?? "");
  const state = params.get("f_state") ?? "";
  const programme = params.get("f_programme") ?? "";
  const q = params.get("f_q") ?? "";
  const sort = (params.get("f_sort") ?? "severity_desc") as FlagSort;
  const page = Math.max(1, Number(params.get("f_page") ?? 1) || 1);

  const query: FlagListParams = {
    page,
    page_size: PAGE_SIZE,
    academic_year: academicYear,
    status: status === "ALL" ? undefined : status,
    severity: severity || undefined,
    type: type || undefined,
    institution_id: chosenInstitution || undefined,
    state: showState ? state || undefined : undefined,
    programme_id: chosenInstitution ? programme || undefined : undefined,
    q: q || undefined,
    sort,
  };
  const list = useFlags(query);
  const institutions = useInstitutions({ page_size: 200, sort: "name" }, variant === "cases");
  const states = useStates();
  const chosen = useInstitution(variant !== "college" ? chosenInstitution || null : null);
  const onSearch = React.useCallback((v: string) => set({ f_q: v, f_page: null }), [set]);

  const data = list.data;
  const rows = data?.items ?? [];
  const showInstitution = variant === "cases";
  const showAssignee = rows.some((r) => r.assignee !== null);
  const cols = 6 + (showInstitution ? 1 : 0) + (showAssignee ? 1 : 0);
  const filtered = Boolean(severity || type || (variant === "cases" && chosenInstitution) || state || programme || q || status !== DEFAULT_STATUS);
  const clearAll = () =>
    set({ f_status: null, f_severity: null, f_type: null, f_institution: null, f_state: null, f_programme: null, f_q: null, f_page: null });

  const openWord = status === "UNRESOLVED" || status === "OPEN";
  const count = data
    ? variant === "cases"
      ? openWord
        ? t("table.count.flags", { total: formatCount(data.total), institutions: formatCount(data.institutions) })
        : t("table.count.flags_any", { total: formatCount(data.total), institutions: formatCount(data.institutions) })
      : openWord
        ? t("table.count.flags_one", { total: formatCount(data.total) })
        : t("table.count.flags_one_any", { total: formatCount(data.total) })
    : " ";

  const tbody = React.useRef<HTMLTableSectionElement>(null);
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key !== "j" && e.key !== "k") return;
    const links = Array.from(tbody.current?.querySelectorAll<HTMLAnchorElement>("a[data-row-link]") ?? []);
    if (links.length === 0) return;
    const at = links.indexOf(document.activeElement as HTMLAnchorElement);
    const next = e.key === "j" ? Math.min(links.length - 1, at + 1) : Math.max(0, at === -1 ? 0 : at - 1);
    links[next]?.focus();
    e.preventDefault();
  }

  const emptyTitle = filtered
    ? t("empty.cases_filtered")
    : variant === "college"
      ? t("empty.flags_college")
      : variant === "tab"
        ? t("empty.flags_institution")
        : t("empty.cases");

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <FilterSelect
          label={t("flags.filter.status")}
          value={status === "ALL" ? "" : status}
          options={STATUSES.map((s) => ({ value: s, label: s === "UNRESOLVED" ? t("app.flags.unresolved") : tk(`flag_status.${s}`) }))}
          allLabel={t("flags.filter.all")}
          onChange={(v) => set({ f_status: v === "" ? "ALL" : v === DEFAULT_STATUS ? null : v, f_page: null })}
        />
        <FilterSelect
          label={t("flags.filter.severity")}
          value={severity}
          options={SEVERITIES.map((s) => ({ value: s, label: tk(`severity.${s}`) }))}
          allLabel={t("flags.filter.all")}
          onChange={(v) => set({ f_severity: v, f_page: null })}
        />
        <FilterSelect
          label={t("flags.filter.type")}
          value={type}
          options={FLAG_TYPES.map((x) => ({ value: x, label: tk(`flag.${x}.name`) }))}
          allLabel={t("flags.filter.all")}
          onChange={(v) => set({ f_type: v, f_page: null })}
        />
        {variant === "cases" && (
          <FilterSelect
            label={t("flags.filter.institution")}
            value={chosenInstitution}
            options={(institutions.data?.items ?? []).map((i) => ({ value: i.id, label: i.name }))}
            allLabel={t("flags.filter.all")}
            onChange={(v) => set({ f_institution: v, f_programme: null, f_page: null })}
          />
        )}
        {showState && (
          <FilterSelect
            label={t("flags.filter.state")}
            value={state}
            options={(states.data ?? []).filter((s) => !region || s.region === region).map((s) => ({ value: s.code, label: `${s.name} (${s.code})` }))}
            allLabel={t("flags.filter.all")}
            onChange={(v) => set({ f_state: v, f_page: null })}
          />
        )}
        {chosenInstitution && chosen.data && (
          <FilterSelect
            label={t("flags.filter.programme")}
            value={programme}
            options={[...chosen.data.programmes].sort((a, b) => a.code.localeCompare(b.code)).map((p) => ({ value: p.id, label: p.code }))}
            allLabel={t("flags.filter.all")}
            onChange={(v) => set({ f_programme: v, f_page: null })}
          />
        )}
        <SearchInput label={t("flags.search")} value={q} onChange={onSearch} className="w-full sm:w-72" />
        {filtered && (
          <Button variant="link" size="sm" className="h-8 px-0" onClick={clearAll}>
            {t("empty.clear_filters")}
          </Button>
        )}
      </div>

      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-medium text-ink" aria-live="polite">
          {count}
        </p>
        <FilterSelect
          label={t("app.filter.sort")}
          value={sort}
          options={(["severity_desc", "created_desc"] as FlagSort[]).map((s) => ({ value: s, label: t(`flags.sort.${s}`) }))}
          allLabel={null}
          onChange={(v) => set({ f_sort: v === "severity_desc" ? null : v, f_page: null })}
        />
      </div>

      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised" onKeyDown={onKeyDown}>
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("section.flags")}</caption>
          <thead>
            <tr>
              <th scope="col" aria-sort={sort === "severity_desc" ? "descending" : "none"} title={t("flags.sort_tip")}>
                {t("col.severity")}
              </th>
              <th scope="col">{t("col.flag_type")}</th>
              {showInstitution && <th scope="col">{t("col.institution")}</th>}
              <th scope="col" className="code">
                {t("col.programme")}
              </th>
              <th scope="col">{t("col.evidence")}</th>
              <th scope="col" className="num" title={t("col.related_tip")}>
                {t("col.related")}
              </th>
              <th scope="col" className="num" aria-sort={sort === "created_desc" ? "descending" : "none"}>
                {t("col.opened")}
              </th>
              {showAssignee && <th scope="col">{t("col.assignee")}</th>}
            </tr>
          </thead>
          <tbody ref={tbody}>
            {list.isLoading && <SkeletonRows cols={cols} />}
            {list.isError && !data && (
              <TableMessage cols={cols}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={cols}>
                <EmptyState
                  icon={variant === "cases" ? <Inbox className="size-5" /> : <Flag className="size-5" />}
                  title={emptyTitle}
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
            {rows.map((f) => (
              <tr key={f.id}>
                <td>
                  <SeverityCell severity={f.severity} />
                </td>
                <td className="font-medium">
                  <span className="flex items-center gap-2">
                    {tk(`flag.${f.type}.name`)}
                    {f.status !== "OPEN" && <FlagStatusBadge status={f.status} compact />}
                  </span>
                </td>
                {showInstitution && (
                  <td className="wrap max-w-[16rem] min-w-[12rem] text-ink-muted">
                    {f.institution.name} <span className="code text-xs">{f.institution.state_code}</span>
                  </td>
                )}
                <td className="code">{f.programme?.code ?? ""}</td>
                <td className="max-w-[32rem] min-w-[16rem]">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link href={`${detailBase}/${f.id}`} data-row-link className="block truncate">
                        {f.summary}
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" align="start" className="max-w-md">
                      {f.summary}
                    </TooltipContent>
                  </Tooltip>
                </td>
                <td className="num">{formatCount(f.related_count)}</td>
                <td className="num text-ink-muted">{formatDate(f.created_at)}</td>
                {showAssignee && <td>{f.assignee?.name ?? ""}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-end gap-3">
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ f_page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
    </div>
  );
}
