"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, Printer } from "lucide-react";
import { ApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { useDegreePrint } from "@/lib/queries-student";
import type { CertificatePrint, GraduateRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Crumbs } from "@/components/common/page-header";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Skeleton } from "@/components/ui/skeleton";
import { QrImage, outlineButton, primaryButton } from "@/components/student/bits";
import { deckError, errorCodeOf } from "@/components/student/errors";
import { IssueDialog, PdfLink } from "@/components/university/degrees-page";

/** "localhost:3000/verify": the verify page's host and path, never the long QR link itself. */
function verifyPlace(url: string): string {
  try {
    return `${new URL(url).host}/verify`;
  } catch {
    return "/verify";
  }
}

/** Print rules for this page only: A4 portrait, white paper, black ink, nothing but the insert. */
const PRINT_CSS = `
@media print {
  @page { size: A4 portrait; margin: 16mm; }
  html, body { background: #fff !important; color: #000 !important; }
  .degree-insert, .degree-insert * { color: #000 !important; background: transparent !important; box-shadow: none !important; }
  .degree-insert { border: 0 !important; }
  .degree-insert .insert-rule { border-color: #000 !important; }
  .degree-insert img { width: 35mm !important; height: 35mm !important; }
}`;

function Insert({ print }: { print: CertificatePrint }) {
  const degree = print.attestation!;
  const apaar = print.student.id_kind === "APAAR";
  const rows: [string, React.ReactNode][] = [
    [t("degree.print.name"), print.student.name],
    [t("degree.print.programme"), print.programme.name],
    [t("degree.print.institution"), print.institution.name],
    [t("degree.print.year"), String(print.year_of_award)],
    [apaar ? t("degree.print.apaar") : t("degree.print.provisional"), <span key="id" className="font-mono">{print.student.id_masked}</span>],
  ];
  return (
    <article className="degree-insert mx-auto max-w-[210mm] border border-line bg-paper-raised px-6 py-8 shadow-hairline print:max-w-none print:px-0 print:py-0 md:px-12 md:py-12">
      <h1 className="text-2xl md:text-3xl">{print.university.name}</h1>
      <p className="mt-4 text-md">{t("degree.print.accompanies")}</p>
      <div className="mt-4 flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between print:flex-row">
        <dl className="insert-rule min-w-0 flex-1 border-t border-rule-strong">
          {rows.map(([label, value]) => (
            <div key={label} className="insert-rule flex flex-wrap gap-x-6 gap-y-0.5 border-b border-rule py-2.5 text-md">
              <dt className="w-36 shrink-0 text-ink-muted">{label}</dt>
              <dd className="min-w-0 flex-1 font-medium break-words">{value}</dd>
            </div>
          ))}
        </dl>
        <figure className="flex shrink-0 flex-col items-center text-center">
          <QrImage svg={degree.qr_svg} alt={t("degree.qr_alt")} className="size-40" />
          <figcaption className="mt-2 text-sm">
            <span className="block font-mono select-all">{t("degree.print.proof_id", { short_id: degree.short_id })}</span>
            <span className="block">{t("degree.scan_line", { verify_url: verifyPlace(degree.verify_url) })}</span>
          </figcaption>
        </figure>
      </div>
      <p className="insert-rule mt-8 max-w-none border-t border-rule pt-3 text-sm">
        {t("degree.print.issued", { issued_date: formatDate(degree.issued_at) })}. {t("degree.print.signed", { university_name: print.university.name })}
      </p>
    </article>
  );
}

function InsertSkeleton() {
  return (
    <div className="mx-auto max-w-[210mm] border border-line bg-paper-raised px-6 py-8 md:px-12 md:py-12" aria-hidden="true">
      <Skeleton className="h-8 w-80" />
      <Skeleton className="mt-4 h-5 w-72" />
      <div className="mt-6 flex gap-6">
        <div className="flex flex-1 flex-col gap-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
        <Skeleton className="size-40" />
      </div>
    </div>
  );
}

