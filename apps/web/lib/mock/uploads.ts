/**
 * Mock upload batches (API_CONTRACT A2.4 to A2.9). Seeded batches are fixed;
 * batches uploaded in this browser session live in sessionStorage with the
 * time they were created, and every GET works out the stage, processed rows
 * and progress from the time elapsed, so polling shows the batch moving
 * through PARSE ... FLAGS to DONE in about 14 seconds, across reloads too.
 */
import { ApiError } from "@/lib/api";
import { ACADEMIC_YEAR, IDS, SEEDS, USERS } from "@/lib/mock/fixtures";
import { INITIAL_UPLOADED_AT, UPDATE_UPLOADED_AT, initialBatchId, initialFilename, rollFor, updateBatchId, updateFilename } from "@/lib/mock/roll";
import {
  UPLOAD_COLUMNS,
  type RowErrorLevel,
  type UploadBatch,
  type UploadCounts,
  type UploadRowError,
  type UploadStage,
  type UploadStatus,
  type User,
} from "@/lib/types";

const KARAD = "10000000-0004-4000-8000-000000000004";

/* ---- Row errors (A2.3 messages, A2.3 masking) --------------------------- */

const E = (row_no: number, level: RowErrorLevel, field: UploadRowError["field"], code: UploadRowError["code"], message: string, value_masked: string | null): UploadRowError => ({
  row_no,
  level,
  field,
  code,
  message,
  value_masked,
});

/** The errors a fresh upload in this session reports, limited to the rows the file has. */
const SESSION_ERRORS: UploadRowError[] = [
  E(17, "WARNING", "apaar_id", "APAAR_FORMAT", "APAAR must be 12 digits", "<11 characters>"),
  E(41, "ERROR", "apaar_id", "DUPLICATE_IN_FILE", "Same APAAR appears on row 12", "XXXX XXXX 4417"),
  E(58, "ERROR", "dob", "DOB_FORMAT", "Date of birth must be YYYY-MM-DD", "21/03/2007"),
  E(77, "ERROR", "programme_code", "UNKNOWN_PROGRAMME", "Programme code CSD is not approved for your college", "CSD"),
  E(90, "WARNING", "mobile", "MOBILE_FORMAT", "Mobile must be 10 digits; the value was not used", "XXXXX4521"),
  E(112, "ERROR", "category", "BAD_ENUM", "Category must be one of General, EWS, OBC, SC, ST, Other", "Gen"),
  E(151, "ERROR", "year_of_study", "YEAR_OF_STUDY_INVALID", "Year of study must be a whole number between 1 and 4", "5"),
  E(188, "ERROR", "admission_route", "BAD_ENUM", "Admission route must be one of Counselling, Management, NRI, Spot, Lateral, International, TFW", "Direct"),
  E(204, "WARNING", "email", "EMAIL_FORMAT", "Email address is not valid; the value was not used", "a***@gmail"),
  E(230, "ERROR", "passport_no", "PASSPORT_REQUIRED", "International students need a passport number", null),
  E(262, "WARNING", "consent_status", "CONSENT_CONFLICT", "Consent is Linked but no APAAR was given; recorded as Pending", "LINKED"),
  E(301, "ERROR", "dob", "DOB_IMPLAUSIBLE", "Date of birth 2019-04-11 gives an age of 7 at admission; expected 14 to 60", "2019-04-11"),
  E(318, "ERROR", "name", "MISSING_REQUIRED", "Name is required", null),
  E(344, "WARNING", "gender", "BAD_ENUM", "Gender must be M, F, O or U; recorded as U", "X"),
  E(377, "ERROR", "year_of_study", "NO_APPROVAL_FOR_COHORT", "IT has no approval for 2023-24, the intake of a year 4 student in 2026-27", "4"),
  E(402, "ERROR", "academic_year", "YEAR_MISMATCH", "Academic year 2025-26 does not match this upload's academic year 2026-27", "2025-26"),
  E(455, "ERROR", "admission_date", "DATE_IN_FUTURE", "Admission date 2026-11-02 is after the upload date", "2026-11-02"),
  E(470, "WARNING", "status", "NOT_PREVIOUSLY_ENROLLED", "No earlier enrolment matches this student; recorded as Withdrawn with no seat", "WITHDRAWN"),
  E(501, "ERROR", "passport_no", "DUPLICATE_IN_FILE", "Same passport number appears on row 488", "XXXXX567"),
  E(512, "ERROR", "nationality", "NATIONALITY_FORMAT", "Nationality must be a two-letter country code, e.g. IN", "IND"),
  E(530, "WARNING", "consent_status", "CONSENT_CONFLICT", "APAAR given but consent is Refused; the APAAR was not used", "REFUSED"),
  E(548, "ERROR", "name", "DUPLICATE_IN_FILE", "Same student (name, date of birth and mobile) appears on row 547", "Sunita Deshmukh"),
  E(566, "ERROR", "status_date", "DATE_FORMAT", "Status date must be YYYY-MM-DD", "20-10-2026"),
  E(580, "ERROR", "status", "BAD_ENUM", "Status must be Active, Withdrawn or Transferred", "Left"),
  E(592, "WARNING", "apaar_id", "APAAR_FORMAT", "APAAR must be 12 digits", "<13 characters>"),
  E(601, "ERROR", "programme_code", "MISSING_REQUIRED", "Programme code is required", null),
  E(601, "ERROR", "year_of_study", "MISSING_REQUIRED", "Year of study is required", null),
];

