"use client";

import * as React from "react";
import Link from "next/link";
import { Check, RefreshCw, TriangleAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { copy, t, type CopyId, type CopyVars } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useNotice, useRespondNotice } from "@/lib/queries-student";
import type { NoticePublic, NoticeResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/shell/logo";
import { Skeleton } from "@/components/ui/skeleton";
import { SlowHint } from "@/components/common/query-state";
import { Disclosure, SheetDialog, outlineButton, retryDeadline, useSecondsLeft } from "@/components/student/bits";

type Lang = "en" | "hi";
const LANG_KEY = "cs_notice_lang";

/** English or the `.hi` row of the deck; a string without one falls back to English (deck section 8). */
function makeTr(lang: Lang) {
  return (id: CopyId, vars?: CopyVars): string => {
    const hi = `${id}.hi`;
    if (lang === "hi" && hi in copy) return t(hi as CopyId, vars);
    return t(id, vars);
  };
}
type Tr = ReturnType<typeof makeTr>;

const langListeners = new Set<() => void>();
function readLang(): Lang {
  try {
    return sessionStorage.getItem(LANG_KEY) === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}
function subscribeLang(onChange: () => void) {
  langListeners.add(onChange);
  return () => langListeners.delete(onChange);
}

/** The language choice lasts for the visit (W3-1): kept in sessionStorage, English on the server. */
function useLang(): [Lang, (l: Lang) => void] {
  const lang = React.useSyncExternalStore(subscribeLang, readLang, () => "en" as Lang);
  const set = React.useCallback((l: Lang) => {
    try {
      sessionStorage.setItem(LANG_KEY, l);
    } catch {
      // Storage refused: the choice cannot be kept, so the page stays in English.
    }
    langListeners.forEach((fn) => fn());
  }, []);
  return [lang, set];
}

type Done = "YES" | "NO" | "CHANGED" | null;

/**
 * W3-1, the public notice page. The token in the link is the only key; the
 * page shows the claim and the masked id, never a name, date of birth or
 * contact detail, and the student answers Yes or No without signing in.
 */
export function NoticePage({ token }: { token: string }) {
  const [lang, setLang] = useLang();
  const tr = React.useMemo(() => makeTr(lang), [lang]);
  const notice = useNotice(token);
  const respond = useRespondNotice(token);
  const [mode, setMode] = React.useState<"view" | "change">("view");
  const [done, setDone] = React.useState<Done>(null);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [comment, setComment] = React.useState("");
  const [pressed, setPressed] = React.useState<NoticeResponse | null>(null);
  const [lastBody, setLastBody] = React.useState<{ response: NoticeResponse; comment?: string } | null>(null);
  const [conflict, setConflict] = React.useState<"CHANGED_ONCE" | "WINDOW_CLOSED" | null>(null);
  const noButton = React.useRef<HTMLButtonElement>(null);
  const status = React.useRef<HTMLDivElement>(null);

  const data = notice.data;
  const institution = data?.institution_name;
  React.useEffect(() => {
    if (institution) document.title = `${tr("notice.page_title", { institution_name: institution })} | ${t("brand.name")}`;
  }, [institution, tr]);

  const sendError = respond.error instanceof ApiError ? respond.error : respond.error ? new ApiError(0, "INTERNAL", "") : null;
  const loadError = notice.error instanceof ApiError ? notice.error : notice.error ? new ApiError(0, "INTERNAL", "") : null;
  const deadline = retryDeadline(respond.error, respond.submittedAt) ?? retryDeadline(notice.error, notice.errorUpdatedAt);
  const secondsLeft = useSecondsLeft(deadline);
  const limited = secondsLeft !== null && secondsLeft > 0;
  const refetch = notice.refetch;
  const loadLimited = loadError?.code === "RATE_LIMITED";
  React.useEffect(() => {
    // A rate-limited first load tries again by itself once the wait is over.
    if (loadLimited && secondsLeft === 0) refetch();
  }, [loadLimited, secondsLeft, refetch]);

  const send = (body: { response: NoticeResponse; comment?: string }) => {
    if (respond.isPending || limited) return;
    setPressed(body.response);
    setLastBody(body);
    const changing = Boolean(data?.response);
    respond.mutate(body, {
      onSuccess: () => {
        setSheetOpen(false);
        setMode("view");
        setDone(changing ? "CHANGED" : body.response);
        setComment("");
        requestAnimationFrame(() => status.current?.focus());
      },
      onError: (err) => {
        if (err instanceof ApiError && err.code === "NOTICE_ALREADY_CHANGED") {
          setSheetOpen(false);
          setMode("view");
          setConflict(err.details.reason === "WINDOW_CLOSED" ? "WINDOW_CLOSED" : "CHANGED_ONCE");
          refetch();
        }
      },
    });
  };

  const header = (
    <header className="border-b border-rule-strong bg-paper-raised">
      <div className="mx-auto flex h-14 max-w-[480px] items-center justify-between gap-3 px-4">
        <Logo className="h-7" />
        <div role="group" aria-label={tr("notice.lang_label")} className="flex rounded-md border border-line p-0.5">
          {(["en", "hi"] as const).map((l) => (
            <button
              key={l}
              type="button"
              lang={l === "hi" ? "hi" : "en"}
              aria-pressed={lang === l}
              onClick={() => setLang(l)}
              className={cn(
                "inline-flex h-10 min-w-11 items-center justify-center gap-1 rounded-[3px] px-3 text-sm font-medium",
                lang === l ? "bg-ink-blue text-on-ink-blue" : "text-ink-blue hover:bg-flag-open-soft",
              )}
            >
              {lang === l && <Check className="size-3.5" aria-hidden="true" />}
              {t(l === "hi" ? "notice.lang_hi" : "notice.lang_en")}
            </button>
          ))}
        </div>
      </div>
    </header>
  );

  let body: React.ReactNode;
  if (notice.isLoading) {
    body = <NoticeSkeleton />;
  } else if (loadError && !data) {
    body = <LoadFailure error={loadError} tr={tr} secondsLeft={secondsLeft} onRetry={() => refetch()} />;
  } else if (data) {
    body = (
      <>
        {mode === "change" ? (
          <>
            <h1 className="text-2xl">{tr("notice.change_heading")}</h1>
            <p className="mt-2 text-ink-muted">{tr("notice.change_once")}</p>
            <Claim notice={data} tr={tr} className="mt-6" />
            <Choices
              tr={tr}
              current={data.response}
              pending={respond.isPending ? pressed : null}
              disabled={respond.isPending || limited}
              onYes={() => send({ response: "YES" })}
              onNo={() => setSheetOpen(true)}
              noRef={noButton}
            />
            <button type="button" className="mt-4 inline-flex h-11 items-center text-md text-ink-blue underline" onClick={() => setMode("view")}>
              {tr("notice.no_cancel")}
            </button>
          </>
        ) : data.response ? (
          <Answered notice={data} tr={tr} done={done} conflict={conflict} onChange={() => setMode("change")} statusRef={status} />
        ) : (
          <>
            <Claim notice={data} tr={tr} />
            <h2 className="mt-8 font-sans text-lg font-semibold">{tr("notice.question")}</h2>
            <p className="mt-2 text-sm text-ink-muted">{lang === "hi" ? tr("consent.notice", { institution_name: data.institution_name }) : data.consent_text}</p>
            <Choices
              tr={tr}
              current={null}
              pending={respond.isPending ? pressed : null}
              disabled={respond.isPending || limited}
              onYes={() => send({ response: "YES" })}
              onNo={() => setSheetOpen(true)}
              noRef={noButton}
            />
            <p className="mt-4 text-ink-muted">{tr("notice.next_step")}</p>
          </>
        )}

        <SendFailure
          error={sendError}
          tr={tr}
          secondsLeft={secondsLeft}
          busy={respond.isPending}
          onRetry={lastBody ? () => send(lastBody) : undefined}
        />

        <Disclosure className="mt-8 border-t border-rule pt-4" summaryClassName="text-md" summary={tr("notice.what_is_this_link")}>
          <p className="mt-2 text-ink-muted">{tr("notice.what_is_this")}</p>
        </Disclosure>

        <SheetDialog
          open={sheetOpen}
          onOpenChange={(o) => {
            if (!respond.isPending) setSheetOpen(o);
          }}
          lang={lang === "hi" ? "hi" : undefined}
          title={tr("notice.no")}
          description={tr("notice.no_confirm", { institution_name: data.institution_name })}
          closeLabel={tr("notice.no_cancel")}
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            document.getElementById("notice-comment")?.focus();
          }}
          footer={
            <div className="flex flex-col gap-3 md:flex-row-reverse">
              <button
                type="button"
                className={cn(outlineButton, "bg-ink-blue text-on-ink-blue hover:bg-ink-blue-hover md:w-auto")}
                disabled={respond.isPending || limited}
                onClick={() => send({ response: "NO", comment: comment.trim() || undefined })}
              >
                {respond.isPending ? tr("notice.sending") : tr(data.response ? "notice.change_submit" : "notice.no_submit")}
              </button>
              <button
                type="button"
                className={cn(outlineButton, "md:w-auto")}
                disabled={respond.isPending}
                onClick={() => setSheetOpen(false)}
              >
                {tr("notice.no_cancel")}
              </button>
            </div>
          }
        >
          <label htmlFor="notice-comment" className="block text-md font-medium">
            {tr("notice.no_comment_label")}
          </label>
          <textarea
            id="notice-comment"
            value={comment}
            maxLength={500}
            rows={4}
            aria-describedby="notice-comment-hint"
            onChange={(e) => setComment(e.target.value)}
            className="mt-2 block w-full rounded-md border border-line bg-paper px-3 py-2 text-md"
          />
          <p id="notice-comment-hint" className="mt-2 text-sm text-ink-muted">
            {tr("notice.no_comment_hint")}
          </p>
          {sendError && sheetOpen && <SendFailure error={sendError} tr={tr} secondsLeft={secondsLeft} busy={respond.isPending} />}
        </SheetDialog>
      </>
    );
  }

  return (
    <div className="min-h-dvh bg-paper">
      {header}
      <main id="main" lang={lang === "hi" ? "hi" : undefined} className="mx-auto max-w-[480px] px-4 pt-8 pb-16 text-md">
        {body}
      </main>
    </div>
  );
}