/** The issue dialog reads a graduates row; the print data carries the same facts. */
function asGraduate(print: CertificatePrint): GraduateRow {
  return {
    enrolment_id: print.enrolment_id,
    student: {
      id: print.enrolment_id,
      name: print.student.name,
      apaar_masked: print.student.id_kind === "APAAR" ? print.student.id_masked : null,
      provisional_id: print.student.id_kind === "PROVISIONAL" ? print.student.id_masked : null,
    },
    institution: { id: "", name: print.institution.name, aicte_permanent_id: print.institution.aicte_permanent_id },
    programme: { id: "", code: print.programme.code, name: print.programme.name, level: "UG" },
    academic_year: print.academic_year,
    year_of_award: print.year_of_award,
    attestation: null,
  };
}

/**
 * W3-5 print view: the A4 insert with the masked APAAR and the degree QR,
 * the proof id and the verify address as text under it. On screen a bar
 * offers Print and Back; the printout leaves out navigation and colour.
 */
export function DegreePrintPage({ enrolmentId }: { enrolmentId: string }) {
  const print = useDegreePrint(enrolmentId);
  const [issuing, setIssuing] = React.useState(false);
  const data = print.data;
  const name = data?.student.name;
  React.useEffect(() => {
    if (name) document.title = `${t("degree.print_title", { student_name: name })} | ${t("brand.name")}`;
  }, [name]);

  const revoked = data?.attestation?.status === "REVOKED";
  const credentialError = print.error instanceof ApiError && print.error.code.startsWith("CREDENTIAL_");
  const ready = data?.attestation && data.attestation.status === "ACTIVE";
  const back = (
    <Link href="/university/degrees" className="inline-flex min-h-11 items-center gap-1.5">
      <ArrowLeft className="size-4" aria-hidden="true" />
      {t("degree.print_back")}
    </Link>
  );

  return (
    <div>
      <style>{PRINT_CSS}</style>
      <div className="print:hidden">
        <Crumbs
          items={[
            { label: t("nav.affiliated"), href: "/university" },
            { label: t("degree.heading"), href: "/university/degrees" },
            ...(name ? [{ label: name }] : []),
          ]}
        />
        <div className="mb-6 flex flex-wrap items-center gap-x-5 gap-y-2">
          {ready && (
            <button type="button" className={cn(primaryButton, "h-10 w-auto px-5")} onClick={() => window.print()}>
              <Printer className="size-5" aria-hidden="true" />
              {t("degree.print")}
            </button>
          )}
          {back}
          {ready && <PdfLink enrolmentId={enrolmentId} className="min-h-11" />}
          {ready && <p className="basis-full text-sm text-ink-muted">{t("degree.print_hint")}</p>}
        </div>
      </div>

      {print.isLoading && (
        <>
          <InsertSkeleton />
          <SlowHint />
        </>
      )}
      {print.isError && !data && credentialError && (
        <div role="alert" className="max-w-[68ch] border-l-2 border-check-fail bg-paper-raised px-4 py-4">
          <p>{deckError(print.error)}</p>
          <p className="code mt-1 text-xs text-ink-muted">{t("err.ref", { code: errorCodeOf(print.error) })}</p>
        </div>
      )}
      {print.isError && !data && !credentialError && (
        <ErrorBlock
          error={print.error}
          entity="enrolment"
          onRetry={() => print.refetch()}
          backHref="/university/degrees"
          backLabel={t("degree.print_back")}
        />
      )}
      {data && revoked && (
        <div role="alert" className="max-w-[68ch] border-l-2 border-check-fail bg-paper-raised px-4 py-4">
          <p>{t("err.CREDENTIAL_REVOKED")}</p>
        </div>
      )}
      {data && !data.attestation && (
        <div className="max-w-[68ch] border-l-2 border-rule-margin bg-paper-raised px-4 py-4">
          <p className="font-medium">{t("degree.issue_heading", { student_name: data.student.name })}</p>
          <p className="mt-1 text-ink-muted">{t("degree.issue_body", { programme_name: data.programme.name, year_of_award: data.year_of_award })}</p>
          <button type="button" className={cn(outlineButton, "mt-3 h-11 w-auto px-4")} onClick={() => setIssuing(true)}>
            {t("degree.issue")}
          </button>
          <IssueDialog graduate={asGraduate(data)} open={issuing} onOpenChange={setIssuing} />
        </div>
      )}
      {data && ready && <Insert print={data} />}
    </div>
  );
}
