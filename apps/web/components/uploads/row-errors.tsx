"use client";

import * as React from "react";
import { CircleAlert, Download, TriangleAlert } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { download } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatCount, singular } from "@/lib/format";
import { useUploadErrors } from "@/lib/queries";
import type { RowErrorLevel, UploadBatch } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ErrorBlock, SkeletonRows, TableMessage, errorMessage } from "@/components/common/query-state";
import { Pager } from "@/components/common/pager";
import { ReadLoggedNote } from "@/components/common/ledger-bits";

const COLS = 5;
const PAGE_SIZE = 25;

/** Error or Warning with its icon; the tooltip says what happened to the row. */
function LevelWord({ level }: { level: RowErrorLevel }) {
  const Icon = level === "ERROR" ? CircleAlert : TriangleAlert;
  return (
    <span
      title={t(`upload.level_tip.${level}`)}
      className={cn("inline-flex items-center gap-1.5 text-xs font-medium", level === "ERROR" ? "text-check-fail-ink" : "text-check-pending-ink")}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {t(`upload.level.${level}`)}
    </span>
  );
}

/**
 * Row errors and warnings of one batch (W2-2, A2.8): the api's message and
 * the masked value exactly as sent, paged, filterable by level, and the
 * whole list as errors.csv.
 */
export function RowErrors({ batch }: { batch: UploadBatch }) {
  const [level, setLevel] = React.useState<RowErrorLevel | "">("");
  const [page, setPage] = React.useState(1);
  const [downloadError, setDownloadError] = React.useState<string | null>(null);
  const list = useUploadErrors(batch.id, { page, page_size: PAGE_SIZE, level: level || undefined });
  const data = list.data;
  const rows = data?.items ?? [];
  const stem = batch.filename.replace(/\.(csv|xlsx)$/i, "");

  const filters: { value: RowErrorLevel | ""; label: string }[] = [
    { value: "", label: t("upload.errors_filter.all") },
    { value: "ERROR", label: t("upload.errors_filter.ERROR") },
    { value: "WARNING", label: t("upload.errors_filter.WARNING") },
  ];

  return (
    <section aria-labelledby="row-errors-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 id="row-errors-heading" className="text-xl">
          {t("upload.errors_heading", { n: data ? formatCount(data.total) : "…" })}
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label={t("upload.errors_heading", { n: "" }).replace(/\s*\(\)$/, "")} className="inline-flex rounded-md border border-line bg-paper-raised p-0.5">
            {filters.map((f) => (
              <button
                key={f.label}
                type="button"
                aria-pressed={level === f.value}
                onClick={() => {
                  setLevel(f.value);
                  setPage(1);
                }}
                className={cn(
                  "h-7 rounded-[4px] px-3 text-xs font-medium",
                  level === f.value ? "bg-ink-blue text-on-ink-blue" : "text-ink-muted hover:text-ink",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDownloadError(null);
              download(`/uploads/${batch.id}/errors.csv`, `${stem}_errors.csv`).catch((e) => setDownloadError(errorMessage(e)));
            }}
          >
            <Download className="size-3.5" aria-hidden="true" />
            {t("upload.errors_download")}
          </Button>
        </div>
      </div>
      {downloadError && (
        <p role="alert" className="mb-2 text-sm text-check-fail-ink">
          {downloadError}
        </p>
      )}
      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("upload.errors_heading", { n: data?.total ?? 0 })}</caption>
          <thead>
            <tr>
              <th scope="col" className="num w-16">
                {t("col.row")}
              </th>
              <th scope="col">{t("col.row_level")}</th>
              <th scope="col" className="code">
                {t("col.column")}
              </th>
              <th scope="col">{t("col.problem")}</th>
              <th scope="col" className="code">
                {t("col.value")}
              </th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading && <SkeletonRows cols={COLS} rows={5} />}
            {list.isError && !data && (
              <TableMessage cols={COLS}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={COLS}>
                <EmptyState title={t("upload.errors_none")} />
              </TableMessage>
            )}
            {rows.map((e, i) => (
              <tr key={`${e.row_no}-${e.field}-${i}`}>
                <td className="num font-medium">{e.row_no}</td>
                <td>
                  <LevelWord level={e.level} />
                </td>
                <td className="code" title={e.field ? tk(`field.${e.field}`) : undefined}>
                  {e.field ?? ""}
                </td>
                <td className="wrap min-w-[18rem] py-2 leading-snug">{e.message}</td>
                <td className="code">{e.value_masked ?? <span className="font-sans text-ink-muted italic">{t("upload.value_blank")}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
        <div className="flex max-w-[68ch] flex-col gap-1 text-sm text-ink-muted">
          {batch.counts.errors > 0 && <p>{singular(t("upload.errors_next"))}</p>}
          <ReadLoggedNote />
        </div>
        {data && data.total > data.page_size && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={setPage} />
        )}
      </div>
    </section>
  );
}
