"use client";

import * as React from "react";
import { CircleCheck, CircleMinus, Clock, Inbox, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { EmptyState } from "@/components/brand/EmptyState";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useDataRequests, useResolveDataRequest } from "@/lib/queries-cases";
import type { DataRequestAdminRow, DataRequestKind, DataRequestStatus } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { FilterSelect } from "@/components/common/filter-select";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage, errorMessage } from "@/components/common/query-state";
import { Pager } from "@/components/common/pager";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { useMe } from "@/components/providers/root-provider";

const PAGE_SIZE = 25;
const STATUSES: DataRequestStatus[] = ["OPEN", "DONE", "REJECTED"];
/** An Access request is fulfilled at once and never waits in this queue. */
const KINDS: DataRequestKind[] = ["CORRECTION", "ERASURE"];

const STATUS_STYLE: Record<DataRequestStatus, { Icon: typeof Clock; chip: string }> = {
  OPEN: { Icon: Clock, chip: "border-check-pending/50 bg-check-pending-soft text-check-pending-ink" },
  DONE: { Icon: CircleCheck, chip: "border-line bg-paper text-ink" },
  REJECTED: { Icon: CircleMinus, chip: "border-check-na/50 bg-check-na-soft text-check-na-ink" },
};

/** Request status as a word with its glyph, never colour alone. */
function StatusChip({ status }: { status: DataRequestStatus }) {
  const { Icon, chip } = STATUS_STYLE[status];
  return (
    <span className={cn("inline-flex h-5 items-center gap-1 rounded-chip border px-1.5 text-xs leading-none font-medium whitespace-nowrap", chip)}>
      <Icon className="size-3 shrink-0" aria-hidden="true" />
      {tk(`data_request_status.${status}`)}
    </span>
  );
}

const asksToUnlink = (text: string | null) => Boolean(text && /unlink/i.test(text) && /apaar/i.test(text));

/**
 * Resolve one request (W3-9): what the student asked, the hint for its kind,
 * Done or Decline, and a written reply the student reads on their Privacy
 * page. An erasure starts from the statutory retention reply.
 */
