"use client";

import * as React from "react";
import Link from "next/link";
import { Check, CircleDashed, X } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate, formatDateTime, singular } from "@/lib/format";
import { isRunning, useUpload } from "@/lib/queries";
import type { UploadBatch, UploadStage, UploadStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Crumbs } from "@/components/common/page-header";
import { RowErrors } from "@/components/uploads/row-errors";
import { useColumnMapping, useCompleteness } from "@/lib/queries-records";

/** "Columns read with your saved mapping, last changed 17 Sep by Registrar, ..." with a link to the mapping (W4-10). */
function MappingLine({ batch }: { batch: UploadBatch }) {
  const q = useColumnMapping(batch.column_mapping.length > 0 ? batch.institution_id : null);
  if (batch.column_mapping.length === 0 || !q.data?.updated_at) return null;
  return (
    <p className="text-sm text-ink-muted">
      {t("mapping.batch_line", { date: formatDate(q.data.updated_at), name: q.data.updated_by?.name ?? "" })}{" "}
      <Link href="/college/column-mapping">{t("mapping.view")}</Link>
    </p>
  );
}

/** "Completeness now 98.5%: 8 joined students still missing from your uploads." once the reconciliation has run. */
function CompletenessNow({ batch }: { batch: UploadBatch }) {
  const q = useCompleteness(batch.institution_id, batch.academic_year);
  const c = q.data;
  if (!c || c.completeness_pct === null || c.missing === 0) return null;
  return (
    <p className="mt-1 text-sm">
      <Link href="/college/completeness">{t("upload.done_completeness", { pct: String(c.completeness_pct).replace(/\.0$/, ""), missing: formatCount(c.missing) })}</Link>
    </p>
  );
}

const STAGES: UploadStage[] = ["PARSE", "VALIDATE", "FILE_DUPLICATES", "UPSERT", "LEDGER", "CHECKS", "DUPLICATES", "FLAGS"];
const VALIDATING: UploadStage[] = ["PARSE", "VALIDATE", "FILE_DUPLICATES"];
const RAIL: UploadStatus[] = ["QUEUED", "VALIDATING", "PROCESSING", "DONE"];

/** Where the batch stands on the four-step rail; a failure sits where it happened and replaces Done. */
function railPosition(b: UploadBatch): number {
  if (b.status === "FAILED") return b.stage && VALIDATING.includes(b.stage) ? 1 : 2;
  return RAIL.indexOf(b.status);
}

