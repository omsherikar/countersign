"use client";

import { Printer } from "lucide-react";
import { t } from "@/lib/copy";
import { useDashboardSummary } from "@/lib/queries";
import { PageHeader } from "@/components/common/page-header";
import { InstitutionsTable } from "@/components/overview/institutions-table";
import { KpiStrip } from "@/components/overview/kpi-strip";

/** /university: affiliates read-only, and where Degree print will live. */
export function UniversityPage() {
  const summary = useDashboardSummary();
  const data = summary.data;
  return (
    <>
      <PageHeader
        title={t("university.heading")}
        description={data ? `${data.scope.label}, ${t("app.academic_year").toLowerCase()} ${data.academic_year}` : " "}
      />
      <KpiStrip
        className="mb-10"
        loading={summary.isLoading}
        failed={summary.isError && !data}
        onRetry={() => summary.refetch()}
        tiles={[
          { label: "kpi.institutions", value: data?.kpis.institutions },
          { label: "kpi.programmes", value: data?.kpis.programmes },
          { label: "kpi.approved_seats", value: data?.kpis.approved_seats },
          { label: "kpi.enrolments", value: data?.kpis.enrolments },
        ]}
      />
      <section aria-label={t("app.university.affiliates")} className="mb-10">
        <InstitutionsTable variant="university" basePath="/university" />
      </section>
      <section className="flex max-w-[68ch] items-start gap-3 border-l-2 border-rule-margin bg-paper-raised px-4 py-3">
        <Printer className="mt-0.5 size-5 shrink-0 text-ink-faint" aria-hidden="true" />
        <div>
          <h2 className="font-sans text-md font-semibold">{t("nav.degree_print")}</h2>
          <p className="mt-0.5 text-sm text-ink-muted">{t("university.degree_teaser")}</p>
        </div>
      </section>
    </>
  );
}
