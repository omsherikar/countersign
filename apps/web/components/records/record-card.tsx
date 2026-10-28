"use client";

import * as React from "react";
import { CHECK_ORDER, STATUS_ORDER, ordered, statusWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import type { CheckType, EvidenceRow, RecordStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { STATUS_MARK } from "@/components/records/record-status-badge";
import { EvidenceState, IndependenceMarker, ResolvedLine, isFull, rowSentence, showsIndependence, type AnyRow } from "@/components/records/evidence-marks";

/** "B.Tech CSE" from "B.Tech Computer Science and Engineering" and CSE; the code alone when the name has no short degree word. */
export function programmeShort(name: string, code: string): string {
  const degree = /^([A-Z][A-Za-z]*\.[A-Za-z.]+)\s/.exec(name)?.[1];
  return degree ? `${degree} ${code}` : code;
}

/** record.header: "B.Tech CSE 2026, ABC College of Engineering · APAAR XXXX XXXX 4417". */
export function recordHeader(p: {
  programmeName: string;
  programmeCode: string;
  cohortYear: string;
  institutionName: string;
  apaarMasked: string | null;
  provisionalId: string | null;
}): string {
  return t("record.header", {
    programme_short: programmeShort(p.programmeName, p.programmeCode),
    cohort_start: p.cohortYear.slice(0, 4),
    institution_name: p.institutionName,
    id_label: p.apaarMasked ? "APAAR" : t("provisional.label"),
    id_masked: p.apaarMasked ?? p.provisionalId ?? "",
  });
}

export type CardAudience = "officer" | "registrar" | "university" | "student";

export interface RecordCardProps {
  header: string;
  /** Short name for the card's accessible label (record.aria_card). */
  programmeShort: string;
  institutionName: string;
  rows: AnyRow[];
  status: RecordStatus | null;
  statusReason: string | null;
  nextStep: string | null;
  audience: CardAudience;
  /** Shows each row's detail sentence under it (record.details_show). */
  showDetails?: boolean;
  className?: string;
}

/**
 * The deck's record card (page spec W4-1, copy deck §22): header, the five
 * rows as a real table (Check, Evidence state, Source and date), the footer
 * with the status and next step, and the status legend. On a phone the
 * table becomes five stacked blocks in the same order.
 */
export function RecordCard({ header, programmeShort: short, institutionName, rows, status, statusReason, nextStep, audience, showDetails = false, className }: RecordCardProps) {
  const list = ordered(rows);
  const legendId = React.useId();
  return (
    <section
      aria-label={t("record.aria_card", { programme_short: short, institution_name: institutionName })}
      className={cn("record-card overflow-hidden rounded-md border border-rule-strong bg-paper-raised shadow-hairline", className)}
    >
      <p className="max-w-none border-b border-rule bg-paper px-4 py-3 font-display text-md font-semibold leading-snug md:px-5 [overflow-wrap:anywhere]">{header}</p>
      {list.length === 0 ? (
        <p className="px-4 py-6 text-sm text-ink-muted md:px-5">{t("empty.checks")}</p>
      ) : (
        <table className="w-full border-collapse text-sm max-md:block">
          <caption className="sr-only">{t("enrolment.section.checks")}</caption>
          <thead className="max-md:sr-only">
            <tr className="border-b border-rule text-left text-xs text-ink-muted">
              <th scope="col" className="w-[9.5rem] px-4 py-2 font-medium md:px-5">
                {t("record.col.check")}
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                {t("record.col.state")}
              </th>
              <th scope="col" className="px-3 py-2 font-medium md:pr-5">
                {t("record.col.source")}
              </th>
            </tr>
          </thead>
          <tbody className="max-md:block">
            {list.map((row) => (
              <RecordRow key={row.type} row={row} institutionName={institutionName} showDetails={showDetails} />
            ))}
          </tbody>
        </table>
      )}
      <footer className="flex flex-col gap-2 border-t border-rule-strong bg-paper px-4 py-3 md:px-5">
        {status && <FooterStatus status={status} nextStep={nextStep} />}
        {status && audience !== "student" && statusReason && <p className="text-sm text-ink-muted">{t("record.reason", { status_reason: statusReason })}</p>}
        {status && audience === "student" && <p className="max-w-[65ch] text-sm text-ink">{tk(`record_status.student.${status}`)}</p>}
        <Legend current={status} id={legendId} />
      </footer>
    </section>
  );
}

function RecordRow({ row, institutionName, showDetails }: { row: AnyRow; institutionName: string; showDetails: boolean }) {
  const full = isFull(row) ? (row as EvidenceRow) : null;
  const contradicted = row.state === "CONTRADICTED";
  return (
    <tr className={cn("border-b border-rule align-top last:border-b-0 max-md:block max-md:px-4 max-md:py-3", contradicted && "bg-check-fail-soft/40")}>
      <th scope="row" className="px-4 py-2.5 text-left font-medium max-md:block max-md:p-0 max-md:text-xs max-md:tracking-wide max-md:text-ink-muted max-md:uppercase md:px-5">
        <span className="sr-only">{rowSentence(row)}</span>
        <span aria-hidden="true" title={tk(`check.label_tip.${row.type}`)} className="cursor-help underline decoration-rule decoration-dotted underline-offset-4">
          {tk(`check.${row.type}`)}
        </span>
      </th>
      <td aria-hidden="true" className="px-3 py-2.5 max-md:block max-md:px-0 max-md:pt-1 max-md:pb-0 max-md:text-md">
        <EvidenceState row={row} />
        <ResolvedLine row={row} />
        {showDetails && full && (
          <p className="mt-1.5 max-w-[60ch] text-xs leading-snug text-ink-muted [overflow-wrap:anywhere]">
            {full.summary}
            {full.attempts > 0 && <span className="mt-0.5 block">{t("check.attempts", { n: full.attempts })}</span>}
          </p>
        )}
      </td>
      <td aria-hidden="true" className="px-3 py-2.5 text-ink-muted max-md:block max-md:px-0 max-md:pt-1 max-md:pb-0 md:pr-5">
        {full ? <span className="block text-ink [overflow-wrap:anywhere]">{full.source_line || (full.checked_at ? "" : t("check.never"))}</span> : null}
        {showsIndependence(row) && (
          <span className="mt-1 block">
            <IndependenceMarker row={row} institutionName={institutionName} />
          </span>
        )}
      </td>
    </tr>
  );
}

/** "Status: Disputed (priority). Next step: College asked for admission documents by 29 Aug." */
function FooterStatus({ status, nextStep }: { status: RecordStatus; nextStep: string | null }) {
  const { Icon, ink } = STATUS_MARK[status];
  const word = statusWord(status, true);
  const [before, after] = t("record.footer_status", { status_word: "\u0000" }).split("\u0000");
  return (
    <p className="max-w-none text-md leading-snug">
      <span className="font-medium">{before}</span>
      <span className={cn("inline-flex items-baseline gap-1 font-semibold", ink)}>
        <Icon className="size-4 shrink-0 self-center" aria-hidden="true" />
        {word}
      </span>
      <span className="font-medium">{after}</span>
      {nextStep && <span>{` ${t("record.footer_next", { next_step: nextStep })}`}</span>}
    </p>
  );
}

/** The deck's legend: the four statuses in order, the record's own marked by weight and icon, with their meanings behind a disclosure. */
export function Legend({ current, id }: { current: RecordStatus | null; id?: string }) {
  return (
    <div className="flex flex-col gap-1.5 text-xs text-ink-muted">
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1" aria-label={t("record_status.legend")}>
        {STATUS_ORDER.map((s, i) => {
          const { Icon, ink } = STATUS_MARK[s];
          const mine = s === current;
          return (
            <React.Fragment key={s}>
              {i > 0 && <span aria-hidden="true">·</span>}
              <span className={cn("inline-flex items-center gap-1", mine && cn("font-semibold", ink))} aria-current={mine ? "true" : undefined}>
                <Icon className={cn("size-3.5 shrink-0", !mine && "opacity-70")} aria-hidden="true" />
                {statusWord(s)}
              </span>
            </React.Fragment>
          );
        })}
      </p>
      <details id={id} className="group">
        <summary className="inline-flex min-h-8 cursor-pointer items-center text-ink-blue underline-offset-4 hover:underline">{t("record_status.legend_label")}</summary>
        <dl className="mt-1.5 grid max-w-[70ch] grid-cols-1 gap-x-3 gap-y-1 sm:grid-cols-[auto_1fr]">
          {STATUS_ORDER.map((s) => {
            const { Icon, ink } = STATUS_MARK[s];
            return (
              <React.Fragment key={s}>
                <dt className={cn("inline-flex items-center gap-1 font-medium", ink)}>
                  <Icon className="size-3.5 shrink-0" aria-hidden="true" />
                  {statusWord(s)}
                </dt>
                <dd className="text-ink">{tk(`record_status.meaning.${s}`)}</dd>
              </React.Fragment>
            );
          })}
        </dl>
        <p className="mt-2 max-w-[70ch] text-ink">{t("record_status.rule")}</p>
      </details>
    </div>
  );
}

/** Five skeleton rows in the card's frame while the record loads. */
export function RecordCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-md border border-rule-strong bg-paper-raised" aria-hidden="true">
      <div className="h-11 border-b border-rule bg-paper" />
      {CHECK_ORDER.map((c: CheckType) => (
        <div key={c} className="flex gap-4 border-b border-rule px-5 py-3 last:border-b-0">
          <div className="h-4 w-24 animate-pulse rounded bg-paper-sunken" />
          <div className="h-4 w-48 animate-pulse rounded bg-paper-sunken" />
          <div className="hidden h-4 w-56 animate-pulse rounded bg-paper-sunken md:block" />
        </div>
      ))}
      <div className="h-16 border-t border-rule-strong bg-paper" />
    </div>
  );
}
