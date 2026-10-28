"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Download, FileSpreadsheet, Upload, X } from "lucide-react";
import { ApiError, download } from "@/lib/api";
import { t } from "@/lib/copy";
import { formatBytes, formatDate } from "@/lib/format";
import { useUploadFile } from "@/lib/queries";
import { UPLOAD_COLUMNS } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { FilterSelect } from "@/components/common/filter-select";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";

const MAX_BYTES = 20 * 1024 * 1024;
/** Columns whose header must be present (API_CONTRACT A2.2). */
export const REQUIRED_COLUMNS = ["name", "dob", "programme_code", "year_of_study", "admission_route", "category"] as const;
const OPTIONAL_COLUMNS = UPLOAD_COLUMNS.filter((c) => !(REQUIRED_COLUMNS as readonly string[]).includes(c));

/** The two template downloads; the api names the files countersign_upload_template.* (A2.9). */
export function TemplateLinks({ className }: { className?: string }) {
  const [error, setError] = React.useState<string | null>(null);
  const get = (ext: "csv" | "xlsx") => {
    setError(null);
    download(`/uploads/template.${ext}`, `countersign_upload_template.${ext}`).catch((e) => setError(errorMessage(e)));
  };
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <Button type="button" variant="outline" size="sm" onClick={() => get("csv")}>
        <Download className="size-3.5" aria-hidden="true" />
        {t("upload.template_csv")}
      </Button>
      <Button type="button" variant="outline" size="sm" onClick={() => get("xlsx")}>
        <Download className="size-3.5" aria-hidden="true" />
        {t("upload.template_xlsx")}
      </Button>
      {error && (
        <span role="alert" className="text-xs text-check-fail-ink">
          {error}
        </span>
      )}
    </div>
  );
}

/** What the server said, in the deck's words (copy deck §13 and the W2-1 states). */
function ServerError({ error }: { error: unknown }) {
  if (!(error instanceof ApiError)) return <p>{errorMessage(error)}</p>;
  const d = error.details;
  switch (error.code) {
    case "FILE_TOO_LARGE":
    case "TOO_MANY_ROWS":
    case "UNSUPPORTED_FILE_TYPE":
    case "UPLOAD_EMPTY":
      return <p>{t(`err.${error.code}`)}</p>;
    case "UPLOAD_HEADER_INVALID": {
      const missing = Array.isArray(d.missing_columns) ? (d.missing_columns as string[]) : [];
      const duplicate = Array.isArray(d.duplicate_columns) ? (d.duplicate_columns as string[]) : [];
      return (
        <>
          {missing.length > 0 && <p>{t("err.UPLOAD_HEADER_INVALID", { columns: missing.join(", ") })}</p>}
          {duplicate.map((c) => (
            <p key={c}>{t("err.UPLOAD_HEADER_DUPLICATE", { column: c })}</p>
          ))}
          {missing.length === 0 && duplicate.length === 0 && <p>{error.message}</p>}
          <p className="text-ink-muted">{t("upload.header_help")}</p>
        </>
      );
    }
    case "UPLOAD_IN_PROGRESS":
      return (
        <p>
          {t("err.UPLOAD_IN_PROGRESS")}{" "}
          {typeof d.batch_id === "string" && <Link href={`/college/uploads/${d.batch_id}`}>{t("upload.in_progress_link")}</Link>}
        </p>
      );
    default:
      return <p>{errorMessage(error)}</p>;
  }
}

/**
 * The registrar's upload (page spec W2-1): one file for one academic year,
 * the declaration as the registrar's signature, and the bytes going out with
 * a progress bar. A 202 opens the batch page, which follows the pipeline.
 */