function Claim({ notice, tr, className }: { notice: NoticePublic; tr: Tr; className?: string }) {
  const idLabel = notice.id_kind === "APAAR" ? "APAAR" : tr("provisional.label");
  return (
    <section className={cn("border-l-2 border-rule-margin bg-paper-raised px-4 py-4 shadow-hairline", className)}>
      <p className="text-md text-ink-muted">{tr("notice.headline", { institution_name: notice.institution_name })}</p>
      <p className="mt-1 font-display text-xl leading-snug font-semibold">{tr("notice.claim", { programme_name: notice.programme_name })}</p>
      <p className="mt-3 text-ink-muted">{tr("notice.meta", { academic_year: notice.academic_year, year_of_study: notice.year_of_study })}</p>
      <p className="mt-1 text-ink-muted">
        {/* {id_masked} is left in place by t() so the id can be set in the mono face. */}
        {tr("notice.uploaded_line", { uploaded_date: formatDate(notice.uploaded_at), id_label: idLabel })
          .split("{id_masked}")
          .flatMap((part, i) => (i === 0 ? [part] : [<span key="id" className="font-mono whitespace-nowrap text-ink">{notice.id_masked}</span>, part]))}
      </p>
    </section>
  );
}

function Choices({
  tr,
  current,
  pending,
  disabled,
  onYes,
  onNo,
  noRef,
}: {
  tr: Tr;
  current: NoticeResponse | null;
  pending: NoticeResponse | null;
  disabled: boolean;
  onYes: () => void;
  onNo: () => void;
  noRef: React.RefObject<HTMLButtonElement | null>;
}) {
  const button = (response: NoticeResponse, ref?: React.RefObject<HTMLButtonElement | null>) => {
    const isCurrent = current === response;
    return (
      <button
        ref={ref}
        type="button"
        className={outlineButton}
        disabled={disabled || isCurrent}
        aria-describedby={isCurrent ? "notice-current" : undefined}
        onClick={response === "YES" ? onYes : onNo}
      >
        {isCurrent && <Check className="size-5" aria-hidden="true" />}
        {pending === response ? tr("notice.sending") : tr(response === "YES" ? "notice.yes" : "notice.no")}
        {isCurrent && (
          <span id="notice-current" className="text-sm font-normal">
            ({tr("notice.current_answer")})
          </span>
        )}
      </button>
    );
  };
  return (
    <div className="mt-5 flex flex-col gap-3">
      {button("YES")}
      {button("NO", noRef)}
    </div>
  );
}