const UPDATE_ERRORS: UploadRowError[] = [
  E(3, "WARNING", "apaar_id", "APAAR_FORMAT", "APAAR must be 12 digits", "<11 characters>"),
  E(9, "ERROR", "apaar_id", "DUPLICATE_IN_FILE", "Same APAAR appears on row 4", "XXXX XXXX 0187"),
  E(14, "ERROR", "dob", "DOB_FORMAT", "Date of birth must be YYYY-MM-DD", "02/11/2007"),
  E(22, "ERROR", "programme_code", "UNKNOWN_PROGRAMME", "Programme code CSD is not approved for your college", "CSD"),
  E(31, "WARNING", "mobile", "MOBILE_FORMAT", "Mobile must be 10 digits; the value was not used", "XXXXX8810"),
];

function tally(errors: UploadRowError[]) {
  const rejected = new Set(errors.filter((e) => e.level === "ERROR").map((e) => e.row_no));
  const warned = new Set(errors.filter((e) => e.level === "WARNING" && !rejected.has(e.row_no)).map((e) => e.row_no));
  return { errors: rejected.size, warnings: warned.size };
}

/* ---- Batches ------------------------------------------------------------ */

interface SessionUpload {
  id: string;
  institutionId: string;
  academic_year: string;
  filename: string;
  rows: number;
  createdMs: number;
  unreadable: boolean;
  sameAs: { batch_id: string; uploaded_at: string } | null;
  uploadedBy: { id: string; name: string };
  kind: "INITIAL" | "UPDATE";
}

const STORE = "cs-mock-uploads";

function readSession(): SessionUpload[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.sessionStorage.getItem(STORE) ?? "[]") as SessionUpload[];
  } catch {
    return [];
  }
}
function writeSession(list: SessionUpload[]) {
  try {
    window.sessionStorage.setItem(STORE, JSON.stringify(list));
  } catch {
    /* private mode: the batch lives for this page only */
  }
}

function registrarOf(institutionId: string): { id: string; name: string } {
  const user = USERS.find((u) => u.role === "INSTITUTION" && u.scope.institution_id === institutionId);
  const seed = SEEDS.find((s) => s.id === institutionId)!;
  return user ? { id: user.id, name: user.name } : { id: `6f1c0a8e-${institutionId.slice(-4)}-4c9a-9e51-1c2f1a0b7d33`, name: `Registrar, ${seed.name}` };
}

const ZERO: UploadCounts = {
  rows: 0, accepted: 0, errors: 0, warnings: 0, created: 0, updated: 0, unchanged: 0, withdrawn: 0, transferred: 0,
  seated: 0, released: 0, unseated: 0, flags_raised: 0, flags_updated: 0,
};

