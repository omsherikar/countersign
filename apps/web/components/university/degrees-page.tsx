"use client";

import * as React from "react";
import Link from "next/link";
import { Check, Download, Minus, Printer, Stamp, X } from "lucide-react";
import { toast } from "sonner";
import { api, API_BASE } from "@/lib/api";
import { t } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useGraduates, useIssueDegree } from "@/lib/queries-student";
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

export function DegreeStatus({ degree }: { degree: GraduateRow["degree"] }) {
  if (!degree)
    return (
      <StatusWord tone="neutral" icon={Minus}>
        {t("degree.status.none")}
      </StatusWord>
    );
  if (degree.status === "REVOKED")
    return (
      <StatusWord tone="alert" icon={X}>
        {t("degree.status.revoked")}
      </StatusWord>
    );
  return (
    <StatusWord tone="ok" icon={Check}>
      {t("degree.status.active", { issued_date: formatDate(degree.issued_at) })}
    </StatusWord>
  );
}

/** Download PDF: a real link to the insert, fetched in place so an error shows as a message, not a page of JSON. */
export function PdfLink({ enrolmentId, className, describedBy }: { enrolmentId: string; className?: string; describedBy?: string }) {
  const [busy, setBusy] = React.useState(false);
  const path = `/university/degrees/${enrolmentId}/insert.pdf`;
  return (
    <a
      href={`${API_BASE}${path}`}
      aria-describedby={describedBy}
      title={t("degree.pdf_note")}
      aria-disabled={busy || undefined}
      className={cn("inline-flex items-center gap-1.5", busy && "pointer-events-none opacity-60", className)}
      onClick={(e) => {
        e.preventDefault();
        if (busy) return;
        setBusy(true);
        api
          .download(path, "degree-insert.pdf")
          .catch((err: unknown) => toast.error(`${deckError(err)} ${t("err.ref", { code: errorCodeOf(err) })}`))
          .finally(() => setBusy(false));
      }}
    >
      <Download className="size-4" aria-hidden="true" />
      {t("degree.pdf")}
    </a>
  );
}

/** The issue dialog (W3-5): what issuing does, the revocation note, and the provisional note when there is no APAAR. */
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
  const issue = useIssueDegree();
  const name = graduate.student.name;
  const confirm = () => {
    if (issue.isPending) return;
    issue.mutate(graduate.enrolment_id, {
      onSuccess: () => {
        toast(t("degree.issued_toast", { student_name: name }));
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
      title={t("degree.issue_heading", { student_name: name })}
      description={t("degree.issue_body", { programme_name: graduate.programme.name, year_of_award: graduate.year_of_award })}
      footer={
        <div className="flex flex-col gap-3 md:flex-row-reverse">
          <button type="button" className={cn(primaryButton, "md:w-auto")} onClick={confirm} disabled={issue.isPending}>
            <Stamp className="size-5" aria-hidden="true" />
            {issue.isPending ? t("degree.issuing") : t("degree.issue_confirm")}
          </button>
          <button type="button" className={cn(outlineButton, "md:w-auto")} onClick={() => onOpenChange(false)} disabled={issue.isPending}>
            {t("degree.issue_cancel")}
          </button>
        </div>
      }
    >
      <div className="flex flex-col gap-3">
        <p>{t("degree.issue_note")}</p>
        <p>{t("degree.issue_revocation_note")}</p>
        {!graduate.student.apaar_masked && <p className="border-l-2 border-line bg-paper px-3 py-2">{t("degree.provisional_note")}</p>}
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
  const active = g.degree?.status === "ACTIVE";
  const printId = `print-${g.enrolment_id}`;
  if (active) {
    return (
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <Link id={printId} href={`/university/degrees/${g.enrolment_id}/print`} className="inline-flex min-h-8 items-center gap-1.5">
          <Printer className="size-4" aria-hidden="true" />
          {t("degree.print_insert")}
        </Link>
        <PdfLink enrolmentId={g.enrolment_id} describedBy="degree-pdf-note" className="min-h-8" />
      </div>
    );
  }
  return (
    <>
      <button type="button" className={cn(outlineButton, "h-8 w-auto px-3 text-sm")} onClick={() => setIssuing(true)}>
        <Stamp className="size-4" aria-hidden="true" />
        {t("degree.issue")}
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

/** W3-5 `/university/degrees`: graduates of the affiliates, issue a degree proof, then print or download the insert. */
export function DegreesPage() {
  const [params, set] = useUrlParams();
  const q = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const list = useGraduates({ page, page_size: PAGE_SIZE, q: q || undefined });
  const onSearch = React.useCallback((value: string) => set({ q: value, page: null }), [set]);
  const data = list.data;
  const rows = data?.items ?? [];
  const count = data ? t("degree.count", { total: formatCount(data.total) }).replace(/^1 graduates$/, "1 graduate") : null;

  return (
    <div>
      <Crumbs items={[{ label: t("nav.affiliated"), href: "/university" }, { label: t("degree.heading") }]} />
      <PageHeader title={t("degree.heading")} description={<p>{t("degree.lead")}</p>} />
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <SearchInput label={t("degree.search")} value={q} onChange={onSearch} delay={250} className="w-full sm:w-96" />
        {count && (
          <span className="num text-sm text-ink-muted" aria-live="polite">
            {count}
          </span>
        )}
      </div>
      <p id="degree-pdf-note" className="sr-only">
        {t("degree.pdf_note")}
      </p>
      <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table" aria-busy={list.isFetching}>
          <caption className="sr-only">{t("degree.heading")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("degree.col.student")}</th>
              <th scope="col" className="code">
                {t("col.apaar")}
              </th>
              <th scope="col">{t("col.institution")}</th>
              <th scope="col" className="code">
                {t("col.programme")}
              </th>
              <th scope="col" className="num">
                {t("degree.col.year_of_award")}
              </th>
              <th scope="col">{t("degree.col.proof")}</th>
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
                    <DegreeStatus degree={g.degree} />
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
