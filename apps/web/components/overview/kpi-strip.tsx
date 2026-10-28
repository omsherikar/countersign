"use client";

import * as React from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { KpiTile } from "@/components/brand/KpiTile";
import { t, type CopyId } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SlowHint } from "@/components/common/query-state";

export interface KpiSpec {
  label: CopyId;
  value: number | null | undefined;
  /** Rendered when value is null (Week 1): "Not yet computed". */
  nullText?: string;
  tone?: "default" | "alert" | "muted";
  hint?: string;
  format?: (n: number) => string;
  /** What the figure counts, on hover and on focus. */
  tip?: string;
  /** The tile opens this page (Open flags opens the case queue). */
  href?: string;
}

/** Percentages arrive with one decimal; print them as sent without a trailing ".0" (0.0 is "0%"). */
export function formatPct(n: number): string {
  return `${String(Math.round(n * 10) / 10).replace(/\.0$/, "")}%`;
}

/** A tile-shaped placeholder that keeps the strip's rhythm while values load or fail. */
function TileShell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 px-4 py-3">
      <span className="truncate text-xs font-medium text-ink-muted">{label}</span>
      {children}
    </div>
  );
}

/**
 * The KPI strip: tiles are <dl>-like cells in one ruled strip, not cards.
 * Loading shows skeleton digits; a failed request shows "Could not load"
 * with a retry in each tile and leaves the rest of the page alone.
 */
export function KpiStrip({
  tiles,
  loading,
  failed,
  onRetry,
  className,
}: {
  tiles: KpiSpec[];
  loading: boolean;
  failed: boolean;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="kpi-strip min-h-24 [grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr))]" role="group" aria-label="Key figures" aria-busy={loading}>
        {tiles.map((tile) => {
          const label = t(tile.label);
          if (loading) {
            return (
              <TileShell key={tile.label} label={label}>
                <Skeleton className="h-7 w-20" />
              </TileShell>
            );
          }
          if (failed) {
            return (
              <TileShell key={tile.label} label={label}>
                <span className="flex items-center gap-1.5 text-sm text-ink-muted">
                  {t("err.tile_failed")}
                  {onRetry && (
                    <button type="button" onClick={onRetry} aria-label={`${t("err.retry")}: ${label}`} className="rounded-chip p-0.5 text-ink-blue">
                      <RefreshCw className="size-3.5" aria-hidden="true" />
                    </button>
                  )}
                </span>
              </TileShell>
            );
          }
          if (tile.value === null || tile.value === undefined) {
            return (
              <TileShell key={tile.label} label={label}>
                <span className="font-display text-lg leading-7 text-ink-muted italic">{tile.nullText ?? t("kpi.not_computed")}</span>
              </TileShell>
            );
          }
          const body = (
            <KpiTile
              label={label}
              value={tile.value}
              hint={tile.hint}
              format={tile.format}
              tone={tile.tone ?? "default"}
              className={cn(tile.tone === "muted" && "text-ink-muted", (tile.href || tile.tip) && "h-full")}
            />
          );
          const wrapped = tile.href ? (
            <Link href={tile.href} className="block h-full text-ink no-underline outline-offset-[-2px] hover:bg-flag-open-soft/60">
              {body}
            </Link>
          ) : tile.tip ? (
            <div tabIndex={0} className="h-full outline-offset-[-2px]">
              {body}
            </div>
          ) : (
            body
          );
          if (!tile.tip) return <React.Fragment key={tile.label}>{wrapped}</React.Fragment>;
          return (
            <Tooltip key={tile.label}>
              <TooltipTrigger asChild>{wrapped}</TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-72">
                {tile.tip}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
      {loading && <SlowHint />}
    </div>
  );
}
