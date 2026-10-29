"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, Download, FileSpreadsheet, Upload, X } from "lucide-react";
import { ApiError, download } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatBytes, formatDate } from "@/lib/format";
import { useUploadFile } from "@/lib/queries";
import { useColumnMapping, useSaveColumnMapping } from "@/lib/queries-records";
import { UPLOAD_COLUMNS, type ColumnMapping, type UploadColumn } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import {
  MappingProblems,
  MappingRows,
  initialChoices,
  mappingBody,
  needsMapping,
  normaliseHeader,
  problemsOf,
  readCsvHeaders,
  type Choice,
} from "@/components/uploads/column-mapping";
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
          {t("err.UPLOAD_IN_PROGRESS")} {typeof d.batch_id === "string" && <Link href={`/college/uploads/${d.batch_id}`}>{t("upload.in_progress_link")}</Link>}
        </p>
      );
    default:
      return <p>{errorMessage(error)}</p>;
  }
}

type Step = "choose" | "map" | "declare";
const STEPS: Step[] = ["choose", "map", "declare"];

/** "1 Choose file, 2 Map your columns, 3 Declare and upload"; on a phone "Step 2 of 3: Map your columns". */
function StepIndicator({ step }: { step: Step }) {
  const at = STEPS.indexOf(step);
  return (
    <>
      <p className="text-sm font-medium md:hidden" aria-live="polite">
        {t("upload.step_of", { n: at + 1, step_word: tk(`upload.steps.${step}`) })}
      </p>
      <ol className="hidden items-center gap-6 text-sm md:flex" aria-label={t("upload.step_of", { n: at + 1, step_word: tk(`upload.steps.${step}`) })}>
        {STEPS.map((s, i) => (
          <li
            key={s}
            aria-current={i === at ? "step" : undefined}
            className={cn("flex items-center gap-2", i === at ? "font-semibold text-ink" : "text-ink-muted")}
          >
            <span
              className={cn(
                "inline-flex size-6 items-center justify-center rounded-full border text-xs",
                i < at ? "border-check-pass bg-check-pass-soft text-check-pass-ink" : i === at ? "border-ink-blue bg-flag-open-soft text-ink" : "border-line",
              )}
            >
              {i < at ? <Check className="size-3.5" aria-hidden="true" /> : i + 1}
            </span>
            {tk(`upload.steps.${s}`)}
          </li>
        ))}
      </ol>
    </>
  );
}

/** Where the mapping step stands: the file's headers, what each reads as, and the required columns to reach. */
interface MapState {
  headers: string[];
  choices: Record<string, Choice>;
  /** From a 422 the server names the required columns still missing; from the file every required column counts. */
  required?: UploadColumn[];
  /** Headers read from the file itself (sent with the PUT so the api checks every required column). */
  fromFile: boolean;
  matched: number;
}

/**
 * The registrar's upload (page specs W2-1 and W4-10): one file for one
 * academic year in three steps. A file whose headers the template and the
 * saved mapping do not cover opens Map your columns; the declaration is the
 * registrar's signature; a 202 opens the batch page, which follows the
 * pipeline.
 */
