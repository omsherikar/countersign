"use client";

import * as React from "react";
import { Bell, Link2, Wallet } from "lucide-react";
import { CHECK_ORDER } from "@/components/brand/CountersignScore";
import { ConsentBadge } from "@/components/brand/ConsentBadge";
import { EmptyState } from "@/components/brand/EmptyState";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useStudentMe } from "@/lib/queries";
import type { StudentEnrolment } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { CountersignStrip } from "@/components/common/ledger-bits";

function EnrolmentCard({ e }: { e: StudentEnrolment }) {
  const headingId = `enrolment-${e.id}`;
  return (
    <section aria-labelledby={headingId} className="border-l-2 border-rule-margin bg-paper-raised px-5 py-5 shadow-hairline">
      <h2 id={headingId} className="font-display text-xl leading-snug font-semibold">
        {t("student.card_lead", { institution_name: e.institution_name, programme_name: e.programme_name })}
      </h2>
      <p className="mt-2 text-md text-ink-muted">
        {t("app.student.year_line", { academic_year: e.academic_year, year_of_study: e.year_of_study })}, {tk(`enrol_status.${e.status}`)}
      </p>
      <div className="mt-5 flex flex-col gap-2 border-t border-rule pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">{t("col.countersign")}</span>
          <CountersignStrip countersign={e.countersign} size="md" />
        </div>
        <p className="text-sm text-ink-muted">{CHECK_ORDER.map((c) => tk(`check.${c}`)).join(", ")}</p>
      </div>
    </section>
  );
}

function Placeholder({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <section className="flex items-start gap-3 border-b border-rule py-4">
      <span className="mt-0.5 text-ink-faint" aria-hidden="true">
        {icon}
      </span>
      <div>
        <h2 className="font-sans text-md font-semibold">{title}</h2>
        <p className="mt-0.5 text-md text-ink-muted">{text}</p>
      </div>
    </section>
  );
}

/** /student: exactly what is held about the student, masked, and that nothing is decided without them. */
export function StudentHome() {
  const me = useStudentMe();
  const s = me.data;

  return (
    <div className="text-md">
      <h1 className="mb-6 text-3xl">{t("student.heading")}</h1>

      {me.isError && !s && <ErrorBlock error={me.error} onRetry={() => me.refetch()} />}

      {me.isLoading && (
        <div className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-5 w-80" />
          <Skeleton className="h-5 w-72" />
          <Skeleton className="mt-6 h-44" />
          <SlowHint />
        </div>
      )}

      {s && (
        <>
          <section aria-label={t("app.student.held")} className="mb-8">
            <p className="font-display text-2xl font-semibold">{s.name}</p>
            <dl className="mt-3 grid grid-cols-[max-content_1fr] items-center gap-x-4 gap-y-2">
              <dt className="text-ink-muted">{s.apaar_masked ? "APAAR" : t("provisional.label")}</dt>
              <dd className="flex flex-wrap items-center gap-2">
                <MaskedApaar apaarMasked={s.apaar_masked} provisionalId={s.provisional_id} className="text-md" />
                <ConsentBadge status={s.consent_status} title={tk(`consent.tip_${s.consent_status}`)} />
              </dd>
              <dt className="text-ink-muted">{t("app.student.dob")}</dt>
              <dd>{formatDate(s.dob)}</dd>
              {s.mobile_masked && (
                <>
                  <dt className="text-ink-muted">{t("app.student.mobile")}</dt>
                  <dd className="code text-md">{s.mobile_masked}</dd>
                </>
              )}
              {s.email && (
                <>
                  <dt className="text-ink-muted">{t("app.student.email")}</dt>
                  <dd className="break-all">{s.email}</dd>
                </>
              )}
            </dl>
          </section>

          <div className="mb-8 flex flex-col gap-4">
            {s.enrolments.length === 0 ? (
              <EmptyState title={t("empty.enrolments_student")} />
            ) : (
              s.enrolments.map((e) => <EnrolmentCard key={e.id} e={e} />)
            )}
          </div>

          <div className="mb-8 border-t border-rule-strong">
            <Placeholder icon={<Bell className="size-5" />} title={t("nav.notices")} text={t("empty.notices_student")} />
            <Placeholder icon={<Wallet className="size-5" />} title={t("nav.wallet")} text={t("empty.credentials_student")} />
            <Placeholder
              icon={<Link2 className="size-5" />}
              title={t("app.student.consent")}
              text={t("app.student.consent_change", { tip: tk(`consent.tip_${s.consent_status}`) })}
            />
          </div>

          <p className="text-sm text-ink-muted">
            {t("privacy.student_line")}{" "}
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" aria-disabled="true" className="cursor-not-allowed text-ink-faint underline underline-offset-2">
                  {t("privacy.how_link")}
                </button>
              </TooltipTrigger>
              <TooltipContent>{t("shell.coming", { n: 3 })}</TooltipContent>
            </Tooltip>
          </p>
        </>
      )}
    </div>
  );
}
