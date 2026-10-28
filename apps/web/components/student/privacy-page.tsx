"use client";

import * as React from "react";
import { Check, Clock, Download, Link2Off, Minus, RefreshCw, X } from "lucide-react";
import { api, API_BASE, ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useStudentMe } from "@/lib/queries";
import {
  useAccessLog,
  useConsents,
  useCreateDataRequest,
  useDataRequests,
  usePrivacyNotice,
  useWithdrawConsent,
} from "@/lib/queries-student";
import type { AccessLogRow, ConsentCurrent, ConsentPurpose, ConsentRow, DataRequestKind, DataRequestRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Crumbs } from "@/components/common/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { Disclosure, SheetDialog, StatusWord, bigButton, outlineButton, primaryButton } from "@/components/student/bits";
import { deckError, errorCodeOf } from "@/components/student/errors";

const PURPOSES: ConsentPurpose[] = ["APAAR_LINK", "NOTICE", "CREDENTIAL_SHARE"];
const KINDS: DataRequestKind[] = ["ACCESS", "CORRECTION", "ERASURE"];

/** A section that loads and fails on its own, so the page never blanks (W3-3). */
function SectionFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-check-fail/30 bg-paper-raised px-4 py-3">
      <p>{t("err.tile_failed")}</p>
      <button type="button" className="inline-flex h-11 items-center gap-2 font-medium text-ink-blue" onClick={onRetry}>
        <RefreshCw className="size-4" aria-hidden="true" />
        {t("err.retry")}
      </button>
    </div>
  );
}

function SectionSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn("h-5", i % 2 ? "w-56" : "w-72")} />
      ))}
    </div>
  );
}

/* ---- Privacy notice ------------------------------------------------------ */

function NoticeDisclosure() {
  const notice = usePrivacyNotice();
  return (
    <Disclosure className="mt-4" summary={t("privacy.notice_link")}>
      <div className="mt-2 border-l-2 border-rule-margin bg-paper-raised px-4 py-4">
        {notice.isLoading && <SectionSkeleton />}
        {notice.isError && <SectionFailed onRetry={() => notice.refetch()} />}
        {notice.data && (
          <>
            <h2 className="text-xl">{notice.data.title || t("privacy.notice_heading")}</h2>
            <p className="mt-1 text-sm text-ink-muted">{t("privacy.notice_version", { version: notice.data.version, date: formatDate(notice.data.effective_from) })}</p>
            {notice.data.sections.map((s) => (
              <section key={s.id} className="mt-4">
                <h3 className="font-sans text-md font-semibold">{s.heading}</h3>
                <p className="mt-1">{s.body}</p>
              </section>
            ))}
          </>
        )}
      </div>
    </Disclosure>
  );
}

/* ---- Consents ------------------------------------------------------------ */

function ConsentState({ c }: { c: ConsentCurrent }) {
  const date = formatDate(c.since);
  switch (c.status) {
    case "GIVEN":
      return (
        <StatusWord tone="ok" icon={Check}>
          {c.purpose === "CREDENTIAL_SHARE" ? t("privacy.consent_last", { date }) : t("privacy.consent_status", { state_word: t("consent_state.GIVEN"), date })}
        </StatusWord>
      );
    case "WITHDRAWN":
      return (
        <StatusWord tone="neutral" icon={Minus}>
          {t("privacy.withdrawn_on", { date })}
        </StatusWord>
      );
    case "REFUSED":
      return (
        <StatusWord tone="neutral" icon={Link2Off}>
          {t("privacy.consent_status", { state_word: t("consent_state.REFUSED"), date })}
        </StatusWord>
      );
    default:
      return (
        <StatusWord tone="neutral" icon={Minus}>
          {t("privacy.consent_state_none")}
        </StatusWord>
      );
  }
}

