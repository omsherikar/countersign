"use client";

import * as React from "react";
import { Check, Minus, Share2, X } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useStudentMe } from "@/lib/queries";
import { useCredential, useCredentials } from "@/lib/queries-student";
import type { CredentialCard, PresentationBrief, StudentEnrolment } from "@/lib/types";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/brand/EmptyState";
import { Crumbs } from "@/components/common/page-header";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusWord, primaryButton, useNow } from "@/components/student/bits";
import { ShareSheet } from "@/components/student/share-sheet";

const TIME = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
/** "10:42" in IST (A3.1: the web formats clock times). */
const clock = (value: string) => TIME.format(new Date(value));

export function ProofStatus({ status }: { status: CredentialCard["status"] }) {
  if (status === "ACTIVE")
    return (
      <StatusWord tone="ok" icon={Check} size="md">
        {t("wallet.status.active")}
      </StatusWord>
    );
  if (status === "REVOKED")
    return (
      <StatusWord tone="neutral" icon={X} size="md">
        {t("wallet.status.revoked")}
      </StatusWord>
    );
  return (
    <StatusWord tone="neutral" icon={Minus} size="md">
      {t("wallet.status.expired")}
    </StatusWord>
  );
}

/** The year a degree is awarded: the end of its academic year ("2025-26" gives 2026). */
function yearOfAward(academicYear: string): string {
  const [start] = academicYear.split("-");
  return String(Number(start) + 1);
}

/** Rows of one share, newest share first (deck section 8, D27). */
function historyRows(p: PresentationBrief, total: number, now: number): string[] {
  const rows = [t("wallet.history.created", { date: formatDate(p.created_at), time: clock(p.created_at), n: p.disclosed.length, m: total })];
  const created = Date.parse(p.created_at);
  const ends = Date.parse(p.expires_at);
  if (p.verify_count > 1 && p.last_verified_at) {
    rows.push(t("wallet.history_item_more", { n: p.verify_count, time: clock(p.last_verified_at) }));
  } else if (p.verify_count === 1 && p.last_verified_at) {
    const today = formatDate(p.last_verified_at) === formatDate(new Date(now || Date.parse(p.last_verified_at)).toISOString());
    rows.push(
      today
        ? t("wallet.history_item", { time: clock(p.last_verified_at) })
        : t("wallet.history_item_date", { date: formatDate(p.last_verified_at), time: clock(p.last_verified_at) }),
    );
  }
  // A share that ended well before its 10 minutes was stopped by a consent withdrawal.
  if (ends - created < 9.5 * 60_000 && now && ends <= now) rows.push(t("wallet.history.stopped", { date: formatDate(p.expires_at) }));
  else if (p.verify_count === 0 && now && ends <= now) rows.push(t("wallet.history.unused"));
  return rows;
}