function Rail({ batch }: { batch: UploadBatch }) {
  const at = railPosition(batch);
  const failed = batch.status === "FAILED";
  return (
    <ol aria-label={t("upload.rail_label")} className="flex flex-wrap items-center gap-y-2">
      {RAIL.map((status, i) => {
        const word = i === 3 && failed ? tk("upload_status.FAILED") : tk(`upload_status.${status}`);
        const done = i < at || (status === "DONE" && batch.status === "DONE");
        const current = i === at && batch.status !== "DONE";
        const failedHere = failed && i === 3;
        return (
          <li key={status} className="flex items-center" aria-current={current ? "step" : undefined}>
            {i > 0 && <span aria-hidden="true" className={cn("mx-2 h-px w-8 sm:w-14", i <= at ? "bg-ink" : "bg-rule-strong")} />}
            <span
              className={cn(
                "inline-flex items-center gap-1.5 text-sm",
                done && "text-ink",
                current && !failed && "font-semibold text-ink-blue",
                !done && !current && !failedHere && "text-ink-muted",
                failedHere && "font-semibold text-check-fail-ink",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "flex size-5 items-center justify-center rounded-full border",
                  done && "border-ink bg-ink text-paper-raised",
                  current && !failed && "border-ink-blue bg-flag-open-soft",
                  !done && !current && !failedHere && "border-rule-strong border-dashed",
                  failedHere && "border-check-fail bg-check-fail-soft",
                )}
              >
                {done ? (
                  <Check className="size-3" />
                ) : failedHere ? (
                  <X className="size-3" />
                ) : current ? (
                  <span className="size-2 rounded-full bg-ink-blue motion-safe:animate-pulse" />
                ) : (
                  <CircleDashed className="size-3 opacity-0" />
                )}
              </span>
              {word}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/** progress_pct never goes down on the api; the page also keeps the highest value it has seen. */
function useHighest(value: number | undefined): number {
  const [max, setMax] = React.useState(value ?? 0);
  if (value !== undefined && value > max) setMax(value);
  return Math.max(max, value ?? 0);
}

function Progress({ batch }: { batch: UploadBatch }) {
  const pct = useHighest(batch.progress_pct);
  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label={t("upload.progress_label")}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-2 w-full max-w-md overflow-hidden rounded-full bg-paper-sunken"
      >
        <div
          className={cn("h-full transition-[width] duration-700 ease-out motion-reduce:transition-none", batch.status === "FAILED" ? "bg-check-fail" : "bg-ink-blue")}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="num w-10 text-sm font-semibold">{pct}%</span>
    </div>
  );
}

function StepLine({ batch }: { batch: UploadBatch }) {
  if (batch.status === "QUEUED") return <p className="text-sm text-ink-muted">{t("upload.queued_note")}</p>;
  if (!batch.stage || batch.stage === "DONE") return null;
  const n = STAGES.indexOf(batch.stage) + 1;
  return (
    <p className="text-sm text-ink">
      {t("upload.step", { n, stage_word: tk(`upload_stage.${batch.stage}`) })}
      {batch.stage_total > 0 && batch.status !== "FAILED" && (
        <span className="num ml-2 text-ink-muted">
          {formatCount(batch.processed_rows)} / {formatCount(batch.stage_total)}
        </span>
      )}
    </p>
  );
}

function Sources({ batch }: { batch: UploadBatch }) {
  if (batch.sources.length === 0) return null;
  return (
    <section aria-labelledby="sources-heading" className="border-l-2 border-rule-margin pl-4">
      <h2 id="sources-heading" className="mb-1.5 font-sans text-md font-semibold">
        {t("upload.checking")}
      </h2>
      <ul className="flex flex-col gap-1 text-sm">
        {batch.sources.map((s) => (
          <li key={s.source}>
            <span className="num">{t("upload.source_line", { source_name: tk(`source.${s.source}`), calls: formatCount(s.calls) })}</span>
            {s.unavailable > 0 && (
              <span className="mt-0.5 block max-w-[68ch] text-check-pending-ink">
                {singular(t("upload.source_waiting", { source_name: tk(`source.${s.source}`), n: formatCount(s.unavailable) }))}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function DoneCard({ batch }: { batch: UploadBatch }) {
  const c = batch.counts;
  return (
    <section aria-labelledby="done-heading" className="rounded-md border border-line border-l-[3px] border-l-ink-blue bg-paper-raised px-5 py-4 shadow-hairline">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="done-heading" className="text-xl">
          {t("upload.done_heading")}
        </h2>
        <span className="stamp stamp--blue">{tk("upload_status.DONE")}</span>
      </div>
      <p className="mt-2 font-display text-lg leading-snug">
        {singular(t("upload.done_summary", { ok: formatCount(c.accepted), seated: formatCount(c.seated), unseated: formatCount(c.unseated), flags: formatCount(c.flags_raised) }))}
      </p>
      <p className="mt-1 text-sm text-ink-muted">
        {t("upload.done_changes", {
          created: formatCount(c.created),
          updated: formatCount(c.updated),
          unchanged: formatCount(c.unchanged),
          withdrawn: formatCount(c.withdrawn),
          transferred: formatCount(c.transferred),
          released: formatCount(c.released),
        })}
      </p>
      <p className="mt-1 text-sm">
        {t("upload.done_status", {
          countersigned: formatCount(c.records.COUNTERSIGNED),
          awaiting: formatCount(c.records.AWAITING_EVIDENCE),
          under_review: formatCount(c.records.UNDER_REVIEW),
          disputed: formatCount(c.records.DISPUTED),
        })}
      </p>
      <CompletenessNow batch={batch} />
      <p className="mt-3 max-w-[68ch] text-sm">{t("upload.done_note")}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button asChild variant="outline" size="sm">
          <Link href="/college">{t("upload.view_ledger")}</Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/college/enrolments">{t("upload.view_enrolments")}</Link>
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/college/flags">{t("upload.view_flags")}</Link>
        </Button>
      </div>
    </section>
  );
}

function FailedCard({ batch }: { batch: UploadBatch }) {
  return (
    <section role="alert" className="rounded-md border border-check-fail/40 border-l-[3px] border-l-check-fail bg-paper-raised px-5 py-4">
      <p className="font-medium">{t("upload.failed")}</p>
      {batch.error && <p className="mt-1">{batch.error}</p>}
      <p className="mt-1 text-sm text-ink-muted">{t("upload.failed_earlier")}</p>
      <Button asChild size="sm" className="mt-3">
        <Link href="/college/upload">{t("upload.upload_again")}</Link>
      </Button>
    </section>
  );
}

/**
 * One upload batch (page spec W2-2): the status rail, the step and the
 * progress bar, polled every 2 s until the batch is done or failed, then the
 * outcome and the rows the registrar has to fix.
 */
export function BatchPage({ id }: { id: string }) {
  const q = useUpload(id);
  const b = q.data;

  const crumbs = [
    { label: t("nav.ledger"), href: "/college" },
    { label: t("nav.upload"), href: "/college/upload" },
    { label: b?.filename ?? "…" },
  ];

  if (q.isError && !b) {
    return (
      <>
        <Crumbs items={crumbs} />
        <h1 className="sr-only">{t("nav.upload")}</h1>
        <ErrorBlock error={q.error} entity="upload" backHref="/college/upload" backLabel={t("upload.upload_again")} onRetry={() => q.refetch()} className="mt-4" />
      </>
    );
  }
  if (!b) {
    return (
      <>
        <Crumbs items={crumbs} />
        <div className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-9 w-96 max-w-full" />
          <Skeleton className="h-4 w-80" />
          <Skeleton className="mt-6 h-24 max-w-2xl" />
        </div>
        <SlowHint />
      </>
    );
  }

  const running = isRunning(b);
  const pastValidation = b.status === "PROCESSING" || b.status === "DONE" || (b.status === "FAILED" && b.stage !== null && !VALIDATING.includes(b.stage));

  return (
    <>
      <Crumbs items={crumbs} />
      <header className="mb-6">
        <h1 className="code text-xl break-all md:text-2xl">{b.filename}</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          {t("upload.batch_meta", {
            kind_word: tk(`upload.kind.${b.kind}`),
            source_word: tk(`upload_source.${b.source}`),
            uploaded_at: formatDateTime(b.uploaded_at),
            uploaded_by: b.uploaded_by.name.replace(/,.*$/, ""),
          })}
        </p>
      </header>

      <section aria-label={t("upload.rail_label")} className="mb-8 flex flex-col gap-3 border-y border-rule bg-paper-raised px-4 py-4" aria-live="polite" aria-busy={running}>
        <Rail batch={b} />
        <StepLine batch={b} />
        <Progress batch={b} />
        {pastValidation && (
          <p className="text-sm tabular-nums">
            {t("upload.rows", { rows: formatCount(b.counts.rows), accepted: formatCount(b.counts.accepted), errors: formatCount(b.counts.errors), warnings: formatCount(b.counts.warnings) })}
          </p>
        )}
        {b.same_file_as && <p className="text-sm text-ink-muted">{t("upload.same_file", { uploaded_date: formatDate(b.same_file_as.uploaded_at) })}</p>}
        {b.ignored_columns.length > 0 && <p className="text-sm text-ink-muted">{t("upload.ignored_columns", { columns: b.ignored_columns.join(", ") })}</p>}
        <MappingLine batch={b} />
      </section>

      <div className="mb-10 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          {b.status === "DONE" && <DoneCard batch={b} />}
          {b.status === "FAILED" && <FailedCard batch={b} />}
        </div>
        <div className="lg:col-span-4">
          <Sources batch={b} />
        </div>
      </div>

      {pastValidation && <RowErrors key={`${b.id}-${b.status}`} batch={b} />}
    </>
  );
}
