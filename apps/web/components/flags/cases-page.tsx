"use client";

import { t } from "@/lib/copy";
import { useMe } from "@/components/providers/root-provider";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { FlagsTable } from "@/components/flags/flags-table";

/** /aicte/cases, /ro/cases and /college/flags: the flags list with its heading. */
export function CasesPage({ variant }: { variant: "aicte" | "ro" | "college" }) {
  const { user } = useMe();
  if (variant === "college") {
    return (
      <>
        <Crumbs items={[{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.flags") }]} />
        <PageHeader title={t("flags.heading_college")} description={user?.scope.institution_name ?? undefined} />
        <p className="mb-5 max-w-[68ch] text-sm text-ink-muted">{t("flag.readonly_college")}</p>
        <FlagsTable variant="college" detailBase="/college/flags" institutionId={user?.scope.institution_id ?? undefined} />
      </>
    );
  }
  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: variant === "aicte" ? "/aicte" : "/ro" }, { label: t("nav.cases") }]} />
      <PageHeader title={t("nav.cases")} />
      <p className="mb-5 max-w-[68ch] text-sm text-ink-muted">{t("flag.readonly_officer")}</p>
      <FlagsTable variant="cases" detailBase={`/${variant}/cases`} showState region={variant === "ro" ? (user?.scope.region ?? null) : null} />
    </>
  );
}
