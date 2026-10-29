"use client";

import { t } from "@/lib/copy";
import { useDashboardSummary } from "@/lib/queries";
import { useMe } from "@/components/providers/root-provider";
import { Crumbs } from "@/components/common/page-header";
import { CompletenessView } from "@/components/records/completeness-view";

/** /college/completeness (page spec W4-4): the college's own completeness, deadline and the students to upload. */
export function CollegeCompleteness() {
  const { user } = useMe();
  const id = user?.scope.institution_id ?? null;
  const summary = useDashboardSummary();
  const academicYear = summary.data?.academic_year ?? "2026-27";
  return (
    <>
      <Crumbs items={[{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.completeness") }]} />
      {id && (
        <CompletenessView institutionId={id} academicYear={academicYear} audience="college" caseHref={(cid) => `/college/flags/${cid}`} headingLevel="h1" />
      )}
    </>
  );
}
