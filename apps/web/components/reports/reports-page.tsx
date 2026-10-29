"use client";

import * as React from "react";
import { Download, FlaskConical, Loader2 } from "lucide-react";
import { api, API_BASE, ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatDateTime } from "@/lib/format";
import { useRegions, useStates } from "@/lib/queries";
import { reportPath, reportQuery, useReportPreview, useReports } from "@/lib/queries-signals";
import { REGION_NAME } from "@/lib/roles";
import type { Region, ReportFormat, ReportInfo, ReportName, ReportQuery } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/brand/EmptyState";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { FieldSelect } from "@/components/cases/sheet-shell";

const YEARS = ["2026-27", "2025-26"];

/** report.name.* and report.desc.* use the deck's short keys. */
const KEY: Record<ReportName, string> = {
  "by-state": "by_state",
  "by-institution-type": "by_institution_type",
  "cases-by-type-and-outcome": "cases",
  "countersign-coverage": "coverage",
  completeness: "completeness",
  summary: "summary",
};

const FORMAT_WORD: Record<ReportFormat, string> = { csv: "CSV", xlsx: "XLSX", pdf: "PDF" };

/**
 * /aicte/reports and /ro/reports (W4-7): summaries for policy,
 * accreditation and monitoring, each a download per format and a preview of
 * its first rows. The synthetic-data label sits on top and never goes away;
 * a regional officer reads that the files cover only the region.
 */
