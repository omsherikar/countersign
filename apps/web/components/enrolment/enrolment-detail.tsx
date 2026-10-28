"use client";

import * as React from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { CheckBadge } from "@/components/brand/CheckBadge";
import { ConsentBadge } from "@/components/brand/ConsentBadge";
import { EmptyState } from "@/components/brand/EmptyState";
import { EvidenceCard } from "@/components/brand/EvidenceCard";
import { FlagStatusBadge } from "@/components/brand/FlagStatusBadge";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { SeverityBadge } from "@/components/brand/SeverityBadge";
import { ApiError } from "@/lib/api";
import { ordered, statusWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import { formatDate, formatDateTime } from "@/lib/format";
import { useEnrolment, useRecheckEnrolment } from "@/lib/queries";
import type { Check, EnrolmentDetail as Detail, EnrolmentRecheck, FlagType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, SlowHint, errorMessage } from "@/components/common/query-state";
import { Crumbs, SectionHeader, type Crumb } from "@/components/common/page-header";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { CountersignStrip } from "@/components/countersign/countersign-strip";
import { useMe } from "@/components/providers/root-provider";
import { NoticeBlock } from "@/components/enrolment/notice-block";
import { ProofsBlock } from "@/components/enrolment/proofs-block";

export type EnrolmentVariant = "aicte" | "ro" | "college" | "university";

const BASE: Record<EnrolmentVariant, string> = { aicte: "/aicte", ro: "/ro", college: "/college", university: "/university" };

function crumbsFor(variant: EnrolmentVariant, d: Detail | undefined): Crumb[] {
  const name = d?.student.name ?? "…";
  if (variant === "college") return [{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.enrolments"), href: "/college/enrolments" }, { label: name }];
  const base = BASE[variant];
  const root = variant === "university" ? t("nav.affiliated") : t("nav.overview");
  const inst = d ? { label: d.institution.name, href: `${base}/institutions/${d.institution.id}` } : { label: "…" };
  if (variant === "university") return [{ label: root, href: base }, inst, { label: name }];
  return [{ label: root, href: base }, inst, { label: t("nav.enrolments"), href: d ? `${base}/institutions/${d.institution.id}#enrolments` : undefined }, { label: name }];
}

function flagHref(variant: EnrolmentVariant, id: string): string | null {
  if (variant === "university") return null;
  return variant === "college" ? `/college/flags/${id}` : `${BASE[variant]}/cases/${id}`;
}

/** A label and its value; the value column is left-aligned prose, not a number. */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-ink">{children}</dd>
    </>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="min-w-0">
      <h2 className="mb-2 border-b border-rule-strong pb-1 font-sans text-md font-semibold">{title}</h2>
      <dl className="grid grid-cols-[minmax(7.5rem,auto)_1fr] gap-x-4 gap-y-1.5 text-sm">{children}</dl>
    </section>
  );
}

/** "Recheck pending checks" and its result, read out in a live region (A2.12). */
function Recheck({ id, show }: { id: string; show: boolean }) {
  const recheck = useRecheckEnrolment(id);
  const [result, setResult] = React.useState<EnrolmentRecheck | null>(null);
  const { user } = useMe();
  const lines = result
    ? result.rechecked === 0
      ? [t("recheck.none")]
      : result.results.map((r) =>
          r.after === "PENDING"
            ? t("recheck.still_pending", { check: tk(`check.${r.type}`) })
            : t("recheck.result_line", { check: tk(`check.${r.type}`), before_word: tk(`check.status.${r.before}`), after_word: tk(`check.status.${r.after}`) }),
        )
    : [];
  if (result && result.flags_raised > 0) lines.push(t("recheck.flags_raised", { n: result.flags_raised }));
  return (
    <div className="flex flex-col items-start gap-2">
      {(show || result) && (
        <Button
          variant="outline"
          size="sm"
          title={t("recheck.enrolment_tip")}
          disabled={recheck.isPending || (!show && Boolean(result))}
          onClick={() => recheck.mutate(undefined, { onSuccess: setResult })}
        >
          <RefreshCw className={cn("size-3.5", recheck.isPending && "animate-spin")} aria-hidden="true" />
          {recheck.isPending ? t("recheck.running") : t("recheck.enrolment")}
        </Button>
      )}
      <div aria-live="polite" className="text-sm">
        {lines.length > 0 && (
          <div className="border-l-2 border-rule-margin bg-paper-raised px-3 py-2">
            <p className="font-medium">{t("recheck.result_heading")}</p>
            <ul className="mt-0.5 text-ink-muted">
              {lines.map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        )}
        {recheck.isError && (
          <p className="text-check-fail-ink">
            {recheck.error instanceof ApiError && recheck.error.code === "RATE_LIMITED"
              ? t("err.RATE_LIMITED", { seconds: recheck.error.retryAfter ?? 60 })
              : errorMessage(recheck.error, user?.role)}
          </p>
        )}
      </div>
    </div>
  );
}

/** "28 Oct 2026" over "18:08 IST": two short lines keep the column narrow without breaking the date. */
function CheckedAt({ value }: { value: string }) {
  const [day, time] = formatDateTime(value).split(", ");
  return (
    <>
      <span className="block whitespace-nowrap">{day}</span>
      {time && <span className="block whitespace-nowrap">{time}</span>}
    </>
  );
}

/**
 * Only the result badge keeps to one line; source, time and detail wrap, so
 * the table fits its column on desktop and the detail sentence is never cut.
 * On phones it scrolls inside its own box.
 */
function ChecksTable({ checks }: { checks: Check[] }) {
  if (checks.length === 0) return <EmptyState title={t("empty.checks")} />;
  return (
    <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
      <table className="ledger-table">
        <caption className="sr-only">{t("enrolment.section.checks")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("col.check")}</th>
            <th scope="col">{t("col.result")}</th>
            <th scope="col">{t("col.source")}</th>
            <th scope="col">{t("col.checked_at")}</th>
            <th scope="col">{t("col.detail")}</th>
          </tr>
        </thead>
        <tbody>
          {ordered(checks).map((c) => (
            <tr key={c.type}>
              <td className="font-medium">{tk(`check.${c.type}`)}</td>
              <td>
                <CheckBadge status={c.status} word={statusWord(c)} />
              </td>
              <td className="wrap leading-snug text-ink-muted">{tk(`source.${c.source}`)}</td>
              <td className="wrap py-1.5 text-xs leading-snug text-ink-muted">{c.checked_at ? <CheckedAt value={c.checked_at} /> : t("check.never")}</td>
              <td className="wrap !h-auto min-w-[12rem] py-2 leading-snug [overflow-wrap:anywhere]">
                {c.detail.summary}
                {c.attempts > 0 && <span className="mt-0.5 block text-xs text-ink-muted">{t("check.attempts", { n: c.attempts })}</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HeaderSkeleton() {
  return (
    <div className="mb-8 flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-9 w-80 max-w-full" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <Skeleton className="mt-3 h-10 w-56" />
    </div>
  );
}

/**
 * Everything Countersign holds about one enrolment and which source agreed
 * (page spec W2-5). One component behind four thin routes. The checks are
 * the page's one bold element: the strip leads, the table explains it.
 */
export function EnrolmentDetail({ id, variant }: { id: string; variant: EnrolmentVariant }) {
  const q = useEnrolment(id);
  const d = q.data;
  const officer = variant === "aicte" || variant === "ro";
  const canRecheck = variant !== "university";

  if (q.isError && !d) {
    return (
      <>
        <Crumbs items={crumbsFor(variant, undefined)} />
        <h1 className="sr-only">{t("enrolment.crumb")}</h1>
        <ErrorBlock error={q.error} entity="enrolment" backHref={BASE[variant]} onRetry={() => q.refetch()} className="mt-4" />
      </>
    );
  }

  const pendingOther = Boolean(d?.checks.some((c) => c.status === "PENDING" && c.type !== "STUDENT"));
  const seatCheck = d?.checks.find((c) => c.type === "SEAT");
  const seatFlagType = seatCheck?.detail.flag_type as FlagType | undefined;
  const seatFlag = seatFlagType ? d?.flags.find((f) => f.type === seatFlagType) : undefined;

  return (
    <>
      <Crumbs items={crumbsFor(variant, d)} />
      {!d ? (
        <>
          <HeaderSkeleton />
          <SlowHint />
        </>
      ) : (
        <>
          <header className="mb-8 flex flex-wrap items-start justify-between gap-x-10 gap-y-5">
            <div className="min-w-0">
              <h1 className="text-2xl md:text-3xl">{d.student.name}</h1>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <MaskedApaar apaarMasked={d.student.apaar_masked} provisionalId={d.student.provisional_id} className="text-sm" />
                <ConsentBadge status={d.student.consent_status} />
              </p>
              <p className="mt-1.5 text-sm text-ink-muted">
                {d.programme.name} (<span className="code text-ink">{d.programme.code}</span>),{" "}
                {officer || variant === "university" ? (
                  <Link href={`${BASE[variant]}/institutions/${d.institution.id}`}>{d.institution.name}</Link>
                ) : (
                  d.institution.name
                )}
              </p>
            </div>
            <div className="flex flex-col gap-3 border-l-2 border-rule-margin pl-4">
              <span className="text-xs font-medium text-ink-muted">{t("enrolment.score_label")}</span>
              <CountersignStrip countersign={d.countersign} checks={d.checks} size="lg" />
              {canRecheck && <Recheck id={d.id} show={pendingOther} />}
            </div>
          </header>

          <div className="grid grid-cols-1 gap-x-10 gap-y-10 lg:grid-cols-12">
            <div className="flex min-w-0 flex-col gap-10 lg:col-span-8">
              <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
                <Block title={t("enrolment.section.student")}>
                  <Field label={t("enrolment.field.dob")}>{formatDate(d.student.dob)}</Field>
                  <Field label={t("enrolment.field.gender")}>{tk(`gender.${d.student.gender}`)}</Field>
                  {variant !== "university" && d.student.mobile_masked && (
                    <Field label={t("enrolment.field.mobile")}>
                      <span className="code">{d.student.mobile_masked}</span>
                    </Field>
                  )}
                  <Field label={t("enrolment.field.nationality")}>{d.student.nationality}</Field>
                </Block>
                <Block title={t("enrolment.section.enrolment")}>
                  <Field label={t("enrolment.field.intake")}>{t("enrolment.intake_value", { cohort_year: d.cohort_year })}</Field>
                  <Field label={t("enrolment.field.year")}>{d.year_of_study}</Field>
                  <Field label={t("enrolment.field.route")}>
                    {tk(`route.${d.admission_route}`)}
                    {d.counselling_ref && (
                      <>
                        , <span className="code text-xs">{d.counselling_ref}</span>
                      </>
                    )}
                  </Field>
                  <Field label={t("enrolment.field.category")}>{tk(`category.${d.category}`)}</Field>
                  <Field label={t("enrolment.field.status")}>
                    {t("enrolment.status_value", { status_word: tk(`enrol_status.${d.status}`), status_date: formatDate(d.status_date) })}
                  </Field>
                  <Field label={t("enrolment.field.admitted_on")}>{formatDate(d.admission_date)}</Field>
                  <Field label={t("enrolment.field.mode")}>{tk(`mode.${d.programme.mode}`)}</Field>
                  <Field label={t("enrolment.field.uploaded")}>{formatDateTime(d.uploaded_at)}</Field>
                  <Field label={t("enrolment.field.source_row")}>
                    {d.upload ? t("enrolment.source_row", { row_no: d.upload.row_no ?? "", filename: d.upload.filename }) : t("enrolment.source_row_none")}
                  </Field>
                </Block>
              </div>

              <section aria-labelledby="seat-heading">
                <SectionHeader id="seat-heading" title={t("enrolment.section.seat")} />
                {d.seat ? (
                  <p className="text-sm">
                    {t("enrolment.seat_value", {
                      seat_code: d.seat.seat_code,
                      seat_type_word: tk(`seat_type.${d.seat.seat_type}`),
                      academic_year: d.seat.academic_year,
                      assigned_date: formatDate(d.seat.assigned_at),
                    })}
                  </p>
                ) : (
                  <p className="text-sm">
                    {t("enrolment.unseated")}{" "}
                    {seatFlagType &&
                      (seatFlag && flagHref(variant, seatFlag.id) ? (
                        <Link href={flagHref(variant, seatFlag.id)!}>{t("enrolment.unseated_flag", { flag_name: tk(`flag.${seatFlagType}.name`) })}</Link>
                      ) : (
                        t("enrolment.unseated_flag", { flag_name: tk(`flag.${seatFlagType}.name`) })
                      ))}
                  </p>
                )}
              </section>

              <section aria-labelledby="checks-heading">
                <SectionHeader id="checks-heading" title={t("enrolment.section.checks")} />
                <ChecksTable checks={d.checks} />
              </section>

              {variant !== "university" && <NoticeBlock d={d} officer={officer} />}
              {variant !== "university" && <ProofsBlock d={d} />}
            </div>

            <aside aria-labelledby="flags-heading" className="min-w-0 lg:col-span-4">
              <SectionHeader id="flags-heading" title={t("enrolment.section.flags")} />
              {d.flags.length === 0 ? (
                <div className="border-l-2 border-rule-margin bg-paper-raised">
                  <EmptyState title={t("empty.flags_enrolment")} />
                </div>
              ) : (
                <ul className="flex flex-col gap-3">
                  {d.flags.map((f) => {
                    const href = flagHref(variant, f.id);
                    const card = (
                      <EvidenceCard
                        type={f.type}
                        severity={f.severity}
                        evidence={{ summary: f.summary }}
                        badges={
                          <>
                            <SeverityBadge severity={f.severity} />
                            <FlagStatusBadge status={f.status} />
                          </>
                        }
                        actions={<span className="text-xs text-ink-muted">{`${t("col.opened")} ${formatDate(f.created_at)}`}</span>}
                      />
                    );
                    return (
                      <li key={f.id}>
                        {href ? (
                          <Link href={href} className="block rounded-md text-ink no-underline hover:[&_h3]:underline">
                            {card}
                          </Link>
                        ) : (
                          card
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </aside>
          </div>
          <p className="mt-8">
            <ReadLoggedNote />
          </p>
        </>
      )}
    </>
  );
}
