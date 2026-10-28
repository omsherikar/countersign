"use client";

import * as React from "react";
import { Loader2, ScrollText, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDateTime } from "@/lib/format";
import { useAuditVerify } from "@/lib/queries";
import { useAudit, useOfficers } from "@/lib/queries-cases";
import type { AuditAction, AuditListQuery, AuditRow } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { FilterSelect } from "@/components/common/filter-select";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { Pager } from "@/components/common/pager";

const PAGE_SIZE = 25;
const ACTIONS: AuditAction[] = ["CREATE", "UPDATE", "DELETE", "READ", "LOGIN", "LOGOUT", "SEED"];
/** Entity types the api writes (ENGINES section 12 and A3.23), printed as stored. */
const ENTITIES = [
  "approval",
  "case_attachment",
  "check",
  "consent",
  "credential",
  "credential_presentation",
  "data_request",
  "enrolment",
  "flag",
  "institution",
  "notification",
  "programme",
  "seat",
  "student",
  "upload_batch",
  "user",
];
const PUBLIC_VERIFIER = ["verifier", "verifier-paste", "degree-qr", "degree-lookup"];

/** Actor in words: the email, or how a public page or the seed reached the record (deck section 12). */
function actorWord(row: AuditRow): string {
  if (row.actor_email) return row.actor_email;
  if (row.via === "notice-link") return t("audit.via.notice_link");
  if (row.via && PUBLIC_VERIFIER.includes(row.via)) return t("audit.via.verifier");
  if (row.via === "demo-seed") return t("audit.via.demo_seed");
  return t("audit.actor_system");
}

/** First 8 characters in monospace, the full value on hover and on focus. */
function Short({ value, tip }: { value: string | null; tip?: string }) {
  if (!value) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="code rounded-chip" aria-label={tip ?? value}>
          {value.slice(0, 8)}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-80 font-mono text-xs break-all">{tip ?? value}</TooltipContent>
    </Tooltip>
  );
}

/** A text filter applied on Enter, so typing a long id does not fire a request per key. */
function EnterInput({
  label,
  value,
  onApply,
  inputMode,
  className,
}: {
  label: string;
  value: string;
  onApply: (v: string) => void;
  inputMode?: "numeric" | "text";
  className?: string;
}) {
  const id = React.useId();
  const [text, setText] = React.useState(value);
  const [synced, setSynced] = React.useState(value);
  if (value !== synced) {
    setSynced(value);
    setText(value);
  }
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <label htmlFor={id} className="text-xs font-medium whitespace-nowrap text-ink-muted">
        {label}
      </label>
      <input
        id={id}
        type="text"
        inputMode={inputMode}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onApply(text.trim());
          if (e.key === "Escape") {
            setText("");
            onApply("");
          }
        }}
        onBlur={() => text.trim() !== value && onApply(text.trim())}
        className="code h-8 w-full min-w-0 rounded-md border border-line bg-paper-raised px-2.5 text-sm"
      />
    </div>
  );
}

/**
 * /admin/audit (page spec W3-6): every change and every view of student
 * records, newest first, with filters in the URL and Verify chain. A broken
 * chain names the first entry that no longer matches its hash; Show entry
 * opens the page around it, marks the row with an icon and words, scrolls
 * to it and moves focus there.
 */
