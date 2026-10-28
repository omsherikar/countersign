"use client";

import * as React from "react";
import Link from "next/link";
import { Flag } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { t } from "@/lib/copy";
import { fillPct, institutionAdmitted, seatedOf } from "@/lib/counts";
import { useDashboardSummary, useInstitution } from "@/lib/queries";
import { useMe } from "@/components/providers/root-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { PageHeader, SectionHeader } from "@/components/common/page-header";
import { KpiStrip } from "@/components/overview/kpi-strip";
import { ProgrammesTable } from "@/components/institution/programmes-table";

/** "What are pools?": a disclosure, so it works on touch and with a keyboard. */
function PoolsHelp() {
  const [open, setOpen] = React.useState(false);
  const id = React.useId();
  return (
    <div className="mt-3 text-sm text-ink-muted">
      <span>{t("ledger.pools_source")} </span>
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)} className="text-ink-blue underline underline-offset-2">
        {t("ledger.pools_help_link")}
      </button>
      {open && (
        <p id={id} className="mt-2 max-w-[68ch] border-l-2 border-rule-margin bg-paper-raised px-3 py-2 text-ink">
          {t("ledger.pools_help")}
        </p>
      )}
    </div>
  );
}

/** /college: the registrar's own seat ledger, per programme, with pools open where enrolments are unseated. */
export function CollegeLedger() {
  const { user } = useMe();
  const institutionId = user?.scope.institution_id ?? null;
  const summary = useDashboardSummary();
  const detail = useInstitution(institutionId);
  const d = detail.data;
  const unseated = d ? d.programmes.reduce((a, p) => a + p.unseated, 0) : undefined;
  const seated = d ? d.programmes.reduce((a, p) => a + seatedOf(p), 0) : undefined;
  const academicYear = summary.data?.academic_year ?? d?.programmes[0]?.approval.academic_year ?? "2026-27";
  // Admitted is this year's intake, the same population as the seats and the unseated count beside it.
  const admitted = d ? institutionAdmitted(d) : undefined;
  const approved = summary.data?.kpis.approved_seats;
  const fill = fillPct(admitted ?? null, approved);

  return (
    <>
      <PageHeader
        title={t("app.college.heading")}
        description={`${user?.scope.institution_name ?? ""}, ${t("app.academic_year").toLowerCase()} ${academicYear}`}
      />
      <KpiStrip
        className="mb-10"
        loading={summary.isLoading || detail.isLoading}
        failed={(summary.isError && !summary.data) || (detail.isError && !d)}
        onRetry={() => {
          void summary.refetch();
          void detail.refetch();
        }}
        tiles={[
          { label: "kpi.programmes", value: summary.data?.kpis.programmes },
          { label: "kpi.approved_seats", value: approved, hint: t("app.hint.intake", { academic_year: academicYear }) },
          { label: "col.admitted", value: admitted, hint: fill !== null ? t("app.hint.fill", { pct: fill }) : undefined },
          { label: "col.seated", value: seated },
          { label: "col.unseated", value: unseated, tone: "default" },
          { label: "app.on_roll", value: summary.data?.kpis.enrolments, hint: t("app.hint.all_years") },
        ]}
      />

      <section aria-labelledby="programmes-heading" className="mb-12">
        <SectionHeader id="programmes-heading" title={t("section.programmes")} aside={<span>{`${t("app.academic_year")} ${academicYear}`}</span>} />
        {detail.isError && !d ? (
          <ErrorBlock error={detail.error} onRetry={() => detail.refetch()} />
        ) : d ? (
          <>
            <ProgrammesTable
              programmes={d.programmes}
              academicYear={academicYear}
              openWhen={(p) => p.unseated > 0}
              emptyText={t("empty.programmes_college")}
            />
            <PoolsHelp />
          </>
        ) : (
          <div className="flex flex-col gap-2" aria-hidden="true">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="flags-heading" className="mb-10">
        <SectionHeader id="flags-heading" title={t("app.college.flags", { n: 0 })} />
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          <EmptyState icon={<Flag className="size-5" />} title={t("empty.flags_college")} />
        </div>
      </section>

      <p className="text-sm text-ink-muted">
        {t("college.no_upload_yet")}{" "}
        <Link href="/college/upload">{t("app.upload.see_columns")}</Link>
      </p>
    </>
  );
}
