"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleCheck, LogOut, ShieldCheck } from "lucide-react";
import { api, ApiError, MOCK_API } from "@/lib/api";
import { safeNext, signInUrl } from "@/lib/digilocker";
import { fetchMe } from "@/lib/queries";
import type { ClaimRequest, ClaimResult, PendingClaim } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SlowHint } from "@/components/common/query-state";
import { outlineButton, primaryButton, retryDeadline, useSecondsLeft } from "@/components/student/bits";
import { PublicHeader, makeTr, useLang } from "@/components/student/lang";

const SHAPE = /^PRV-[0-9A-Z]{8}$/;

/** Upper case, spaces out, and the PRV- prefix added when it was left off. */
function normalise(raw: string): string {
  const s = raw.toUpperCase().replace(/\s+/g, "");
  if (!s) return s;
  return s.startsWith("PRV-") ? s : `PRV-${s.replace(/^PRV/, "")}`;
}

/**
 * Claim by provisional ID (W4-9). The field takes the ID with or without
 * PRV- and spaces, checks its shape before anything is sent, and keeps the
 * value when the api refuses it. Five failed tries in 15 minutes pause
 * claiming. Signed out, the page sends the visitor to DigiLocker first.
 */
export function ClaimPage({ demo }: { demo: boolean }) {
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [lang, setLang] = useLang();
  const tr = React.useMemo(() => makeTr(lang), [lang]);
  const qc = useQueryClient();
  const pending = useQuery({
    queryKey: ["auth", "digilocker", "claim"],
    queryFn: () => api.get<PendingClaim>("/auth/digilocker/claim", undefined, { redirectOn401: false }),
    retry: false,
  });
  const noClaim = pending.error instanceof ApiError && pending.error.status === 401;
  // Without a pending claim: a signed-in student has nothing to claim here; anyone else signs in first.
  const me = useQuery({ queryKey: ["me", "claim-page"], queryFn: fetchMe, enabled: noClaim, retry: false });
  React.useEffect(() => {
    if (noClaim && me.isSuccess && !me.data) window.location.replace(signInUrl(`/student/claim?next=${encodeURIComponent(next)}`));
  }, [noClaim, me.isSuccess, me.data, next]);

  const [value, setValue] = React.useState("");
  const [fieldError, setFieldError] = React.useState<string | null>(null);
  const input = React.useRef<HTMLInputElement>(null);
  const done = React.useRef<HTMLHeadingElement>(null);
  const claim = useMutation({
    mutationFn: (body: ClaimRequest) => api.post<ClaimResult>("/auth/digilocker/claim", body, { redirectOn401: false }),
    onSuccess: () => {
      // The session changed: whatever was read signed out is stale now.
      void qc.invalidateQueries({ queryKey: ["me"] });
      void qc.invalidateQueries({ queryKey: ["notices"] });
      void qc.invalidateQueries({ queryKey: ["students", "me"] });
      requestAnimationFrame(() => done.current?.focus());
    },
  });
  const deadline = retryDeadline(claim.error, claim.submittedAt);
  const secondsLeft = useSecondsLeft(deadline);
  const locked = secondsLeft !== null && secondsLeft > 0;
  const [demoId, setDemoId] = React.useState<string | null>(null);
  React.useEffect(() => {
    if (!MOCK_API || !demo) return;
    void import("@/lib/mock/student-loop").then((m) => setDemoId(m.ashaProvisionalId()));
  }, [demo]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (claim.isPending || locked) return;
    const id = normalise(value);
    if (!SHAPE.test(id)) {
      setFieldError(tr("claim.format"));
      input.current?.focus();
      return;
    }
    setFieldError(null);
    claim.mutate(
      { provisional_id: id },
      {
        onError: (err) => {
          if (!(err instanceof ApiError)) return setFieldError(tr("err.INTERNAL"));
          if (err.code === "CLAIM_NO_MATCH" || err.code === "CLAIM_ALREADY_CLAIMED" || err.code === "CLAIM_NOT_NEEDED") setFieldError(tr(`err.${err.code}`));
          else if (err.code === "VALIDATION_ERROR") setFieldError(tr("claim.format"));
          else if (err.code === "RATE_LIMITED") setFieldError(null);
          else if (err.code === "DIGILOCKER_STATE_INVALID") setFieldError(tr("err.DIGILOCKER_STATE_INVALID"));
          else setFieldError(tr("err.INTERNAL"));
          input.current?.focus();
        },
      },
    );
  }

  async function signOut() {
    try {
      await api.post("/auth/logout", {}, { redirectOn401: false });
    } catch {
      // Already signed out.
    }
    window.location.assign(/^\/student\/notices\//.test(next) ? next : "/login");
  }

  let body: React.ReactNode;
  if (claim.isSuccess) {
    const institution = claim.data.claimed.enrolments[0]?.institution_name ?? "";
    const answer = /^\/student\/notices\//.test(claim.data.next) ? claim.data.next : null;
    body = (
      <div role="status">
        <h1 ref={done} tabIndex={-1} className="flex items-start gap-2 text-2xl outline-none">
          <CircleCheck className="mt-1.5 size-6 shrink-0 text-check-pass-ink" aria-hidden="true" />
          {tr("claim.done_heading")}
        </h1>
        <p className="mt-3">{tr("claim.done", { institution_name: institution })}</p>
        <div className="mt-6 flex flex-col gap-3">
          {answer && (
            <a href={answer} className={cn(primaryButton, "no-underline")}>
              {tr("claim.done_answer")}
            </a>
          )}
          <a href="/student" className={cn(answer ? outlineButton : primaryButton, "no-underline")}>
            {tr("claim.done_home")}
          </a>
        </div>
      </div>
    );
  } else if (pending.isLoading || (noClaim && !me.isFetched) || (noClaim && me.isSuccess && !me.data)) {
    body = (
      <div aria-hidden="true">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="mt-4 h-16 w-full" />
        <Skeleton className="mt-6 h-12 w-full" />
        <SlowHint />
      </div>
    );
  } else if (noClaim && me.data) {
    body = (
      <div>
        <h1 className="text-2xl">{tr("claim.heading")}</h1>
        <p className="mt-3">{tr("claim.nothing_to_claim")}</p>
        <a href="/student" className={cn(primaryButton, "mt-6 no-underline")}>
          {tr("claim.done_home")}
        </a>
      </div>
    );
  } else if (pending.isError && !noClaim) {
    body = (
      <div role="alert" className="border-l-2 border-rule-margin bg-paper-raised px-4 py-5">
        <p>{tr("err.INTERNAL")}</p>
        <button type="button" className={cn(outlineButton, "mt-4")} onClick={() => pending.refetch()}>
          {tr("err.retry")}
        </button>
      </div>
    );
  } else if (pending.data) {
    const describedBy = ["claim-hint", fieldError ? "claim-error" : null, locked ? "claim-locked" : null].filter(Boolean).join(" ");
    body = (
      <>
        <h1 className="text-2xl">{tr("claim.heading")}</h1>
        <p className="mt-3">{tr("claim.lead")}</p>
        <form onSubmit={submit} noValidate className="mt-6 flex flex-col gap-2">
          <label htmlFor="claim-id" className="font-medium">
            {tr("claim.id_label")}
          </label>
          <input
            ref={input}
            id="claim-id"
            value={value}
            onChange={(e) => setValue(e.target.value.toUpperCase())}
            placeholder="PRV-________"
            autoCapitalize="characters"
            autoComplete="off"
            spellCheck={false}
            maxLength={16}
            aria-invalid={fieldError ? true : undefined}
            aria-describedby={describedBy}
            disabled={claim.isPending}
            className="h-12 rounded-md border border-line bg-paper-raised px-3 font-mono text-lg tracking-wider aria-invalid:border-check-fail"
          />
          <p id="claim-hint" className="text-sm text-ink-muted">
            {tr("claim.id_hint")}
          </p>
          {fieldError && (
            <p id="claim-error" role="alert" className="text-sm text-check-fail-ink">
              {fieldError}
            </p>
          )}
          {locked && (
            <p id="claim-locked" role="alert" className="text-sm text-check-pending-ink">
              {tr("claim.locked", { minutes: Math.max(1, Math.ceil(secondsLeft! / 60)) })}
            </p>
          )}
          <p className="mt-3 text-sm text-ink-muted">{tr("claim.match_note")}</p>
          {demoId && <p className="text-sm text-ink-muted">{tr("claim.demo_hint", { provisional_id: demoId })}</p>}
          <button type="submit" disabled={claim.isPending || locked} className={cn(primaryButton, "mt-4")}>
            {claim.isPending ? tr("claim.submitting") : tr("claim.submit")}
          </button>
        </form>
        <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-rule pt-4 text-sm">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="size-4 shrink-0 text-check-pass-ink" aria-hidden="true" />
            {tr("notice.signed_in_as", { name: pending.data.name })}
          </span>
          <button type="button" onClick={signOut} className="inline-flex min-h-11 items-center gap-1.5 font-medium text-ink-blue">
            <LogOut className="size-4" aria-hidden="true" />
            {tr("signin.signout")}
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="min-h-dvh bg-paper">
      <PublicHeader lang={lang} setLang={setLang} tr={tr} />
      <main id="main" lang={lang === "hi" ? "hi" : undefined} className="mx-auto max-w-[480px] px-4 pt-8 pb-16 text-md">
        {body}
      </main>
    </div>
  );
}
