"use client";

import { Suspense } from "react";
import { t } from "@/lib/copy";
import { useInstitution } from "@/lib/queries";
import { useMe } from "@/components/providers/root-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { EnrolmentsTable } from "@/components/institution/enrolments-table";

/** /college/enrolments: the same table as the officer tab, scoped by the api to this college. */
export function CollegeEnrolments() {
  const { user } = useMe();
  const detail = useInstitution(user?.scope.institution_id ?? null);
  const d = detail.data;
  return (
    <>
      <Crumbs items={[{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.enrolments") }]} />
      <PageHeader title={t("app.college.enrolments")} description={user?.scope.institution_name ?? undefined} />
      {detail.isError && !d && <ErrorBlock error={detail.error} onRetry={() => detail.refetch()} />}
      {!d && detail.isLoading && <Skeleton className="h-64" />}
      {d && (
        <Suspense>
          <EnrolmentsTable
            institutionId={d.id}
            programmes={d.programmes}
            academicYear={d.programmes[0]?.approval.academic_year ?? "2026-27"}
            enrolmentHref={(id) => `/college/enrolments/${id}`}
            flagHref={(id) => `/college/flags/${id}`}
          />
        </Suspense>
      )}
    </>
  );
}
