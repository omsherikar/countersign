"use client";

import * as React from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { t } from "@/lib/copy";
import { formatClock, formatCount, formatLatency } from "@/lib/format";
import { useAdapterPing, useApplyChaos, useAuditVerify, useChaos, useHealth, useResetChaos } from "@/lib/queries";
import { SOURCE_KEYS, type AdapterPing, type ChaosSetting, type SourceKey } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, errorMessage } from "@/components/common/query-state";
import { Crumbs, PageHeader, SectionHeader } from "@/components/common/page-header";
import { SOURCE_NAME, SourceStatusWord } from "@/components/overview/sources-panel";

/** Announces source status changes ("APAAR registry now Unavailable") to screen readers. */
function useStatusAnnouncements(ping: AdapterPing | undefined): string {
  const [previous, setPrevious] = React.useState<AdapterPing | undefined>(ping);
  const [message, setMessage] = React.useState("");
  if (ping !== previous) {
    setPrevious(ping);
    if (ping && previous) {
      const changed = SOURCE_KEYS.filter((k) => previous.sources[k].status !== ping.sources[k].status);
      if (changed.length) {
        setMessage(changed.map((k) => `${SOURCE_NAME[k]} now ${t(`source.status.${ping.sources[k].status}` as "source.status.OK")}`).join(". "));
      }
    }
  }
  return message;
}

