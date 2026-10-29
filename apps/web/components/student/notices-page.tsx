"use client";

import * as React from "react";
import { Check, Clock, Minus, X } from "lucide-react";
import { t } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useStudentMe } from "@/lib/queries";
import { useConsents } from "@/lib/queries-student";
import { EmptyState } from "@/components/brand/EmptyState";
import { Crumbs } from "@/components/common/page-header";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusWord, useNow } from "@/components/student/bits";
import { DecisionLine } from "@/components/student/decision-line";
import { channelWords, groupNotices, type NoticeGroup } from "@/components/student/notice-groups";
import type { StudentEnrolment } from "@/lib/types";

/** "Your reply" as a word with its icon; a No is the student's own answer, so it is grey, not red. */
export function ReplyWord({ group }: { group: NoticeGroup }) {
  switch (group.reply) {
    case "YES":
      return (
        <StatusWord tone="ok" icon={Check}>
          {t("notices.reply.YES", { responded_date: formatDate(group.respondedAt) })}
        </StatusWord>
      );
    case "NO":
      return (
        <StatusWord tone="neutral" icon={X}>
          {t("notices.reply.NO", { responded_date: formatDate(group.respondedAt) })}
        </StatusWord>
      );
    case "EXPIRED":
      return (
        <StatusWord tone="neutral" icon={Minus}>
          {t("notices.reply.EXPIRED")}
        </StatusWord>
      );
    default:
      return (
        <StatusWord tone="caution" icon={Clock}>
          {t("notices.reply.NONE")}
        </StatusWord>
      );
  }
}

/** The lines under a reply: the change date, the case line under a No, the officer's decision, or how to reply. */
function ReplyNotes({ group, enrolment, compact = false }: { group: NoticeGroup; enrolment?: StudentEnrolment; compact?: boolean }) {
  const size = compact ? "text-sm" : "text-md";
  return (
    <>
      {enrolment?.decision && <DecisionLine enrolment={enrolment} />}
      {group.changedAt && <p className="mt-1 text-sm text-ink-muted">{t("notices.changed", { changed_date: formatDate(group.changedAt) })}</p>}
      {group.reply === "NO" && <p className={cn("mt-1.5", size)}>{t("notices.denied_line")}</p>}
      {group.live && <p className={cn("mt-1.5 text-ink-muted", size)}>{t("notices.reply_hint", { expires_date: formatDate(group.expiresAt) })}</p>}
    </>
  );
}

/**
 * W3-2 Notices: every notice sent to the student, one block per claim,
 * newest first. The list cannot open a notice: only a hash of each link is
 * stored, so an unanswered notice says where the link was sent instead.
 */
export function NoticesPage() {
  const me = useStudentMe();
  const consents = useConsents();
  const now = useNow();
  const s = me.data;
  const groups = React.useMemo(() => (s ? groupNotices(s.notices, s.enrolments, now) : []), [s, now]);
  const noticeConsent = consents.data?.current.find((c) => c.purpose === "NOTICE");

  return (
    <div className="text-md">
      <Crumbs items={[{ label: t("nav.my_enrolment"), href: "/student" }, { label: t("notices.heading") }]} />
      <h1 className="text-3xl">{t("notices.heading")}</h1>
      <p className="mt-2 text-ink-muted">{t("notices.lead")}</p>

      {noticeConsent?.status === "WITHDRAWN" && noticeConsent.since && (
        <p className="mt-5 border-l-2 border-check-pending bg-check-pending-soft px-4 py-3 text-check-pending-ink">
          {t("notices.consent_off", { withdrawn_date: formatDate(noticeConsent.since) })}
        </p>
      )}

      <div className="mt-6">
        {me.isLoading && (
          <div className="flex flex-col gap-3" aria-hidden="true">
            {[0, 1].map((i) => (
              <div key={i} className="border-b border-rule pb-4">
                <Skeleton className="h-4 w-56" />
                <Skeleton className="mt-2 h-5 w-64" />
                <Skeleton className="mt-2 h-4 w-40" />
                <Skeleton className="mt-3 h-5 w-36" />
              </div>
            ))}
            <SlowHint />
          </div>
        )}
        {me.isError && !s && <ErrorBlock error={me.error} onRetry={() => me.refetch()} />}
        {s && groups.length === 0 && <EmptyState className="border-y border-rule" title={t("empty.notices_student")} />}
        {s && groups.length > 0 && (
          <>
            <ul className="border-t border-rule-strong md:hidden">
              {groups.map((g) => (
                <li key={g.enrolmentId} className="border-b border-rule py-4">
                  <p className="text-sm text-ink-muted">
                    {formatDate(g.sentAt)} · {g.institutionName}
                  </p>
                  <p className="mt-1 font-semibold">{t("notices.claim", { programme_short: g.programmeShort, academic_year: g.academicYear })}</p>
                  <p className="text-ink-muted">{t("notices.channels", { channel_words: channelWords(g.channels) })}</p>
                  <div className="mt-2">
                    <span className="sr-only">{t("notices.col.reply")}: </span>
                    <ReplyWord group={g} />
                  </div>
                  <ReplyNotes group={g} enrolment={s.enrolments.find((e) => e.id === g.enrolmentId)} />
                </li>
              ))}
            </ul>
            <div className="hidden md:block">
              <table className="ledger-table w-full">
                <thead>
                  <tr>
                    <th scope="col">{t("notices.col.sent")}</th>
                    <th scope="col">{t("notices.col.from")}</th>
                    <th scope="col">{t("notices.col.claim")}</th>
                    <th scope="col">{t("notices.col.reply")}</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((g) => (
                    <tr key={g.enrolmentId} className="[&>td]:!align-top">
                      <td className="!h-auto py-3">{formatDate(g.sentAt)}</td>
                      <td className="wrap !h-auto py-3">{g.institutionName}</td>
                      <td className="wrap !h-auto py-3">
                        {t("notices.claim", { programme_short: g.programmeShort, academic_year: g.academicYear })}
                        <span className="block text-ink-muted">{t("notices.channels", { channel_words: channelWords(g.channels) })}</span>
                      </td>
                      <td className="wrap !h-auto max-w-[22rem] py-3">
                        <ReplyWord group={g} />
                        <ReplyNotes group={g} enrolment={s.enrolments.find((e) => e.id === g.enrolmentId)} compact />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
