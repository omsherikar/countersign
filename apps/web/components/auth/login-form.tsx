"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import { useLogin } from "@/lib/queries";
import { ROLE_PREFIXES, landingFor } from "@/lib/roles";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DEMO_PASSWORD, DEMO_ROLES } from "@/components/auth/demo-roles";

/** Only same-origin paths the signed-in role may open are honoured as `next`. */
function destination(role: Role, next: string | null): string {
  if (next && next.startsWith("/") && !next.startsWith("//")) {
    const path = next.split("?")[0];
    if (ROLE_PREFIXES[role].some((p) => path === p || path.startsWith(`${p}/`))) return next;
  }
  return landingFor(role);
}

function useCountdown(): [number, (seconds: number) => void] {
  const [left, setLeft] = React.useState(0);
  React.useEffect(() => {
    if (left <= 0) return;
    const id = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [left]);
  return [left, setLeft];
}

export function LoginForm({ next, notice }: { next: string | null; notice: string | null }) {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [show, setShow] = React.useState(false);
  const [selected, setSelected] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>({});
  const [wait, setWait] = useCountdown();
  const submitRef = React.useRef<HTMLButtonElement>(null);
  const busy = login.isPending || login.isSuccess;

  function pick(key: string) {
    const demo = DEMO_ROLES.find((d) => d.key === key);
    if (!demo) return;
    setSelected(key);
    setEmail(demo.email);
    setPassword(DEMO_PASSWORD);
    setError(null);
    setFieldErrors({});
    submitRef.current?.focus();
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || wait > 0) return;
    setError(null);
    setFieldErrors({});
    login.mutate(
      { email: email.trim(), password },
      {
        onSuccess: (res) => {
          router.replace(destination(res.user.role, next));
          router.refresh();
        },
        onError: (err) => {
          if (!(err instanceof ApiError)) {
            setError(t("err.INTERNAL"));
            return;
          }
          if (err.code === "VALIDATION_ERROR" && err.fields.length) {
            setFieldErrors(Object.fromEntries(err.fields.map((f) => [f.field, f.message])));
            setError(t("err.VALIDATION_ERROR"));
          } else if (err.code === "RATE_LIMITED") {
            const seconds = err.retryAfter ?? 30;
            setWait(seconds);
            setError(null);
          } else if (err.code === "INVALID_CREDENTIALS") {
            setError(t("err.INVALID_CREDENTIALS"));
          } else if (err.code === "NETWORK") {
            setError(t("err.NETWORK"));
          } else {
            setError(err.message || t("err.INTERNAL"));
          }
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <section aria-labelledby="demo-roles">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="demo-roles" className="font-sans text-sm font-semibold text-ink">
            {t("app.pick_role")}
          </h2>
          <span className="stamp">{t("login.demo_tag")}</span>
        </div>
        <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {DEMO_ROLES.map((d) => {
            const [role, scope] = t(d.card).split(" / ");
            const on = selected === d.key;
            return (
              <li key={d.key}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => pick(d.key)}
                  className={cn(
                    "relative flex h-full w-full flex-col gap-1 rounded-md border bg-paper-raised px-3.5 pt-3 pb-3 text-left shadow-hairline",
                    on ? "border-ink-blue ring-1 ring-ink-blue" : "border-line hover:border-rule-strong",
                  )}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="font-display text-md font-semibold text-ink">{role}</span>
                    <span className="shrink-0 rounded-chip border border-line px-1 text-2xs text-ink-muted">Demo</span>
                  </span>
                  <span className="text-sm leading-snug text-ink-muted">{scope}</span>
                  <span className="code mt-1 truncate text-xs text-ink-faint">{d.email}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <form
        onSubmit={onSubmit}
        noValidate
        className="flex flex-col gap-4 border-l-2 border-rule-margin bg-paper-raised py-5 pr-5 pl-5 shadow-hairline sm:pl-6"
        aria-describedby={error ? "login-error" : undefined}
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor="email" className="text-sm font-medium">
            {t("login.email")}
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            disabled={busy}
            aria-invalid={Boolean(fieldErrors.email) || undefined}
            aria-describedby={fieldErrors.email ? "email-error" : undefined}
            onChange={(e) => {
              setEmail(e.target.value);
              setSelected(null);
            }}
            className="h-10 rounded-md border border-line bg-paper px-3 text-base aria-invalid:border-check-fail"
          />
          {fieldErrors.email && (
            <p id="email-error" className="text-xs text-check-fail-ink">
              {fieldErrors.email}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="password" className="text-sm font-medium">
            {t("login.password")}
          </label>
          <div className="flex gap-2">
            <input
              id="password"
              name="password"
              type={show ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              disabled={busy}
              aria-invalid={Boolean(fieldErrors.password) || undefined}
              aria-describedby={fieldErrors.password ? "password-error" : undefined}
              onChange={(e) => setPassword(e.target.value)}
              className="h-10 min-w-0 flex-1 rounded-md border border-line bg-paper px-3 text-base aria-invalid:border-check-fail"
            />
            <Button type="button" variant="outline" className="h-10 w-16" onClick={() => setShow((s) => !s)} aria-pressed={show}>
              {show ? t("login.hide") : t("login.show")}
            </Button>
          </div>
          {fieldErrors.password && (
            <p id="password-error" className="text-xs text-check-fail-ink">
              {fieldErrors.password}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Button ref={submitRef} type="submit" className="h-10 min-w-32 px-5" disabled={busy || wait > 0}>
            {busy ? t("login.submitting") : t("login.submit")}
          </Button>
          {notice && !error && wait === 0 && (
            <p className="text-sm text-ink-muted" role="status">
              {notice}
            </p>
          )}
        </div>
        <div aria-live="assertive">
          {wait > 0 && (
            <p id="login-error" role="alert" className="text-sm text-check-pending-ink">
              {t("err.RATE_LIMITED", { seconds: wait })}
            </p>
          )}
          {error && (
            <p id="login-error" role="alert" className="text-sm text-check-fail-ink">
              {error}
            </p>
          )}
        </div>
      </form>
    </div>
  );
}