export function AuditPage() {
  const [params, set] = useUrlParams();
  const entity = params.get("a_entity") ?? "";
  const action = (params.get("a_action") ?? "") as AuditAction | "";
  const actor = params.get("a_actor") ?? "";
  const entityId = params.get("a_entity_id") ?? "";
  const seqFrom = params.get("a_seq_from") ?? "";
  const page = Math.max(1, Number(params.get("a_page") ?? 1) || 1);

  const query: AuditListQuery = {
    page,
    page_size: PAGE_SIZE,
    entity_type: entity || undefined,
    action: action || undefined,
    actor_id: actor || undefined,
    entity_id: entityId || undefined,
    seq_from: seqFrom && Number.isFinite(Number(seqFrom)) ? Number(seqFrom) : undefined,
  };
  const list = useAudit(query);
  const verify = useAuditVerify();
  const officers = useOfficers();
  const data = list.data;
  const rows = React.useMemo(() => data?.items ?? [], [data]);
  const broken = verify.data && !verify.data.ok ? verify.data.first_broken_seq : null;

  const filtered = Boolean(entity || action || actor || entityId || seqFrom);
  const clearAll = () => set({ a_entity: null, a_action: null, a_actor: null, a_entity_id: null, a_seq_from: null, a_page: null });

  // Officers by name, plus anyone else acting on this page by email.
  const actorOptions = React.useMemo(() => {
    const seen = new Map<string, string>();
    for (const o of officers.data ?? []) seen.set(o.id, o.name);
    for (const r of rows) if (r.actor_id && r.actor_email && !seen.has(r.actor_id)) seen.set(r.actor_id, r.actor_email);
    if (actor && !seen.has(actor)) seen.set(actor, actor.slice(0, 8));
    return [...seen.entries()].map(([value, label]) => ({ value, label }));
  }, [officers.data, rows, actor]);

  const focusSeq = React.useRef<number | null>(null);
  const tbody = React.useRef<HTMLTableSectionElement>(null);
  React.useEffect(() => {
    const seq = focusSeq.current;
    if (seq === null || !data) return;
    const row = tbody.current?.querySelector<HTMLTableRowElement>(`tr[data-seq="${seq}"]`);
    if (!row) return;
    focusSeq.current = null;
    row.scrollIntoView({ block: "center" });
    row.focus({ preventScroll: true });
  }, [data]);

  function showEntry(seq: number) {
    const here = tbody.current?.querySelector<HTMLTableRowElement>(`tr[data-seq="${seq}"]`);
    if (here && seqFrom === String(seq + 10) && !entity && !action && !actor && !entityId) {
      here.scrollIntoView({ block: "center" });
      here.focus({ preventScroll: true });
      return;
    }
    focusSeq.current = seq;
    // The list is newest first; opening ten entries above the break keeps the rows before it in view.
    set({ a_entity: null, a_action: null, a_actor: null, a_entity_id: null, a_seq_from: seq + 10, a_page: null });
  }

  const cols = 7;
  const count = data ? (data.total === 1 ? t("audit.count", { total: 1 }).replace("entries", "entry") : t("audit.count", { total: formatCount(data.total) })) : " ";

  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: "/aicte" }, { label: t("nav.audit") }]} />
      <PageHeader title={t("audit.heading")} description={<p className="max-w-[68ch]">{t("audit.lead")}</p>} />

      <section aria-label={t("audit.verify")} className="mb-6 flex flex-col gap-3 border-l-2 border-rule-margin bg-paper-raised px-4 py-3 sm:flex-row sm:items-start sm:gap-5">
        <Button type="button" variant="outline" className="h-11 shrink-0 md:h-9" onClick={() => verify.mutate()} disabled={verify.isPending} aria-busy={verify.isPending}>
          {verify.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <ShieldCheck className="size-4" aria-hidden="true" />}
          {verify.isPending ? t("audit.verifying") : t("audit.verify")}
        </Button>
        <div aria-live="polite" className="min-w-0 flex-1 text-sm">
          {verify.isError && <ErrorBlock error={verify.error} onRetry={() => verify.mutate()} compact />}
          {!verify.isPending && verify.data?.ok && (
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1.5">
              <span className="inline-flex items-center gap-1.5 font-medium text-ink">
                <ShieldCheck className="size-4 text-check-pass" aria-hidden="true" />
                {t("audit.chain_ok", { n: formatCount(verify.data.length) })}
              </span>
              <span className="text-ink-muted">{t("audit.chain_checked", { time: formatDateTime(verify.data.checked_at) })}</span>
            </p>
          )}
          {!verify.isPending && verify.data && !verify.data.ok && broken !== null && (
            <div className="flex flex-col gap-2 pt-1.5">
              <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="inline-flex items-center gap-1.5 font-medium text-check-fail-ink">
                  <ShieldAlert className="size-4" aria-hidden="true" />
                  {t("audit.chain_broken", { seq: broken })}
                </span>
                <span className="text-ink-muted">{t("audit.chain_checked", { time: formatDateTime(verify.data.checked_at) })}</span>
              </p>
              <p className="max-w-[68ch] text-ink">{t("audit.chain_broken_detail", { seq: broken })}</p>
              <div>
                <Button type="button" variant="outline" size="sm" className="h-11 md:h-8" onClick={() => showEntry(broken)}>
                  {t("audit.show_entry", { seq: broken })}
                </Button>
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-2">
        <FilterSelect
          label={t("audit.filter.entity_type")}
          value={entity}
          options={ENTITIES.map((e) => ({ value: e, label: e }))}
          allLabel={t("audit.filter.all")}
          onChange={(v) => set({ a_entity: v, a_page: null })}
        />
        <FilterSelect
          label={t("audit.filter.action")}
          value={action}
          options={ACTIONS.map((a) => ({ value: a, label: tk(`audit_action.${a}`) }))}
          allLabel={t("audit.filter.all")}
          onChange={(v) => set({ a_action: v, a_page: null })}
        />
        <FilterSelect
          label={t("audit.filter.actor")}
          value={actor}
          options={actorOptions}
          allLabel={t("audit.filter.all")}
          onChange={(v) => set({ a_actor: v, a_page: null })}
        />
        <EnterInput label={t("audit.filter.entity_id")} value={entityId} onApply={(v) => set({ a_entity_id: v, a_page: null })} className="w-full sm:w-72" />
        <EnterInput label={t("audit.filter.seq_from")} value={seqFrom} inputMode="numeric" onApply={(v) => set({ a_seq_from: v.replace(/\D/g, ""), a_page: null })} className="w-48" />
        {filtered && (
          <Button variant="link" size="sm" className="h-8 px-0" onClick={clearAll}>
            {t("empty.clear_filters")}
          </Button>
        )}
      </div>
      <p className="mb-4 text-xs text-ink-muted">{t("audit.read_note")}</p>

      <p className="mb-2 text-sm font-medium" aria-live="polite">
        {count}
      </p>
      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table ledger-table--dense" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("audit.heading")}</caption>
          <thead>
            <tr>
              <th scope="col" className="num">
                {t("audit.col.seq")}
              </th>
              <th scope="col">{t("audit.col.at")}</th>
              <th scope="col">{t("audit.col.actor")}</th>
              <th scope="col">{t("audit.col.action")}</th>
              <th scope="col">{t("audit.col.entity")}</th>
              <th scope="col">{t("audit.col.entity_id")}</th>
              <th scope="col">{t("audit.col.hash")}</th>
            </tr>
          </thead>
          <tbody ref={tbody}>
            {list.isLoading && <SkeletonRows cols={cols} rows={12} />}
            {list.isError && !data && (
              <TableMessage cols={cols}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={cols}>
                <EmptyState
                  icon={<ScrollText className="size-5" />}
                  title={filtered ? t("empty.audit_filtered") : t("empty.audit")}
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
            {rows.map((r) => {
              const isBreak = broken === r.seq;
              return (
                <tr key={r.seq} data-seq={r.seq} tabIndex={isBreak ? -1 : undefined} className={cn(isBreak && "bg-check-fail-soft outline-offset-[-2px]")}>
                  <td className="num code">{r.seq}</td>
                  <td className="whitespace-nowrap text-ink-muted tabular-nums">{formatDateTime(r.at)}</td>
                  <td className={cn(!r.actor_email && "text-ink-muted")}>{actorWord(r)}</td>
                  <td>{tk(`audit_action.${r.action}`)}</td>
                  <td className="code">{r.entity_type}</td>
                  <td>
                    <Short value={r.entity_id} />
                  </td>
                  <td>
                    <span className="flex items-center gap-3">
                      <Short value={r.hash} tip={t("audit.hash_tip", { hash: r.hash })} />
                      {isBreak && (
                        <span className="inline-flex items-center gap-1 text-xs font-medium whitespace-nowrap text-check-fail-ink">
                          <X className="size-3.5" aria-hidden="true" />
                          {t("audit.break_marker")}
                        </span>
                      )}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-end gap-3">
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ a_page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
    </>
  );
}