export function UploadForm({ years }: { years: string[] }) {
  const router = useRouter();
  const { user } = useMe();
  const upload = useUploadFile();
  const institutionId = user?.scope.institution_id ?? null;
  const mappingQuery = useColumnMapping(institutionId);
  const saveMapping = useSaveColumnMapping(institutionId ?? "");
  const [step, setStep] = React.useState<Step>("choose");
  const [map, setMap] = React.useState<MapState | null>(null);
  const [reading, setReading] = React.useState(false);
  const [saveForNext, setSaveForNext] = React.useState(true);
  const [mappingNote, setMappingNote] = React.useState<string | null>(null);
  const restoreTo = React.useRef<ColumnMapping["mapping"] | null>(null);
  const firstProblem = React.useRef<HTMLSelectElement | null>(null);
  const problemsId = React.useId();
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
  const generalError =
    upload.isError &&
    !fieldErrors.some((f) => f.field === "academic_year" || f.field === "declaration") &&
    !(upload.error instanceof ApiError && upload.error.code === "UPLOAD_HEADER_UNMAPPED");

  async function checkHeaders(f: File) {
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setStep("declare");
      return;
    }
    setReading(true);
    try {
      const headers = await readCsvHeaders(f);
      const saved = (mappingQuery.data ?? (await mappingQuery.refetch()).data)?.mapping ?? {};
      if (needsMapping(headers, saved)) {
        const choices = initialChoices(headers, saved);
        const savedKeys = new Set(Object.keys(saved).map(normaliseHeader));
        setMap({ headers, choices, fromFile: true, matched: headers.filter((h) => savedKeys.has(normaliseHeader(h))).length });
        setStep("map");
      } else {
        setStep("declare");
      }
    } catch {
      setStep("declare");
    } finally {
      setReading(false);
    }
  }

  function choose(f: File | null | undefined) {
    upload.reset();
    setLocalError(null);
    setMap(null);
    setMappingNote(null);
    setStep("choose");
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
    void checkHeaders(f);
  }

  /** Save mapping and continue: any problem keeps the step and moves focus to it; nothing is sent (W4-10). */
  function continueFromMapping() {
    if (!map || !institutionId) return;
    const { missing, duplicates } = problemsOf(map.choices, map.required);
    if (missing.length || duplicates.length) {
      (firstProblem.current ?? document.getElementById(problemsId))?.focus();
      return;
    }
    const before = mappingQuery.data?.mapping ?? {};
    const merged: Record<string, UploadColumn> = { ...before };
    for (const h of map.headers) {
      for (const k of Object.keys(merged)) if (normaliseHeader(k) === normaliseHeader(h)) delete merged[k];
    }
    Object.assign(merged, mappingBody(map.choices));
    restoreTo.current = saveForNext ? null : before;
    saveMapping.mutate(
      { mapping: merged, headers: map.fromFile ? map.headers : undefined },
      {
        onSuccess: () => {
          setMappingNote(saveForNext ? t("mapping.saved") : null);
          setStep("declare");
        },
      },
    );
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
    upload.mutate(
      { file, academicYear: year, onProgress: setSent },
      {
        onSuccess: (res) => {
          // "Saved for next time" was unticked: the mapping served this file only.
          if (restoreTo.current && institutionId) saveMapping.mutate({ mapping: restoreTo.current });
          router.push(`/college/uploads/${res.batch.id}`);
        },
        onError: (err) => {
          if (err instanceof ApiError && err.code === "UPLOAD_HEADER_UNMAPPED") {
            const d = err.details as { unknown_headers?: string[]; missing_columns?: UploadColumn[]; suggestions?: { header: string; column: UploadColumn }[] };
            const headers = d.unknown_headers ?? [];
            setMap({ headers, choices: initialChoices(headers, {}, d.suggestions ?? []), required: d.missing_columns ?? [], fromFile: false, matched: 0 });
            setStep("map");
          }
        },
      },
    );
  }

  const mapping = step === "map" && map && (
    <section aria-labelledby="mapping-heading" className="flex flex-col gap-3">
      <h2 id="mapping-heading" className="text-xl">
        {t("mapping.step")}
      </h2>
      <p className="max-w-[70ch] text-sm text-ink">
        {map.matched > 0 ? t("mapping.lead_saved", { matched: map.matched, total: map.headers.length }) : t("mapping.lead")}
      </p>
      <MappingRows
        headers={map.headers}
        choices={map.choices}
        onChange={(h, v) => setMap({ ...map, choices: { ...map.choices, [h]: v } })}
        firstProblemRef={firstProblem}
      />
      <div id={problemsId} tabIndex={-1} className="outline-none">
        <MappingProblems choices={map.choices} required={map.required} />
      </div>
      <label className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" checked={saveForNext} onChange={(e) => setSaveForNext(e.target.checked)} className="size-4 accent-ink-blue" />
        {t("mapping.saved_for_next_time")}
      </label>
      {saveMapping.isError && (
        <p role="alert" className="text-sm text-check-fail-ink">
          {saveMapping.error instanceof ApiError && (saveMapping.error.code === "MAPPING_INCOMPLETE" || saveMapping.error.code === "MAPPING_DUPLICATE")
            ? saveMapping.error.code === "MAPPING_INCOMPLETE"
              ? t("err.MAPPING_INCOMPLETE", { columns: ((saveMapping.error.details.missing_columns as string[]) ?? []).join(", ") })
              : t("err.MAPPING_DUPLICATE", { column: String(saveMapping.error.details.column ?? "") })
            : errorMessage(saveMapping.error)}
        </p>
      )}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button type="button" className="h-12 w-full sm:h-9 sm:w-auto" disabled={saveMapping.isPending} onClick={continueFromMapping}>
          {t("mapping.continue")}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-12 w-full sm:h-9 sm:w-auto"
          onClick={() => {
            choose(null);
            setFile(null);
            if (input.current) input.current.value = "";
            input.current?.click();
          }}
        >
          {t("mapping.cancel")}
        </Button>
      </div>
    </section>
  );

  return (
    <form onSubmit={submit} noValidate className="grid grid-cols-1 gap-x-10 gap-y-8 lg:grid-cols-12">
      <div className="lg:col-span-12">
        <StepIndicator step={step} />
      </div>
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

        {reading && (
          <div className="flex flex-col gap-2" aria-live="polite">
            <p className="text-sm text-ink-muted">{t("mapping.reading")}</p>
            <Skeleton className="h-24" />
          </div>
        )}
        {mapping}
        {mappingNote && step === "declare" && (
          <p role="status" className="text-sm text-check-pass-ink">
            {mappingNote}
          </p>
        )}
        {step !== "map" && (
          <>
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
                <Button type="submit" className="h-12 w-full sm:h-9 sm:w-auto" disabled={busy || !file || reading}>
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
          </>
        )}
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
                <code
                  key={c}
                  title={t(`field.${c}`)}
                  className="rounded-chip border border-ink-blue/30 bg-flag-open-soft px-1.5 py-0.5 font-mono text-xs text-ink"
                >
                  {c}
                </code>
              ))}
            </dd>
          </div>
          <div>
            <dt className="mb-1 text-xs font-medium text-ink-muted">{t("upload.columns_optional")}</dt>
            <dd className="flex flex-wrap gap-1.5">
              {OPTIONAL_COLUMNS.map((c) => (
                <code
                  key={c}
                  title={t(`field.${c}`)}
                  className="rounded-chip border border-line bg-paper-raised px-1.5 py-0.5 font-mono text-xs text-ink-muted"
                >
                  {c}
                </code>
              ))}
            </dd>
          </div>
        </dl>
        <p className="mt-4 text-sm text-ink-muted">{t("upload.columns_note")}</p>
        <p className="mt-3 text-sm">
          <Link href="/college/column-mapping">{t("mapping.view")}</Link>
        </p>
        <p className="mt-3 text-sm text-ink-muted">{t("upload.changes_note")}</p>
      </aside>
    </form>
  );
}