function SourcesSection() {
  const ping = useAdapterPing();
  const announcement = useStatusAnnouncements(ping.data);
  const data = ping.data;
  return (
    <section aria-labelledby="sources-h" className="mb-10">
      <SectionHeader
        id="sources-h"
        title={t("admin.sources")}
        aside={
          <>
            {data && <span className="rounded-chip border border-line px-1.5 font-mono text-2xs">{t("admin.adapter", { adapter: data.adapter })}</span>}
            {data && <span className="num">{t("app.admin.checked_at", { time: formatClock(data.checked_at) })}</span>}
            <Button variant="outline" size="sm" onClick={() => ping.refetch()} disabled={ping.isFetching}>
              <RefreshCw className={cn("size-3.5", ping.isFetching && "animate-spin")} aria-hidden="true" />
              {ping.isFetching ? t("admin.pinging") : t("admin.ping")}
            </Button>
          </>
        }
      />
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
      {ping.isError && !data && <ErrorBlock error={ping.error} onRetry={() => ping.refetch()} />}
      {ping.isError && data && <ErrorBlock error={ping.error} onRetry={() => ping.refetch()} compact className="mb-3" />}
      {(data || ping.isLoading) && (
        <div className="overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
          <table className="ledger-table ledger-table--dense">
            <caption className="sr-only">{t("admin.sources")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("app.admin.col.source")}</th>
                <th scope="col">{t("app.admin.col.status")}</th>
                <th scope="col" className="num">
                  {t("app.admin.col.latency")}
                </th>
                <th scope="col">{t("app.admin.col.detail")}</th>
              </tr>
            </thead>
            <tbody>
              {SOURCE_KEYS.map((k) => {
                const s = data?.sources[k];
                return (
                  <tr key={k} className={cn(s?.status === "UNAVAILABLE" && "[&>td]:bg-check-pending-soft")}>
                    <td className="font-medium">{SOURCE_NAME[k]}</td>
                    <td>
                      {ping.isFetching ? (
                        <span className="text-xs text-ink-muted">{t("app.admin.checking")}</span>
                      ) : s ? (
                        <SourceStatusWord status={s.status} />
                      ) : (
                        <Skeleton className="h-3.5 w-20" />
                      )}
                    </td>
                    <td className="num">{s ? formatLatency(s.latency_ms) : ""}</td>
                    <td className="wrap text-ink-muted">{s ? (s.status === "DISABLED" ? t("source.disabled_detail") : (s.detail ?? "")) : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function AuditSection() {
  const verify = useAuditVerify();
  const r = verify.data;
  return (
    <section aria-labelledby="audit-h" className="mb-10">
      <SectionHeader
        id="audit-h"
        title={t("admin.audit")}
        aside={
          <Button variant="outline" size="sm" onClick={() => verify.mutate()} disabled={verify.isPending}>
            {t("admin.verify")}
          </Button>
        }
      />
      <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm" aria-live="polite">
        {verify.isPending && <span className="text-ink-muted">{t("app.admin.checking")}</span>}
        {!verify.isPending && verify.isError && <ErrorBlock error={verify.error} onRetry={() => verify.mutate()} compact />}
        {!verify.isPending && !verify.isError && !r && <span className="text-ink-muted">{t("admin.verify_idle")}</span>}
        {!verify.isPending && r && (
          <span className={cn("flex items-center gap-3", r.ok ? "text-ink" : "font-medium text-check-fail-ink")}>
            <span className={cn("stamp", r.ok ? "stamp--ok" : "stamp--alert")}>{r.ok ? t("app.admin.intact") : t("app.admin.broken")}</span>
            {r.ok
              ? t("admin.chain_ok", { length: formatCount(r.length), time: formatClock(r.checked_at) })
              : t("admin.chain_broken", { length: formatCount(r.length), seq: r.first_broken_seq ?? "", time: formatClock(r.checked_at) })}
          </span>
        )}
      </div>
    </section>
  );
}

function HealthSection() {
  const health = useHealth();
  const h = health.data;
  return (
    <section aria-labelledby="health-h" className="mb-10">
      <SectionHeader id="health-h" title={t("admin.health")} />
      <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm">
        {health.isLoading && <Skeleton className="h-4 w-80" />}
        {health.isError && !h && <ErrorBlock error={health.error} onRetry={() => health.refetch()} compact />}
        {h && <span className="num">{t("admin.health_line", { status: h.status, db: h.db, redis: h.redis, version: h.version })}</span>}
      </div>
    </section>
  );
}

const CHAOS_SOURCES: (SourceKey | "all")[] = [...SOURCE_KEYS, "all"];

function chaosSummary(c: ChaosSetting): string {
  const parts = [];
  if (c.down) parts.push(t("app.admin.chaos_down"));
  if (c.latency_ms > 0) parts.push(t("app.admin.chaos_latency", { ms: formatCount(c.latency_ms) }));
  if (c.fail_rate > 0) parts.push(t("app.admin.chaos_fail", { pct: Math.round(c.fail_rate * 100) }));
  return parts.length ? parts.join(", ") : t("app.admin.chaos_normal");
}

function DemoSection() {
  const chaos = useChaos();
  const apply = useApplyChaos();
  const reset = useResetChaos();
  const [source, setSource] = React.useState<SourceKey | "all">("apaar");
  const [latency, setLatency] = React.useState("0");
  const [failRate, setFailRate] = React.useState("0");
  const [down, setDown] = React.useState(false);

  function onApply(e: React.FormEvent) {
    e.preventDefault();
    const setting: ChaosSetting = {
      latency_ms: Math.max(0, Math.round(Number(latency) || 0)),
      fail_rate: Math.min(1, Math.max(0, Number(failRate) || 0)),
      down,
    };
    apply.mutate(
      { source, ...setting },
      {
        onSuccess: () =>
          toast(t("admin.chaos_applied", { source: source === "all" ? t("app.admin.all_sources") : SOURCE_NAME[source], summary: chaosSummary(setting) })),
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <section aria-label={t("admin.demo")} className="mb-10">
      <SectionHeader title={t("admin.demo")} aside={<span className="stamp">{t("admin.demo_tag")}</span>} />
      <div className="flex flex-col gap-6 border-l-2 border-rule-margin bg-paper-raised px-4 py-4">
        <div>
          <h3 className="mb-1 font-sans text-md font-semibold">{t("admin.chaos")}</h3>
          <p className="mb-3 text-sm text-ink-muted">{t("app.admin.chaos_note")}</p>
          <form onSubmit={onApply} className="flex flex-wrap items-end gap-x-4 gap-y-3">
            <label className="flex flex-col gap-1 text-xs font-medium text-ink-muted">
              {t("admin.chaos_source")}
              <select
                value={source}
                onChange={(e) => setSource(e.target.value as SourceKey | "all")}
                className="h-8 rounded-md border border-line bg-paper px-2 text-sm text-ink"
              >
                {CHAOS_SOURCES.map((k) => (
                  <option key={k} value={k}>
                    {k === "all" ? t("app.admin.all_sources") : SOURCE_NAME[k]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-ink-muted">
              {t("admin.chaos_latency")}
              <input
                type="number"
                min={0}
                step={100}
                value={latency}
                onChange={(e) => setLatency(e.target.value)}
                className="num h-8 w-28 rounded-md border border-line bg-paper px-2 text-sm text-ink"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-ink-muted">
              {t("admin.chaos_fail")}
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                value={failRate}
                onChange={(e) => setFailRate(e.target.value)}
                className="num h-8 w-24 rounded-md border border-line bg-paper px-2 text-sm text-ink"
              />
            </label>
            <label className="flex h-8 items-center gap-2 text-sm">
              <input type="checkbox" checked={down} onChange={(e) => setDown(e.target.checked)} className="size-4 accent-[var(--ink-blue)]" />
              {t("admin.chaos_down")}
            </label>
            <Button type="submit" size="sm" disabled={apply.isPending}>
              {t("admin.chaos_apply")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={reset.isPending}
              onClick={() =>
                reset.mutate(undefined, {
                  onSuccess: () => toast(t("app.admin.chaos_reset_done")),
                  onError: (err) => toast.error(errorMessage(err)),
                })
              }
            >
              {t("admin.chaos_reset")}
            </Button>
          </form>
          {chaos.isError && !chaos.data && <ErrorBlock error={chaos.error} onRetry={() => chaos.refetch()} compact className="mt-3" />}
          {chaos.data && (
            <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
              {SOURCE_KEYS.map((k) => (
                <li key={k}>
                  <span className="text-ink">{SOURCE_NAME[k]}</span>: {chaosSummary(chaos.data[k])}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="border-t border-rule pt-4">
          <h3 className="mb-1 font-sans text-md font-semibold">{t("admin.reset")}</h3>
          <p className="text-sm text-ink-muted">{t("admin.reset_note")}</p>
          <p className="mt-2 text-sm">
            {t("admin.reset_cli").replace(t("app.admin.reset_cli_cmd") + ".", "")}
            <code className="code rounded-chip border border-line bg-paper px-1.5 py-0.5">{t("app.admin.reset_cli_cmd")}</code>
          </p>
        </div>
      </div>
    </section>
  );
}

/** /admin/system: adapters ping, audit chain, service health and the demo controls. AICTE_ADMIN only. */
export function SystemPage() {
  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: "/aicte" }, { label: t("nav.system") }]} />
      <PageHeader title={t("admin.heading")} />
      <SourcesSection />
      <AuditSection />
      <HealthSection />
      <DemoSection />
    </>
  );
}
