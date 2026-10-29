"use client";

import * as React from "react";
import Link from "next/link";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useSignals } from "@/lib/queries-signals";
import type { SignalListQuery, SignalStatus, SignalType } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { EmptyState } from "@/components/brand/EmptyState";
import { Pager } from "@/components/common/pager";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Skeleton } from "@/components/ui/skeleton";
import { FieldSelect } from "@/components/cases/sheet-shell";
import { NeverStatusLine, SignalStatusBadge, SignalTypeWord, countLine } from "@/components/signals/signal-bits";

const YEARS = ["2026-27", "2025-26"];
const TYPES: SignalType[] = ["GHOST_RING", "ANOMALY"];
const STATUSES: SignalStatus[] = ["NEW", "CASE_OPENED", "DISMISSED"];
const PAGE_SIZE = 25;

/**
 * /aicte/signals and /ro/signals (W4-6): patterns found by a published rule
 * or a model, for officers only. Filters live in the URL with the `s_`
 * prefix; the default shows New signals, newest first.
 */
export function SignalsPage({ variant }: { variant: "aicte" | "ro" }) {
  const [params, set] = useUrlParams();
  const base = `/${variant}/signals`;
  const year = params.get("s_year") ?? YEARS[0];
  const type = (params.get("s_type") ?? "") as SignalType | "";
  const statusParam = params.get("s_status");
  const status = (statusParam === null ? "NEW" : statusParam === "all" ? "" : statusParam) as SignalStatus | "";
  const institution = params.get("s_inst") ?? "";
  const page = Math.max(1, Number(params.get("s_page") ?? 1));
  const query: SignalListQuery = { academic_year: year, type: type || undefined, status: status || undefined, institution_id: institution || undefined, page, page_size: PAGE_SIZE };
  const list = useSignals(query);
  // The count line and the college filter read every signal of the year, whatever the filters.
  const everything = useSignals({ academic_year: year, page_size: 200 });
  const total = everything.data?.total ?? 0;
  const fresh = everything.data?.items.filter((s) => s.status === "NEW").length ?? 0;
  const colleges = React.useMemo(() => {
    const map = new Map<string, string>();
    for (const s of everything.data?.items ?? []) for (const i of s.institutions) map.set(i.id, i.name);
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [everything.data]);
  const filtered = Boolean(type || institution || statusParam !== null);

  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: `/${variant}` }, { label: t("signal.heading") }]} />
      <PageHeader
        title={t("signal.heading")}
        actions={
          <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
            <FieldSelect
              id="signals-year"
              label={t("app.academic_year")}
              value={year}
              onChange={(v) => set({ s_year: v === YEARS[0] ? null : v, s_page: null })}
              options={YEARS.map((y) => ({ value: y, label: y }))}
              required={false}
              className="w-36"
            />
            <p className="pb-2 text-sm text-ink-muted" aria-live="polite">
              {everything.data ? countLine(total, fresh) : " "}
            </p>
          </div>
        }
      />
      <div className="mb-6 flex flex-col gap-2">
        <p className="max-w-[68ch] text-md text-ink-muted md:text-sm">{t("signal.lead")}</p>
        <NeverStatusLine />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3 lg:max-w-3xl">
        <FieldSelect
          id="signals-type"
          label={t("signal.col.type")}
          value={type}
          onChange={(v) => set({ s_type: v || null, s_page: null })}
          options={[{ value: "", label: t("flags.filter.all") }, ...TYPES.map((x) => ({ value: x, label: tk(`signal.type.${x}`) }))]}
          required={false}
        />
        <FieldSelect
          id="signals-status"
          label={t("signal.col.status")}
          value={statusParam === null ? "NEW" : statusParam}
          onChange={(v) => set({ s_status: v === "NEW" ? null : v, s_page: null })}
          options={[{ value: "all", label: t("flags.filter.all") }, ...STATUSES.map((x) => ({ value: x, label: tk(`signal.status.${x}`) }))]}
          required={false}
        />
        <FieldSelect
          id="signals-institution"
          label={t("flags.filter.institution")}
          value={institution}
          onChange={(v) => set({ s_inst: v || null, s_page: null })}
          options={[{ value: "", label: t("flags.filter.all") }, ...colleges.map(([id, name]) => ({ value: id, label: name }))]}
          required={false}
        />
      </div>

      {list.isError && !list.data ? (
        <ErrorBlock error={list.error} onRetry={() => list.refetch()} />
      ) : !list.data ? (
        <div aria-hidden="true" className="flex flex-col gap-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
          <SlowHint />
        </div>
      ) : list.data.items.length === 0 ? (
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          {filtered ? (
            <EmptyState
              title={t("signal.empty_filtered")}
              action={
                <button type="button" className="inline-flex min-h-11 items-center text-ink-blue underline" onClick={() => set({ s_type: null, s_status: "all", s_inst: null, s_page: null })}>
                  {t("empty.clear_filters")}
                </button>
              }
            />
          ) : (
            <EmptyState title={t("signal.empty", { academic_year: year })} />
          )}
        </div>
      ) : (
        <>
          <ul className="flex flex-col divide-y divide-rule border-l-2 border-rule-margin bg-paper-raised md:hidden">
            {list.data.items.map((s) => (
              <li key={s.id}>
                <Link href={`${base}/${s.id}`} className="block px-3 py-3 text-ink no-underline">
                  <span className="flex items-center justify-between gap-2">
                    <SignalTypeWord type={s.type} className="font-medium text-ink-blue" />
                    <SignalStatusBadge status={s.status} />
                  </span>
                  <span className="mt-1 block text-md leading-snug">{s.summary}</span>
                  <span className="mt-1 block text-sm text-ink-muted">
                    {s.institutions.map((i) => i.name).join("; ")}
                    {s.institutions_hidden > 0 ? ` +${s.institutions_hidden}` : ""}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="relative hidden overflow-x-auto border-l-2 border-rule-margin bg-paper-raised md:block">
            <table className="ledger-table">
              <caption className="sr-only">{t("signal.heading")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("signal.col.type")}</th>
                  <th scope="col">{t("signal.col.summary")}</th>
                  <th scope="col" className="num">
                    {t("signal.col.colleges")}
                  </th>
                  <th scope="col" className="num">
                    {t("signal.col.records")}
                  </th>
                  <th scope="col">{t("signal.col.found")}</th>
                  <th scope="col">{t("signal.col.status")}</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((s) => (
                  <tr key={s.id}>
                    <td className="whitespace-nowrap">
                      <Link href={`${base}/${s.id}`} className="font-medium">
                        <SignalTypeWord type={s.type} />
                      </Link>
                    </td>
                    <td className="wrap !h-auto min-w-80 py-2 leading-snug">{s.summary}</td>
                    <td className="num">{formatCount(s.institutions.length + s.institutions_hidden)}</td>
                    <td className="num">{s.type === "ANOMALY" ? "-" : formatCount(s.member_count)}</td>
                    <td className="whitespace-nowrap">{formatDate(s.created_at)}</td>
                    <td>
                      <SignalStatusBadge status={s.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {list.data.total > PAGE_SIZE && (
            <div className="mt-3 flex justify-end">
              <Pager page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={(p) => set({ s_page: p === 1 ? null : p })} busy={list.isFetching} />
            </div>
          )}
        </>
      )}
    </>
  );
}
