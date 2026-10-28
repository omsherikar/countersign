"use client";

import * as React from "react";
import Link from "next/link";
import { EmptyState } from "@/components/brand/EmptyState";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDateTime } from "@/lib/format";
import { useUploads } from "@/lib/queries";
import { ErrorBlock, SkeletonRows, TableMessage } from "@/components/common/query-state";
import { Pager } from "@/components/common/pager";
import { UploadStatusWord } from "@/components/uploads/upload-status-word";

const COLS = 10;

/** Previous uploads for the year, newest first; each row opens its batch page (W2-1). */
export function UploadHistory({ academicYear, batchHref }: { academicYear: string; batchHref: (id: string) => string }) {
  const [page, setPage] = React.useState(1);
  const list = useUploads({ academic_year: academicYear, page, page_size: 10 });
  const data = list.data;
  const rows = data?.items ?? [];
  return (
    <div>
      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("upload.previous")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("col.file")}</th>
              <th scope="col">{t("col.uploaded")}</th>
              <th scope="col">{t("col.uploaded_by")}</th>
              <th scope="col" title={t("upload.kind_tip")}>
                {t("col.kind")}
              </th>
              <th scope="col">{t("col.upload_source")}</th>
              <th scope="col">{t("col.status")}</th>
              <th scope="col" className="num">
                {t("col.rows")}
              </th>
              <th scope="col" className="num">
                {t("col.accepted")}
              </th>
              <th scope="col" className="num">
                {t("col.with_errors")}
              </th>
              <th scope="col" className="num">
                {t("col.with_warnings")}
              </th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading && <SkeletonRows cols={COLS} rows={3} />}
            {list.isError && !data && (
              <TableMessage cols={COLS}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={COLS}>
                <EmptyState title={t("empty.uploads")} />
              </TableMessage>
            )}
            {rows.map((b) => (
              <tr key={b.id}>
                <td className="code max-w-[20rem] truncate">
                  <Link href={batchHref(b.id)} title={b.filename}>
                    {b.filename}
                  </Link>
                </td>
                <td className="text-ink-muted">{formatDateTime(b.uploaded_at)}</td>
                <td className="max-w-[12rem] truncate text-ink-muted" title={b.uploaded_by.name}>
                  {b.uploaded_by.name.replace(/,.*$/, "")}
                </td>
                <td title={t("upload.kind_tip")}>{tk(`upload.kind.${b.kind}`)}</td>
                <td className="text-ink-muted">{tk(`upload_source.${b.source}`)}</td>
                <td>
                  <UploadStatusWord status={b.status} />
                </td>
                <td className="num">{formatCount(b.counts.rows)}</td>
                <td className="num">{formatCount(b.counts.accepted)}</td>
                <td className="num">{b.counts.errors > 0 ? <span className="font-semibold">{formatCount(b.counts.errors)}</span> : <span className="text-ink-muted">0</span>}</td>
                <td className="num text-ink-muted">{formatCount(b.counts.warnings)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && data.total > data.page_size && (
        <div className="mt-2 flex justify-end">
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={setPage} />
        </div>
      )}
    </div>
  );
}