function ConsentBlock({
  c,
  latest,
  onWithdraw,
  onUnlink,
}: {
  c: ConsentCurrent;
  latest: ConsentRow | undefined;
  onWithdraw: (purpose: "NOTICE" | "CREDENTIAL_SHARE") => void;
  onUnlink: () => void;
}) {
  return (
    <li className="border-b border-rule py-4">
      <h3 className="font-sans text-md font-semibold">{tk(`consent_purpose.${c.purpose}`)}</h3>
      <div className="mt-1.5">
        <ConsentState c={c} />
      </div>
      {c.status !== "NONE" && <p className="mt-1.5 text-ink-muted">{tk(`privacy.consent_via.${c.purpose}`)}</p>}
      {latest && (
        <Disclosure summary={t("privacy.consent_text_show")} className="mt-1">
          <blockquote className="mt-1 border-l-2 border-line bg-paper px-3 py-2">
            <p>{latest.notice_text}</p>
            <p className="mt-1 text-sm text-ink-muted">{t("privacy.consent_version", { version: latest.notice_version })}</p>
          </blockquote>
        </Disclosure>
      )}
      {c.purpose === "APAAR_LINK" ? (
        c.status !== "NONE" && (
          <>
            <p className="mt-2">{t("consent.unlink_apaar")}</p>
            <button type="button" className={cn(outlineButton, "mt-3 md:w-auto")} onClick={onUnlink}>
              {t("privacy.unlink_apaar")}
            </button>
          </>
        )
      ) : (
        c.can_withdraw &&
        c.status !== "WITHDRAWN" && (
          <button type="button" className={cn(outlineButton, "mt-3 md:w-auto")} onClick={() => onWithdraw(c.purpose as "NOTICE" | "CREDENTIAL_SHARE")}>
            {t("privacy.withdraw")}
          </button>
        )
      )}
    </li>
  );
}

function Consents({ onUnlink }: { onUnlink: (institution: string, enrolmentId: string | undefined) => void }) {
  const consents = useConsents();
  const withdraw = useWithdrawConsent();
  const me = useStudentMe();
  const [asking, setAsking] = React.useState<"NOTICE" | "CREDENTIAL_SHARE" | null>(null);
  const [done, setDone] = React.useState("");
  const keep = React.useRef<HTMLButtonElement>(null);
  const data = consents.data;
  const latest = (purpose: ConsentPurpose) => data?.items.find((r) => r.purpose === purpose);

  const confirm = () => {
    if (!asking || withdraw.isPending) return;
    const purpose = asking;
    withdraw.mutate(purpose, {
      onSuccess: () => {
        setAsking(null);
        setDone(tk(`privacy.withdraw_done.${purpose}`));
      },
    });
  };

  return (
    <section aria-labelledby="consents-heading" className="mt-10">
      <h2 id="consents-heading" className="text-2xl">
        {t("privacy.consents_heading")}
      </h2>
      <p className="sr-only" aria-live="polite">
        {done}
      </p>
      {done && <p className="mt-3 border-l-2 border-check-pass bg-check-pass-soft px-4 py-2 text-check-pass-ink">{done}</p>}
      <div className="mt-3">
        {consents.isLoading && <SectionSkeleton lines={6} />}
        {consents.isError && !data && <SectionFailed onRetry={() => consents.refetch()} />}
        {data && data.items.length === 0 && data.current.every((c) => c.status === "NONE") && <p className="text-ink-muted">{t("privacy.consent_none")}</p>}
        {data && (data.items.length > 0 || data.current.some((c) => c.status !== "NONE")) && (
          <ul className="border-t border-rule">
            {PURPOSES.map((p) => data.current.find((c) => c.purpose === p))
              .filter((c): c is ConsentCurrent => Boolean(c))
              .map((c) => (
                <ConsentBlock
                  key={c.purpose}
                  c={c}
                  latest={latest(c.purpose)}
                  onWithdraw={setAsking}
                  onUnlink={() => {
                    const row = latest("APAAR_LINK");
                    const institution = row?.enrolment?.institution_name ?? me.data?.enrolments[0]?.institution_name ?? "";
                    onUnlink(institution, row?.enrolment?.id ?? me.data?.enrolments[0]?.id);
                  }}
                />
              ))}
          </ul>
        )}
      </div>
      <SheetDialog
        open={asking !== null}
        onOpenChange={(o) => {
          if (!o && !withdraw.isPending) {
            setAsking(null);
            withdraw.reset();
          }
        }}
        title={asking ? tk(`consent_purpose.${asking}`) : ""}
        description={asking ? tk(`consent.withdraw.${asking}`) : ""}
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          keep.current?.focus();
        }}
        footer={
          <div className="flex flex-col gap-3 md:flex-row-reverse">
            <button ref={keep} type="button" className={cn(primaryButton, "md:w-auto")} onClick={() => setAsking(null)} disabled={withdraw.isPending}>
              {t("privacy.withdraw_cancel")}
            </button>
            <button type="button" className={cn(outlineButton, "md:w-auto")} onClick={confirm} disabled={withdraw.isPending}>
              {t("privacy.withdraw_confirm")}
            </button>
          </div>
        }
      >
        {withdraw.isError ? (
          <p role="alert" className="text-check-fail-ink">
            {deckError(withdraw.error)} <span className="code text-xs text-ink-muted">{t("err.ref", { code: errorCodeOf(withdraw.error) })}</span>
          </p>
        ) : null}
      </SheetDialog>
    </section>
  );
}