function staticBatches(): UploadBatch[] {
  const out: UploadBatch[] = [];
  for (const seed of SEEDS) {
    const roll = rollFor(seed.id).filter((e) => e.upload?.batch_id === initialBatchId(seed.id));
    const intakeUnseated = roll.filter((e) => e.row.cohort_year === ACADEMIC_YEAR && !e.seat).length;
    const abc = seed.id === IDS.abc;
    out.push({
      id: initialBatchId(seed.id),
      institution_id: seed.id,
      institution_name: seed.name,
      academic_year: ACADEMIC_YEAR,
      filename: initialFilename(seed.aicte_permanent_id),
      source: abc ? "FILE" : "SEED",
      kind: "INITIAL",
      status: "DONE",
      stage: "DONE",
      total_rows: roll.length,
      stage_total: 0,
      processed_rows: 0,
      progress_pct: 100,
      counts: {
        ...ZERO,
        rows: roll.length,
        accepted: roll.length,
        created: roll.length,
        seated: roll.filter((e) => e.seat && e.row.cohort_year === ACADEMIC_YEAR).length,
        unseated: intakeUnseated,
        flags_raised: abc ? 6 : 1,
      },
      sources: [
        { source: "APAAR", calls: roll.filter((e) => e.row.student.consent_status === "LINKED").length, unavailable: abc ? 1 : 0 },
        { source: "COUNSELLING", calls: roll.filter((e) => e.row.counselling_ref).length, unavailable: 0 },
        { source: "ABC", calls: roll.filter((e) => e.row.year_of_study > 1).length, unavailable: 0 },
        { source: "SII", calls: roll.filter((e) => e.row.admission_route === "INTERNATIONAL").length, unavailable: 0 },
      ],
      timings_ms: { PARSE: 40, VALIDATE: 120, FILE_DUPLICATES: 8, UPSERT: 900, LEDGER: 700, CHECKS: 6100, DUPLICATES: 300, FLAGS: 60 },
      error: null,
      ignored_columns: [],
      same_file_as: null,
      uploaded_by: registrarOf(seed.id),
      uploaded_at: INITIAL_UPLOADED_AT,
      started_at: "2026-10-27T09:30:15Z",
      finished_at: "2026-10-27T09:30:24Z",
    });
  }
  for (const id of [IDS.abc, KARAD]) {
    const seed = SEEDS.find((s) => s.id === id)!;
    const t = tally(id === IDS.abc ? UPDATE_ERRORS : []);
    const rows = id === IDS.abc ? 48 : 11;
    const accepted = rows - t.errors;
    out.push({
      id: updateBatchId(id),
      institution_id: id,
      institution_name: seed.name,
      academic_year: ACADEMIC_YEAR,
      filename: updateFilename(seed.aicte_permanent_id),
      source: "FILE",
      kind: "UPDATE",
      status: "DONE",
      stage: "DONE",
      total_rows: rows,
      stage_total: 0,
      processed_rows: 0,
      progress_pct: 100,
      counts: {
        ...ZERO,
        rows,
        accepted,
        errors: t.errors,
        warnings: t.warnings,
        created: 4,
        updated: 7,
        unchanged: accepted - 11,
        withdrawn: 3,
        transferred: 1,
        seated: 4,
        released: 4,
        flags_raised: id === KARAD ? 1 : 0,
        flags_updated: 0,
      },
      sources: [
        { source: "APAAR", calls: 11, unavailable: 0 },
        { source: "COUNSELLING", calls: 6, unavailable: 0 },
        { source: "ABC", calls: 7, unavailable: 0 },
      ],
      timings_ms: { PARSE: 12, VALIDATE: 30, FILE_DUPLICATES: 3, UPSERT: 80, LEDGER: 60, CHECKS: 410, DUPLICATES: 40, FLAGS: 20 },
      error: null,
      ignored_columns: id === IDS.abc ? ["remarks"] : [],
      same_file_as: null,
      uploaded_by: registrarOf(id),
      uploaded_at: UPDATE_UPLOADED_AT,
      started_at: "2026-10-28T08:15:41Z",
      finished_at: "2026-10-28T08:15:56Z",
    });
  }
  return out;
}

/* ---- The pipeline timeline for session uploads -------------------------- */

