"use client";

import * as React from "react";
import Link from "next/link";
import { Check, ChevronRight, Download, Minus, Printer, Stamp, X } from "lucide-react";
import { toast } from "sonner";
import { api, API_BASE } from "@/lib/api";
import { t } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useGraduates, useIssueCompletion } from "@/lib/queries-student";
import type { GraduateRow } from "@/lib/types";
import { useUrlParams } from "@/lib/use-url-params";
import { cn } from "@/lib/utils";
import { EmptyState } from "@/components/brand/EmptyState";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { SearchInput } from "@/components/common/filter-select";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { Crumbs, PageHeader } from "@/components/common/page-header";
import { Pager } from "@/components/common/pager";
import { ErrorBlock, SkeletonRows, SlowHint, TableMessage } from "@/components/common/query-state";
import { SheetDialog, StatusWord, outlineButton, primaryButton } from "@/components/student/bits";
import { deckError, errorCodeOf } from "@/components/student/errors";

const PAGE_SIZE = 25;
const COLS = 6;

export function AttestationStatus({ attestation }: { attestation: GraduateRow["attestation"] }) {
  if (!attestation)
    return (
      <StatusWord tone="neutral" icon={Minus}>
        {t("cert.status.none")}
      </StatusWord>
    );
  if (attestation.status === "REVOKED")
    return (
      <StatusWord tone="alert" icon={X}>
        {t("cert.status.revoked")}
      </StatusWord>
    );
  return (
    <StatusWord tone="ok" icon={Check}>
      {t("cert.status.active", { issued_date: formatDate(attestation.issued_at) })}
    </StatusWord>
  );
}

/** Download PDF: a real link to the certificate block, fetched in place so an error shows as a message, not a page of JSON. */
export function PdfLink({ enrolmentId, className, describedBy }: { enrolmentId: string; className?: string; describedBy?: string }) {
  const [busy, setBusy] = React.useState(false);
  const path = `/university/certificates/${enrolmentId}/block.pdf`;
  return (
    <a
      href={`${API_BASE}${path}`}
      aria-describedby={describedBy}
      title={t("cert.pdf_note")}
      aria-disabled={busy || undefined}
      className={cn("inline-flex items-center gap-1.5", busy && "pointer-events-none opacity-60", className)}
      onClick={(e) => {
        e.preventDefault();
        if (busy) return;
        setBusy(true);
        api
          .download(path, "certificate-block.pdf")
          .catch((err: unknown) => toast.error(`${deckError(err)} ${t("err.ref", { code: errorCodeOf(err) })}`))
          .finally(() => setBusy(false));
      }}
    >
      <Download className="size-4" aria-hidden="true" />
      {t("cert.pdf")}
    </a>
  );
}

const SEEN_KEY = "cs_cert_how_seen";
const noSubscribe = () => () => {};

/**
 * How it works and the API line, as native disclosures: open on the first
 * visit, closed after that (remembered in this browser only).
 */
function HowItWorks() {
  const [open, setOpen] = React.useState(false);
  const origin = React.useSyncExternalStore(noSubscribe, () => window.location.origin, () => "");
  React.useEffect(() => {
    try {
      if (!localStorage.getItem(SEEN_KEY)) {
        setOpen(true);
        localStorage.setItem(SEEN_KEY, "1");
      }
    } catch {
      // Storage refused: the panel stays closed.
    }
  }, []);
  return (
    <div className="mb-6 flex max-w-[72ch] flex-col gap-2">
      <details className="group border-l-2 border-rule-margin bg-paper-raised px-4 py-2" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 font-medium text-ink-blue [&::-webkit-details-marker]:hidden">
          <ChevronRight className="size-4 shrink-0 group-open:rotate-90" aria-hidden="true" />
          {t("cert.how_heading")}
        </summary>
        <ol className="mb-2 ml-5 list-decimal space-y-1 text-md md:text-sm">
          <li>{t("cert.how_issue")}</li>
          <li>{t("cert.how_print")}</li>
          <li>{t("cert.how_verify")}</li>
        </ol>
      </details>
      <details className="group border-l-2 border-rule-margin bg-paper-raised px-4 py-2">
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 font-medium text-ink-blue [&::-webkit-details-marker]:hidden">
          <ChevronRight className="size-4 shrink-0 group-open:rotate-90" aria-hidden="true" />
          {t("cert.api_heading")}
        </summary>
        <p className="code mb-2 text-sm [overflow-wrap:anywhere]">{t("cert.api_line", { api_url: `${origin}${API_BASE}` })}</p>
      </details>
    </div>
  );
}

