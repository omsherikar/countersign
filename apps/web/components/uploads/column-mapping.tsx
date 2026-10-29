"use client";

import * as React from "react";
import { ChevronDown, Tag } from "lucide-react";
import { t, tk } from "@/lib/copy";
import { UPLOAD_COLUMNS, type UploadColumn } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Columns whose header must be present (API_CONTRACT A2.2). */
export const REQUIRED: UploadColumn[] = ["name", "dob", "programme_code", "year_of_study", "admission_route", "category"];

/** A header cell normalised as the api does (A2.2, A4.16): trimmed, lower case, spaces and hyphens to underscores. */
export function normaliseHeader(h: string): string {
  return h
    .trim()
    .replace(/^﻿/, "")
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
}

/** The header row of a CSV file, read in the browser; no row below it is read or shown. */
export async function readCsvHeaders(file: File): Promise<string[]> {
  const head = await file.slice(0, 64 * 1024).text();
  const line = head.split(/\r?\n/)[0] ?? "";
  const cells: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cur += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      cells.push(cur);
      cur = "";
    } else cur += ch;
  }
  cells.push(cur);
  return cells.map((c) => c.trim().replace(/^﻿/, "")).filter(Boolean);
}

export type Choice = UploadColumn | "";

/**
 * Common names colleges give the template's columns, offered as a first
 * guess the registrar confirms (the api makes the same kind of suggestion
 * when it refuses a file, A4.16). A guess is never saved unless confirmed.
 */
const GUESSES: Record<string, UploadColumn> = {
  student_name: "name",
  full_name: "name",
  name_of_student: "name",
  candidate_name: "name",
  "d.o.b.": "dob",
  "d.o.b": "dob",
  date_of_birth: "dob",
  birth_date: "dob",
  course_code: "programme_code",
  branch_code: "programme_code",
  branch: "programme_code",
  programme: "programme_code",
  program_code: "programme_code",
  current_year: "year_of_study",
  year: "year_of_study",
  class_year: "year_of_study",
  admission_type: "admission_route",
  quota: "admission_route",
  route: "admission_route",
  caste_category: "category",
  reservation_category: "category",
  apaar_no: "apaar_id",
  apaar: "apaar_id",
  apaar_number: "apaar_id",
  mobile_no: "mobile",
  phone: "mobile",
  contact_no: "mobile",
  email_id: "email",
  e_mail: "email",
  sex: "gender",
  passport: "passport_no",
  passport_number: "passport_no",
  allotment_no: "counselling_ref",
  cap_id: "counselling_ref",
  date_of_admission: "admission_date",
  joining_date: "admission_date",
};

/** What each header reads as: the saved mapping first, then a template column of the same name, else nothing. */
export function initialChoices(
  headers: string[],
  saved: Record<string, UploadColumn>,
  suggestions: { header: string; column: UploadColumn }[] = [],
): Record<string, Choice> {
  const savedByKey = new Map(Object.entries(saved).map(([k, v]) => [normaliseHeader(k), v]));
  const out: Record<string, Choice> = {};
  for (const h of headers) {
    const key = normaliseHeader(h);
    const fromSaved = savedByKey.get(key);
    const template = (UPLOAD_COLUMNS as readonly string[]).includes(key) ? (key as UploadColumn) : undefined;
    out[h] = fromSaved ?? template ?? suggestions.find((s) => s.header === h)?.column ?? GUESSES[key] ?? "";
  }
  // A guess never takes a column another header already holds.
  const taken = new Set<string>();
  for (const h of headers) {
    const c = out[h];
    if (!c) continue;
    if (taken.has(c) && !(UPLOAD_COLUMNS as readonly string[]).includes(normaliseHeader(h))) out[h] = "";
    else taken.add(c);
  }
  return out;
}

/** True when a header is neither a template column nor in the saved mapping: the mapping step is needed (W4-10). */
export function needsMapping(headers: string[], saved: Record<string, UploadColumn>): boolean {
  const keys = new Set(Object.keys(saved).map(normaliseHeader));
  return headers.some((h) => {
    const k = normaliseHeader(h);
    return !keys.has(k) && !(UPLOAD_COLUMNS as readonly string[]).includes(k);
  });
}

export function columnLabel(c: UploadColumn): string {
  return `${tk(`field.${c}`)} (${c})`;
}