const STAGES: { stage: UploadStage; ms: number; weight: number }[] = [
  { stage: "PARSE", ms: 900, weight: 5 },
  { stage: "VALIDATE", ms: 1500, weight: 10 },
  { stage: "FILE_DUPLICATES", ms: 600, weight: 5 },
  { stage: "UPSERT", ms: 1800, weight: 15 },
  { stage: "LEDGER", ms: 1200, weight: 10 },
  { stage: "CHECKS", ms: 4200, weight: 45 },
  { stage: "DUPLICATES", ms: 900, weight: 5 },
  { stage: "FLAGS", ms: 600, weight: 5 },
];
const QUEUED_MS = 1200;
const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d+Z$/, "Z");

function finalCounts(u: SessionUpload): UploadCounts {
  const t = tally(sessionErrors(u));
  const accepted = u.rows - t.errors;
  if (u.sameAs) return { ...ZERO, rows: u.rows, accepted, errors: t.errors, warnings: t.warnings, unchanged: accepted };
  const created = Math.min(accepted, 6 + Math.floor(accepted * 0.02));
  const updated = Math.min(accepted - created, 9);
  const moved = accepted > 20 ? 4 : 0;
  return {
    rows: u.rows,
    accepted,
    errors: t.errors,
    warnings: t.warnings,
    created,
    updated,
    unchanged: accepted - created - updated,
    withdrawn: moved ? 3 : 0,
    transferred: moved ? 1 : 0,
    seated: Math.max(0, created - 2),
    released: moved,
    unseated: Math.min(2, created),
    flags_raised: created > 2 ? 2 : 0,
    flags_updated: created > 2 ? 1 : 0,
  };
}

function stageTotal(stage: UploadStage, c: UploadCounts): number {
  if (stage === "PARSE" || stage === "VALIDATE" || stage === "FILE_DUPLICATES") return c.rows;
  if (stage === "UPSERT" || stage === "LEDGER") return c.accepted;
  if (stage === "CHECKS" || stage === "DUPLICATES") return c.created + c.updated;
  if (stage === "FLAGS") return 6;
  return 0;
}

function statusOf(stage: UploadStage): UploadStatus {
  return stage === "PARSE" || stage === "VALIDATE" || stage === "FILE_DUPLICATES" ? "VALIDATING" : "PROCESSING";
}