function Details({ card }: { card: CredentialCard }) {
  const [open, setOpen] = React.useState(false);
  const detail = useCredential(card.id, open);
  const id = `details-${card.id}`;
  return (
    <div className="mt-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex min-h-11 items-center font-medium text-ink-blue underline underline-offset-2"
      >
        {open ? t("wallet.hide_details") : t("wallet.details")}
      </button>
      {open && (
        <div id={id} className="mt-1 border-t border-rule pt-3">
          <h3 className="font-sans text-md font-semibold">{t("wallet.details_heading")}</h3>
          {detail.isLoading && (
            <div className="mt-2 flex flex-col gap-2" aria-hidden="true">
              <Skeleton className="h-4 w-56" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-60" />
            </div>
          )}
          {detail.isError && <ErrorBlock compact className="mt-2" error={detail.error} onRetry={() => detail.refetch()} />}
          {detail.data && (
            <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[max-content_1fr]">
              {detail.data.claims.map((c) => (
                <React.Fragment key={c.key}>
                  <dt className="text-ink-muted">{c.label}</dt>
                  <dd className="mb-2 break-words sm:mb-0">{c.value}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}
          <p className="code mt-3 text-sm text-ink-muted">{t("wallet.proof_id", { short_id: card.short_id })}</p>
        </div>
      )}
    </div>
  );
}

function History({ card, now }: { card: CredentialCard; now: number }) {
  const total = card.disclosable.length;
  return (
    <section aria-labelledby={`history-${card.id}`} className="mt-4 border-t border-rule pt-3">
      <h3 id={`history-${card.id}`} className="font-sans text-md font-semibold">
        {t("wallet.history_heading")}
      </h3>
      {card.presentations.length === 0 ? (
        <p className="mt-1 text-ink-muted">{t("wallet.history_empty")}</p>
      ) : (
        <ol className="mt-1 flex flex-col gap-2">
          {card.presentations.map((p) => (
            <li key={p.id} className="text-md">
              {historyRows(p, total, now).map((row, i) => (
                <p key={i} className={cn(i > 0 && "text-ink-muted")}>
                  {row}
                </p>
              ))}
            </li>
          ))}
        </ol>
      )}
      <p className="mt-2 text-sm text-ink-muted">{t("wallet.history_note")}</p>
    </section>
  );
}

function ProofCard({ card, now }: { card: CredentialCard; now: number }) {
  const [sharing, setSharing] = React.useState(false);
  const headingId = `proof-${card.id}`;
  const degree = card.kind === "COMPLETION";
  const reason = card.revoked_reason_code && `wallet.revoked_reason.${card.revoked_reason_code}`;
  return (
    <section aria-labelledby={headingId} className="border-l-2 border-rule-margin bg-paper-raised px-4 py-4 shadow-hairline md:px-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id={headingId} className="font-display text-xl font-semibold">
          {tk(`wallet.kind.${card.kind}`)}
        </h2>
        <ProofStatus status={card.status} />
      </div>
      {degree ? (
        <>
          <p className="mt-2 font-medium">{card.university_name}</p>
          <p>
            {card.programme_name}, {yearOfAward(card.academic_year)}
          </p>
        </>
      ) : (
        <>
          <p className="mt-2 font-medium">{card.institution_name}</p>
          <p>{card.programme_name}</p>
        </>
      )}
      <p className="mt-2 text-ink-muted">
        {degree ? t("wallet.issued_by_completion", { university_name: card.university_name ?? "" }) : t("wallet.issued_by", { institution_name: card.institution_name })}
      </p>
      <p className="text-ink-muted">{t("wallet.issued_on", { issued_date: formatDate(card.issued_at) })}</p>
      {card.expires_at && card.status !== "REVOKED" && <p className="text-ink-muted">{t("wallet.valid_until", { expires_date: formatDate(card.expires_at) })}</p>}

      {card.status === "REVOKED" && (
        <div className="mt-3 border-l-2 border-line bg-paper px-3 py-2">
          <p>{t("wallet.revoked_line", { revoked_date: formatDate(card.revoked_at) })}</p>
          <p>{reason && tk(reason) !== reason ? tk(reason) : t("wallet.revoked_reason.ADMIN")}</p>
          <p className="text-ink-muted">{t("wallet.revoked_help")}</p>
        </div>
      )}
      {card.status === "EXPIRED" && <p className="mt-3 border-l-2 border-line bg-paper px-3 py-2">{t("wallet.expired_line", { expires_date: formatDate(card.expires_at) })}</p>}

      {card.status === "ACTIVE" && (
        <button type="button" className={cn(primaryButton, "mt-4 md:w-auto")} onClick={() => setSharing(true)}>
          <Share2 className="size-5" aria-hidden="true" />
          {t("wallet.share")}
        </button>
      )}
      <Details card={card} />
      <History card={card} now={now} />
      {card.status === "ACTIVE" && <ShareSheet card={card} open={sharing} onOpenChange={setSharing} />}
    </section>
  );
}

/**
 * No attestation yet for an active enrolment: one line by the record's
 * status (A4.14: issued only to a Countersigned record), never naming a
 * case or a contradicted row.
 */
function NotIssued({ e }: { e: StudentEnrolment }) {
  const line =
    e.record_status === "DISPUTED"
      ? t("wallet.not_issued.DISPUTED", { institution_name: e.institution_name })
      : e.record_status === "UNDER_REVIEW"
        ? t("wallet.not_issued.UNDER_REVIEW")
        : t("wallet.not_issued.AWAITING_EVIDENCE");
  return (
    <section className="border-l-2 border-line bg-paper-raised px-4 py-4 md:px-5">
      <h2 className="font-display text-xl font-semibold">{t("wallet.not_issued_heading")}</h2>
      <p className="mt-1 text-ink-muted">
        {e.institution_name}, {e.programme_name}
      </p>
      <p className="mt-2">{line}</p>
    </section>
  );
}

/** W3-2 My attestations: the student's attestations, sharing chosen fields as a QR and code, and who checked them when. */
export function WalletPage() {
  const list = useCredentials();
  const me = useStudentMe();
  const now = useNow(true);
  const cards = list.data?.items ?? [];
  // A Countersigned record without its attestation yet is about to get one; it needs no explanation.
  const missing = (me.data?.enrolments ?? []).filter(
    (e) => e.status === "ACTIVE" && e.record_status !== "COUNTERSIGNED" && !cards.some((c) => c.kind === "ENROLMENT" && c.enrolment_id === e.id && c.status === "ACTIVE"),
  );
  const loading = list.isLoading || me.isLoading;

  return (
    <div className="text-md">
      <Crumbs items={[{ label: t("nav.my_enrolment"), href: "/student" }, { label: t("wallet.heading") }]} />
      <h1 className="text-3xl">{t("wallet.heading")}</h1>
      <p className="mt-2 text-ink-muted">{t("wallet.lead")}</p>

      <div className="mt-6 flex flex-col gap-4">
        {loading && (
          <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-4" aria-hidden="true">
            <Skeleton className="h-6 w-44" />
            <Skeleton className="mt-3 h-5 w-64" />
            <Skeleton className="mt-2 h-5 w-56" />
            <Skeleton className="mt-4 h-12 w-full" />
          </div>
        )}
        {loading && <SlowHint />}
        {list.isError && !list.data && <ErrorBlock error={list.error} onRetry={() => list.refetch()} />}
        {!loading && list.data && (
          <>
            {missing.map((e) => (
              <NotIssued key={e.id} e={e} />
            ))}
            {cards.map((c) => (
              <ProofCard key={c.id} card={c} now={now} />
            ))}
            {cards.length === 0 && missing.length === 0 && <EmptyState className="border-y border-rule" title={t("empty.credentials_student")} />}
          </>
        )}
      </div>
    </div>
  );
}
