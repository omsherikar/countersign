"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { primaryButton } from "@/components/student/bits";

/**
 * What a typed code opens: a 24-character share code goes to /verify/{code}
 * in six groups of four, an 8-character degree proof id to
 * /verify/degree/{id}; anything else is a format error and sends nothing.
 */
export function codeTarget(raw: string): string | null {
  const s = raw.toUpperCase().replace(/[\s-]/g, "");
  if (!/^[0-9A-Z]+$/.test(s)) return null;
  if (s.length === 24) return `/verify/${s.match(/.{4}/g)!.join("-")}`;
  if (s.length === 8) return `/verify/degree/${s}`;
  return null;
}

/** A scanned QR: one of our own verify links opens its own path; anything else is treated as a typed code. */
export function scanTarget(text: string): string | null {
  try {
    const u = new URL(text);
    if (/^\/verify\/(d\/[^/]+|degree\/[^/]+|[^/]+)$/.test(u.pathname)) return u.pathname;
  } catch {
    // Not a URL: a printed code.
  }
  return codeTarget(text);
}

/**
 * The code box (W3-4): label, hint, Check. Upper-cases and regroups the code
 * before it leaves, and says so when the length is wrong. `waitSeconds`
 * holds Check during a rate limit, with the countdown on the button.
 */
export function CodeForm({
  initial = "",
  autoFocus = false,
  waitSeconds = 0,
  onSameCode,
  inputRef,
  error,
}: {
  initial?: string;
  autoFocus?: boolean;
  waitSeconds?: number;
  /** Called instead of navigating when the code opens the page already shown (a retry). */
  onSameCode?: (path: string) => boolean;
  inputRef?: React.RefObject<HTMLInputElement | null>;
  /** A message from the page above, shown as this field's error. */
  error?: string | null;
}) {
  const router = useRouter();
  const [value, setValue] = React.useState(initial);
  const [formatError, setFormatError] = React.useState(false);
  const [pending, startTransition] = React.useTransition();
  const ownRef = React.useRef<HTMLInputElement>(null);
  const ref = inputRef ?? ownRef;
  const message = formatError ? t("verify.code_format") : (error ?? null);

  React.useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus, ref]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (waitSeconds > 0 || pending) return;
    const path = codeTarget(value);
    if (!path) {
      setFormatError(true);
      ref.current?.focus();
      return;
    }
    setFormatError(false);
    if (onSameCode?.(path)) return;
    startTransition(() => router.push(path));
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-1.5">
      <label htmlFor="verify-code" className="font-medium">
        {t("verify.code_label")}
      </label>
      <input
        ref={ref}
        id="verify-code"
        name="code"
        type="text"
        inputMode="text"
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        value={value}
        placeholder={t("verify.placeholder")}
        aria-invalid={message ? true : undefined}
        aria-describedby={cn("verify-code-hint", message && "verify-code-error")}
        onChange={(e) => {
          setValue(e.target.value);
          setFormatError(false);
        }}
        className="h-12 w-full min-w-0 rounded-md border border-line bg-paper-raised px-3 font-mono text-md tracking-wide uppercase placeholder:font-sans placeholder:text-sm placeholder:tracking-normal placeholder:normal-case aria-invalid:border-check-fail"
      />
      <p id="verify-code-hint" className="text-sm text-ink-muted">
        {t("verify.code_hint")} {t("verify.code_hint_degree")}
      </p>
      {message && (
        <p id="verify-code-error" role="alert" className="text-sm text-check-fail-ink">
          {message}
        </p>
      )}
      <button type="submit" className={cn(primaryButton, "mt-2")} aria-disabled={waitSeconds > 0 || pending || undefined}>
        {pending ? t("verify.checking") : waitSeconds > 0 ? `${t("verify.check")} (${waitSeconds} s)` : t("verify.check")}
      </button>
    </form>
  );
}
