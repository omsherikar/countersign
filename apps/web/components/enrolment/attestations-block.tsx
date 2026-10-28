"use client";

import * as React from "react";
import { Loader2, ShieldOff } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useRevokeCredential } from "@/lib/queries-cases";
import type { CredentialRef, EnrolmentDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { SectionHeader } from "@/components/common/page-header";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";

const REASON_MIN = 5;
const REASON_MAX = 300;

/** Why an attestation was revoked, in the words the student's wallet uses (the officer's text for ADMIN). */
function revokedReason(c: CredentialRef): string {
  if (c.revoked_reason_code === "ADMIN" && c.revoked_reason) return c.revoked_reason;
  return c.revoked_reason_code ? tk(`wallet.revoked_reason.${c.revoked_reason_code}`) : "";
}

/**
 * The attestations of this record (API_CONTRACT A4.6, A4.14; copy deck §22).
 * An AICTE officer can revoke an active one with a reason; the record and its
 * status do not change. One revoked by the student's dispute says so.
 */
export function AttestationsBlock({ d }: { d: EnrolmentDetail }) {
  const { user } = useMe();
  const revoke = useRevokeCredential(d.id);
  const [target, setTarget] = React.useState<CredentialRef | null>(null);
  const [reason, setReason] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);
  const opener = React.useRef<HTMLButtonElement | null>(null);
  const ids = React.useId();
  const canRevoke = user?.role === "AICTE_ADMIN";

  function submit() {
    const text = reason.trim();
    if (text.length < REASON_MIN) {
      setError(t("enrolment.attestations.reason_short"));
      return;
    }
    if (!target) return;
    setError(null);
    revoke.mutate(
      { id: target.id, reason: text },
      {
        onSuccess: () => {
          setTarget(null);
          setReason("");
          setMessage(t("enrolment.attestations.revoked_toast"));
        },
        onError: (err) => setError(errorMessage(err, user?.role, "enrolment")),
      },
    );
  }

  return (
    <section aria-labelledby={`${ids}-heading`}>
      <SectionHeader id={`${ids}-heading`} title={t("enrolment.section.attestations")} />
      <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm">
        {d.credentials.length === 0 ? (
          <p className="text-ink-muted">{t("enrolment.attestations.none")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {d.credentials.map((c) => (
              <li key={c.id} className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p>
                    {t("enrolment.attestations.line", {
                      kind_word: tk(`wallet.kind.${c.kind}`),
                      short_id: c.short_id,
                      issued_date: formatDate(c.issued_at),
                    })}{" "}
                    <span className={cn("font-medium", c.status === "ACTIVE" ? "text-ink" : "text-check-fail-ink")}>
                      {tk(`wallet.status.${c.status.toLowerCase()}`)}
                    </span>
                  </p>
                  {c.status === "REVOKED" && (
                    <p className="text-ink-muted [overflow-wrap:anywhere]">
                      {t("enrolment.attestations.revoked_line", { revoked_date: formatDate(c.revoked_at), reason: revokedReason(c) })}
                    </p>
                  )}
                  {c.status === "REVOKED" && c.revoked_reason_code === "STUDENT_DISPUTE" && (
                    <p className="text-ink-muted">{t("enrolment.attestations.held_by_dispute")}</p>
                  )}
                </div>
                {canRevoke && c.status === "ACTIVE" && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-11 md:h-8"
                    onClick={(e) => {
                      opener.current = e.currentTarget;
                      setMessage(null);
                      setError(null);
                      setTarget(c);
                    }}
                  >
                    <ShieldOff className="size-3.5" aria-hidden="true" />
                    {t("enrolment.attestations.revoke")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        <div aria-live="polite">{message && <p className="mt-2 font-medium text-ink">{message}</p>}</div>
      </div>

      <Dialog open={target !== null} onOpenChange={(next) => !next && !revoke.isPending && setTarget(null)}>
        <DialogContent
          className="max-h-[calc(100dvh-2rem)] gap-5 overflow-y-auto bg-paper-raised sm:max-w-md"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            opener.current?.focus();
          }}
        >
          <div className="flex flex-col gap-2 pr-6">
            <DialogTitle className="font-display text-xl font-semibold">{t("enrolment.attestations.revoke_heading")}</DialogTitle>
            <DialogDescription className="text-sm text-ink">{t("enrolment.attestations.revoke_body")}</DialogDescription>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${ids}-reason`} className="text-sm font-medium">
              {t("enrolment.attestations.reason_label")}
            </label>
            <textarea
              id={`${ids}-reason`}
              value={reason}
              maxLength={REASON_MAX}
              rows={3}
              onChange={(e) => setReason(e.target.value)}
              aria-describedby={`${ids}-reason-hint${error ? ` ${ids}-reason-error` : ""}`}
              aria-invalid={error ? true : undefined}
              aria-required="true"
              disabled={revoke.isPending}
              className="min-h-24 w-full rounded-md border border-line bg-paper px-2.5 py-2 text-md leading-snug aria-invalid:border-check-fail md:text-sm"
            />
            <p id={`${ids}-reason-hint`} className="text-xs text-ink-muted">
              {t("enrolment.attestations.reason_hint")}
            </p>
            {error && (
              <p id={`${ids}-reason-error`} className="text-sm text-check-fail-ink">
                {error}
              </p>
            )}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="outline" className="h-11 sm:h-9" onClick={() => setTarget(null)} disabled={revoke.isPending}>
              {t("enrolment.attestations.cancel")}
            </Button>
            <Button type="button" className="h-11 sm:h-9" onClick={submit} disabled={revoke.isPending} aria-busy={revoke.isPending}>
              {revoke.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {revoke.isPending ? t("enrolment.attestations.revoking") : t("enrolment.attestations.revoke_confirm")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