function Answered({
  notice,
  tr,
  done,
  conflict,
  onChange,
  statusRef,
}: {
  notice: NoticePublic;
  tr: Tr;
  done: Done;
  conflict: "CHANGED_ONCE" | "WINDOW_CLOSED" | null;
  onChange: () => void;
  statusRef: React.RefObject<HTMLDivElement | null>;
}) {
  const reply = tr(notice.response === "YES" ? "notice.reply.YES" : "notice.reply.NO");
  const canChange = Boolean(notice.can_change_until) && !notice.changed_at && conflict === null;
  const windowLine = notice.can_change_until ? tr("notice.change_window", { change_until_date: formatDate(notice.can_change_until) }) : null;

  let lead: React.ReactNode;
  if (done === "CHANGED") {
    lead = <p className="font-display text-xl leading-snug font-semibold">{tr("notice.changed_done", { reply })}</p>;
  } else if (done === "YES") {
    lead = (
      <>
        <p className="font-display text-xl leading-snug font-semibold">{tr("notice.yes_done", { institution_name: notice.institution_name })}</p>
        <p className="mt-3">{tr("notice.yes_next")}</p>
        <p className="mt-2">
          <Link href="/student/wallet" className="inline-flex min-h-11 items-center">
            {tr("notice.see_proofs")}
          </Link>
        </p>
      </>
    );
  } else if (done === "NO") {
    lead = <p className="font-display text-xl leading-snug font-semibold">{tr("notice.no_done")}</p>;
  } else if (notice.changed_at || conflict === "CHANGED_ONCE") {
    lead = <p className="font-display text-xl leading-snug font-semibold">{tr("notice.change_used", { changed_date: formatDate(notice.changed_at ?? notice.responded_at), reply })}</p>;
  } else {
    lead = <p className="font-display text-xl leading-snug font-semibold">{tr("notice.answered", { reply, responded_date: formatDate(notice.responded_at) })}</p>;
  }

  const closed = !canChange && !notice.changed_at && done !== "CHANGED" && conflict !== "CHANGED_ONCE";
  return (
    <>
      <div ref={statusRef} tabIndex={-1} role="status" className="flex items-start gap-3 outline-none">
        <span className="mt-1 inline-flex size-7 shrink-0 items-center justify-center rounded-full border border-check-pass/40 bg-check-pass-soft text-check-pass-ink" aria-hidden="true">
          <Check className="size-4" />
        </span>
        <div className="min-w-0">{lead}</div>
      </div>
      <Claim notice={notice} tr={tr} className="mt-6" />
      {canChange && done !== "CHANGED" && (
        <div className="mt-6">
          {windowLine && <p>{windowLine}</p>}
          <button type="button" className={cn(outlineButton, "mt-3")} onClick={onChange}>
            {tr("notice.change")}
          </button>
        </div>
      )}
      {closed && <p className="mt-6 text-ink-muted">{tr("notice.change_closed")}</p>}
    </>
  );
}

