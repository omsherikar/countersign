"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Clock, Loader2, Mail, Send, ShieldCheck } from "lucide-react";
import { ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { keys } from "@/lib/queries";
import { useResendNotice, useStudentComment } from "@/lib/queries-cases";
import type { EnrolmentDetail, EnrolmentNotice, NoticeChannel, NoticeDelivery } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SectionHeader } from "@/components/common/page-header";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";

const DELIVERY_ICON: Record<NoticeDelivery, typeof Clock> = { QUEUED: Clock, SENT: CircleCheck, FAILED: CircleAlert };
const CHANNEL_ICON: Record<NoticeChannel, typeof Mail> = { EMAIL: Mail, DIGILOCKER: ShieldCheck };
const channelWord = (c: NoticeChannel) => (c === "EMAIL" ? "email" : "DigiLocker");
const isLive = (n: EnrolmentNotice) => n.state === "AWAITING" || n.state === "QUEUED";
const decidedAt = (n: EnrolmentNotice) => n.changed_at ?? n.responded_at ?? "";

/** One line per channel of the newest notice: "Email: Sent, 28 Oct 2026", with the reason when not delivered. */
function ChannelLine({ n }: { n: EnrolmentNotice }) {
  const Icon = DELIVERY_ICON[n.delivery_status];
  const Channel = CHANNEL_ICON[n.channel];
  const line = t("enrolment.notice.channel_line", {
    channel_name: tk(`notice_channel.${n.channel}`),
    delivery_word: tk(`notice_delivery.${n.delivery_status}`),
    sent_date: formatDate(n.sent_at),
  }).replace(/,\s*$/, "");
  return (
    <li className="flex items-start gap-2">
      <Channel className="mt-0.5 size-4 shrink-0 text-ink-muted" aria-hidden="true" />
      <span className="min-w-0">
        {line}
        {n.delivery_status === "FAILED" && n.last_error && <> {t("enrolment.notice.failed_reason", { last_error: n.last_error })}</>}
      </span>
      <Icon
        className={cn("mt-0.5 size-3.5 shrink-0", n.delivery_status === "FAILED" ? "text-check-pending" : "text-ink-muted")}
        aria-hidden="true"
      />
    </li>
  );
}

/**
 * The student notice block on enrolment detail (page spec W3-10): how the
 * newest notice went out on each channel, whether the student replied, and
 * Resend notice when nothing is live. The comment on a No is for officers
 * only and comes from the Student denied flag.
 */