/* ---- Access log ---------------------------------------------------------- */

function whoWord(row: AccessLogRow): string {
  switch (row.role) {
    case "VERIFIER":
      return t("privacy.access.verifier");
    case "NOTICE_LINK":
      return t("privacy.access.notice_link");
    case "SYSTEM":
      return t("privacy.access.SYSTEM");
    default:
      return tk(`privacy.access.${row.role}`);
  }
}

function AccessRows({ page, onTotal }: { page: number; onTotal?: (total: number) => void }) {
  const log = useAccessLog(page);
  const total = log.data?.total;
  React.useEffect(() => {
    if (total !== undefined) onTotal?.(total);
  }, [total, onTotal]);
  if (log.isLoading)
    return (
      <tr aria-hidden="true">
        <td>
          <Skeleton className="h-4 w-24" />
        </td>
        <td>
          <Skeleton className="h-4 w-40" />
        </td>
      </tr>
    );
  if (log.isError)
    return (
      <tr>
        <td colSpan={2} className="!h-auto !whitespace-normal !p-0">
          <SectionFailed onRetry={() => log.refetch()} />
        </td>
      </tr>
    );
  return (
    <>
      {(log.data?.items ?? []).map((row, i) => (
        <tr key={`${page}-${i}`}>
          <td>{formatDate(row.at)}</td>
          <td className="wrap">{whoWord(row)}</td>
        </tr>
      ))}
    </>
  );
}

function AccessLog() {
  const [pages, setPages] = React.useState(1);
  const [total, setTotal] = React.useState<number | null>(null);
  return (
    <section aria-labelledby="access-heading" className="mt-10">
      <h2 id="access-heading" className="text-2xl">
        {t("privacy.access_heading")}
      </h2>
      <p className="mt-2 text-ink-muted">{t("privacy.access_lead")}</p>
      {total === 0 ? (
        <p className="mt-3 text-ink-muted">{t("privacy.access_empty")}</p>
      ) : (
        <table className="ledger-table mt-3 w-full">
          <thead>
            <tr>
              <th scope="col" className="w-36">
                {t("privacy.access.col.date")}
              </th>
              <th scope="col">{t("privacy.access.col.who")}</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: pages }, (_, i) => (
              <AccessRows key={i} page={i + 1} onTotal={i === 0 ? setTotal : undefined} />
            ))}
          </tbody>
        </table>
      )}
      {total !== null && total > pages * 25 && (
        <button type="button" className={cn(outlineButton, "mt-3 h-11 md:w-auto")} onClick={() => setPages((p) => p + 1)}>
          {t("privacy.access.more")}
        </button>
      )}
    </section>
  );
}

/* ---- Data requests ------------------------------------------------------- */

function RequestStatus({ row }: { row: DataRequestRow }) {
  if (row.status === "OPEN")
    return (
      <StatusWord tone="caution" icon={Clock}>
        {t("data_request_status.OPEN")}
      </StatusWord>
    );
  if (row.status === "DONE")
    return (
      <StatusWord tone="ok" icon={Check}>
        {t("data_request_status.DONE")}
      </StatusWord>
    );
  return (
    <StatusWord tone="neutral" icon={X}>
      {t("data_request_status.REJECTED")}
    </StatusWord>
  );
}