function errorText(err: ApiError, tr: Tr, secondsLeft: number | null): string {
  switch (err.code) {
    case "NOTICE_NOT_FOUND":
      return tr("notice.invalid");
    case "NOTICE_EXPIRED":
      return tr("notice.expired");
    case "RATE_LIMITED":
      return tr("notice.rate_limited", { seconds: secondsLeft ?? err.retryAfter ?? 30 });
    case "NETWORK":
      return tr("err.NETWORK");
    default:
      return tr("err.INTERNAL");
  }
}

function LoadFailure({ error, tr, secondsLeft, onRetry }: { error: ApiError; tr: Tr; secondsLeft: number | null; onRetry: () => void }) {
  const final = error.code === "NOTICE_NOT_FOUND" || error.code === "NOTICE_EXPIRED";
  const limited = error.code === "RATE_LIMITED";
  return (
    <div role={final ? undefined : "alert"} className="border-l-2 border-rule-margin bg-paper-raised px-4 py-5 shadow-hairline">
      <p className={cn(final ? "font-display text-xl leading-snug font-semibold" : "text-md")}>{errorText(error, tr, secondsLeft)}</p>
      {!final && !limited && (
        <button type="button" className={cn(outlineButton, "mt-4")} onClick={onRetry}>
          <RefreshCw className="size-4" aria-hidden="true" />
          {tr("err.retry")}
        </button>
      )}
      {!final && <p className="code mt-3 text-xs text-ink-muted">{t("err.ref", { code: error.code })}</p>}
    </div>
  );
}

function SendFailure({
  error,
  tr,
  secondsLeft,
  busy,
  onRetry,
}: {
  error: ApiError | null;
  tr: Tr;
  secondsLeft: number | null;
  busy: boolean;
  onRetry?: () => void;
}) {
  if (!error || error.code === "NOTICE_ALREADY_CHANGED") return null;
  const limited = error.code === "RATE_LIMITED";
  const waiting = limited && secondsLeft !== null && secondsLeft > 0;
  if (limited && !waiting) return null;
  return (
    <div role="alert" className="mt-5 flex items-start gap-3 rounded-md border border-check-fail/30 bg-paper-raised px-4 py-3">
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-check-fail" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p>{errorText(error, tr, secondsLeft)}</p>
        {!limited && onRetry && (
          <button type="button" className="mt-2 inline-flex h-11 items-center gap-2 font-medium text-ink-blue" disabled={busy} onClick={onRetry}>
            <RefreshCw className="size-4" aria-hidden="true" />
            {tr("err.retry")}
          </button>
        )}
        <p className="code mt-1 text-xs text-ink-muted">{t("err.ref", { code: error.code })}</p>
      </div>
    </div>
  );
}

function NoticeSkeleton() {
  return (
    <div>
      <div aria-hidden="true" className="border-l-2 border-rule-margin bg-paper-raised px-4 py-4">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="mt-3 h-7 w-full" />
        <Skeleton className="mt-4 h-5 w-56" />
        <Skeleton className="mt-2 h-5 w-64" />
      </div>
      <Skeleton className="mt-8 h-6 w-36" />
      <Skeleton className="mt-5 h-12 w-full" />
      <Skeleton className="mt-3 h-12 w-full" />
      <SlowHint />
    </div>
  );
}
