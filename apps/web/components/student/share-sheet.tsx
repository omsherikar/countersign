"use client";

import * as React from "react";
import { Copy, Lock, QrCode, TriangleAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { useCredential, usePresent } from "@/lib/queries-student";
import type { ClaimKey, CredentialCard, PresentationCreated } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SheetDialog, bigButton, outlineButton, primaryButton, retryDeadline, useSecondsLeft } from "@/components/student/bits";
import { deckError, errorCodeOf } from "@/components/student/errors";

/** Deck section 8 order: institution and programme first and locked, then the rest unticked. */
const FIELD_ORDER: ClaimKey[] = [
  "institution",
  "programme",
  "name",
  "academic_year",
  "year_of_study",
  "dob",
  "apaar_masked",
  "countersigned",
  "university",
  "year_of_award",
];

/** "localhost:3000/verify" from the share link, for wallet.code_hint. */
function verifyPlace(url: string): string {
  try {
    const u = new URL(url);
    return `${u.host}/verify`;
  } catch {
    return "/verify";
  }
}

/** The QR from the api as an image, never as injected markup. */
export function QrImage({ svg, alt, className }: { svg: string; alt: string; className?: string }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={`data:image/svg+xml;utf8,${encodeURIComponent(svg)}`} alt={alt} className={cn("block bg-white", className)} />;
}

/**
 * W3-2 share sheet: choose fields (institution and programme locked on),
 * agree to the share text, create a QR and code that work for 10 minutes.
 * A modal from 768 px, a bottom sheet below; focus starts on Name, stays
 * inside, and returns to Share proof on close.
 */