function sessionBatch(u: SessionUpload, now = Date.now()): UploadBatch {
  const seed = SEEDS.find((s) => s.id === u.institutionId)!;
  const final = finalCounts(u);
  const base: UploadBatch = {
    id: u.id,
    institution_id: u.institutionId,
    institution_name: seed.name,
    academic_year: u.academic_year,
    filename: u.filename,
    source: "FILE",
    kind: u.kind,
    status: "QUEUED",
    stage: null,
    total_rows: 0,
    stage_total: 0,
    processed_rows: 0,
    progress_pct: 0,
    counts: { ...ZERO },
    sources: [],
    timings_ms: {},
    error: null,
    ignored_columns: [],
    same_file_as: u.sameAs,
    uploaded_by: u.uploadedBy,
    uploaded_at: iso(u.createdMs),
    started_at: null,
    finished_at: null,
  };
  let elapsed = now - u.createdMs - QUEUED_MS;
  if (elapsed < 0) return base;
  base.started_at = iso(u.createdMs + QUEUED_MS);
  base.total_rows = u.rows;
  let done = 0;
  const counts: UploadCounts = { ...ZERO };
  for (const s of STAGES) {
    const total = stageTotal(s.stage, final);
    if (elapsed < s.ms) {
      const fraction = elapsed / s.ms;
      base.status = statusOf(s.stage);
      base.stage = s.stage;
      base.stage_total = total;
      base.processed_rows = Math.floor(total * fraction);
      base.progress_pct = Math.floor(done + (s.weight * base.processed_rows) / Math.max(total, 1));
      if (u.unreadable && s.stage === "PARSE") {
        base.status = "FAILED";
        base.error = "The file could not be read as CSV or XLSX.";
        base.processed_rows = 0;
        base.progress_pct = 0;
        base.finished_at = iso(now);
      }
      if (s.stage === "CHECKS") {
        const calls = base.processed_rows;
        base.sources = [
          { source: "APAAR", calls: Math.round(calls * 0.9), unavailable: 0 },
          { source: "COUNSELLING", calls: Math.round(calls * 0.6), unavailable: 0 },
          { source: "ABC", calls: Math.round(calls * 0.5), unavailable: Math.min(3, Math.round(calls * 0.5)) },
        ];
      }
      base.counts = counts;
      return base;
    }
    if (u.unreadable && s.stage === "PARSE") {
      return { ...base, status: "FAILED", stage: "PARSE", error: "The file could not be read as CSV or XLSX.", finished_at: iso(u.createdMs + QUEUED_MS + s.ms) };
    }
    elapsed -= s.ms;
    done += s.weight;
    base.timings_ms = { ...base.timings_ms, [s.stage]: s.ms };
    if (s.stage === "PARSE") counts.rows = final.rows;
    if (s.stage === "FILE_DUPLICATES") Object.assign(counts, { accepted: final.accepted, errors: final.errors, warnings: final.warnings });
    if (s.stage === "UPSERT")
      Object.assign(counts, { created: final.created, updated: final.updated, unchanged: final.unchanged, withdrawn: final.withdrawn, transferred: final.transferred });
    if (s.stage === "LEDGER") Object.assign(counts, { seated: final.seated, released: final.released, unseated: final.unseated });
    if (s.stage === "FLAGS") Object.assign(counts, { flags_raised: final.flags_raised, flags_updated: final.flags_updated });
  }
  const checks = final.created + final.updated;
  return {
    ...base,
    status: "DONE",
    stage: "DONE",
    stage_total: 0,
    processed_rows: 0,
    progress_pct: 100,
    counts: final,
    sources: [
      { source: "APAAR", calls: Math.round(checks * 0.9), unavailable: 0 },
      { source: "COUNSELLING", calls: Math.round(checks * 0.6), unavailable: 0 },
      { source: "ABC", calls: Math.round(checks * 0.5), unavailable: Math.min(3, Math.round(checks * 0.5)) },
    ],
    finished_at: iso(u.createdMs + QUEUED_MS + STAGES.reduce((a, s) => a + s.ms, 0)),
  };
}

function sessionErrors(u: SessionUpload): UploadRowError[] {
  return SESSION_ERRORS.filter((e) => e.row_no <= u.rows + 1);
}

/* ---- Public api for the handler ----------------------------------------- */

export function allBatches(): UploadBatch[] {
  return [...readSession().map((u) => sessionBatch(u)), ...staticBatches()].sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at));
}

export function batchById(id: string): UploadBatch | undefined {
  return allBatches().find((b) => b.id === id);
}

/** Row errors of a batch; a session batch reports them once VALIDATE is past. */
export function errorsOf(batch: UploadBatch): UploadRowError[] {
  const session = readSession().find((u) => u.id === batch.id);
  if (session) return batch.counts.rows > 0 && batch.counts.accepted + batch.counts.errors > 0 ? sessionErrors(session) : [];
  if (batch.id === updateBatchId(IDS.abc)) return UPDATE_ERRORS;
  return [];
}

