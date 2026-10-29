"use client";

import * as React from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { Check, LogOut, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import { resolveSignInUrl } from "@/lib/digilocker";
import { formatDate } from "@/lib/format";
import { studentKeys, useNotice, useRespondNotice } from "@/lib/queries-student";
import type { NoticePublic, NoticeResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SlowHint } from "@/components/common/query-state";
import { Disclosure, SheetDialog, outlineButton, primaryButton, retryDeadline, useSecondsLeft } from "@/components/student/bits";
import { PublicHeader, makeTr, useLang, type Tr } from "@/components/student/lang";

type Done = "YES" | "NO" | "CHANGED" | null;

/**
 * W3-1 and W4-8, the public notice page. The token in the link shows the
 * claim and the masked id to whoever holds it, never a name, date of birth
 * or contact detail. Yes and No exist only after the student signs in with
 * DigiLocker and the api says the sign-in matches the record; anyone else
 * reads that the notice is for someone else, and nothing is recorded.
 */
export function NoticePage({ token, demo }: { token: string; demo: boolean }) {
  const qc = useQueryClient();
  const [signingOut, setSigningOut] = React.useState(false);
  const signOut = async () => {
    setSigningOut(true);
    try {
      await api.post("/auth/logout", {}, { redirectOn401: false });
    } catch {
      // Signed out already, or the session had ended: the notice reloads either way.
    }
    await qc.invalidateQueries({ queryKey: studentKeys.notice(token) });
    setSigningOut(false);
  };
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
  const changeHeading = React.useRef<HTMLHeadingElement>(null);
  const startChange = () => {
    setMode("change");
    requestAnimationFrame(() => changeHeading.current?.focus());
  };

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

  const header = <PublicHeader lang={lang} setLang={setLang} tr={tr} />;

  let body: React.ReactNode;
  if (notice.isLoading) {
    body = <NoticeSkeleton />;
  } else if (loadError && !data) {
    body = <LoadFailure error={loadError} tr={tr} secondsLeft={secondsLeft} onRetry={() => refetch()} />;
  } else if (data) {
    const match = data.viewer.match;
    const signInHref = resolveSignInUrl(data.sign_in_url, `/student/notices/${token}`);
    const signedInLine = match === "MATCH" && data.viewer.name ? (
      <SignedInAs tr={tr} name={data.viewer.name} onSignOut={signOut} busy={signingOut} />
    ) : null;
    const gate =
      !data.viewer.signed_in && match === null ? (
        <SignInGate tr={tr} href={signInHref} demo={demo} />
      ) : match === "SOMEONE_ELSE" ? (
        <SomeoneElse tr={tr} notice={data} onSignOut={signOut} busy={signingOut} />
      ) : match === "CLAIM_NEEDED" ? (
        <ClaimNeeded tr={tr} href={data.claim_url ?? `/student/claim?next=${encodeURIComponent(`/student/notices/${token}`)}`} onSignOut={signOut} busy={signingOut} />
      ) : null;
    body = (
      <>
        {mode === "change" && match === "MATCH" ? (
          <>
            {signedInLine}
            <h1 ref={changeHeading} tabIndex={-1} className="text-2xl outline-none">
              {tr("notice.change_heading")}
            </h1>
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
            <button
              type="button"
              className="mt-4 inline-flex h-11 items-center text-md text-ink-blue underline"
              onClick={() => {
                setMode("view");
                requestAnimationFrame(() => status.current?.focus());
              }}
            >
              {tr("notice.no_cancel")}
            </button>
          </>
        ) : data.response ? (
          <>
            {signedInLine}
            <Answered notice={data} tr={tr} done={done} conflict={conflict} onChange={startChange} statusRef={status} allowChange={match === "MATCH" && data.can_answer} />
            {gate}
          </>
        ) : (
          <>
            {signedInLine}
            <Claim notice={data} tr={tr} />
            {match === "MATCH" ? (
              <>
                <h2 className="mt-8 font-sans text-lg font-semibold">{tr("notice.question")}</h2>
                <p className="mt-2 text-sm text-ink-muted">{lang === "hi" ? tr("consent.notice", { institution_name: data.institution_name }) : data.consent_text}</p>
                <Choices
                  tr={tr}
                  current={null}
                  pending={respond.isPending ? pressed : null}
                  disabled={respond.isPending || limited || !data.can_answer}
                  onYes={() => send({ response: "YES" })}
                  onNo={() => setSheetOpen(true)}
                  noRef={noButton}
                />
                <p className="mt-4 text-ink-muted">{tr("notice.next_step")}</p>
              </>
            ) : (
              gate
            )}
          </>
        )}

        <SendFailure
          error={sendError}
          tr={tr}
          secondsLeft={secondsLeft}
          busy={respond.isPending}
          onRetry={lastBody ? () => send(lastBody) : undefined}
          signInHref={resolveSignInUrl(data.sign_in_url, `/student/notices/${token}`)}
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
  allowChange,
}: {
  notice: NoticePublic;
  tr: Tr;
  done: Done;
  conflict: "CHANGED_ONCE" | "WINDOW_CLOSED" | null;
  onChange: () => void;
  statusRef: React.RefObject<HTMLDivElement | null>;
  /** Only the signed-in student whose record this is can change the answer (W4-8). */
  allowChange: boolean;
}) {
  const reply = tr(notice.response === "YES" ? "notice.reply.YES" : "notice.reply.NO");
  const canChange = allowChange && Boolean(notice.can_change_until) && !notice.changed_at && conflict === null;
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

  const closed = allowChange && !canChange && !notice.changed_at && done !== "CHANGED" && conflict !== "CHANGED_ONCE";
  return (
    <>
      <div ref={statusRef} tabIndex={-1} role="status" className="flex items-start gap-3 outline-none">
        <span
          className={cn(
            "mt-1 inline-flex size-7 shrink-0 items-center justify-center rounded-full border",
            // Green means countersigned (DESIGN 3.2): only a Yes earns it; a No is recorded, not passed.
            notice.response === "YES" ? "border-check-pass/40 bg-check-pass-soft text-check-pass-ink" : "border-flag-open/40 bg-flag-open-soft text-flag-open-ink",
          )}
          aria-hidden="true"
        >
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
    case "SIGNIN_REQUIRED":
      return tr("err.SIGNIN_REQUIRED");
    case "NOTICE_IDENTITY_MISMATCH":
      return tr("err.NOTICE_IDENTITY_MISMATCH");
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
      <p className={cn(final ? "font-display text-lg leading-snug font-semibold" : "text-md")}>{errorText(error, tr, secondsLeft)}</p>
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
  signInHref,
}: {
  error: ApiError | null;
  tr: Tr;
  secondsLeft: number | null;
  busy: boolean;
  onRetry?: () => void;
  signInHref?: string;
}) {
  if (!error || error.code === "NOTICE_ALREADY_CHANGED") return null;
  if (error.code === "SIGNIN_REQUIRED" || error.code === "NOTICE_IDENTITY_MISMATCH") {
    return (
      <div role="alert" className="mt-5 rounded-md border border-line bg-paper-raised px-4 py-3">
        <p>{errorText(error, tr, secondsLeft)}</p>
        {error.code === "SIGNIN_REQUIRED" && signInHref && (
          <a href={signInHref} className="mt-2 inline-flex min-h-11 items-center font-medium">
            {tr("notice.signin_button")}
          </a>
        )}
      </div>
    );
  }
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

/* ---- The DigiLocker gate (W4-8, copy deck section 23) ----------------------- */

function SignInGate({ tr, href, demo }: { tr: Tr; href: string; demo: boolean }) {
  return (
    <section className="mt-8">
      <p className="text-md">{tr("notice.signin_lead")}</p>
      <a href={href} className={cn(primaryButton, "mt-4 no-underline")}>
        <ShieldCheck className="size-5" aria-hidden="true" />
        {tr("notice.signin_button")}
      </a>
      <p className="mt-3 text-sm text-ink-muted">{tr("signin.redirect_note")}</p>
      {demo && <p className="mt-1 text-sm text-ink-muted">{tr("signin.demo_note")}</p>}
    </section>
  );
}

function SignOutButton({ tr, onSignOut, busy, label }: { tr: Tr; onSignOut: () => void; busy: boolean; label?: string }) {
  return (
    <button type="button" onClick={onSignOut} disabled={busy} className="inline-flex min-h-11 items-center gap-1.5 font-medium text-ink-blue underline-offset-2 hover:underline disabled:opacity-60">
      <LogOut className="size-4" aria-hidden="true" />
      {label ?? tr("notice.signout")}
    </button>
  );
}

function SignedInAs({ tr, name, onSignOut, busy }: { tr: Tr; name: string; onSignOut: () => void; busy: boolean }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-rule pb-3 text-sm">
      <p className="flex items-center gap-1.5 text-ink">
        <ShieldCheck className="size-4 shrink-0 text-check-pass-ink" aria-hidden="true" />
        {tr("notice.signed_in_as", { name })}
      </p>
      <SignOutButton tr={tr} onSignOut={onSignOut} busy={busy} />
    </div>
  );
}

/** Someone else is signed in: the claim card stays, no buttons, nothing recorded, and never the record's student name. */
function SomeoneElse({ tr, notice, onSignOut, busy }: { tr: Tr; notice: NoticePublic; onSignOut: () => void; busy: boolean }) {
  return (
    <section className="mt-8" aria-labelledby="someone-else">
      <h2 id="someone-else" className="font-sans text-lg font-semibold">
        {tr("notice.someone_else_heading")}
      </h2>
      <p className="mt-2">{tr("notice.someone_else_body", { name: notice.viewer.name ?? "" })}</p>
      <p className="mt-3">{tr("notice.someone_else_college", { institution_name: notice.institution_name })}</p>
      <p className="mt-3">{tr("notice.someone_else_other", { institution_name: notice.institution_name })}</p>
      <div className="mt-3">
        <SignOutButton tr={tr} onSignOut={onSignOut} busy={busy} />
      </div>
    </section>
  );
}

/** The record has no APAAR and nobody has claimed it: claim it with the provisional ID first. */
function ClaimNeeded({ tr, href, onSignOut, busy }: { tr: Tr; href: string; onSignOut: () => void; busy: boolean }) {
  return (
    <section className="mt-8" aria-labelledby="claim-needed">
      <h2 id="claim-needed" className="font-sans text-lg font-semibold">
        {tr("notice.claim_needed_heading")}
      </h2>
      <p className="mt-2">{tr("notice.claim_needed")}</p>
      <Link href={href} className={cn(primaryButton, "mt-4 no-underline")}>
        {tr("notice.claim_button")}
      </Link>
      <div className="mt-3">
        <SignOutButton tr={tr} onSignOut={onSignOut} busy={busy} />
      </div>
    </section>
  );
}
