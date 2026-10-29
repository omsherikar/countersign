"use client";

import * as React from "react";
import Link from "next/link";
import { Bell, Check, Link2, Minus, Wallet, X } from "lucide-react";
import { ConsentBadge } from "@/components/brand/ConsentBadge";
import { EmptyState } from "@/components/brand/EmptyState";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useStudentMe } from "@/lib/queries";
import type { StudentCredentialBrief, StudentEnrolment } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { RecordStatusBadge } from "@/components/records/record-status-badge";
import { StatusWord, useNow } from "@/components/student/bits";
import { groupNotices, homeLine, type NoticeGroup } from "@/components/student/notice-groups";
import { ReplyWord } from "@/components/student/notices-page";

function EnrolmentCard({ e, group }: { e: StudentEnrolment; group: NoticeGroup | undefined }) {
  const line = homeLine(group, formatDate);
  const headingId = `enrolment-${e.id}`;
  return (
    <section aria-labelledby={headingId} className="border-l-2 border-rule-margin bg-paper-raised px-5 py-5 shadow-hairline">
      <h2 id={headingId} className="font-display text-xl leading-snug font-semibold">
        {t("student.card_lead", { institution_name: e.institution_name, programme_name: e.programme_name })}
      </h2>
      <p className="mt-2 text-md text-ink-muted">
        {t("notice.meta", { academic_year: e.academic_year, year_of_study: e.year_of_study })} · {tk(`enrol_status.${e.status}`)}
      </p>
      <div className="mt-5 flex flex-col gap-2 border-t border-rule pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">{t("col.record_status")}</span>
          <RecordStatusBadge status={e.record_status} size="md" tip={null} />
        </div>
        {e.record_status && <p className="max-w-[60ch] text-md text-ink-muted">{tk(`record_status.student.${e.record_status}`)}</p>}
        {line && e.status === "ACTIVE" && <p className="max-w-[60ch] text-md text-ink-muted">{line}</p>}
      </div>
    </section>
  );
}

/** A ruled section under the enrolment cards: its title links to the full page. */
function Section({ icon, title, href, children }: { icon: React.ReactNode; title: string; href?: string; children: React.ReactNode }) {
  return (
    <section className="flex items-start gap-3 border-b border-rule py-4">
      <span className="mt-0.5 text-ink-faint" aria-hidden="true">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="font-sans text-md font-semibold">
          {href ? (
            <Link href={href} className="inline-flex min-h-11 items-center">
              {title}
            </Link>
          ) : (
            title
          )}
        </h2>
        <div className="mt-0.5 text-md text-ink-muted">{children}</div>
      </div>
    </section>
  );
}

function ProofLine({ c }: { c: StudentCredentialBrief }) {
  const word =
    c.status === "ACTIVE" ? (
      <StatusWord tone="ok" icon={Check}>{t("wallet.status.active")}</StatusWord>
    ) : c.status === "REVOKED" ? (
      <StatusWord tone="neutral" icon={X}>{t("wallet.status.revoked")}</StatusWord>
    ) : (
      <StatusWord tone="neutral" icon={Minus}>{t("wallet.status.expired")}</StatusWord>
    );
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="text-ink">{tk(`wallet.kind.${c.kind}`)}</span>
      {word}
      <span>
        {c.institution_name}, {t("wallet.issued_on", { issued_date: formatDate(c.issued_at) })}
      </span>
    </p>
  );
}

/** /student: exactly what is held about the student, masked, and that nothing is decided without them. */
export function StudentHome() {
  const me = useStudentMe();
  const s = me.data;
  const now = useNow();
  const groups = React.useMemo(() => (s ? groupNotices(s.notices, s.enrolments, now) : []), [s, now]);
  const newestProof = s?.credentials.slice().sort((a, b) => b.issued_at.localeCompare(a.issued_at))[0];

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
                <ConsentBadge status={s.consent_status} />
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
              s.enrolments.map((e) => <EnrolmentCard key={e.id} e={e} group={groups.find((g) => g.enrolmentId === e.id)} />)
            )}
          </div>

          <div className="mb-8 border-t border-rule-strong">
            <Section icon={<Bell className="size-5" />} title={t("nav.notices")} href="/student/notices">
              {groups[0] ? (
                <div className="flex flex-col gap-1">
                  <p>
                    {groups[0].institutionName}: {t("notices.claim", { programme_short: groups[0].programmeShort, academic_year: groups[0].academicYear })}
                  </p>
                  <div>
                    <ReplyWord group={groups[0]} />
                  </div>
                </div>
              ) : (
                t("empty.notices_student")
              )}
            </Section>
            <Section icon={<Wallet className="size-5" />} title={t("nav.wallet")} href="/student/wallet">
              {newestProof ? <ProofLine c={newestProof} /> : t("empty.credentials_student")}
            </Section>
            <Section icon={<Link2 className="size-5" />} title={t("app.student.consent")}>
              {t("student.consent_change", { tip: tk(`student.consent_${s.consent_status}`).replace(/\.$/, "") })}
            </Section>
          </div>

          <p className="text-md text-ink-muted">
            {t("privacy.student_line")} <Link href="/student/privacy">{t("privacy.how_link")}</Link>
          </p>
        </>
      )}
    </div>
  );
}
