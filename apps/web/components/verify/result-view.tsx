"use client";

import * as React from "react";
import Link from "next/link";
import { Ban, Check, Clock, TriangleAlert } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import type { VerifyResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SlowHint } from "@/components/common/query-state";
import { StatusWord, primaryButton, useNow } from "@/components/student/bits";

/** Where the result came from: a share code, pasted attestation text, a certificate QR, or an attestation id typed from a certificate. */
export type VerifySource = "code" | "paste" | "degree" | "lookup";

const TIME = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });

function ResultBadge({ result }: { result: VerifyResult["result"] }) {
  const word = tk(`verify.state.${result}`);
  switch (result) {
    case "VALID":
      return (
        <StatusWord tone="ok" icon={Check} size="md">
          {word}
        </StatusWord>
      );
    case "REVOKED":
      return (
        <StatusWord tone="alert" icon={Ban} size="md">
          {word}
        </StatusWord>
      );
    case "EXPIRED":
      return (
        <StatusWord tone="neutral" icon={Clock} size="md">
          {word}
        </StatusWord>
      );
    default:
      return (
        <StatusWord tone="alert" icon={TriangleAlert} size="md">
          {word}
        </StatusWord>
      );
  }
}

/** Label beside value, or above it when the value would not fit (W3-4 phone rule). */
function Fields({ result }: { result: VerifyResult }) {
  return (
    <dl className="mt-2 border-t border-rule">
      {result.disclosed.map((f) => (
        <div key={f.key} className="flex flex-wrap gap-x-4 gap-y-0.5 border-b border-rule py-2.5">
          <dt className="min-w-[8.5rem] text-ink-muted">{f.label}</dt>
          <dd className={cn("min-w-[12rem] flex-1 font-medium break-words", (f.key === "apaar_masked" || f.key === "proof_id" || f.key === "provisional_id") && "font-mono")}>
            {f.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * One verification answer (deck section 10). Only what the api returned is
 * shown: a VALID result lists exactly the disclosed fields in the order
 * sent; REVOKED, EXPIRED and INVALID show no fields at all.
 */
export function ResultView({ result, source }: { result: VerifyResult; source: VerifySource }) {
  const now = useNow();
  const degree = source === "degree" || source === "lookup" || result.kind === "COMPLETION";
  const checkedAt = result.status_checked_at ? Date.parse(result.status_checked_at) : null;
  const revocationLine =
    checkedAt && now && now - checkedAt > 60_000 ? t("verify.revocation_at", { time: TIME.format(new Date(checkedAt)) }) : t("verify.revocation");

  let heading: string;
  let sub: string;
  if (result.result === "VALID") {
    heading = degree ? t("verify.completion_valid") : t("verify.valid");
    sub = degree
      ? t("verify.completion_sub", { university_name: result.university_name ?? "" })
      : t("verify.valid_sub", { institution_name: result.institution_name ?? "", issued_date: formatDate(result.issued_at) });
  } else if (result.result === "REVOKED") {
    heading = t("verify.revoked");
    sub = degree ? t("verify.completion_revoked_sub") : t("verify.revoked_sub");
  } else if (result.result === "EXPIRED") {
    heading = t("verify.expired");
    sub = t("verify.expired_sub");
  } else {
    heading = t("verify.invalid");
    sub = t("verify.invalid_sub");
  }

  return (
    <section aria-labelledby="verify-result" className="border-l-2 border-rule-margin bg-paper-raised px-4 py-5 shadow-hairline">
      <ResultBadge result={result.result} />
      <h1 id="verify-result" tabIndex={-1} className="mt-3 text-2xl outline-none">
        {heading}
      </h1>
      {result.result === "VALID" && result.kind && !degree && <p className="mt-1 font-medium">{tk(`verify.kind.${result.kind}`)}</p>}
      <p className="mt-2">{sub}</p>
      {result.result === "VALID" && (
        <>
          <ul className="mt-3 flex flex-col gap-1 text-ink-muted">
            <li className="flex gap-2">
              <Check className="mt-1 size-4 shrink-0 text-check-pass" aria-hidden="true" />
              {result.method === "register_lookup" ? t("verify.method_lookup") : t("verify.signature")}
            </li>
            <li className="flex gap-2">
              <Check className="mt-1 size-4 shrink-0 text-check-pass" aria-hidden="true" />
              {revocationLine}
            </li>
            {result.holder_bound && source !== "paste" && (
              <li className="flex gap-2">
                <Check className="mt-1 size-4 shrink-0 text-check-pass" aria-hidden="true" />
                {t("verify.holder_bound")}
              </li>
            )}
          </ul>
          <h2 className="mt-6 font-sans text-lg font-semibold">{degree ? t("verify.completion_heading") : t("verify.shared_heading")}</h2>
          <Fields result={result} />
          {degree ? (
            <>
              <p className="mt-3">{t("verify.completion_printed")}</p>
              {source !== "lookup" && <p className="mt-2 text-ink-muted">{t("verify.completion_wallet")}</p>}
            </>
          ) : (
            <p className="mt-3 text-ink-muted">{t("verify.not_shared")}</p>
          )}
          {source === "paste" && <p className="mt-3 border-l-2 border-check-pending bg-check-pending-soft px-3 py-2 text-check-pending-ink">{t("verify.pasted_note")}</p>}
        </>
      )}
    </section>
  );
}

/** Every result ends the same way: check another attestation, and what Countersign is. */
export function ResultFooter({ onAnother }: { onAnother?: () => void }) {
  return (
    <div className="mt-6 flex flex-col gap-3">
      {onAnother ? (
        <button type="button" className={primaryButton} onClick={onAnother}>
          {t("verify.check_another")}
        </button>
      ) : (
        <Link href="/verify" className={cn(primaryButton, "no-underline hover:text-on-ink-blue")}>
          {t("verify.check_another")}
        </Link>
      )}
      <a href="#about" className="inline-flex min-h-11 w-fit items-center">
        {t("verify.about_link")}
      </a>
    </div>
  );
}

export function ResultSkeleton() {
  return (
    <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-5" aria-busy="true">
      <div aria-hidden="true">
        <Skeleton className="h-7 w-24" />
        <Skeleton className="mt-3 h-8 w-56" />
        <Skeleton className="mt-3 h-5 w-full" />
        <Skeleton className="mt-2 h-5 w-64" />
        <Skeleton className="mt-6 h-5 w-40" />
        <Skeleton className="mt-3 h-10 w-full" />
        <Skeleton className="mt-2 h-10 w-full" />
      </div>
      <p className="mt-3 text-ink-muted">{t("verify.checking")}</p>
      <SlowHint />
    </div>
  );
}