export function UploadForm({ years }: { years: string[] }) {
  const router = useRouter();
  const { user } = useMe();
  const upload = useUploadFile();
  const [year, setYear] = React.useState(years[0] ?? "2026-27");
  const [file, setFile] = React.useState<File | null>(null);
  const [localError, setLocalError] = React.useState<string | null>(null);
  const [declared, setDeclared] = React.useState(false);
  const [declarationError, setDeclarationError] = React.useState<string | null>(null);
  const [sent, setSent] = React.useState(0);
  const [over, setOver] = React.useState(false);
  const [today] = React.useState(() => new Date().toISOString());
  const input = React.useRef<HTMLInputElement>(null);
  const declaration = React.useRef<HTMLInputElement>(null);
  const busy = upload.isPending || upload.isSuccess;
  const fieldErrors = upload.error instanceof ApiError && upload.error.code === "VALIDATION_ERROR" ? upload.error.fields : [];
  const yearError = fieldErrors.find((f) => f.field === "academic_year")?.message;
  const serverDeclaration = fieldErrors.find((f) => f.field === "declaration")?.message;
  const generalError = upload.isError && !fieldErrors.some((f) => f.field === "academic_year" || f.field === "declaration");

  function choose(f: File | null | undefined) {
    upload.reset();
    setLocalError(null);
    if (!f) return;
    const ext = f.name.toLowerCase().split(".").pop();
    if (ext !== "csv" && ext !== "xlsx") {
      setFile(null);
      setLocalError(t("upload.err_type"));
      return;
    }
    if (f.size > MAX_BYTES) {
      setFile(null);
      setLocalError(t("upload.err_size"));
      return;
    }
    setFile(f);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !file) return;
    if (!declared) {
      setDeclarationError(t("upload.err_declaration"));
      declaration.current?.focus();
      return;
    }
    setDeclarationError(null);
    setSent(0);
    upload.mutate({ file, academicYear: year, onProgress: setSent }, { onSuccess: (res) => router.push(`/college/uploads/${res.batch.id}`) });
  }

  return (
    <form onSubmit={submit} noValidate className="grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-12">
      <div className="flex min-w-0 flex-col gap-6 lg:col-span-7">
        <div className="flex flex-col gap-1">
          <FilterSelect label={t("upload.year")} value={year} options={years.map((y) => ({ value: y, label: y }))} allLabel={null} onChange={setYear} />
          {yearError && (
            <p role="alert" className="text-xs text-check-fail-ink">
              {yearError}
            </p>
          )}
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            if (!busy) choose(e.dataTransfer.files?.[0]);
          }}
          className={cn(
            "relative flex flex-col gap-4 rounded-md border-2 border-dashed bg-paper-raised px-5 py-6",
            over ? "border-ink-blue bg-flag-open-soft" : "border-rule-strong",
          )}
        >
          <input
            ref={input}
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="sr-only"
            tabIndex={-1}
            aria-hidden="true"
            data-testid="upload-file"
            onChange={(e) => choose(e.target.files?.[0])}
          />
          {file ? (
            <div className="flex flex-wrap items-center gap-3">
              <FileSpreadsheet className="size-8 shrink-0 text-ink-blue" aria-hidden="true" />
              <div className="min-w-0">
                <p className="truncate font-medium">{t("upload.chosen", { filename: file.name, size: formatBytes(file.size) })}</p>
                <p className="text-xs text-ink-muted">{t("upload.max")}</p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="ml-auto"
                disabled={busy}
                onClick={() => {
                  setFile(null);
                  upload.reset();
                  if (input.current) input.current.value = "";
                }}
              >
                <X className="size-3.5" aria-hidden="true" />
                {t("upload.remove")}
              </Button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-4">
              <Upload className="size-8 shrink-0 text-ink-faint" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-medium">{t("upload.drop")}</p>
                <p className="text-xs text-ink-muted">{t("upload.max")}</p>
              </div>
              <Button type="button" variant="outline" onClick={() => input.current?.click()}>
                {t("upload.choose")}
              </Button>
            </div>
          )}
          <TemplateLinks className="border-t border-rule pt-4" />
          {localError && (
            <p role="alert" className="text-sm text-check-fail-ink">
              {localError}
            </p>
          )}
        </div>

        <div className="border-l-2 border-rule-margin bg-paper-raised px-4 py-4">
          <label className="flex items-start gap-3 text-sm leading-relaxed">
            <input
              ref={declaration}
              type="checkbox"
              checked={declared}
              disabled={busy}
              aria-invalid={Boolean(declarationError || serverDeclaration) || undefined}
              aria-describedby={declarationError || serverDeclaration ? "declaration-error" : undefined}
              onChange={(e) => {
                setDeclared(e.target.checked);
                if (e.target.checked) setDeclarationError(null);
              }}
              className="mt-1 size-4 shrink-0 accent-ink-blue"
            />
            <span>{t("upload.declaration")}</span>
          </label>
          {(declarationError || serverDeclaration) && (
            <p id="declaration-error" role="alert" className="mt-2 pl-7 text-xs text-check-fail-ink">
              {declarationError ?? serverDeclaration}
            </p>
          )}
          {user && <p className="mt-3 pl-7 font-display text-sm text-ink-muted italic">{`${user.name}, ${formatDate(today)}`}</p>}
        </div>

        {generalError && (
          <div role="alert" className="flex flex-col gap-1 rounded-md border border-check-fail/30 bg-paper-raised px-4 py-3 text-sm text-ink">
            <ServerError error={upload.error} />
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div>
            <Button type="submit" disabled={busy || !file}>
              <Upload className="size-4" aria-hidden="true" />
              {upload.isPending ? t("upload.sending", { pct: sent }) : t("upload.submit")}
            </Button>
          </div>
          {upload.isPending && (
            <div
              role="progressbar"
              aria-label={t("upload.sending", { pct: sent })}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={sent}
              className="h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-paper-sunken"
            >
              <div className="h-full bg-ink-blue transition-[width] duration-150" style={{ width: `${sent}%` }} />
            </div>
          )}
        </div>
      </div>

      <aside aria-labelledby="columns-heading" className="min-w-0 lg:col-span-5">
        <h2 id="columns-heading" className="mb-3 text-xl">
          {t("upload.columns")}
        </h2>
        <dl className="flex flex-col gap-3 text-sm">
          <div>
            <dt className="mb-1 text-xs font-medium text-ink-muted">{t("upload.columns_required")}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {REQUIRED_COLUMNS.map((c) => (
                <code key={c} title={t(`field.${c}`)} className="rounded-chip border border-ink-blue/30 bg-flag-open-soft px-1.5 py-0.5 font-mono text-xs text-ink">
                  {c}
                </code>
              ))}
            </dd>
          </div>
          <div>
            <dt className="mb-1 text-xs font-medium text-ink-muted">{t("upload.columns_optional")}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {OPTIONAL_COLUMNS.map((c) => (
                <code key={c} title={t(`field.${c}`)} className="rounded-chip border border-line bg-paper-raised px-1.5 py-0.5 font-mono text-xs text-ink-muted">
                  {c}
                </code>
              ))}
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-sm text-ink-muted">{t("upload.columns_note")}</p>
        <p className="mt-3 text-sm text-ink-muted">{t("upload.changes_note")}</p>
      </aside>
    </form>
  );
}
