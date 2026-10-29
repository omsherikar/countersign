"use client";

import * as React from "react";
import { t } from "@/lib/copy";
import { admittedOf } from "@/lib/counts";
import { formatCount } from "@/lib/format";
import { useDashboardSummary, useRegions } from "@/lib/queries";
import { REGION_NAME } from "@/lib/roles";
import { useMe } from "@/components/providers/root-provider";
import { ErrorBlock } from "@/components/common/query-state";
import { FilterSelect } from "@/components/common/filter-select";
import { PageHeader, SectionHeader } from "@/components/common/page-header";
import { FlagsByType } from "@/components/overview/flags-by-type";
import { InstitutionsTable } from "@/components/overview/institutions-table";
import { KpiStrip, formatPct } from "@/components/overview/kpi-strip";
import { SourcesPanel } from "@/components/overview/sources-panel";
import { RegionTable, StateGrid } from "@/components/overview/state-grid";

/**
 * /aicte and /ro. The same page with the region baked in for RO: no Sources
 * panel (the ping is admin only), no Region column or filter, and By region
 * collapses to one summary line.
 */
export function OverviewPage({ variant }: { variant: "aicte" | "ro" }) {
  const { user } = useMe();
  const summary = useDashboardSummary();
  const regions = useRegions();
  const data = summary.data;
  const basePath = variant === "aicte" ? "/aicte" : "/ro";
  const region = variant === "ro" ? (user?.scope.region ?? null) : null;
  const regionMeta = region ? regions.data?.find((r) => r.code === region) : undefined;
  const regionRow = data?.by_region[0];

  const admitted = admittedOf(data?.kpis);
  const intake = data ? t("app.hint.intake", { academic_year: data.academic_year }) : undefined;
  const regionAdmitted = admittedOf(regionRow);

  const heading = variant === "aicte" ? t("aicte.heading") : t("ro.heading", { region_name: region ? REGION_NAME[region] : "" });

  return (
    <>
      <PageHeader
        title={heading}
        description={data ? `${data.scope.label}, academic year ${data.academic_year}` : " "}
        actions={
          <FilterSelect
            label={t("app.academic_year")}
            value={data?.academic_year ?? "2026-27"}
            options={[{ value: data?.academic_year ?? "2026-27", label: data?.academic_year ?? "2026-27" }]}
            allLabel={null}
            onChange={() => undefined}
          />
        }
      />

      <div className="mb-10">
        <KpiStrip
          loading={summary.isLoading}
          failed={summary.isError && !data}
          onRetry={() => summary.refetch()}
          tiles={[
            { label: "kpi.institutions", value: data?.kpis.institutions },
            { label: "kpi.programmes", value: data?.kpis.programmes },
            { label: "kpi.approved_seats", value: data?.kpis.approved_seats, hint: intake },
            ...(data && admitted === null ? [] : [{ label: "kpi.admitted" as const, value: admitted ?? undefined, hint: intake }]),
            { label: "kpi.enrolments", value: data?.kpis.enrolments, hint: t("app.hint.all_years") },
            {
              label: "kpi.flags_open",
              value: data?.kpis.flags_open,
              tone: data && data.kpis.flags_open > 0 ? "default" : "muted",
              tip: data ? t("kpi.flags_open_tip", { academic_year: data.academic_year }) : undefined,
              href: `${basePath}/cases`,
            },
            {
              label: "kpi.countersigned",
              value: data ? data.kpis.countersigned_pct : undefined,
              format: formatPct,
              hint: data && data.kpis.countersigned_pct !== null ? t("kpi.countersigned_value", { pct: formatPct(data.kpis.countersigned_pct).replace("%", "") }) : undefined,
              tip: t("kpi.countersigned_tip"),
            },
          ]}
        />
        {variant === "aicte" ? (
          <SourcesPanel />
        ) : (
          <div className="flex flex-col gap-x-6 gap-y-1 border-b border-rule bg-paper-raised px-4 py-2.5 text-sm lg:flex-row lg:items-center">
            <span className="text-ink-muted">{regionMeta ? t("ro.office_line", { hq_city: regionMeta.hq_city }) : " "}</span>
            {regionRow && (
              <span className="text-ink">
                {regionRow.region_name}: {formatCount(regionRow.institutions)} institutions, {formatCount(regionRow.approved_seats)} approved
                seats{regionAdmitted !== null && <>, {formatCount(regionAdmitted)} admitted</>}, {formatCount(regionRow.enrolments)} students on roll,{" "}
                {formatCount(regionRow.flags_open)} open flags
              </span>
            )}
          </div>
        )}
      </div>

      <section aria-labelledby="flags-by-type-heading" className="mb-12">
        <SectionHeader id="flags-by-type-heading" title={t("section.flags_by_type")} />
        {summary.isError && !data ? (
          <ErrorBlock error={summary.error} onRetry={() => summary.refetch()} />
        ) : (
          <FlagsByType summary={data} loading={summary.isLoading} casesHref={`${basePath}/cases`} />
        )}
      </section>

      <section aria-labelledby="ranked-heading" className="mb-12">
        <SectionHeader id="ranked-heading" title={t("section.institutions_ranked")} />
        <InstitutionsTable variant={variant} basePath={basePath} region={region} academicYear={data?.academic_year} />
      </section>

      <section aria-labelledby="by-state-heading" className="mb-12">
        <SectionHeader id="by-state-heading" title={t("section.by_state")} aside={<span>{t("app.state_pick_hint")}</span>} />
        {summary.isError && !data ? (
          <ErrorBlock error={summary.error} onRetry={() => summary.refetch()} />
        ) : (
          <StateGrid summary={data} loading={summary.isLoading} />
        )}
      </section>

      {variant === "aicte" && data && data.by_region.length > 0 && (
        <section aria-labelledby="by-region-heading" className="mb-6">
          <SectionHeader id="by-region-heading" title={t("section.by_region")} />
          <RegionTable summary={data} regions={regions.data} />
        </section>
      )}
    </>
  );
}
