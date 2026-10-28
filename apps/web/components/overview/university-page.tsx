"use client";

import { t } from "@/lib/copy";
import { admittedOf } from "@/lib/counts";
import { useDashboardSummary } from "@/lib/queries";
import { PageHeader } from "@/components/common/page-header";
import { InstitutionsTable } from "@/components/overview/institutions-table";
import { KpiStrip } from "@/components/overview/kpi-strip";

/** /university: affiliates read-only; Degree print has its own page. */
export function UniversityPage() {
  const summary = useDashboardSummary();
  const data = summary.data;
  const admitted = admittedOf(data?.kpis);
  const intake = data ? t("app.hint.intake", { academic_year: data.academic_year }) : undefined;
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
          { label: "kpi.approved_seats", value: data?.kpis.approved_seats, hint: intake },
          ...(data && admitted === null ? [] : [{ label: "kpi.admitted" as const, value: admitted ?? undefined, hint: intake }]),
          { label: "kpi.enrolments", value: data?.kpis.enrolments, hint: t("app.hint.all_years") },
        ]}
      />
      <section aria-label={t("app.university.affiliates")} className="mb-10">
        <InstitutionsTable variant="university" basePath="/university" academicYear={data?.academic_year} />
      </section>
    </>
  );
}
