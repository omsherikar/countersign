"use client";

import * as React from "react";
import { RefreshCw } from "lucide-react";
import { KpiTile } from "@/components/brand/KpiTile";
import { t, type CopyId } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SlowHint } from "@/components/common/query-state";

export interface KpiSpec {
  label: CopyId;
  value: number | null | undefined;
  /** Rendered when value is null (Week 1): "Not yet computed". */
  nullText?: string;
  tone?: "default" | "alert" | "muted";
  hint?: string;
  format?: (n: number) => string;
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
      <div className="kpi-strip min-h-24" role="group" aria-label="Key figures" aria-busy={loading}>
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
                <span className="font-display text-lg leading-7 text-ink-faint italic">{tile.nullText ?? t("kpi.not_computed")}</span>
              </TileShell>
            );
          }
          return (
            <KpiTile
              key={tile.label}
              label={label}
              value={tile.value}
              hint={tile.hint}
              format={tile.format}
              tone={tile.tone ?? "default"}
              className={cn(tile.tone === "muted" && "text-ink-muted")}
            />
          );
        })}
      </div>
      {loading && <SlowHint />}
    </div>
  );
}
