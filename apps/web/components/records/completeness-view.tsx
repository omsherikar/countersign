"use client";

import * as React from "react";
import Link from "next/link";
import { Download, Upload } from "lucide-react";
import { download } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatCardDate, formatCount } from "@/lib/format";
import { useCompleteness } from "@/lib/queries-records";
import type { InstitutionCompleteness, MissingStudent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock, errorMessage } from "@/components/common/query-state";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { DeadlineWord, completenessLine, deadlineTip } from "@/components/records/deadline-word";

/** "round 2", or "Management admission approved by the state" outside counselling (copy deck §15). */
function roundWords(m: MissingStudent): string {
  if (m.route === "COUNSELLING" || m.route === "LATERAL") return m.round ? `round ${m.round}` : tk(`route.${m.route}`);
  return `${tk(`route.${m.route}`)} admission approved by the state`;
}

/** The masked APAAR as sent, else the authority's roll number masked to its last four (D40). */
function MissingId({ m }: { m: MissingStudent }) {
  if (m.apaar_masked) return <MaskedApaar apaarMasked={m.apaar_masked} />;
  return <span className="font-mono text-xs text-ink-muted">{m.roll_no ? `Roll XXXX${m.roll_no.slice(-4)}` : ""}</span>;
}

export type CompletenessAudience = "officer" | "college" | "university";

/**
 * Completeness and missing students (page spec W4-4): the line, the deadline
 * word with its dates as visible text, the counts, the Missing from upload
 * case, and the students the authority lists as joined but the uploads lack.
 */
export function CompletenessView({
  institutionId,
  academicYear,
  audience,
  caseHref,
  headingLevel = "h2",
}: {
  institutionId: string;
  academicYear: string;
  audience: CompletenessAudience;
  caseHref?: (id: string) => string;
  headingLevel?: "h1" | "h2";
}) {
  const q = useCompleteness(institutionId, academicYear);
  const c = q.data;
  const [csvError, setCsvError] = React.useState<string | null>(null);
  const Heading = headingLevel;

  if (q.isError && !c) return <ErrorBlock error={q.error} entity="institution" onRetry={() => q.refetch()} />;
  if (!c) {
    return (
      <div className="flex flex-col gap-3" aria-hidden="true">
        <Skeleton className="h-7 w-96 max-w-full" />
        <Skeleton className="h-5 w-80 max-w-full" />
        <Skeleton className="mt-4 h-40" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <Summary c={c} caseHref={caseHref} Heading={Heading} />
      {c.published && c.completeness_pct !== null && audience !== "university" && (
        <section aria-labelledby={`missing-${institutionId}`} className="flex flex-col gap-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 id={`missing-${institutionId}`} className="text-xl">
              {t("missing.heading", { n: formatCount(c.missing) })}
            </h2>
            {c.missing > 0 && (
              <Button
                variant="outline"
                className="h-11 sm:h-9"
                onClick={() => {
                  setCsvError(null);
                  download(`/institutions/${institutionId}/completeness.csv`, `missing_${academicYear}.csv`).catch((e) => setCsvError(errorMessage(e)));
                }}
              >
                <Download className="size-4" aria-hidden="true" />
                {t("missing.download")}
              </Button>
            )}
          </div>
          {csvError && (
            <p role="alert" className="text-sm text-check-fail-ink">
              {csvError}
            </p>
          )}
          {c.missing === 0 ? (
            <p className="border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm text-ink-muted">{t("missing.none")}</p>
          ) : (
            <>
              <p className="max-w-[80ch] text-sm text-ink">
                {audience === "college"
                  ? t("missing.lead_college", { academic_year: c.academic_year })
                  : t("missing.lead_officer", { institution_name: c.institution.name, academic_year: c.academic_year })}
              </p>
              <MissingTable students={c.missing_students ?? []} />
              {audience === "college" && (
                <p>
                  <Button asChild className="h-12 w-full sm:h-9 sm:w-auto">
                    <Link href="/college/upload">
                      <Upload className="size-4" aria-hidden="true" />
                      {t("upload.upload_again")}
                    </Link>
                  </Button>
                </p>
              )}
              <ReadLoggedNote />
            </>
          )}
        </section>
      )}
    </div>
  );
}

function Summary({ c, caseHref, Heading }: { c: InstitutionCompleteness; caseHref?: (id: string) => string; Heading: "h1" | "h2" }) {
  const line = completenessLine(c);
  return (
    <div className="flex flex-col gap-2">
      <Heading className={Heading === "h1" ? "text-2xl md:text-3xl" : "text-xl"}>{t("completeness.heading")}</Heading>
      <p className="max-w-none font-display text-lg font-semibold">{line}</p>
      <p className="flex max-w-none flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <DeadlineWord state={c.deadline_state} deadline={c.deadline} firstUploadAt={c.first_upload_at} className="font-medium" />
        <span className="text-ink-muted">{deadlineTip(c.deadline_state, c.deadline, c.first_upload_at)}</span>
      </p>
      {c.published && c.completeness_pct !== null && (
        <p className="max-w-none text-sm text-ink-muted">
          {t("completeness.col_joined")} {formatCount(c.joined)} · {t("completeness.col_uploaded")} {formatCount(c.uploaded_and_joined)} ·{" "}
          {t("completeness.col_missing")} {formatCount(c.missing)}
        </p>
      )}
      {c.case && caseHref && c.missing > 0 && (
        <p className="text-sm">
          <Link href={caseHref(c.case.id)}>{t("missing.case_line")}</Link>
        </p>
      )}
      <p className="max-w-[80ch] text-xs text-ink-muted">{t("completeness.tip", { academic_year: c.academic_year })}</p>
    </div>
  );
}

function MissingTable({ students }: { students: MissingStudent[] }) {
  return (
    <>
      <div className="relative hidden overflow-x-auto border-l-2 border-rule-margin bg-paper-raised md:block">
        <table className="ledger-table">
          <caption className="sr-only">{t("missing.heading", { n: students.length })}</caption>
          <thead>
            <tr>
              <th scope="col">{t("missing.col.student")}</th>
              <th scope="col" className="code">
                {t("col.apaar")}
              </th>
              <th scope="col" className="code">
                {t("missing.col.programme")}
              </th>
              <th scope="col">{t("missing.col.joined_on")}</th>
              <th scope="col">{t("missing.col.round")}</th>
            </tr>
          </thead>
          <tbody>
            {students.map((m) => (
              <tr key={`${m.name}-${m.roll_no ?? m.apaar_masked}`}>
                <td className="font-medium">{m.name}</td>
                <td className="code">
                  <MissingId m={m} />
                </td>
                <td className="code">{m.programme_code}</td>
                <td>{formatCardDate(m.joined_on)}</td>
                <td className="wrap">{roundWords(m)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="flex flex-col border-l-2 border-rule-margin bg-paper-raised md:hidden">
        {students.map((m) => (
          <li key={`${m.name}-${m.roll_no ?? m.apaar_masked}`} className="border-b border-rule px-4 py-3 last:border-b-0">
            <p className="font-medium">{m.name}</p>
            <p className="mt-0.5">
              <MissingId m={m} />
            </p>
            <p className="mt-1 text-sm text-ink-muted">
              {m.programme_code} · {t("missing.col.joined_on")} {formatCardDate(m.joined_on)} · {roundWords(m)}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