function ResolveSheet({ row, onClose, returnFocus }: { row: DataRequestAdminRow | null; onClose: () => void; returnFocus: () => void }) {
  const resolve = useResolveDataRequest();
  const { user } = useMe();
  const [outcome, setOutcome] = React.useState<"DONE" | "REJECTED">("DONE");
  const [reply, setReply] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);
  const replyRef = React.useRef<HTMLTextAreaElement>(null);
  const ids = React.useId();

  const [shown, setShown] = React.useState<string | null>(row?.id ?? null);
  if ((row?.id ?? null) !== shown) {
    setShown(row?.id ?? null);
    if (row) {
      setOutcome("DONE");
      setReply(row.kind === "ERASURE" ? `${t("admin.requests.erasure_reply")} ` : "");
      setError(null);
      setFormError(null);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!row || resolve.isPending) return;
    const text = reply.trim();
    if (text.length < 10 || (row.kind === "ERASURE" && text === t("admin.requests.erasure_reply"))) {
      setError(t("admin.requests.response_required"));
      replyRef.current?.focus();
      return;
    }
    setError(null);
    setFormError(null);
    resolve.mutate(
      { id: row.id, body: { status: outcome, response: text } },
      {
        onSuccess: () => {
          toast(t("admin.requests.resolved_toast"));
          onClose();
        },
        onError: (err) => {
          const field = err instanceof ApiError ? err.fields.find((f) => f.field === "response") : undefined;
          if (field) {
            setError(field.message);
            replyRef.current?.focus();
            return;
          }
          setFormError(errorMessage(err, user?.role));
        },
      },
    );
  }

  const hintId = `${ids}-hint`;
  const errId = `${ids}-error`;
  return (
    <Dialog open={row !== null} onOpenChange={(next) => !next && !resolve.isPending && onClose()}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] gap-5 overflow-y-auto bg-paper-raised sm:max-w-xl"
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          replyRef.current?.focus();
        }}
        onCloseAutoFocus={(e) => {
          e.preventDefault();
          returnFocus();
        }}
      >
        {row && (
          <form onSubmit={submit} noValidate className="flex flex-col gap-5">
            <div className="flex flex-col gap-2 pr-6">
              <DialogTitle className="font-display text-xl font-semibold">{t("admin.requests.resolve_heading")}</DialogTitle>
              <DialogDescription asChild>
                <div className="flex flex-col gap-2 text-sm text-ink">
                  <p className="text-ink-muted">
                    {t("admin.requests.request_line", {
                      student_name: row.student.name,
                      kind_word: tk(`data_request_kind.${row.kind}`).toLowerCase(),
                      date: formatDate(row.created_at),
                    })}
                  </p>
                  {row.details && <p className="max-w-[68ch] text-base [overflow-wrap:anywhere] md:text-md">&ldquo;{row.details}&rdquo;</p>}
                  {row.enrolment && (
                    <p className="text-xs text-ink-muted">
                      {row.enrolment.institution_name}, {row.enrolment.programme_name}, {row.enrolment.academic_year}
                    </p>
                  )}
                </div>
              </DialogDescription>
            </div>

            <div className="flex flex-col gap-2 border-l-2 border-rule-margin pl-3 text-sm">
              {row.kind === "CORRECTION" && <p>{t("admin.requests.correction_hint")}</p>}
              {row.kind === "CORRECTION" && asksToUnlink(row.details) && <p>{t("admin.requests.unlink_hint")}</p>}
              {row.kind === "ERASURE" && <p>{t("admin.requests.erasure_retention")}</p>}
            </div>

            <fieldset className="flex flex-col gap-2">
              <legend className="mb-1 text-sm font-medium">{t("admin.requests.outcome")}</legend>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                {(["DONE", "REJECTED"] as const).map((o) => (
                  <label key={o} className="inline-flex min-h-11 cursor-pointer items-center gap-2 text-sm md:min-h-8">
                    <input
                      type="radio"
                      name={`${ids}-outcome`}
                      value={o}
                      checked={outcome === o}
                      onChange={() => setOutcome(o)}
                      disabled={resolve.isPending}
                      className="size-4 accent-[var(--ink-blue)]"
                    />
                    {t(`admin.requests.outcome.${o}`)}
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="flex flex-col gap-1.5">
              <label htmlFor={`${ids}-reply`} className="text-sm font-medium">
                {t("admin.requests.response_label")}
              </label>
              <p id={hintId} className="text-sm text-ink-muted">
                {t("admin.requests.response_hint")}
              </p>
              <textarea
                ref={replyRef}
                id={`${ids}-reply`}
                value={reply}
                onChange={(e) => {
                  setReply(e.target.value);
                  if (error && e.target.value.trim().length >= 10) setError(null);
                }}
                rows={row.kind === "ERASURE" ? 7 : 5}
                maxLength={2000}
                aria-required="true"
                aria-invalid={error ? true : undefined}
                aria-describedby={[hintId, error ? errId : null].filter(Boolean).join(" ")}
                disabled={resolve.isPending}
                className="min-h-28 w-full rounded-md border border-line bg-paper px-2.5 py-2 text-base leading-snug aria-invalid:border-check-fail md:text-sm"
              />
              {error && (
                <p id={errId} className="text-sm text-check-fail-ink">
                  {error}
                </p>
              )}
            </div>

            <div aria-live="polite">
              {formError && (
                <p role="alert" className="rounded-md border border-check-fail/30 bg-paper px-3 py-2 text-sm">
                  {formError}
                </p>
              )}
            </div>

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" className="h-11 sm:h-9" onClick={onClose} disabled={resolve.isPending}>
                {t("case.cancel")}
              </Button>
              <Button type="submit" className="h-11 sm:h-9" aria-busy={resolve.isPending} disabled={resolve.isPending}>
                {resolve.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                {resolve.isPending ? t("admin.requests.sending") : t("admin.requests.submit")}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

/**
 * /admin/data-requests (page spec W3-9): students' correction and erasure
 * requests, open first and oldest first, each resolved with a written reply.
 */
export function DataRequestsPage() {
  const [params, set] = useUrlParams();
  const rawStatus = params.get("r_status");
  const status = (rawStatus === "ALL" ? "" : (rawStatus ?? "OPEN")) as DataRequestStatus | "";
  const kind = (params.get("r_kind") ?? "") as DataRequestKind | "";
  const page = Math.max(1, Number(params.get("r_page") ?? 1) || 1);
  const list = useDataRequests({ page, page_size: PAGE_SIZE, status: status || undefined, kind: kind || undefined });
  const data = list.data;
  const rows = data?.items ?? [];
  const [resolving, setResolving] = React.useState<DataRequestAdminRow | null>(null);
  const opener = React.useRef<HTMLButtonElement | null>(null);
  const heading = React.useRef<HTMLDivElement>(null);

  const filtered = Boolean(kind || status !== "OPEN");
  const clearAll = () => set({ r_status: null, r_kind: null, r_page: null });
  // A row resolved here stays in view with its new status; it no longer counts under the Open filter.
  const total = data ? data.total - (status ? rows.filter((r) => r.status !== status).length : 0) : 0;
  const countId = status === "OPEN" ? "admin.requests.count" : "admin.requests.count_any";
  const count = data ? (total === 1 ? t(countId, { total: 1 }).replace("requests", "request") : t(countId, { total: formatCount(total) })) : " ";
  const cols = 7;

  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: "/aicte" }, { label: t("nav.data_requests") }]} />
      <div ref={heading} tabIndex={-1} className="outline-none">
        <PageHeader title={t("admin.requests.heading")} description={<p className="max-w-[68ch]">{t("admin.requests.lead")}</p>} />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <FilterSelect
          label={t("admin.requests.filter.status")}
          value={status}
          options={STATUSES.map((s) => ({ value: s, label: tk(`data_request_status.${s}`) }))}
          allLabel={t("flags.filter.all")}
          onChange={(v) => set({ r_status: v === "" ? "ALL" : v === "OPEN" ? null : v, r_page: null })}
        />
        <FilterSelect
          label={t("admin.requests.filter.kind")}
          value={kind}
          options={KINDS.map((k) => ({ value: k, label: tk(`data_request_kind.${k}`) }))}
          allLabel={t("flags.filter.all")}
          onChange={(v) => set({ r_kind: v, r_page: null })}
        />
        {filtered && (
          <Button variant="link" size="sm" className="h-8 px-0" onClick={clearAll}>
            {t("empty.clear_filters")}
          </Button>
        )}
      </div>

      <p className="mb-2 text-sm font-medium" aria-live="polite">
        {count}
      </p>
      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("admin.requests.heading")}</caption>
          <thead>
            <tr>
              <th scope="col" className="num">
                {t("admin.requests.col.received")}
              </th>
              <th scope="col">{t("admin.requests.col.kind")}</th>
              <th scope="col">{t("admin.requests.col.student")}</th>
              <th scope="col">{t("admin.requests.col.details")}</th>
              <th scope="col">{t("admin.requests.col.status")}</th>
              <th scope="col" className="num hidden xl:table-cell">
                {t("admin.requests.col.resolved")}
              </th>
              <th scope="col">
                <span className="sr-only">{t("admin.requests.resolve")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading && <SkeletonRows cols={cols} rows={5} />}
            {list.isError && !data && (
              <TableMessage cols={cols}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={cols}>
                <EmptyState
                  icon={<Inbox className="size-5" />}
                  title={filtered ? t("admin.requests.empty_filtered") : t("admin.requests.empty")}
                  action={
                    filtered ? (
                      <Button variant="outline" size="sm" onClick={clearAll}>
                        {t("empty.clear_filters")}
                      </Button>
                    ) : undefined
                  }
                />
              </TableMessage>
            )}
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="num !h-auto py-2 align-top text-ink-muted">{formatDate(r.created_at)}</td>
                <td className="!h-auto py-2 align-top">{tk(`data_request_kind.${r.kind}`)}</td>
                <td className="!h-auto py-2 align-top">
                  <span className="block font-medium">{r.student.name}</span>
                  <MaskedApaar apaarMasked={r.student.apaar_masked} provisionalId={r.student.provisional_id} className="text-xs" />
                </td>
                <td className="wrap !h-auto min-w-[13rem] py-2 align-top leading-snug [overflow-wrap:anywhere] xl:min-w-[18rem]">{r.details}</td>
                <td className="!h-auto py-2 align-top">
                  <StatusChip status={r.status} />
                  {r.resolved_at && (
                    // Below 1280 px the resolved date sits under the status instead of in its own column.
                    <span className="mt-1 block text-xs whitespace-nowrap text-ink-muted xl:hidden">
                      {t("admin.requests.col.resolved")} {formatDate(r.resolved_at)}
                    </span>
                  )}
                </td>
                <td className="num hidden !h-auto py-2 align-top text-ink-muted xl:table-cell">{r.resolved_at ? formatDate(r.resolved_at) : ""}</td>
                <td className="!h-auto py-1.5 align-top">
                  {r.status === "OPEN" && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-11 md:h-8"
                      aria-label={t("admin.requests.resolve_for", { student_name: r.student.name })}
                      onClick={(e) => {
                        opener.current = e.currentTarget;
                        setResolving(r);
                      }}
                    >
                      {t("admin.requests.resolve")}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <ReadLoggedNote />
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ r_page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
      <ResolveSheet
        row={resolving}
        onClose={() => setResolving(null)}
        returnFocus={() => {
          const el = opener.current;
          if (el && el.isConnected) el.focus();
          else heading.current?.focus();
        }}
      />
    </>
  );
}
