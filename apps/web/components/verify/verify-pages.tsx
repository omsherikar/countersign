"use client";

import * as React from "react";
import { RefreshCw, TriangleAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import { useVerifyCode, useVerifyDegree, useVerifyLookup, useVerifyPaste } from "@/lib/queries-student";
import type { VerifyResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Disclosure, outlineButton, retryDeadline, useSecondsLeft } from "@/components/student/bits";
import { deckError, errorCodeOf } from "@/components/student/errors";
import { CodeForm } from "@/components/verify/code-form";
import { ResultFooter, ResultSkeleton, ResultView, type VerifySource } from "@/components/verify/result-view";
import { Scanner } from "@/components/verify/scanner";

/** "What is Countersign?", the same paragraph on every verify page. */
function About() {
  return (
    <section id="about" className="mt-10 border-t border-rule pt-5">
      <h2 className="font-sans text-md font-semibold">{t("verify.about_link")}</h2>
      <p className="mt-2 text-ink-muted">{t("verify.about")}</p>
    </section>
  );
}

function PasteBox({ onResult }: { onResult: (r: VerifyResult) => void }) {
  const paste = useVerifyPaste();
  const [text, setText] = React.useState("");
  const deadline = retryDeadline(paste.error, paste.submittedAt);
  const left = useSecondsLeft(deadline) ?? 0;
  return (
    <Disclosure className="mt-6" summary={t("verify.paste_link")}>
      <form
        className="mt-2 flex flex-col gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (!text.trim() || paste.isPending || left > 0) return;
          paste.mutate(text.trim(), { onSuccess: onResult });
        }}
      >
        <label htmlFor="verify-paste" className="font-medium">
          {t("verify.paste_label")}
        </label>
        <textarea
          id="verify-paste"
          rows={5}
          value={text}
          maxLength={16384}
          spellCheck={false}
          aria-describedby="verify-paste-hint"
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-md border border-line bg-paper-raised px-3 py-2 font-mono text-sm break-all"
        />
        <p id="verify-paste-hint" className="text-sm text-ink-muted">
          {t("verify.paste_hint")}
        </p>
        {paste.isError && (
          <p role="alert" className="text-sm text-check-fail-ink">
            {paste.error instanceof ApiError && paste.error.code === "RATE_LIMITED"
              ? t("verify.rate_limited", { seconds: left })
              : deckError(paste.error)}
          </p>
        )}
        <button type="submit" className={cn(outlineButton, "mt-2")} aria-disabled={paste.isPending || left > 0 || undefined}>
          {paste.isPending ? t("verify.checking") : t("verify.paste_check")}
        </button>
      </form>
    </Disclosure>
  );
}

/** W3-4 `/verify`: scan, type a code or paste attestation text. No sign-in, no search, never a list. */
export function VerifyEntry() {
  const codeInput = React.useRef<HTMLInputElement>(null);
  const [pasted, setPasted] = React.useState<VerifyResult | null>(null);
  const resultTop = React.useRef<HTMLDivElement>(null);

  if (pasted) {
    return (
      <div ref={resultTop}>
        <ResultView result={pasted} source="paste" />
        <ResultFooter
          onAnother={() => {
            setPasted(null);
            requestAnimationFrame(() => codeInput.current?.focus());
          }}
        />
        <About />
      </div>
    );
  }

  return (
    <>
      <h1 className="text-2xl">{t("verify.heading")}</h1>
      <p className="mt-2 text-ink-muted">{t("verify.lead")}</p>
      <div className="mt-6 flex flex-col gap-5 border-l-2 border-rule-margin bg-paper-raised px-4 py-5 shadow-hairline">
        <Scanner onDenied={() => codeInput.current?.focus()} />
        <CodeForm inputRef={codeInput} />
      </div>
      <PasteBox
        onResult={(r) => {
          setPasted(r);
          requestAnimationFrame(() => document.getElementById("verify-result")?.focus());
        }}
      />
      <p className="mt-6 text-ink-muted">{t("verify.what")}</p>
      <About />
    </>
  );
}

/** A failed check: the deck wording, the code box again for a wrong code or a rate limit, else Try again. */
function VerifyFailure({
  error,
  errorAt,
  code,
  onRetry,
}: {
  error: unknown;
  errorAt: number;
  code: string | null;
  onRetry: () => void;
}) {
  const limited = error instanceof ApiError && error.code === "RATE_LIMITED";
  const notFound = error instanceof ApiError && error.code === "PRESENTATION_NOT_FOUND";
  const left = useSecondsLeft(retryDeadline(error, errorAt)) ?? 0;
  if ((notFound || limited) && code !== null) {
    return (
      <>
        <h1 className="text-2xl">{t("verify.heading")}</h1>
        <div className="mt-4 border-l-2 border-rule-margin bg-paper-raised px-4 py-5 shadow-hairline">
          <CodeForm
            initial={code}
            autoFocus
            waitSeconds={limited ? left : 0}
            error={limited ? t("verify.rate_limited", { seconds: left }) : t("err.PRESENTATION_NOT_FOUND")}
            onSameCode={(path) => {
              if (decodeURIComponent(window.location.pathname) !== path) return false;
              onRetry();
              return true;
            }}
          />
        </div>
      </>
    );
  }
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-check-fail/30 bg-paper-raised px-4 py-4">
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-check-fail" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p>{limited ? t("verify.rate_limited", { seconds: left }) : deckError(error)}</p>
        {!limited || left === 0 ? (
          <button type="button" className={cn(outlineButton, "mt-3 h-11")} onClick={onRetry}>
            <RefreshCw className="size-4" aria-hidden="true" />
            {t("err.retry")}
          </button>
        ) : null}
        <p className="code mt-2 text-xs text-ink-muted">{t("err.ref", { code: errorCodeOf(error) })}</p>
      </div>
    </div>
  );
}

function ResultPage({
  query,
  source,
  code,
}: {
  query: { data?: VerifyResult; error: unknown; isLoading: boolean; errorUpdatedAt: number; refetch: () => unknown };
  source: VerifySource;
  code: string | null;
}) {
  const result = query.data;
  const focused = React.useRef(false);
  React.useEffect(() => {
    if (result && !focused.current) {
      focused.current = true;
      document.getElementById("verify-result")?.focus();
    }
  }, [result]);
  return (
    <>
      {query.isLoading && <ResultSkeleton />}
      {!query.isLoading && query.error != null && !result && (
        <VerifyFailure error={query.error} errorAt={query.errorUpdatedAt} code={code} onRetry={() => query.refetch()} />
      )}
      {result && <ResultView result={result} source={source} />}
      {(result || query.error != null) && <ResultFooter />}
      <About />
    </>
  );
}

/** `/verify/[code]`: a share code from a student's wallet. */
export function VerifyCodePage({ code }: { code: string }) {
  const query = useVerifyCode(code);
  return <ResultPage query={query} source="code" code={code} />;
}

/** `/verify/d/[jws]`: the QR printed in a certificate block. */
export function VerifyDegreePage({ jws }: { jws: string }) {
  const query = useVerifyDegree(jws);
  return <ResultPage query={query} source="degree" code={null} />;
}

/** `/verify/completion/[shortId]`: an attestation id typed from a certificate, checked against the register. */
export function VerifyLookupPage({ shortId }: { shortId: string }) {
  const query = useVerifyLookup(shortId);
  return <ResultPage query={query} source="lookup" code={shortId} />;
}
