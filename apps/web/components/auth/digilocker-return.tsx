"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Loader2, TriangleAlert } from "lucide-react";
import { safeNext, signInUrl } from "@/lib/digilocker";
import { fetchMe } from "@/lib/queries";
import type { User } from "@/lib/types";
import { cn } from "@/lib/utils";
import { outlineButton, primaryButton } from "@/components/student/bits";
import { PublicHeader, makeTr, useLang } from "@/components/student/lang";

const ERRORS = ["DIGILOCKER_CANCELLED", "DIGILOCKER_FAILED", "DIGILOCKER_STATE_INVALID"] as const;
type ErrorCode = (typeof ERRORS)[number];

/**
 * /auth/digilocker/return (W4-8): "Signing you in" while the session
 * settles, then on to `next` (a same-origin path only). A cancelled or
 * failed sign-in says so and offers to try again; a stale one points back
 * to the notice. Nothing is recorded on any of these.
 */
export function DigiLockerReturn() {
  const params = useSearchParams();
  const [lang, setLang] = useLang();
  const tr = React.useMemo(() => makeTr(lang), [lang]);
  const next = safeNext(params.get("next"));
  const raw = params.get("error");
  const error: ErrorCode | null = raw ? ((ERRORS as readonly string[]).includes(raw) ? (raw as ErrorCode) : "DIGILOCKER_FAILED") : null;
  const [me, setMe] = React.useState<User | null | undefined>(undefined);
  const status = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (error) {
      status.current?.focus();
      return;
    }
    let gone = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    (async () => {
      let user: User | null = null;
      // The session cookie is set by the redirect that brought us here; ask once or twice while it settles.
      for (let i = 0; i < 3 && !user && !gone; i++) {
        user = await fetchMe().catch(() => null);
        if (!user) await new Promise((r) => setTimeout(r, 400));
      }
      if (gone) return;
      setMe(user);
      // A full navigation, so every page reads the new session rather than a cached signed-out one.
      timer = setTimeout(() => window.location.replace(next), user ? 900 : 300);
    })();
    return () => {
      gone = true;
      if (timer) clearTimeout(timer);
    };
  }, [error, next]);

  const notice = /^\/student\/notices\//.test(next) ? next : null;
  return (
    <div className="min-h-dvh bg-paper">
      <PublicHeader lang={lang} setLang={setLang} tr={tr} />
      <main id="main" lang={lang === "hi" ? "hi" : undefined} className="mx-auto max-w-[480px] px-4 pt-10 pb-16 text-md">
        {error ? (
          <div ref={status} tabIndex={-1} role="alert" className="border-l-2 border-check-fail bg-paper-raised px-4 py-5 shadow-hairline outline-none">
            <p className="flex items-start gap-2 font-display text-lg leading-snug font-semibold">
              <TriangleAlert className="mt-1 size-5 shrink-0 text-check-fail" aria-hidden="true" />
              {tr(`err.${error}`)}
            </p>
            <div className="mt-5 flex flex-col gap-3">
              {error === "DIGILOCKER_STATE_INVALID" && notice ? (
                <Link href={notice} className={cn(primaryButton, "no-underline")}>
                  {tr("claim.done_answer")}
                </Link>
              ) : (
                <a href={signInUrl(next)} className={cn(primaryButton, "no-underline")}>
                  {tr("signin.try_again")}
                </a>
              )}
              {error === "DIGILOCKER_STATE_INVALID" && notice && (
                <a href={signInUrl(next)} className={cn(outlineButton, "no-underline")}>
                  {tr("signin.try_again")}
                </a>
              )}
            </div>
            <p className="code mt-4 text-xs text-ink-muted">Ref: {error}</p>
          </div>
        ) : (
          <div role="status" aria-live="polite" className="flex flex-col items-center gap-4 py-10 text-center">
            {me ? (
              <p className="font-display text-xl font-semibold">{tr("signin.done", { name: me.name })}</p>
            ) : (
              <>
                <Loader2 className="size-8 animate-spin text-ink-blue" aria-hidden="true" />
                <p className="font-display text-xl font-semibold">{tr("signin.returning")}</p>
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