/** Problems with a set of choices: required columns no header reaches, and columns chosen twice. */
export function problemsOf(choices: Record<string, Choice>, required: UploadColumn[] = REQUIRED) {
  const chosen = Object.values(choices).filter((c): c is UploadColumn => Boolean(c));
  const missing = required.filter((c) => !chosen.includes(c));
  const duplicates = [...new Set(chosen.filter((c, i) => chosen.indexOf(c) !== i))].map((column) => ({
    column,
    headers: Object.entries(choices)
      .filter(([, v]) => v === column)
      .map(([h]) => h),
  }));
  return { missing, duplicates };
}

/**
 * One row per column of the college's file (page spec W4-10): its name as
 * uploaded and a select of the template columns, required ones tagged, or
 * Not used. No value from the file's rows is ever shown here.
 */
export function MappingRows({
  headers,
  choices,
  onChange,
  readOnly = false,
  firstProblemRef,
}: {
  headers: string[];
  choices: Record<string, Choice>;
  onChange?: (header: string, value: Choice) => void;
  readOnly?: boolean;
  firstProblemRef?: React.RefObject<HTMLSelectElement | null>;
}) {
  const { duplicates } = problemsOf(choices);
  const dupColumns = new Set(duplicates.map((d) => d.column));
  const ids = React.useId();
  // The first header whose column is chosen twice takes the focus when the reader continues.
  const firstDup = headers.find((h) => {
    const v = choices[h] ?? "";
    return v !== "" && dupColumns.has(v);
  });
  return (
    <div className="border-l-2 border-rule-margin bg-paper-raised">
      <div className="hidden grid-cols-[minmax(10rem,1fr)_minmax(14rem,1.4fr)] gap-4 border-b border-rule-strong px-4 py-2 text-xs font-medium text-ink-muted md:grid">
        <span>{t("mapping.col.theirs")}</span>
        <span>{t("mapping.col.ours")}</span>
      </div>
      <ul>
        {headers.map((h, i) => {
          const value = choices[h] ?? "";
          const dup = value !== "" && dupColumns.has(value);
          const giveRef = dup && h === firstDup;
          return (
            <li
              key={`${h}-${i}`}
              className="grid grid-cols-1 gap-1.5 border-b border-rule px-4 py-2.5 last:border-b-0 md:grid-cols-[minmax(10rem,1fr)_minmax(14rem,1.4fr)] md:items-center md:gap-4"
            >
              <label htmlFor={`${ids}-${i}`} className="font-mono text-sm break-all text-ink">
                {h}
              </label>
              {readOnly ? (
                <span className="text-sm">{value ? columnLabel(value) : t("mapping.not_used")}</span>
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative min-w-0 flex-1">
                    <select
                      id={`${ids}-${i}`}
                      ref={giveRef ? firstProblemRef : undefined}
                      value={value}
                      aria-invalid={dup || undefined}
                      onChange={(e) => onChange?.(h, e.target.value as Choice)}
                      className={cn(
                        "h-11 w-full appearance-none rounded-md border bg-paper py-0 pr-8 pl-2.5 text-md md:h-9 md:text-sm",
                        dup ? "border-check-fail" : "border-line",
                      )}
                    >
                      <option value="">{t("mapping.not_used")}</option>
                      {UPLOAD_COLUMNS.map((c) => (
                        <option key={c} value={c}>
                          {columnLabel(c)}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
                  </div>
                  {value && REQUIRED.includes(value) && (
                    <span className="inline-flex items-center gap-1 rounded-chip border border-ink-blue/30 bg-flag-open-soft px-1.5 text-xs text-ink">
                      <Tag className="size-3" aria-hidden="true" />
                      {t("mapping.required_tag")}
                    </span>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The live problem lines, announced as they change. */
export function MappingProblems({ choices, required, id }: { choices: Record<string, Choice>; required?: UploadColumn[]; id?: string }) {
  const { missing, duplicates } = problemsOf(choices, required);
  return (
    <div id={id} aria-live="polite" className="flex flex-col gap-1 text-sm text-check-fail-ink">
      {missing.length > 0 && <p>{t("mapping.required_missing", { columns: missing.map((c) => tk(`field.${c}`)).join(", ") })}</p>}
      {duplicates.map((d) => (
        <p key={d.column}>{t("mapping.duplicate", { column: columnLabel(d.column), their_columns: d.headers.join(", ") })}</p>
      ))}
    </div>
  );
}

/** The mapping a PUT sends: every header whose choice differs from reading it as a template column. */
export function mappingBody(choices: Record<string, Choice>): Record<string, UploadColumn> {
  const out: Record<string, UploadColumn> = {};
  for (const [h, c] of Object.entries(choices)) {
    if (!c) continue;
    if (normaliseHeader(h) === c) continue;
    out[h] = c;
  }
  return out;
}