export function errorsCsv(batch: UploadBatch): { blob: Blob; filename: string } {
  const quote = (v: string | number | null) => {
    const s = v === null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = ["row_no,level,field,code,message,value_masked", ...errorsOf(batch).map((e) => [e.row_no, e.level, e.field, e.code, e.message, e.value_masked].map(quote).join(","))];
  const stem = batch.filename.replace(/\.(csv|xlsx)$/i, "");
  return { blob: new Blob(["﻿" + lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" }), filename: `${stem}_errors.csv` };
}

export function templateCsv(): { blob: Blob; filename: string } {
  return { blob: new Blob(["﻿" + UPLOAD_COLUMNS.join(",") + "\r\n"], { type: "text/csv;charset=utf-8" }), filename: "countersign_upload_template.csv" };
}

const REQUIRED = ["name", "dob", "programme_code", "year_of_study", "admission_route", "category"];
const MAX_BYTES = 20 * 1024 * 1024;

function normaliseHeader(h: string): string {
  return h.trim().replace(/^﻿/, "").toLowerCase().replace(/[\s-]+/g, "_");
}

function validation(field: string, message: string): ApiError {
  return new ApiError(422, "VALIDATION_ERROR", message, { fields: [{ field, message }] });
}

/** POST /uploads with the A2.4 checks that the api runs before it answers 202. */
export async function createUpload(user: User, form: FormData): Promise<{ batch: UploadBatch }> {
  const file = form.get("file");
  const year = String(form.get("academic_year") ?? "");
  const declaration = String(form.get("declaration") ?? "");
  let institutionId = String(form.get("institution_id") ?? "");
  if (user.role === "INSTITUTION") {
    if (institutionId && institutionId !== user.scope.institution_id) throw new ApiError(404, "NOT_FOUND", "Institution not found.");
    institutionId = user.scope.institution_id ?? "";
  } else if (user.role === "AICTE_ADMIN") {
    if (!institutionId) throw validation("institution_id", "Choose the institution this file belongs to.");
    if (!SEEDS.some((s) => s.id === institutionId)) throw new ApiError(404, "NOT_FOUND", "Institution not found.");
  } else {
    throw new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: ["INSTITUTION", "AICTE_ADMIN"] });
  }
  if (!(file instanceof File)) throw validation("file", "Choose a file to upload.");
  const ext = file.name.toLowerCase().split(".").pop();
  if (ext !== "csv" && ext !== "xlsx") throw new ApiError(415, "UNSUPPORTED_FILE_TYPE", "Only .csv and .xlsx files can be uploaded.");
  if (file.size > MAX_BYTES) throw new ApiError(413, "FILE_TOO_LARGE", "The file is larger than 20 MB. Split it by programme and upload each part.");
  if (declaration !== "true") throw validation("declaration", "Tick the declaration to upload.");
  if (year !== ACADEMIC_YEAR) throw validation("academic_year", `Your college has no approvals for ${year || "that year"}.`);

  const session = readSession();
  const running = session.map((u) => sessionBatch(u)).find((b) => b.institution_id === institutionId && b.academic_year === year && b.status !== "DONE" && b.status !== "FAILED");
  if (running) throw new ApiError(409, "UPLOAD_IN_PROGRESS", "An upload for this college and year is still being processed.", { batch_id: running.id });

  let rows = 605;
  const unreadable = /unreadable|corrupt/i.test(file.name);
  if (ext === "csv" && !unreadable) {
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
    const header = (lines[0] ?? "").split(",").map(normaliseHeader);
    const missing = REQUIRED.filter((c) => !header.includes(c));
    const duplicate = header.filter((h, i) => h && header.indexOf(h) !== i);
    if (missing.length || duplicate.length) {
      const message = missing.length ? `The file is missing required columns: ${missing.join(", ")}.` : `The column ${duplicate[0]} appears more than once.`;
      throw new ApiError(422, "UPLOAD_HEADER_INVALID", message, { missing_columns: missing, duplicate_columns: [...new Set(duplicate)] });
    }
    rows = lines.length - 1;
    if (rows <= 0) throw new ApiError(422, "UPLOAD_EMPTY", "The file has a header but no rows.");
    if (rows > 50000) throw new ApiError(413, "TOO_MANY_ROWS", "The file has more than 50,000 rows. Split it and upload each part.");
  }

  const earlier = allBatches().filter((b) => b.institution_id === institutionId && b.academic_year === year && b.status === "DONE");
  const same = earlier.find((b) => b.filename === file.name);
  const record: SessionUpload = {
    id: `d${Math.floor(Math.random() * 0xfffffff).toString(16).padStart(7, "0")}-4444-4555-8666-${Date.now().toString(16).padStart(12, "0").slice(-12)}`,
    institutionId,
    academic_year: year,
    filename: file.name,
    rows,
    createdMs: Date.now(),
    unreadable,
    sameAs: same ? { batch_id: same.id, uploaded_at: same.uploaded_at } : null,
    uploadedBy: { id: user.id, name: user.name },
    kind: earlier.length ? "UPDATE" : "INITIAL",
  };
  writeSession([record, ...session]);
  return { batch: sessionBatch(record) };
}