export function ReportsPage({ variant }: { variant: "aicte" | "ro" }) {
  const { user } = useMe();
  const [params, set] = useUrlParams();
  const year = params.get("r_year") ?? YEARS[0];
  const list = useReports();
  const regions = useRegions();
  const states = useStates();
  const [generated] = React.useState(() => new Date().toISOString());
  const region = variant === "ro" ? (user?.scope.region ?? null) : null;
  // A4.21: AICTE may narrow to a region or a state; a regional officer's files are its region, narrowed to a state at most.
  const pickedRegion = variant === "aicte" ? ((params.get("r_region") as Region | null) ?? null) : null;
  const pickedState = params.get("r_state") ?? null;
  const inScope = (states.data ?? []).filter((st) => (region ? st.region === region : pickedRegion ? st.region === pickedRegion : true));
  const stateName = pickedState ? states.data?.find((st) => st.code === pickedState)?.name : undefined;
  const scopeName = stateName ?? (region ? `${REGION_NAME[region]} Region` : pickedRegion ? `${REGION_NAME[pickedRegion]} Region` : "All India");
  const query: ReportQuery = { academic_year: year, region: pickedRegion ?? undefined, state: pickedState ?? undefined };

  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: `/${variant}` }, { label: t("report.heading") }]} />
      <PageHeader
        title={t("report.heading")}
        actions={
          <FieldSelect
            id="reports-year"
            label={t("app.academic_year")}
            value={year}
            onChange={(v) => set({ r_year: v === YEARS[0] ? null : v })}
            options={YEARS.map((y) => ({ value: y, label: y }))}
            required={false}
            className="w-36"
          />
        }
      />
      <p className="mb-4 max-w-[68ch] text-md text-ink-muted md:text-sm">{t("report.lead")}</p>
      <p className="mb-3 flex max-w-[68ch] items-start gap-2 rounded-md border border-check-pending/50 bg-check-pending-soft px-3 py-2 text-sm text-check-pending-ink">
        <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <span>{t("report.synthetic")}</span>
      </p>
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:max-w-xl">
        {variant === "aicte" && (
          <FieldSelect
            id="reports-region"
            label={t("report.filter.region")}
            value={pickedRegion ?? ""}
            onChange={(v) => set({ r_region: v || null, r_state: null })}
            options={[{ value: "", label: "All India" }, ...(regions.data ?? []).map((r) => ({ value: r.code, label: `${REGION_NAME[r.code]} Region` }))]}
            required={false}
          />
        )}
        <FieldSelect
          id="reports-state"
          label={t("report.filter.state")}
          value={pickedState ?? ""}
          onChange={(v) => set({ r_state: v || null })}
          options={[{ value: "", label: t("flags.filter.all") }, ...inScope.map((st) => ({ value: st.code, label: st.name }))]}
          required={false}
        />
      </div>
      <p className="mb-1 text-sm text-ink-muted">{t("report.scope_line", { scope_name: scopeName, academic_year: year, time: formatDateTime(generated) })}</p>
      {region && <p className="mb-1 text-sm text-ink-muted">{t("report.ro_scope", { region_name: REGION_NAME[region] })}</p>}

      <div className="mt-6">
        {list.isError && !list.data ? (
          <ErrorBlock error={list.error} onRetry={() => list.refetch()} />
        ) : !list.data ? (
          <div aria-hidden="true" className="flex flex-col gap-3">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
            <SlowHint />
          </div>
        ) : (
          <ul className="flex flex-col divide-y divide-rule border-y border-rule">
            {list.data.items.map((r) => (
              <ReportRow key={r.name} report={r} query={query} />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function ReportRow({ report, query }: { report: ReportInfo; query: ReportQuery }) {
  const [preview, setPreview] = React.useState(false);
  const name = tk(`report.name.${KEY[report.name]}`);
  const regionId = React.useId();
  const formats = (["csv", "xlsx", "pdf"] as ReportFormat[]).filter((f) => report.formats.includes(f));
  const shown = formats;
  return (
    <li className="py-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 lg:max-w-[60ch]">
          <h2 className="font-sans text-md font-semibold">{name}</h2>
          <p className="mt-0.5 text-md text-ink-muted md:text-sm">{tk(`report.desc.${KEY[report.name]}`)}</p>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-start">
          {shown.map((f) => (
            <DownloadLink key={f} report={report.name} reportName={name} format={f} query={query} />
          ))}
          {report.name !== "summary" && (
            <button
              type="button"
              aria-expanded={preview}
              aria-controls={regionId}
              onClick={() => setPreview((p) => !p)}
              className="inline-flex h-12 items-center justify-center rounded-md border border-line bg-paper-raised px-3 text-md font-medium hover:bg-paper-sunken sm:h-9 sm:text-sm"
            >
              {t("report.preview")}
            </button>
          )}
        </div>
      </div>
      <div id={regionId}>{preview && <Preview name={report.name} query={query} />}</div>
    </li>
  );
}

/**
 * A real link to the file, so it can be opened in a new tab; a plain click
 * fetches it instead, to say "Preparing" while the server builds it and to
 * show the error under the report when it cannot.
 */
function DownloadLink({ report, reportName, format, query }: { report: ReportName; reportName: string; format: ReportFormat; query: ReportQuery }) {
  const [state, setState] = React.useState<"idle" | "busy" | "failed" | "missing">("idle");
  const path = `${reportPath(report, format)}${reportQuery(query)}`;
  const year = query.academic_year ?? "";
  const word = FORMAT_WORD[format];
  async function go(e: React.MouseEvent<HTMLAnchorElement>) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    if (state === "busy") return;
    setState("busy");
    try {
      await api.download(path, `countersign_${report}_${year}.${format}`);
      setState("idle");
    } catch (err) {
      setState(err instanceof ApiError && err.status === 404 ? "missing" : "failed");
    }
  }
  return (
    <span className="flex min-w-0 flex-col">
      <a
        href={`${API_BASE}${path}`}
        onClick={go}
        aria-label={t("report.download_label", { report_name: reportName, format: word })}
        aria-busy={state === "busy" || undefined}
        className={cn(
          "inline-flex h-12 items-center justify-center gap-1.5 rounded-md border-[1.5px] border-ink-blue bg-paper-raised px-3 text-md font-medium text-ink-blue no-underline hover:bg-flag-open-soft sm:h-9 sm:text-sm",
          state === "busy" && "opacity-70",
        )}
      >
        {state === "busy" ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Download className="size-4" aria-hidden="true" />}
        {state === "busy" ? t("report.preparing", { format: word }) : word}
      </a>
      {(state === "failed" || state === "missing") && (
        <span role="alert" className="mt-1 max-w-56 text-sm text-check-fail-ink">
          {state === "missing" ? t("err.NOT_FOUND_report") : t("err.REPORT_FAILED")}
        </span>
      )}
    </span>
  );
}

function Preview({ name, query }: { name: ReportName; query: ReportQuery }) {
  const q = useReportPreview(name, query);
  const year = query.academic_year ?? "";
  if (q.isError && !q.data) {
    const missing = q.error instanceof ApiError && q.error.status === 404;
    return (
      <p role="alert" className="mt-3 text-sm text-check-fail-ink">
        {missing ? t("err.NOT_FOUND_report") : t("err.REPORT_FAILED")}
      </p>
    );
  }
  if (!q.data) {
    return (
      <div aria-hidden="true" className="mt-3 flex flex-col gap-1.5">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-3/4" />
      </div>
    );
  }
  if (q.data.total === 0) {
    return (
      <div className="mt-3 border-l-2 border-rule-margin bg-paper-raised">
        <EmptyState title={t("report.empty", { academic_year: year })} />
      </div>
    );
  }
  const { columns, rows, total } = q.data;
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-sm text-ink-muted">{total === 1 ? t("report.preview_rows", { n: rows.length, total }).replace(/ rows$/, " row") : t("report.preview_rows", { n: rows.length, total })}</p>
      <div className="relative max-h-[26rem] overflow-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table">
          <caption className="sr-only">{t("report.preview")}</caption>
          <thead className="sticky top-0 z-10 bg-paper-raised">
            <tr>
              {columns.map((c, i) => (
                <th key={c} scope="col" className={cn("code text-xs", i === 0 && "sticky left-0 z-20 bg-paper-raised")}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri}>
                {r.map((cell, ci) => (
                  <td key={ci} className={cn(/^-?\d+(\.\d+)?$/.test(cell) ? "num" : "", ci === 0 && "sticky left-0 bg-paper-raised")}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