export function ShareSheet({ card, open, onOpenChange }: { card: CredentialCard; open: boolean; onOpenChange: (open: boolean) => void }) {
  const detail = useCredential(card.id, open);
  const present = usePresent(card.id);
  const [chosen, setChosen] = React.useState<Set<ClaimKey>>(() => new Set());
  const [agreed, setAgreed] = React.useState(false);
  const [consentError, setConsentError] = React.useState(false);
  const [result, setResult] = React.useState<PresentationCreated | null>(null);
  const [announce, setAnnounce] = React.useState("");
  const consentRef = React.useRef<HTMLInputElement>(null);
  const firstOpen = React.useRef<HTMLInputElement>(null);
  const codeRef = React.useRef<HTMLParagraphElement>(null);

  const fields = FIELD_ORDER.map((key) => card.disclosable.find((d) => d.key === key)).filter((d): d is NonNullable<typeof d> => Boolean(d));
  const always = new Set(card.disclosable.filter((d) => d.always).map((d) => d.key));
  const count = always.size + [...chosen].filter((k) => !always.has(k)).length;
  const total = card.disclosable.length;
  const values = new Map((detail.data?.claims ?? []).map((c) => [c.key, c.value]));

  const reset = () => {
    setChosen(new Set());
    setAgreed(false);
    setConsentError(false);
    setResult(null);
    setAnnounce("");
    present.reset();
  };

  const change = (o: boolean) => {
    if (!o) reset();
    onOpenChange(o);
  };

  const create = () => {
    if (present.isPending) return;
    if (!agreed) {
      setConsentError(true);
      consentRef.current?.focus();
      return;
    }
    present.mutate(
      { fields: [...chosen], consent: true },
      {
        onSuccess: (r) => {
          setResult(r);
          requestAnimationFrame(() => codeRef.current?.focus());
        },
      },
    );
  };

  const deadline = retryDeadline(present.error, present.submittedAt);
  const secondsLeft = useSecondsLeft(deadline);
  const limited = secondsLeft !== null && secondsLeft > 0;
  const consentApiError = present.error instanceof ApiError && present.error.code === "VALIDATION_ERROR" && present.error.fields.some((f) => f.field === "consent");

  const footer = result ? (
    <button type="button" className={primaryButton} onClick={() => change(false)}>
      {t("wallet.done")}
    </button>
  ) : (
    <button type="button" className={primaryButton} disabled={present.isPending || limited || detail.isLoading} onClick={create}>
      <QrCode className="size-5" aria-hidden="true" />
      {present.isPending ? t("wallet.creating") : t("wallet.create_qr")}
    </button>
  );

  return (
    <SheetDialog
      open={open}
      onOpenChange={change}
      title={t("wallet.share_heading")}
      description={`${tk(`wallet.kind.${card.kind}`)}, ${card.institution_name}`}
      footer={footer}
      onOpenAutoFocus={(e) => {
        e.preventDefault();
        firstOpen.current?.focus();
      }}
    >
      <div className="sr-only" aria-live="polite">
        {announce}
      </div>
      {result ? (
        <ShareResult result={result} labels={card.disclosable} onAnnounce={setAnnounce} onNew={reset} codeRef={codeRef} />
      ) : (
        <>
          <fieldset>
            <legend className="font-sans text-lg font-semibold">{t("wallet.fields_heading")}</legend>
            <p className="mt-1 text-ink-muted">{t("wallet.fields_hint")}</p>
            <ul className="mt-3 border-t border-rule">
              {fields.map((f, i) => {
                const locked = always.has(f.key);
                const id = `share-${card.id}-${f.key}`;
                const firstUnlocked = !locked && fields.slice(0, i).every((x) => always.has(x.key));
                return (
                  <li key={f.key} className="flex items-start gap-3 border-b border-rule py-3">
                    <input
                      ref={firstUnlocked ? firstOpen : undefined}
                      id={id}
                      type="checkbox"
                      className="mt-0.5 size-5 shrink-0 accent-[var(--ink-blue)]"
                      checked={locked || chosen.has(f.key)}
                      aria-disabled={locked || undefined}
                      aria-describedby={locked ? `${id}-locked` : f.key === "countersigned" ? `${id}-hint` : undefined}
                      onChange={() => {
                        if (locked) return;
                        setChosen((prev) => {
                          const next = new Set(prev);
                          if (next.has(f.key)) next.delete(f.key);
                          else next.add(f.key);
                          return next;
                        });
                      }}
                    />
                    <div className="min-w-0 flex-1">
                      <label htmlFor={id} className="block font-medium">
                        {tk(`wallet.field.${f.key}`) === `wallet.field.${f.key}` ? f.label : tk(`wallet.field.${f.key}`)}
                      </label>
                      {locked && (
                        <span id={`${id}-locked`} className="mt-0.5 inline-flex items-center gap-1 text-sm text-ink-muted">
                          <Lock className="size-3.5" aria-hidden="true" />
                          {t("wallet.always_shared")}
                        </span>
                      )}
                      {f.key === "countersigned" && (
                        <span id={`${id}-hint`} className="block text-sm text-ink-muted">
                          {t("wallet.field.countersigned_hint")}
                        </span>
                      )}
                      <span className="mt-0.5 block break-words text-ink-muted">
                        {detail.isLoading ? <span className="inline-block h-4 w-40 animate-pulse rounded-md bg-accent" aria-hidden="true" /> : (values.get(f.key) ?? "")}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          </fieldset>
          <p className="mt-3 font-medium" aria-live="polite">
            {t("wallet.shares", { n: count, m: total })}
          </p>

          <div className="mt-5 border-l-2 border-rule-margin bg-paper px-4 py-3">
            <p id={`consent-text-${card.id}`} className="text-sm">
              {t("consent.credential_share")}
            </p>
            <div className="mt-3 flex min-h-11 items-center gap-3">
              <input
                ref={consentRef}
                id={`consent-${card.id}`}
                type="checkbox"
                className="size-5 shrink-0 accent-[var(--ink-blue)]"
                checked={agreed}
                aria-required="true"
                aria-invalid={consentError || consentApiError || undefined}
                aria-describedby={`consent-text-${card.id}${consentError || consentApiError ? ` consent-error-${card.id}` : ""}`}
                onChange={(e) => {
                  setAgreed(e.target.checked);
                  if (e.target.checked) setConsentError(false);
                }}
              />
              <label htmlFor={`consent-${card.id}`} className="font-medium">
                {t("wallet.consent_label")}
              </label>
            </div>
            {(consentError || consentApiError) && (
              <p id={`consent-error-${card.id}`} className="mt-1 text-sm text-check-fail-ink">
                {t("wallet.consent_required")}
              </p>
            )}
          </div>

          {present.isError && !consentApiError && (
            <div role="alert" className="mt-4 flex items-start gap-3 rounded-md border border-check-fail/30 bg-paper-raised px-4 py-3">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-check-fail" aria-hidden="true" />
              <div>
                <p>{deckError(present.error, secondsLeft)}</p>
                <p className="code mt-1 text-xs text-ink-muted">{t("err.ref", { code: errorCodeOf(present.error) })}</p>
              </div>
            </div>
          )}
          {detail.isError && (
            <p role="alert" className="mt-4 text-sm text-check-fail-ink">
              {deckError(detail.error)}
            </p>
          )}
        </>
      )}
    </SheetDialog>
  );
}

function formatTimer(seconds: number): { mm: string; ss: string } {
  return { mm: String(Math.floor(seconds / 60)), ss: String(seconds % 60).padStart(2, "0") };
}

function ShareResult({
  result,
  labels,
  onAnnounce,
  onNew,
  codeRef,
}: {
  result: PresentationCreated;
  labels: CredentialCard["disclosable"];
  onAnnounce: (text: string) => void;
  onNew: () => void;
  codeRef: React.RefObject<HTMLParagraphElement | null>;
}) {
  const left = useSecondsLeft(Date.parse(result.expires_at)) ?? 0;
  const expired = left <= 0;
  const minutes = Math.ceil(left / 60);
  const shared = result.disclosed.map((k) => labels.find((d) => d.key === k)?.label ?? k).join(", ");
  const timer = formatTimer(left);

  // Screen readers hear the countdown at 5 minutes and at 1 minute only (W3-2).
  const said = React.useRef<number | null>(null);
  React.useEffect(() => {
    if (expired) return;
    if ((minutes === 5 || minutes === 1) && said.current !== minutes) {
      said.current = minutes;
      onAnnounce(t("wallet.expires_in_sr", { minutes }));
    }
  }, [minutes, expired, onAnnounce]);

  const copy = async (text: string, done: string) => {
    try {
      await navigator.clipboard.writeText(text);
      onAnnounce(done);
    } catch {
      onAnnounce("");
    }
  };

  return (
    <div className="flex flex-col items-center text-center">
      {expired ? (
        <div className="flex size-60 flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed border-line px-5">
          <p>{t("wallet.expired_share")}</p>
          <button type="button" className={cn(outlineButton, "h-11")} onClick={onNew}>
            {t("wallet.new_qr")}
          </button>
        </div>
      ) : (
        <QrImage svg={result.qr_svg} alt={t("wallet.qr_alt")} className="size-60 rounded-md border border-line" />
      )}
      <p className="mt-3 text-sm text-ink-muted">{t("wallet.code_label")}</p>
      <p ref={codeRef} tabIndex={-1} className="font-mono text-lg font-medium tracking-wide break-all select-all outline-none focus-visible:outline-2">
        <span className={cn(expired && "text-ink-muted line-through")}>{result.code}</span>
        {expired && <span className="ml-2 font-sans text-sm font-semibold text-ink">{t("wallet.status.expired")}</span>}
      </p>
      <p className="mt-3 font-medium">{t("wallet.shares", { n: result.disclosed.length, m: result.total })}</p>
      <p className="text-ink-muted">{t("wallet.shared_fields", { fields: shared })}</p>
      {!expired && (
        <p className="mt-2">
          {t("wallet.valid_for")} · <span className="num">{t("wallet.expires_in", timer)}</span>
        </p>
      )}
      <p className="mt-2 text-sm text-ink-muted">{t("wallet.code_hint", { verify_url: verifyPlace(result.url) })}</p>
      <div className="mt-4 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        <button type="button" className={cn(bigButton, "h-11 border border-line bg-paper text-ink hover:bg-paper-sunken")} onClick={() => copy(result.code, t("wallet.code_copied"))}>
          <Copy className="size-4" aria-hidden="true" />
          {t("wallet.copy_code")}
        </button>
        <button type="button" className={cn(bigButton, "h-11 border border-line bg-paper text-ink hover:bg-paper-sunken")} onClick={() => copy(result.url, t("wallet.copied"))}>
          <Copy className="size-4" aria-hidden="true" />
          {t("wallet.copy_link")}
        </button>
      </div>
    </div>
  );
}
