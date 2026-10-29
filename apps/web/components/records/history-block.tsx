"use client";

import * as React from "react";
import Link from "next/link";
import { t, tk } from "@/lib/copy";
import { formatCardDate, formatClock } from "@/lib/format";
import { useEnrolmentHistory } from "@/lib/queries-records";
import type { EnrolmentVersion, FieldChange } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { SectionHeader } from "@/components/common/page-header";
import { ErrorBlock } from "@/components/common/query-state";
import { Pager } from "@/components/common/pager";
import { roleWordOf } from "@/components/cases/case-words";

const PAGE_SIZE = 25;
const ENUM_PREFIX: Record<string, string> = {
  admission_route: "route",
  category: "category",
  consent_status: "consent",
  status: "enrol_status",
};
const DATE_FIELDS = new Set(["dob", "admission_date", "status_date"]);

/** A value as the history prints it: masked as sent, enums in the deck's words, a null as "blank". */
function valueWord(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return t("history.blank");
  if (typeof value === "boolean") return value ? "yes" : "no";
  const text = String(value);
  if (ENUM_PREFIX[field]) return tk(`${ENUM_PREFIX[field]}.${text}`);
  if (DATE_FIELDS.has(field)) return formatCardDate(text);
  return text;
}

function fieldWord(field: string): string {
  return tk(field === "apaar_masked" ? "field.apaar_id" : `field.${field}`);
}

/** The sentences of one version (copy deck §22): the record's creation, or one sentence per changed field. */
function sentences(v: EnrolmentVersion): string[] {
  const date = formatCardDate(v.at);
  if (v.version === 1) {
    if (v.source === "SEED") return [t("history.created.SEED", { date })];
    if (v.batch) return [t("history.created.UPLOAD", { filename: v.batch.filename, date })];
    return [t("history.created.API", { date })];
  }
  const source = v.source === "UPLOAD" && !v.batch ? "API" : v.source;
  return v.changes.map((c: FieldChange) =>
    tk(`history.change.${source}`, { field_word: fieldWord(c.field), before: valueWord(c.field, c.before), after: valueWord(c.field, c.after), date }),
  );
}

export type HistoryAudience = "officer" | "registrar" | "university" | "student";

/**
 * The record's history (page spec W4-1, item 9): every version newest first,
 * one sentence per change. Officers see who acted by name and role; the
 * registrar and the university the role only; the student only the sentences.
 */
export function HistoryBlock({
  enrolmentId,
  audience,
  caseHref,
}: {
  enrolmentId: string;
  audience: HistoryAudience;
  caseHref?: (id: string) => string | null;
}) {
  const [page, setPage] = React.useState(1);
  const q = useEnrolmentHistory(enrolmentId, page);
  const ids = React.useId();
  const showBy = audience !== "student";
  const by = (v: EnrolmentVersion) => {
    if (!v.actor) return "";
    const role = roleWordOf(v.actor.role, null);
    if (audience !== "officer") return t("history.by_role", { role_word: role });
    // "Registrar, ABC College of Engineering" already names the role; the deck's "{name}, {role_word}" would say it twice.
    return v.actor.name.toLowerCase().startsWith(role.toLowerCase()) ? v.actor.name : t("history.by_named", { name: v.actor.name, role_word: role });
  };
  const when = (at: string) => `${formatCardDate(at)}, ${formatClock(at).slice(0, 5)} IST`;
  const items = q.data?.items ?? [];

  return (
    <section aria-labelledby={`${ids}-heading`}>
      <SectionHeader id={`${ids}-heading`} title={t("history.heading")} />
      {q.isError && !q.data ? (
        <ErrorBlock error={q.error} onRetry={() => q.refetch()} />
      ) : q.isLoading ? (
        <div className="flex flex-col gap-2" aria-hidden="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : items.length === 0 ? (
        <p className="border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm text-ink-muted">{t("history.empty")}</p>
      ) : (
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          <table className="w-full border-collapse text-sm max-md:block">
            <caption className="sr-only">{t("history.heading")}</caption>
            <thead className="max-md:sr-only">
              <tr className="border-b border-rule-strong text-left text-xs text-ink-muted">
                <th scope="col" className="w-44 px-3 py-2 font-medium">
                  {t("history.col.when")}
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  {t("history.col.what")}
                </th>
                {showBy && (
                  <th scope="col" className="w-56 px-3 py-2 font-medium">
                    {t("history.col.by")}
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="max-md:block">
              {items.map((v) => {
                const link = v.case && caseHref ? caseHref(v.case.id) : null;
                return (
                  <tr key={v.version} className="border-b border-rule align-top last:border-b-0 max-md:block max-md:px-3 max-md:py-2.5">
                    <td className="px-3 py-2 whitespace-nowrap text-ink-muted max-md:block max-md:p-0 max-md:text-xs">{when(v.at)}</td>
                    <td className="px-3 py-2 max-md:block max-md:p-0 max-md:pt-1">
                      {sentences(v).map((s) => (
                        <p key={s} className="leading-snug [overflow-wrap:anywhere]">
                          {s}
                        </p>
                      ))}
                      <p className="mt-0.5 text-xs text-ink-muted">
                        {v.batch && <>{t("history.file", { filename: v.batch.filename })} · </>}
                        {v.case &&
                          (link ? (
                            <>
                              <Link href={link}>{t("history.case_link", { case_name: tk(`flag.${v.case.type}.name`) })}</Link> ·{" "}
                            </>
                          ) : audience !== "student" ? (
                            <>{t("history.case_link", { case_name: tk(`flag.${v.case.type}.name`) })} · </>
                          ) : null)}
                        {t("history.version", { version: v.version })}
                      </p>
                    </td>
                    {showBy && <td className="px-3 py-2 text-ink-muted max-md:block max-md:p-0 max-md:pt-1 max-md:text-xs">{by(v)}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {q.data && q.data.total > PAGE_SIZE && (
            <div className="flex justify-end border-t border-rule px-3 py-2">
              <Pager page={q.data.page} pageSize={q.data.page_size} total={q.data.total} busy={q.isFetching} onPage={setPage} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