export function NoticeBlock({ d, officer }: { d: EnrolmentDetail; officer: boolean }) {
  const { user } = useMe();
  const qc = useQueryClient();
  const resend = useResendNotice(d.id);
  const [open, setOpen] = React.useState(false);
  const [message, setMessage] = React.useState<{ text: string; error: boolean } | null>(null);
  const [limitHit, setLimitHit] = React.useState(false);
  const opener = React.useRef<HTMLButtonElement>(null);
  const ids = React.useId();

  const notices = d.notices;
  // The newest row of each channel (the list arrives newest first), email before DigiLocker.
  const newest = (["EMAIL", "DIGILOCKER"] as const).map((c) => notices.find((n) => n.channel === c)).filter((n): n is EnrolmentNotice => Boolean(n));
  const no = notices.filter((n) => n.response === "NO").sort((a, b) => decidedAt(a).localeCompare(decidedAt(b)))[0];
  const yes = notices.filter((n) => n.response === "YES").sort((a, b) => decidedAt(a).localeCompare(decidedAt(b)))[0];
  const reply = no ?? yes;
  const live = notices.filter(isLive)[0];
  const expired = notices.filter((n) => n.state === "EXPIRED")[0];
  const deniedFlag = d.flags.find((f) => f.type === "STUDENT_DENIED");
  const comment = useStudentComment(officer && no ? deniedFlag?.id : undefined, t("enrolment.notice.comment"));

  // A resend goes out from a queue; look again once it has had time to be delivered.
  const queued = notices.some((n) => n.delivery_status === "QUEUED");
  React.useEffect(() => {
    if (!queued) return;
    const timer = setTimeout(() => void qc.invalidateQueries({ queryKey: keys.enrolment(d.id) }), 4000);
    return () => clearTimeout(timer);
  }, [queued, qc, d.id]);

  const blocked = d.resend.blocked_by;
  const disabledReason =
    blocked === "LIVE" && live
      ? t("resend.live_tip", { sent_date: formatDate(live.sent_at ?? live.expires_at), expires_date: formatDate(live.expires_at) })
      : blocked === "LIMIT" || limitHit
        ? t("err.RESEND_LIMIT")
        : null;
  const showButton = d.resend.allowed || disabledReason !== null;

  function send() {
    setMessage(null);
    resend.mutate(undefined, {
      onSuccess: (res) => {
        setOpen(false);
        const expires = res.notices[0]?.expires_at;
        setMessage({ text: t("resend.sent", { expires_date: formatDate(expires) }), error: false });
      },
      onError: (err) => {
        setOpen(false);
        if (err instanceof ApiError && err.code === "RESEND_LIMIT") {
          setLimitHit(true);
          setMessage({ text: t("err.RESEND_LIMIT"), error: true });
        } else if (err instanceof ApiError && err.code === "NOTICE_LIVE") {
          setMessage({ text: t("err.NOTICE_LIVE"), error: true });
        } else {
          setMessage({ text: errorMessage(err, user?.role, "enrolment"), error: true });
        }
      },
    });
  }

  const reasonId = `${ids}-reason`;
  const button = showButton && (
    <Button
      ref={opener}
      type="button"
      variant="outline"
      size="sm"
      aria-disabled={disabledReason !== null || resend.isPending ? true : undefined}
      aria-describedby={disabledReason ? reasonId : undefined}
      onClick={() => {
        if (disabledReason !== null || resend.isPending) return;
        setOpen(true);
      }}
      className={cn("h-11 md:h-8", disabledReason !== null && "cursor-not-allowed opacity-60")}
    >
      <Send className="size-3.5" aria-hidden="true" />
      {t("resend.button")}
    </Button>
  );

  return (
    <section aria-labelledby={`${ids}-heading`}>
      <SectionHeader
        id={`${ids}-heading`}
        title={t("enrolment.section.notice")}
        aside={
          button &&
          (disabledReason === null ? (
            <Tooltip>
              <TooltipTrigger asChild>{button}</TooltipTrigger>
              <TooltipContent className="max-w-72">{t("resend.tip")}</TooltipContent>
            </Tooltip>
          ) : (
            button
          ))
        }
      />
      <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm">
        {notices.length === 0 ? (
          <p className="text-ink-muted">{t("enrolment.notice.none")}</p>
        ) : (
          <div className="flex flex-col gap-2">
            <ul className="flex flex-col gap-1">
              {newest.map((n) => (
                <ChannelLine key={n.id} n={n} />
              ))}
            </ul>
            {reply ? (
              <div className="flex flex-col gap-1">
                <p className="font-medium">
                  {t("enrolment.notice.reply", {
                    reply_word: tk(`notice_reply.${reply.response}`),
                    responded_date: formatDate(reply.responded_at),
                    channel_word: channelWord(reply.channel),
                  })}
                </p>
                {reply.changed_at && <p className="text-ink-muted">{t("enrolment.notice.changed", { changed_date: formatDate(reply.changed_at) })}</p>}
                {officer && no && comment.isLoading && <Skeleton className="mt-1 h-8 w-64" />}
                {officer && no && comment.data && (
                  <div className="mt-1 border-l-2 border-rule pl-3">
                    <p className="text-xs font-medium text-ink-muted">{t("enrolment.notice.comment")}</p>
                    <p className="max-w-[68ch] [overflow-wrap:anywhere]">{comment.data}</p>
                  </div>
                )}
              </div>
            ) : live ? (
              <p className="text-ink-muted">{t("enrolment.notice.expires", { expires_date: formatDate(live.expires_at) })}</p>
            ) : expired ? (
              <p className="text-ink-muted">{t("enrolment.notice.expired", { expires_date: formatDate(expired.expires_at) })}</p>
            ) : null}
          </div>
        )}
        {blocked === "CONSENT_WITHDRAWN" && <p className="mt-2 text-ink-muted">{t("enrolment.notice.consent_off_undated")}</p>}
        {disabledReason && (
          <p id={reasonId} className="mt-2 text-xs text-ink-muted">
            {disabledReason}
          </p>
        )}
        <div aria-live="polite">
          {message && <p className={cn("mt-2", message.error ? "text-check-fail-ink" : "font-medium text-ink")}>{message.text}</p>}
        </div>
      </div>

      <Dialog open={open} onOpenChange={(next) => !next && !resend.isPending && setOpen(false)}>
        <DialogContent
          className="max-h-[calc(100dvh-2rem)] gap-5 overflow-y-auto bg-paper-raised sm:max-w-md"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            opener.current?.focus();
          }}
        >
          <div className="flex flex-col gap-2 pr-6">
            <DialogTitle className="font-display text-xl font-semibold">{t("resend.confirm_heading")}</DialogTitle>
            <DialogDescription className="text-sm text-ink">
              {t("resend.confirm", { student_name: d.student.name, academic_year: d.academic_year })}
            </DialogDescription>
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" className="h-11 sm:h-9" onClick={() => setOpen(false)} disabled={resend.isPending}>
              {t("resend.cancel")}
            </Button>
            <Button type="button" className="h-11 sm:h-9" onClick={send} disabled={resend.isPending} aria-busy={resend.isPending}>
              {resend.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {resend.isPending ? t("resend.sending") : t("resend.send")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
