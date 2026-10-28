"use client";

import * as React from "react";
import { Lock } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { EvidenceCard } from "@/components/brand/EvidenceCard";
import { FlagStatusBadge } from "@/components/brand/FlagStatusBadge";
import { SeverityBadge } from "@/components/brand/SeverityBadge";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate, formatDateTime, singular } from "@/lib/format";
import { useFlag } from "@/lib/queries";
import type { FlagDetail as Detail } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Crumbs, SectionHeader, type Crumb } from "@/components/common/page-header";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { RelatedEnrolmentsTable } from "@/components/flags/related-enrolments";

export type FlagDetailVariant = "aicte" | "ro" | "college";

const LIST: Record<FlagDetailVariant, string> = { aicte: "/aicte/cases", ro: "/ro/cases", college: "/college/flags" };
const ENROLMENT: Record<FlagDetailVariant, string> = { aicte: "/aicte/enrolments", ro: "/ro/enrolments", college: "/college/enrolments" };

function crumbsFor(variant: FlagDetailVariant, d: Detail | undefined): Crumb[] {
  const name = d ? tk(`flag.${d.type}.name`) : "…";
  if (variant === "college") {
    const last = d?.programme ? `${name} in ${d.programme.code}` : name;
    return [{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.flags"), href: LIST.college }, { label: last }];
  }
  return [
    { label: t("nav.overview"), href: variant === "aicte" ? "/aicte" : "/ro" },
    { label: t("nav.cases"), href: LIST[variant] },
    { label: d ? `${name}, ${d.institution.name}` : name },
  ];
}

/**
 * One flag, read only (page spec W2-8): what it says, the evidence as the
 * engines wrote it with each fact's source and the rule, then the
 * enrolments it names. Actions arrive with the case queue.
 */
export function FlagDetail({ id, variant }: { id: string; variant: FlagDetailVariant }) {
  const q = useFlag(id);
  const d = q.data;

  if (q.isError && !d) {
    return (
      <>
        <Crumbs items={crumbsFor(variant, undefined)} />
        <h1 className="sr-only">{t("nav.flags")}</h1>
        <ErrorBlock error={q.error} entity="flag" backHref={LIST[variant]} backLabel={t("case.back")} onRetry={() => q.refetch()} className="mt-4" />
      </>
    );
  }

  const enrolmentHref = (eid: string) => `${ENROLMENT[variant]}/${eid}`;
  const flagHref = (fid: string) => `${LIST[variant]}/${fid}`;

  return (
    <>
      <Crumbs items={crumbsFor(variant, d)} />
      {!d ? (
        <div className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-9 w-80" />
          <Skeleton className="h-4 w-96" />
          <Skeleton className="mt-6 h-56 max-w-3xl" />
          <SlowHint />
        </div>
      ) : (
        <>
          <header className="mb-6">
            <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
              <h1 className="text-2xl md:text-3xl">{tk(`flag.${d.type}.name`)}</h1>
              <p className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
                <SeverityBadge severity={d.severity} />
                <FlagStatusBadge status={d.status} />
                <span>{t("flag.meta", { severity_word: tk(`severity.${d.severity}`), status_word: tk(`flag_status.${d.status}`), created_date: formatDate(d.created_at) }).split(" · ").pop()}</span>
              </p>
            </div>
            <p className="mt-1.5 text-sm text-ink-muted">
              {d.programme
                ? t("flag.where", { institution_name: d.institution.name, programme_code: d.programme.code, academic_year: d.academic_year })
                : t("flag.where_no_programme", { institution_name: d.institution.name, academic_year: d.academic_year })}
            </p>
            <p className="mt-4 flex max-w-[68ch] items-start gap-2 border-l-2 border-rule-strong bg-paper-raised px-3 py-2 text-sm text-ink-muted">
              <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {variant === "college" ? t("flag.readonly_college") : t("flag.readonly_officer")}
            </p>
          </header>

          <section aria-labelledby="evidence-heading" className="mb-10 max-w-4xl">
            <SectionHeader id="evidence-heading" title={t("section.evidence")} />
            <EvidenceCard
              type={d.type}
              severity={d.severity}
              heading={d.programme ? `${d.programme.name} (${d.programme.code})` : d.institution.name}
              evidence={{ summary: d.evidence.summary, facts: d.evidence.facts, rule_source: d.evidence.rule_source }}
            />
          </section>

          {d.enrolment && (
            <section aria-labelledby="enrolment-heading" className="mb-10">
              <SectionHeader id="enrolment-heading" title={t("flag.enrolment_heading")} />
              <RelatedEnrolmentsTable rows={[d.enrolment]} caption={t("flag.enrolment_heading")} enrolmentHref={enrolmentHref} flagHref={flagHref} />
            </section>
          )}

          <section aria-labelledby="related-heading" className="mb-10">
            <SectionHeader id="related-heading" title={t("flag.related_heading", { n: formatCount(d.related_enrolments.length) })} />
            {d.related_enrolments.length === 0 ? (
              <div className="border-l-2 border-rule-margin bg-paper-raised">
                <EmptyState title={t("empty.related")} />
              </div>
            ) : (
              <RelatedEnrolmentsTable rows={d.related_enrolments} caption={t("section.related")} enrolmentHref={enrolmentHref} flagHref={flagHref} />
            )}
            {d.related_hidden > 0 && <p className="mt-2 text-sm text-ink-muted">{d.related_hidden === 1
                  ? singular(t("flag.related_hidden", { n: 1 })).replace(" are not shown", " is not shown")
                  : t("flag.related_hidden", { n: formatCount(d.related_hidden) })}</p>}
          </section>

          <section aria-labelledby="history-heading" className="mb-8">
            <SectionHeader id="history-heading" title={t("section.history")} />
            <ol className="border-l-2 border-rule-margin pl-4 text-sm">
              <li className="flex flex-wrap gap-x-6">
                <span className="num text-ink-muted">{formatDateTime(d.created_at)}</span>
                <span>{t("case.history.opened")}</span>
              </li>
            </ol>
          </section>
          <ReadLoggedNote />
        </>
      )}
    </>
  );
}