/** The export link: a real link to the file, fetched in place so a failure shows as a message. */
function ExportLink() {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<unknown>(null);
  const path = "/students/me/export.json";
  return (
    <div className="mt-3">
      <a
        href={`${API_BASE}${path}`}
        download="countersign-my-data.json"
        className={cn(primaryButton, "no-underline md:w-auto", busy && "pointer-events-none opacity-60")}
        aria-disabled={busy || undefined}
        onClick={(e) => {
          e.preventDefault();
          if (busy) return;
          setBusy(true);
          setError(null);
          api
            .download(path, "countersign-my-data.json")
            .catch((err: unknown) => setError(err))
            .finally(() => setBusy(false));
        }}
      >
        <Download className="size-5" aria-hidden="true" />
        {busy ? t("privacy.export_preparing") : t("privacy.export_download")}
      </a>
      {error ? (
        <p role="alert" className="mt-2 text-check-fail-ink">
          {deckError(error)}
        </p>
      ) : null}
    </div>
  );
}

export interface RequestDraft {
  kind: DataRequestKind;
  details: string;
  enrolmentId?: string;
}

function RequestForm({ draft, onDone, onCancel }: { draft: RequestDraft; onDone: (row: DataRequestRow) => void; onCancel: () => void }) {
  const create = useCreateDataRequest();
  const [kind, setKind] = React.useState<DataRequestKind>(draft.kind);
  const [details, setDetails] = React.useState(draft.details);
  const [missing, setMissing] = React.useState(false);
  const detailsRef = React.useRef<HTMLTextAreaElement>(null);
  const first = React.useRef<HTMLInputElement>(null);
  const required = kind !== "ACCESS";

  React.useEffect(() => {
    if (draft.details) detailsRef.current?.focus();
    else first.current?.focus();
  }, [draft]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (create.isPending) return;
    if (required && details.trim().length < 10) {
      setMissing(true);
      detailsRef.current?.focus();
      return;
    }
    create.mutate(
      { kind, details: details.trim() || undefined, enrolment_id: draft.enrolmentId },
      { onSuccess: (row) => onDone(row) },
    );
  };

  const apiDetailsError = create.error instanceof ApiError ? create.error.fields.find((f) => f.field === "details") : undefined;
  const showMissing = missing || Boolean(apiDetailsError);

  return (
    <form onSubmit={submit} noValidate className="mt-4 border-l-2 border-rule-margin bg-paper-raised px-4 py-4 md:px-5">
      <fieldset>
        <legend className="font-sans text-lg font-semibold">{t("privacy.request.kind_label")}</legend>
        <div className="mt-2 flex flex-col">
          {KINDS.map((k, i) => (
            <label key={k} className="flex cursor-pointer items-start gap-3 border-b border-rule py-3 last:border-b-0">
              <input
                ref={i === 0 ? first : undefined}
                type="radio"
                name="request-kind"
                value={k}
                checked={kind === k}
                onChange={() => {
                  setKind(k);
                  setMissing(false);
                }}
                aria-describedby={`kind-hint-${k}`}
                className="mt-1 size-5 shrink-0 accent-[var(--ink-blue)]"
              />
              <span>
                <span className="block font-medium">{tk(`privacy.request.kind.${k}`)}</span>
                <span id={`kind-hint-${k}`} className="block text-ink-muted">
                  {tk(`privacy.request.kind_hint.${k}`)}
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <label htmlFor="request-details" className="mt-4 block font-medium">
        {tk(`privacy.request.details.${kind}`)}
      </label>
      <textarea
        ref={detailsRef}
        id="request-details"
        rows={4}
        maxLength={2000}
        value={details}
        aria-required={required || undefined}
        aria-invalid={showMissing || undefined}
        aria-describedby={showMissing ? "request-details-error" : undefined}
        onChange={(e) => {
          setDetails(e.target.value);
          if (e.target.value.trim().length >= 10) setMissing(false);
        }}
        className="mt-2 block w-full rounded-md border border-line bg-paper px-3 py-2 text-md aria-invalid:border-check-fail"
      />
      {showMissing && (
        <p id="request-details-error" className="mt-1 text-sm text-check-fail-ink">
          {t("privacy.request.details_required")}
        </p>
      )}
      {create.isError && !apiDetailsError && (
        <p role="alert" className="mt-3 text-check-fail-ink">
          {deckError(create.error)} <span className="code text-xs text-ink-muted">{t("err.ref", { code: errorCodeOf(create.error) })}</span>
        </p>
      )}
      <div className="mt-4 flex flex-col gap-3 md:flex-row">
        <button type="submit" className={cn(primaryButton, "md:w-auto")} disabled={create.isPending}>
          {create.isPending ? t("privacy.request.sending") : t("privacy.request.submit")}
        </button>
        <button type="button" className={cn(bigButton, "text-ink-blue underline md:w-auto")} onClick={onCancel}>
          {t("privacy.request.cancel")}
        </button>
      </div>
    </form>
  );
}

function Requests({ draft, setDraft }: { draft: RequestDraft | null; setDraft: (d: RequestDraft | null) => void }) {
  const list = useDataRequests();
  const [exportReady, setExportReady] = React.useState(false);
  const [sent, setSent] = React.useState("");
  const newButton = React.useRef<HTMLButtonElement>(null);
  const rows = list.data?.items ?? [];
  return (
    <section aria-labelledby="requests-heading" className="mt-10">
      <h2 id="requests-heading" className="text-2xl">
        {t("privacy.requests_heading")}
      </h2>
      <p className="mt-2 text-ink-muted">{t("privacy.requests_lead")}</p>
      <p className="sr-only" aria-live="polite">
        {sent}
      </p>

      {exportReady ? (
        <div className="mt-4 border-l-2 border-check-pass bg-paper-raised px-4 py-4">
          <p className="font-semibold">{t("privacy.export_ready")}</p>
          <ExportLink />
          <p className="mt-3 text-ink-muted">{t("privacy.export_note")}</p>
        </div>
      ) : draft ? (
        <RequestForm
          key={`${draft.kind}-${draft.details}`}
          draft={draft}
          onCancel={() => {
            setDraft(null);
            requestAnimationFrame(() => newButton.current?.focus());
          }}
          onDone={(row) => {
            setDraft(null);
            if (row.kind === "ACCESS") setExportReady(true);
            else {
              setSent(t("privacy.request.sent"));
              requestAnimationFrame(() => newButton.current?.focus());
            }
          }}
        />
      ) : (
        <>
          {sent && <p className="mt-3 border-l-2 border-check-pass bg-check-pass-soft px-4 py-2 text-check-pass-ink">{sent}</p>}
          <button
            ref={newButton}
            type="button"
            className={cn(primaryButton, "mt-4 md:w-auto")}
            onClick={() => {
              setSent("");
              setDraft({ kind: "ACCESS", details: "" });
            }}
          >
            {t("privacy.request.new")}
          </button>
        </>
      )}

      <div className="mt-5">
        {list.isLoading && <SectionSkeleton />}
        {list.isError && !list.data && <SectionFailed onRetry={() => list.refetch()} />}
        {list.data && rows.length === 0 && <p className="text-ink-muted">{t("privacy.request.none")}</p>}
        {rows.length > 0 && (
          <ul className="border-t border-rule">
            {rows.map((r) => (
              <li key={r.id} className="border-b border-rule py-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-medium">{t("privacy.request.row", { kind_word: tk(`data_request_kind.${r.kind}`), date: formatDate(r.created_at) })}</span>
                  <RequestStatus row={r} />
                </div>
                {r.details && <p className="mt-1 text-ink-muted">{r.details}</p>}
                {r.status === "OPEN" && <p className="mt-1">{t("privacy.request.waiting")}</p>}
                {r.status !== "OPEN" && r.response && r.kind !== "ACCESS" && (
                  <div className="mt-2 border-l-2 border-line bg-paper px-3 py-2">
                    <p className="text-sm font-medium">{t("privacy.request.reply", { date: formatDate(r.resolved_at) })}</p>
                    <p>{r.response}</p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/** W3-3 Privacy: what the student agreed to, who viewed their record, and requests about their data (D30). */
export function PrivacyPage() {
  const [draft, setDraft] = React.useState<RequestDraft | null>(null);
  return (
    <div className="text-md">
      <Crumbs items={[{ label: t("nav.my_enrolment"), href: "/student" }, { label: t("privacy.heading") }]} />
      <h1 className="text-3xl">{t("privacy.heading")}</h1>
      <p className="mt-2 text-ink-muted">{t("privacy.lead")}</p>
      <NoticeDisclosure />
      <Consents
        onUnlink={(institution, enrolmentId) => {
          setDraft({ kind: "CORRECTION", details: t("privacy.request.unlink_prefill", { institution_name: institution }), enrolmentId });
          requestAnimationFrame(() => document.getElementById("requests-heading")?.scrollIntoView({ block: "start" }));
        }}
      />
      <AccessLog />
      <Requests draft={draft} setDraft={setDraft} />
    </div>
  );
}