/** The issue sheet (W4-12): what issuing does, that it is not a degree, the revocation note, and the provisional note when there is no APAAR. */
export function IssueDialog({
  graduate,
  open,
  onOpenChange,
  onIssued,
}: {
  graduate: GraduateRow;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onIssued?: () => void;
}) {
  const issue = useIssueCompletion();
  const name = graduate.student.name;
  const confirm = () => {
    if (issue.isPending) return;
    issue.mutate(graduate.enrolment_id, {
      onSuccess: () => {
        toast(t("cert.issued_toast", { student_name: name }));
        onOpenChange(false);
        onIssued?.();
      },
    });
  };
  return (
    <SheetDialog
      open={open}
      onOpenChange={(o) => {
        if (issue.isPending) return;
        if (!o) issue.reset();
        onOpenChange(o);
      }}
      title={t("cert.issue_heading", { student_name: name })}
      description={t("cert.issue_body", { student_name: name, programme_name: graduate.programme.name, year: graduate.year_of_award, institution_name: graduate.institution.name })}
      footer={
        <div className="flex flex-col gap-3 md:flex-row-reverse">
          <button type="button" className={cn(primaryButton, "md:w-auto")} onClick={confirm} disabled={issue.isPending}>
            <Stamp className="size-5" aria-hidden="true" />
            {issue.isPending ? t("cert.issuing") : t("cert.issue_confirm")}
          </button>
          <button type="button" className={cn(outlineButton, "md:w-auto")} onClick={() => onOpenChange(false)} disabled={issue.isPending}>
            {t("cert.issue_cancel")}
          </button>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <p>{t("cert.issue_note")}</p>
        <p>{t("cert.issue_revocation_note")}</p>
        {!graduate.student.apaar_masked && <p className="border-l-2 border-line bg-paper px-3 py-2">{t("cert.provisional_note")}</p>}
        {issue.isError && (
          <p role="alert" className="text-check-fail-ink">
            {deckError(issue.error)} <span className="code text-xs text-ink-muted">{t("err.ref", { code: errorCodeOf(issue.error) })}</span>
          </p>
        )}
      </div>
    </SheetDialog>
  );
}

function RowActions({ g }: { g: GraduateRow }) {
  const [issuing, setIssuing] = React.useState(false);
  const active = g.attestation?.status === "ACTIVE";
  const printId = `print-${g.enrolment_id}`;
  if (active) {
    return (
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <Link id={printId} href={`/university/certificates/${g.enrolment_id}/print`} className="hidden min-h-8 items-center gap-1.5 md:inline-flex">
          <Printer className="size-4" aria-hidden="true" />
          {t("cert.print_block")}
        </Link>
        <PdfLink enrolmentId={g.enrolment_id} describedBy="cert-pdf-note" className="min-h-11 md:min-h-8" />
      </div>
    );
  }
  return (
    <>
      <button type="button" className={cn(outlineButton, "h-11 w-full px-3 text-sm md:h-8 md:w-auto")} onClick={() => setIssuing(true)}>
        <Stamp className="size-4" aria-hidden="true" />
        {t("cert.issue")}
      </button>
      <IssueDialog
        graduate={g}
        open={issuing}
        onOpenChange={setIssuing}
        onIssued={() => setTimeout(() => document.getElementById(printId)?.focus(), 400)}
      />
    </>
  );
}

/**
 * W4-12 `/university/certificates`: Countersign does not issue degrees. The
 * graduates of the affiliates, a completion attestation for each, then the
 * certificate block with the masked APAAR and the QR, to print or download.
 */
export function CertificatesPage() {
  const [params, set] = useUrlParams();
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const list = useGraduates({ page, page_size: PAGE_SIZE, q: q || undefined });
  const onSearch = React.useCallback((value: string) => set({ q: value, page: null }), [set]);
  const data = list.data;
  const rows = data?.items ?? [];
  const count = data ? t("cert.count", { total: formatCount(data.total) }).replace(/^1 graduates$/, "1 graduate") : null;

  return (
    <div>
      <Crumbs items={[{ label: t("nav.affiliated"), href: "/university" }, { label: t("cert.heading") }]} />
      <PageHeader title={t("cert.heading")} description={<p className="max-w-[72ch] text-md text-ink md:text-sm">{t("cert.lead")}</p>} />
      <HowItWorks />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <SearchInput label={t("cert.search")} value={q} onChange={onSearch} delay={250} className="w-full sm:w-96" />
        {count && (
          <span className="num text-sm text-ink-muted" aria-live="polite">
            {count}
          </span>
        )}
      </div>
      <p id="cert-pdf-note" className="sr-only">
        {t("cert.pdf_note")}
      </p>
      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("cert.heading")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("cert.col.graduate")}</th>
              <th scope="col" className="code">
                {t("col.apaar")}
              </th>
              <th scope="col">{t("col.institution")}</th>
              <th scope="col" className="code">
                {t("col.programme")}
              </th>
              <th scope="col" className="num">
                {t("cert.col.year")}
              </th>
              <th scope="col">{t("cert.col.attestation")}</th>
            </tr>
          </thead>
          <tbody>
            {list.isLoading && <SkeletonRows cols={COLS} />}
            {list.isError && !data && (
              <TableMessage cols={COLS}>
                <ErrorBlock error={list.error} onRetry={() => list.refetch()} className="m-3" />
              </TableMessage>
            )}
            {data && rows.length === 0 && (
              <TableMessage cols={COLS}>
                <EmptyState title={q ? t("empty.graduates_search", { q }) : t("empty.graduates")} />
              </TableMessage>
            )}
            {rows.map((g) => (
              <tr key={g.enrolment_id}>
                <td className="font-medium">{g.student.name}</td>
                <td className="code">
                  <MaskedApaar apaarMasked={g.student.apaar_masked} provisionalId={g.student.provisional_id} />
                </td>
                <td>{g.institution.name}</td>
                <td className="code" title={g.programme.name}>
                  {g.programme.code}
                </td>
                <td className="num">{g.year_of_award}</td>
                <td className="!h-auto py-1.5">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                    <AttestationStatus attestation={g.attestation} />
                    <RowActions g={g} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-ink-muted">
          <ReadLoggedNote />
        </span>
        {data && data.total > 0 && (
          <Pager page={data.page} pageSize={data.page_size} total={data.total} busy={list.isFetching} onPage={(p) => set({ page: p > 1 ? p : null })} />
        )}
      </div>
      {list.isLoading && <SlowHint />}
    </div>
  );
}
