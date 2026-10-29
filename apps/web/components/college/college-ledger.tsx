"use client";

import * as React from "react";
import Link from "next/link";
import { t } from "@/lib/copy";
import { institutionAdmitted, seatedOf } from "@/lib/counts";
import { formatCount } from "@/lib/format";
import { useDashboardSummary, useInstitution } from "@/lib/queries";
import { useMe } from "@/components/providers/root-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { PageHeader, SectionHeader } from "@/components/common/page-header";
import { KpiStrip } from "@/components/overview/kpi-strip";
import { ProgrammesTable } from "@/components/institution/programmes-table";
import { CollegeFlagsPanel } from "@/components/college/college-flags-panel";
import { LastUploadLine } from "@/components/uploads/last-upload-line";
import { StatusPanel } from "@/components/records/status-panel";
import { DeadlineWord, completenessLine, deadlineTip } from "@/components/records/deadline-word";

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
  const intake = t("app.hint.intake", { academic_year: academicYear });

  return (
    <>
      <PageHeader
        title={t("app.college.heading")}
        description={`${user?.scope.institution_name ?? ""}, ${t("app.academic_year").toLowerCase()} ${academicYear}`}
      />
      <KpiStrip
        className="mb-2"
        loading={summary.isLoading || detail.isLoading}
        failed={(summary.isError && !summary.data) || (detail.isError && !d)}
        onRetry={() => {
          void summary.refetch();
          void detail.refetch();
        }}
        tiles={[
          { label: "kpi.programmes", value: summary.data?.kpis.programmes },
          { label: "kpi.approved_seats", value: approved, hint: intake },
          { label: "kpi.admitted", value: admitted, hint: intake },
          { label: "col.seated", value: seated },
          { label: "col.unseated", value: unseated, tone: "default" },
        ]}
      />

      <p className="mb-10 text-sm text-ink-muted">
        {summary.data ? t("app.all_years_line", { n: formatCount(summary.data.kpis.enrolments) }) : " "}
      </p>

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

      <section aria-labelledby="records-heading" className="mb-10">
        <SectionHeader id="records-heading" title={t("kpi.status_heading")} />
        <StatusPanel
          counts={summary.data?.kpis.records}
          academicYear={academicYear}
          headingId="records-heading"
          loading={summary.isLoading}
          failed={summary.isError && !summary.data}
          onRetry={() => summary.refetch()}
          hrefFor={(s) => `/college/enrolments?e_status=${s}`}
        />
      </section>

      <section aria-labelledby="completeness-heading" className="mb-10">
        <SectionHeader id="completeness-heading" title={t("completeness.heading")} aside={summary.data?.completeness && summary.data.completeness.missing > 0 ? <Link href="/college/completeness">{t("missing.heading", { n: formatCount(summary.data.completeness.missing) })}</Link> : undefined} />
        {summary.isLoading ? (
          <Skeleton className="h-16" />
        ) : summary.isError && !summary.data ? (
          <ErrorBlock error={summary.error} onRetry={() => summary.refetch()} />
        ) : summary.data?.completeness ? (
          <div className="flex flex-col gap-1.5 border-l-2 border-rule-margin bg-paper-raised px-4 py-3">
            <p className="max-w-none font-display text-lg font-semibold">
              <Link href="/college/completeness" className="text-ink">
                {completenessLine(summary.data.completeness)}
              </Link>
            </p>
            <p className="flex max-w-none flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              <DeadlineWord
                state={summary.data.completeness.deadline_state}
                deadline={summary.data.completeness.deadline}
                firstUploadAt={summary.data.completeness.first_upload_at}
                className="font-medium"
              />
              <span className="text-ink-muted">
                {deadlineTip(summary.data.completeness.deadline_state, summary.data.completeness.deadline, summary.data.completeness.first_upload_at)}
              </span>
            </p>
          </div>
        ) : (
          <p className="text-sm text-ink-muted">{t("completeness.line_none")}</p>
        )}
      </section>

      <CollegeFlagsPanel academicYear={academicYear} />

      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-ink-muted">
        {d ? <LastUploadLine last={d.last_upload} href={(id) => `/college/uploads/${id}`} /> : <span> </span>}
        <Link href="/college/upload">{t("upload.upload_again")}</Link>
      </div>
    </>
  );
}
