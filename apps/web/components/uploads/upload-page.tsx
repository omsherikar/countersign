"use client";

import { t } from "@/lib/copy";
import { useInstitution } from "@/lib/queries";
import { useMe } from "@/components/providers/root-provider";
import { Crumbs, PageHeader, SectionHeader } from "@/components/common/page-header";
import { UploadForm } from "@/components/uploads/upload-form";
import { UploadHistory } from "@/components/uploads/upload-history";

/** /college/upload: the form, then the year's previous uploads. */
export function UploadPage() {
  const { user } = useMe();
  const detail = useInstitution(user?.scope.institution_id ?? null);
  const years = [...new Set((detail.data?.programmes ?? []).map((p) => p.approval.academic_year))].sort().reverse();
  const academicYear = years[0] ?? "2026-27";
  return (
    <>
      <Crumbs items={[{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.upload") }]} />
      <PageHeader title={t("upload.heading")} description={<p className="max-w-[68ch]">{t("upload.lead")}</p>} />
      <div className="mb-12">
        <UploadForm key={academicYear} years={years.length ? years : [academicYear]} />
      </div>
      <section aria-labelledby="previous-heading">
        <SectionHeader id="previous-heading" title={t("upload.previous")} aside={<span>{`${t("app.academic_year")} ${academicYear}`}</span>} />
        <UploadHistory academicYear={academicYear} batchHref={(id) => `/college/uploads/${id}`} />
      </section>
    </>
  );
}
