"use client";

import * as React from "react";
import Link from "next/link";
import { CircleSlash, ListCollapse, ListTree, RefreshCw } from "lucide-react";
import { ConsentBadge } from "@/components/brand/ConsentBadge";
import { EmptyState } from "@/components/brand/EmptyState";
import { FlagStatusBadge } from "@/components/brand/FlagStatusBadge";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { SeverityBadge } from "@/components/brand/SeverityBadge";
import { ApiError } from "@/lib/api";
import { awaitsSource, stateWord, statusWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import { formatCardDate, formatDate, formatDateTime } from "@/lib/format";
import { useEnrolment, useRecheckEnrolment } from "@/lib/queries";
import type { EnrolmentDetail as Detail, EnrolmentRecheck, Eligibility, FlagType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, SlowHint, errorMessage } from "@/components/common/query-state";
import { Crumbs, SectionHeader, type Crumb } from "@/components/common/page-header";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { useMe } from "@/components/providers/root-provider";
import { NoticeBlock } from "@/components/enrolment/notice-block";
import { AttestationsBlock } from "@/components/enrolment/attestations-block";
import { RecordCard, RecordCardSkeleton, programmeShort, recordHeader, type CardAudience } from "@/components/records/record-card";
import { RecordStatusBadge } from "@/components/records/record-status-badge";
import { HistoryBlock } from "@/components/records/history-block";

export type EnrolmentVariant = "aicte" | "ro" | "college" | "university";

const BASE: Record<EnrolmentVariant, string> = { aicte: "/aicte", ro: "/ro", college: "/college", university: "/university" };

function crumbsFor(variant: EnrolmentVariant, d: Detail | undefined): Crumb[] {
  const name = d?.student.name ?? "…";
  if (variant === "college") return [{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.enrolments"), href: "/college/enrolments" }, { label: name }];
  const base = BASE[variant];
  const root = variant === "university" ? t("nav.affiliated") : t("nav.overview");
  const inst = d ? { label: d.institution.name, href: `${base}/institutions/${d.institution.id}` } : { label: "…" };
  if (variant === "university") return [{ label: root, href: base }, inst, { label: name }];
  return [{ label: root, href: base }, inst, { label: t("nav.enrolments"), href: d ? `${base}/institutions/${d.institution.id}?tab=enrolments` : undefined }, { label: name }];
}

/** Case detail for officers and the registrar; the university reads case names without links. */
function caseHref(variant: EnrolmentVariant, id: string): string | null {
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

/** The eligibility the college reported (A4.16): TFW income certificate, NRI sponsored, CIWG, or none. */
function eligibilityWords(e: Eligibility): string {
  const words = (["tfw_income_certified", "nri_sponsored", "ciwg"] as const)
    .filter((k) => e[k] !== null)
    .map((k) => (e[k] ? tk(`field.${k}`) : `${tk(`field.${k}`)}: no`));
  return words.length ? words.join(", ") : t("app.none");
}

/** "Recheck evidence" and its result, read out in a live region (A4.6, copy deck §17). */
function Recheck({ id, show }: { id: string; show: boolean }) {
  const recheck = useRecheckEnrolment(id);
  const [result, setResult] = React.useState<EnrolmentRecheck | null>(null);
  const { user } = useMe();
  const lines = result
    ? result.rechecked === 0
      ? [t("recheck.none")]
      : result.results.map((r) =>
          r.before === r.after
            ? t("recheck.no_change", { check: tk(`check.${r.type}`), state_word: stateWord(r.after) })
            : t("recheck.result_line", { check: tk(`check.${r.type}`), before_word: stateWord(r.before), after_word: stateWord(r.after) }),
        )
    : [];
  if (result && result.flags_raised > 0) lines.push(t("recheck.flags_raised", { n: result.flags_raised }));
  if (result?.record_status) lines.push(t("recheck.status_line", { status_word: statusWord(result.record_status) }));
  return (
    <div className="flex flex-col items-start gap-2">
      {(show || result) && (
        <Button
          variant="outline"
          className="h-11 w-full sm:h-9 sm:w-auto"
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

function HeaderSkeleton() {
  return (
    <div className="mb-6 flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-9 w-80 max-w-full" />
      <Skeleton className="h-10 w-56 rounded-chip" />
    </div>
  );
}

/** Cases naming the record: severity, name, status word, the summary as sent, opened date (W4-1, item 5). */
function CasesAboutRecord({ d, variant }: { d: Detail; variant: EnrolmentVariant }) {
  const ids = React.useId();
  return (
    <section aria-labelledby={`${ids}-heading`}>
      <SectionHeader id={`${ids}-heading`} title={t("enrolment.section.flags")} />
      {d.flags.length === 0 ? (
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          <EmptyState title={t("empty.flags_enrolment")} />
        </div>
      ) : (
        <ul className="flex flex-col border-l-2 border-rule-margin bg-paper-raised">
          {d.flags.map((f) => {
            const href = caseHref(variant, f.id);
            const name = tk(`flag.${f.type}.name`);
            return (
              <li key={f.id} className="flex flex-col gap-1 border-b border-rule px-4 py-3 last:border-b-0">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={f.severity} />
                  <span className="font-medium">{href ? <Link href={href}>{name}</Link> : name}</span>
                  <FlagStatusBadge status={f.status} />
                  <span className="ml-auto text-xs text-ink-muted">{`${t("col.opened")} ${formatDate(f.created_at)}`}</span>
                </div>
                <p className="text-sm text-ink-muted [overflow-wrap:anywhere]">{f.summary}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/**
 * The record card page (page spec W4-1): the student's name with the
 * record's status at its largest, the deck's card, then the record's
 * details, cases, notice, attestations and history. One component behind
 * four thin routes; what each role sees follows the spec's role differences.
 */
export function EnrolmentDetail({ id, variant }: { id: string; variant: EnrolmentVariant }) {
  const q = useEnrolment(id);
  const d = q.data;
  const officer = variant === "aicte" || variant === "ro";
  const audience: CardAudience = officer ? "officer" : variant === "college" ? "registrar" : "university";
  const [details, setDetails] = React.useState(false);

  if (q.isError && !d) {
    return (
      <>
        <Crumbs items={crumbsFor(variant, undefined)} />
        <h1 className="sr-only">{t("enrolment.crumb")}</h1>
        <ErrorBlock error={q.error} entity="enrolment" backHref={BASE[variant]} onRetry={() => q.refetch()} className="mt-4" />
      </>
    );
  }

  const active = d?.status === "ACTIVE";
  const pendingOther = Boolean(active && d?.checks.some((c) => awaitsSource(c) && c.type !== "STUDENT"));
  const seatRow = d?.checks.find((c) => c.type === "SEAT");
  const seatCaseType = seatRow?.detail.flag_type as FlagType | undefined;
  const seatCase = seatCaseType ? d?.flags.find((f) => f.type === seatCaseType) : undefined;
  const withdrawnByDecision = d && d.status === "WITHDRAWN" && d.next_step;

  return (
    <>
      <Crumbs items={crumbsFor(variant, d)} />
      {!d ? (
        <>
          <HeaderSkeleton />
          <RecordCardSkeleton />
          <SlowHint />
        </>
      ) : (
        <>
          <header className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between md:gap-10">
            <div className="min-w-0">
              <h1 className="text-2xl md:text-3xl">{d.student.name}</h1>
              <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <MaskedApaar apaarMasked={d.student.apaar_masked} provisionalId={d.student.provisional_id} className="text-sm" />
                <ConsentBadge status={d.student.consent_status} />
              </p>
            </div>
            {d.record_status && (
              <div className="flex flex-col gap-1 max-md:w-full md:items-end">
                <RecordStatusBadge status={d.record_status} size="lg" priority className="max-md:w-full max-md:justify-center" />
                {d.record_status_at && <span className="text-xs text-ink-muted md:text-right">{t("record.status_since", { date: formatCardDate(d.record_status_at) })}</span>}
              </div>
            )}
          </header>

          {!active && (
            <p role="note" className="mb-4 flex items-start gap-2 border-l-2 border-check-na bg-check-na-soft px-4 py-3 text-sm text-ink">
              <CircleSlash className="mt-0.5 size-4 shrink-0 text-check-na-ink" aria-hidden="true" />
              {withdrawnByDecision
                ? t("record.withdrawn_banner", { date: formatCardDate(d.status_date) })
                : t("record.withdrawn_upload_banner", { status_word: tk(`enrol_status.${d.status}`), date: formatCardDate(d.status_date) })}
            </p>
          )}

          <RecordCard
            className="max-w-5xl"
            header={recordHeader({
              programmeName: d.programme.name,
              programmeCode: d.programme.code,
              cohortYear: d.cohort_year,
              institutionName: d.institution.name,
              apaarMasked: d.student.apaar_masked,
              provisionalId: d.student.provisional_id,
            })}
            programmeShort={programmeShort(d.programme.name, d.programme.code)}
            institutionName={d.institution.name}
            rows={d.checks}
            status={d.record_status}
            statusReason={d.status_reason}
            nextStep={d.next_step}
            audience={audience}
            showDetails={details}
          />

          <div className="mt-3 mb-10 flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <Button variant="ghost" className="h-11 justify-start px-2 sm:h-9" aria-pressed={details} onClick={() => setDetails((v) => !v)}>
              {details ? <ListCollapse className="size-4" aria-hidden="true" /> : <ListTree className="size-4" aria-hidden="true" />}
              {details ? t("record.details_hide") : t("record.details_show")}
            </Button>
            {variant !== "university" && active && <Recheck id={d.id} show={pendingOther} />}
          </div>

          <div className="flex max-w-5xl min-w-0 flex-col gap-10">
            <div className="contents">
              <CasesAboutRecord d={d} variant={variant} />

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
                  <Field label={t("enrolment.field.programme")}>
                    {d.programme.name} (<span className="code">{d.programme.code}</span>)
                  </Field>
                  <Field label={t("enrolment.field.institution")}>
                    {variant === "college" ? d.institution.name : <Link href={`${BASE[variant]}/institutions/${d.institution.id}`}>{d.institution.name}</Link>}
                  </Field>
                  <Field label={t("enrolment.field.intake")}>
                    {d.approval ? t("enrolment.intake_value", { version: d.approval.version, cohort_year: d.approval.academic_year }) : d.cohort_year}
                  </Field>
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
                  <Field label={t("enrolment.field.eligibility")}>{eligibilityWords(d.eligibility)}</Field>
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
                      version: d.approval?.version ?? 1,
                      cohort_year: d.seat.academic_year,
                      assigned_date: formatDate(d.seat.assigned_at),
                    })}
                  </p>
                ) : (
                  <p className="text-sm">
                    {t("enrolment.unseated")}{" "}
                    {seatCaseType &&
                      (seatCase && caseHref(variant, seatCase.id) ? (
                        <Link href={caseHref(variant, seatCase.id)!}>{t("enrolment.unseated_flag", { flag_name: tk(`flag.${seatCaseType}.name`) })}</Link>
                      ) : (
                        t("enrolment.unseated_flag", { flag_name: tk(`flag.${seatCaseType}.name`) })
                      ))}
                  </p>
                )}
              </section>

              {variant !== "university" && <NoticeBlock d={d} officer={officer} />}
              {officer && <AttestationsBlock d={d} />}
              <HistoryBlock enrolmentId={d.id} audience={audience} caseHref={(cid) => caseHref(variant, cid)} />
            </div>
          </div>
          <p className="mt-8">
            <ReadLoggedNote />
          </p>
        </>
      )}
    </>
  );
}
