"use client";

import * as React from "react";
import { RefreshCw } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatDateTime, formatLatency, formatRelative } from "@/lib/format";
import { useAdapterPing } from "@/lib/queries";
import { SOURCE_KEYS, type SourceKey, type SourceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const SOURCE_NAME: Record<SourceKey, string> = {
  apaar: t("source.APAAR"),
  counselling: t("source.COUNSELLING"),
  abc: t("source.ABC"),
  digilocker: t("source.DIGILOCKER"),
  sii: t("source.SII"),
};

/** Status word with a mark; colour never stands alone (OK green dot, Unavailable amber, Disabled grey). */
export function SourceStatusWord({ status }: { status: SourceStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium",
        status === "OK" && "text-check-pass-ink",
        status === "UNAVAILABLE" && "text-check-pending-ink",
        status === "DISABLED" && "text-check-na-ink",
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-2 rounded-full",
          status === "OK" && "bg-check-pass",
          status === "UNAVAILABLE" && "bg-check-pending",
          status === "DISABLED" && "border border-check-na bg-transparent",
        )}
      />
      {tk(`source.status.${status}`)}
    </span>
  );
}

/** Re-renders every 30 s so "2 min ago" stays true. */
function useNow(): number {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  return now;
}

/**
 * Sources on /aicte: one compact ruled bar under the KPI strip, a line per
 * government source with its status word and latency, refreshed every 60 s.
 */
export function SourcesPanel() {
  const ping = useAdapterPing();
  const now = useNow();
  return (
    <section
      aria-labelledby="sources-heading"
      className="flex flex-col gap-2 border-b border-rule bg-paper-raised px-4 py-2.5 lg:flex-row lg:items-center lg:gap-5"
    >
      <div className="flex shrink-0 items-center gap-2">
        <h2 id="sources-heading" className="font-sans text-sm font-semibold">
          {t("section.sources")}
        </h2>
        {ping.data && <span className="rounded-chip border border-line px-1.5 font-mono text-2xs text-ink-muted">{ping.data.adapter}</span>}
      </div>
      {ping.isLoading && (
        <div className="flex flex-1 flex-wrap gap-4" aria-hidden="true">
          {SOURCE_KEYS.map((k) => (
            <Skeleton key={k} className="h-4 w-36" />
          ))}
        </div>
      )}
      {ping.isError && !ping.data && (
        <p className="flex flex-1 items-center gap-2 text-sm text-ink-muted" role="alert">
          {t("source.failed")}
          <button type="button" onClick={() => ping.refetch()} className="inline-flex items-center gap-1 text-ink-blue hover:underline">
            <RefreshCw className="size-3.5" aria-hidden="true" />
            {t("err.retry")}
          </button>
        </p>
      )}
      {ping.data && (
        <>
          <ul className="flex flex-1 flex-wrap items-center gap-x-5 gap-y-1.5">
            {SOURCE_KEYS.map((k) => {
              const s = ping.data.sources[k];
              const item = (
                <li
                  key={k}
                  tabIndex={s.status === "OK" ? undefined : 0}
                  className={cn(
                    "flex items-center gap-2 text-sm whitespace-nowrap",
                    s.status === "UNAVAILABLE" && "rounded-chip bg-check-pending-soft px-1.5",
                  )}
                >
                  <span>{SOURCE_NAME[k]}</span>
                  <SourceStatusWord status={s.status} />
                  <span className="num text-xs text-ink-muted">{formatLatency(s.latency_ms)}</span>
                </li>
              );
              if (s.status === "OK") return item;
              return (
                <Tooltip key={k}>
                  <TooltipTrigger asChild>{item}</TooltipTrigger>
                  <TooltipContent>{s.status === "DISABLED" ? t("source.disabled_detail") : (s.detail ?? t("source.status.UNAVAILABLE"))}</TooltipContent>
                </Tooltip>
              );
            })}
          </ul>
          <p className="shrink-0 text-xs text-ink-muted">
            <span title={formatDateTime(ping.data.checked_at)}>{t("source.checked", { relative: formatRelative(ping.data.checked_at, now) })}</span>
            {ping.isFetching && <span className="ml-2 text-ink-faint">checking</span>}
          </p>
        </>
      )}
    </section>
  );
}
