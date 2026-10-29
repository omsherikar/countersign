/**
 * Mock-mode reports (API_CONTRACT A4.21): the five tables as CSV and XLSX
 * and the one-page summary as PDF, built from the mock roll, cases and
 * joinings, scoped like the api (AICTE national, a regional officer its
 * region). Aggregates only: no file names a student.
 */
import { ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ACADEMIC_YEAR, INSTITUTIONS } from "@/lib/mock/fixtures";
import { allFlags, UNRESOLVED } from "@/lib/mock/flags";
import { completenessOf, countsFor, pct } from "@/lib/mock/records";
import { rollFor } from "@/lib/mock/roll";
import { csvText, pdfBlob, xlsxBlob } from "@/lib/mock/files";
import type { FlagType, InstitutionRow, InstitutionType, ItemsEnvelope, RecordCounts, ReportFormat, ReportInfo, ReportName, Role, User } from "@/lib/types";

const OFFICERS: Role[] = ["AICTE_ADMIN", "RO_OFFICER"];
const SYNTHETIC = "Synthetic demo data. Every number comes from the Countersign demo dataset.";

const COLUMNS: Record<Exclude<ReportName, "summary">, string[]> = {
  "by-state": [
    "academic_year", "state_code", "state_name", "region", "institutions", "approved_seats", "admitted", "records", "countersigned",
    "awaiting_evidence", "under_review", "disputed", "countersigned_pct", "cases_open", "joined", "missing_from_upload", "completeness_pct",
  ],
  "by-institution-type": [
    "academic_year", "institution_type", "institutions", "approved_seats", "admitted", "records", "countersigned", "awaiting_evidence",
    "under_review", "disputed", "countersigned_pct", "cases_open", "completeness_pct",
  ],
  "cases-by-type-and-outcome": [
    "academic_year", "case_type", "case_name", "open", "docs_requested", "escalated", "upheld", "corrected", "withdrawn", "total", "median_days_to_decision",
  ],
  "countersign-coverage": [
    "academic_year", "aicte_permanent_id", "institution_name", "state_code", "institution_type", "records", "countersigned", "awaiting_evidence",
    "under_review", "disputed", "countersigned_pct", "independent_joining_record", "independent_credits", "independent_student",
  ],
  completeness: [
    "academic_year", "aicte_permanent_id", "institution_name", "state_code", "joined", "uploaded_and_joined", "missing", "uploaded_not_joined",
    "completeness_pct", "deadline", "first_upload_on", "deadline_state", "case_status",
  ],
};

const TITLES: Record<ReportName, string> = {
  "by-state": "Records by state",
  "by-institution-type": "Records by institution type",
  "cases-by-type-and-outcome": "Cases by type and outcome",
  "countersign-coverage": "Countersign coverage",
  completeness: "Completeness and deadlines",
  summary: "One-page summary",
};

const CASE_NAME: Record<FlagType, string> = {
  EXCESS_ADMISSION: "Excess admission",
  QUOTA_BREACH: "Quota breach",
  LATE_REFILL: "Late refill",
  INVALID_APAAR: "APAAR not verified",
  NAME_MISMATCH: "Name or date of birth mismatch",
  DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
  DUPLICATE_WITHIN_UPLOAD: "Duplicate within institution",
  DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
  NO_ACADEMIC_ACTIVITY: "No academic activity",
  NOT_IN_JOINING_RECORD: "Not in joining record",
  ELIGIBILITY_BREACH: "Seat category not eligible",
  MISSING_FROM_UPLOAD: "Missing from upload",
  STUDENT_DENIED: "Student dispute",
  GHOST_RING: "Shared contact ring",
  ANOMALY: "Unusual pattern",
};

const REGION_WORD: Record<string, string> = {
  NORTH: "Northern", NORTH_WEST: "North-Western", CENTRAL: "Central", WEST: "Western", WEST_CENTRAL: "West-Central",
  SOUTH_WEST: "South-Western", SOUTH: "Southern", SOUTH_CENTRAL: "South-Central", EAST: "Eastern", NORTH_EAST: "North-Eastern",
};

function requireOfficer(user: User) {
  if (!OFFICERS.includes(user.role)) throw new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: OFFICERS });
}

export function listReports(user: User): ItemsEnvelope<ReportInfo> {
  requireOfficer(user);
  const names: ReportName[] = ["by-state", "by-institution-type", "cases-by-type-and-outcome", "countersign-coverage", "completeness", "summary"];
  return {
    items: names.map((name) => ({
      name,
      title: TITLES[name],
      formats: name === "summary" ? ["pdf"] : (["csv", "xlsx", "pdf"] as ReportFormat[]),
      columns: name === "summary" ? [] : COLUMNS[name],
    })),
  };
}

function scope(user: User): { rows: InstitutionRow[]; name: string; slug: string } {
  if (user.role === "RO_OFFICER") {
    const region = user.scope.region!;
    return { rows: INSTITUTIONS.filter((i) => i.region === region), name: `${REGION_WORD[region]} Region`, slug: region };
  }
  return { rows: INSTITUTIONS, name: "All India", slug: "national" };
}

const total = (r: RecordCounts) => r.AWAITING_EVIDENCE + r.COUNTERSIGNED + r.UNDER_REVIEW + r.DISPUTED;
const one = (n: number | null) => (n === null ? "" : n.toFixed(1));
const openCases = (id: string) => allFlags().filter((f) => f.institutionId === id && UNRESOLVED.includes(f.status)).length;

function add(into: RecordCounts, from: RecordCounts) {
  for (const k of Object.keys(into) as (keyof RecordCounts)[]) into[k] += from[k];
}
const zero = (): RecordCounts => ({ AWAITING_EVIDENCE: 0, COUNTERSIGNED: 0, UNDER_REVIEW: 0, DISPUTED: 0 });

function tableOf(name: Exclude<ReportName, "summary">, rows: InstitutionRow[], year: string): unknown[][] {
  if (name === "by-state" || name === "by-institution-type") {
    const groups = new Map<string, InstitutionRow[]>();
    for (const r of rows) {
      const key = name === "by-state" ? r.state_code : r.type;
      groups.set(key, [...(groups.get(key) ?? []), r]);
    }
    const out = [...groups.entries()].map(([key, list]) => {
      const rec = zero();
      let joined = 0;
      let matched = 0;
      let missing = 0;
      for (const r of list) {
        add(rec, countsFor(r.id));
        const c = completenessOf(r.id);
        joined += c.joined;
        matched += c.uploaded_and_joined;
        missing += c.missing;
      }
      const seats = list.reduce((a, r) => a + r.approved_seats, 0);
      const admitted = list.reduce((a, r) => a + (r.admitted ?? 0), 0);
      const cases = list.reduce((a, r) => a + openCases(r.id), 0);
      const n = total(rec);
      const common = [list.length, seats, admitted, n, rec.COUNTERSIGNED, rec.AWAITING_EVIDENCE, rec.UNDER_REVIEW, rec.DISPUTED, one(pct(rec.COUNTERSIGNED, n)), cases];
      return name === "by-state"
        ? { sort: list[0].state_name, row: [year, key, list[0].state_name, list[0].region, ...common, joined, missing, one(pct(matched, joined))] }
        : { sort: key, row: [year, key as InstitutionType, ...common, one(pct(matched, joined))] };
    });
    return out.sort((a, b) => a.sort.localeCompare(b.sort)).map((x) => x.row);
  }
  if (name === "cases-by-type-and-outcome") {
    const ids = new Set(rows.map((r) => r.id));
    const flags = allFlags().filter((f) => ids.has(f.institutionId));
    return (Object.keys(CASE_NAME) as FlagType[])
      .map((type) => {
        const list = flags.filter((f) => f.type === type);
        const count = (s: string) => list.filter((f) => f.status === s).length;
        const days = list
          .filter((f) => f.status === "UPHELD" || f.status === "CORRECTED" || f.status === "WITHDRAWN")
          .map((f) => (Date.parse(f.updated_at) - Date.parse(f.created_at)) / 86_400_000)
          .sort((a, b) => a - b);
        const median = days.length ? days[Math.floor(days.length / 2)].toFixed(1) : "";
        return { type, row: [year, type, CASE_NAME[type], count("OPEN"), count("DOCS_REQUESTED"), count("ESCALATED"), count("UPHELD"), count("CORRECTED"), count("WITHDRAWN"), list.length, median] };
      })
      .sort((a, b) => a.type.localeCompare(b.type))
      .map((x) => x.row);
  }
  const sorted = [...rows].sort((a, b) => a.name.localeCompare(b.name));
  if (name === "countersign-coverage") {
    return sorted.map((r) => {
      const rec = countsFor(r.id);
      const active = rollFor(r.id).filter((e) => e.row.status === "ACTIVE" && e.row.academic_year === ACADEMIC_YEAR);
      const independent = (type: string) => active.filter((e) => e.checks.some((c) => c.type === type && c.state === "CONFIRMED" && c.independent)).length;
      return [year, r.aicte_permanent_id, r.name, r.state_code, r.type, total(rec), rec.COUNTERSIGNED, rec.AWAITING_EVIDENCE, rec.UNDER_REVIEW, rec.DISPUTED, one(pct(rec.COUNTERSIGNED, total(rec))), independent("ADMISSION"), independent("STUDYING"), independent("STUDENT")];
    });
  }
  return sorted
    .map((r) => {
      const c = completenessOf(r.id);
      return {
        pct: c.completeness_pct,
        row: [year, r.aicte_permanent_id, r.name, r.state_code, c.joined, c.uploaded_and_joined, c.missing, c.uploaded_not_joined, one(c.completeness_pct), c.deadline, c.first_upload_at ? c.first_upload_at.slice(0, 10) : "", c.deadline_state, c.case?.status ?? ""],
      };
    })
    .sort((a, b) => (a.pct ?? Infinity) - (b.pct ?? Infinity))
    .map((x) => x.row);
}

function summaryLines(user: User, rows: InstitutionRow[], year: string, scopeName: string): string[] {
  const rec = zero();
  for (const r of rows) add(rec, countsFor(r.id));
  const n = total(rec);
  const ids = new Set(rows.map((r) => r.id));
  const flags = allFlags().filter((f) => ids.has(f.institutionId));
  const open = flags.filter((f) => UNRESOLVED.includes(f.status));
  const top = [...rows].sort((a, b) => openCases(b.id) - openCases(a.id)).slice(0, 10);
  const late = rows.filter((r) => ["LATE", "OVERDUE"].includes(completenessOf(r.id).deadline_state));
  return [
    `Countersign summary, ${scopeName}, ${year}`,
    `Institutions ${rows.length}   Active records ${n}   Open cases ${open.length}`,
    "",
    "Records by status             Count     Share",
    ...([
      ["Countersigned", rec.COUNTERSIGNED],
      ["Awaiting evidence", rec.AWAITING_EVIDENCE],
      ["Under review", rec.UNDER_REVIEW],
      ["Disputed", rec.DISPUTED],
    ] as [string, number][]).map(([w, c]) => `${w.padEnd(30)}${String(c).padStart(5)}  ${(one(pct(c, n)) + "%").padStart(8)}  ${"#".repeat(Math.round(((c / Math.max(1, n)) * 40)))}`),
    "",
    "Open cases by type",
    ...(Object.keys(CASE_NAME) as FlagType[]).filter((t) => open.some((f) => f.type === t)).map((t) => `  ${CASE_NAME[t].padEnd(34)}${open.filter((f) => f.type === t).length}`),
    "",
    "Colleges with most unresolved cases",
    ...top.map((r) => `  ${r.name.slice(0, 60).padEnd(62)}${openCases(r.id)}`),
    "",
    "Late and overdue colleges",
    ...(late.length ? late.map((r) => `  ${r.name.slice(0, 60).padEnd(62)}${completenessOf(r.id).deadline_state}`) : ["  None"]),
    "",
    `${SYNTHETIC} Generated ${formatDate(new Date().toISOString())} by ${user.role === "AICTE_ADMIN" ? "AICTE officer" : "Regional officer"}. Page 1 of 1.`,
  ];
}

/** GET /reports/{name}.{format} in mock mode. */
export function reportFile(user: User, path: string): { blob: Blob; filename: string } {
  requireOfficer(user);
  const [pathname, qs] = path.split("?");
  const m = /^\/reports\/([a-z-]+)\.(csv|xlsx|pdf)$/.exec(pathname);
  const name = m?.[1] as ReportName | undefined;
  const format = m?.[2] as ReportFormat | undefined;
  if (!name || !format || !(name in TITLES) || (name === "summary" && format !== "pdf")) throw new ApiError(404, "REPORT_NOT_FOUND", "Report not found.");
  const year = new URLSearchParams(qs ?? "").get("academic_year") || ACADEMIC_YEAR;
  const { rows, name: scopeName, slug } = scope(user);
  const filename = `countersign_${name}_${year}_${slug}.${format}`;
  if (name === "summary") return { blob: pdfBlob(summaryLines(user, rows, year, scopeName)), filename };
  const header = COLUMNS[name];
  const table = year === ACADEMIC_YEAR ? tableOf(name, rows, year) : [];
  if (format === "csv") return { blob: new Blob([csvText(header, table)], { type: "text/csv;charset=utf-8" }), filename };
  if (format === "xlsx") {
    const about = [["Title", TITLES[name]], ["Scope", scopeName], ["Academic year", year], ["Generated", new Date().toISOString()], [SYNTHETIC]];
    return { blob: xlsxBlob([{ name: TITLES[name], rows: [header, ...table] }, { name: "About", rows: about }]), filename };
  }
  const widths = header.map((h, i) => Math.min(18, Math.max(h.length, ...table.slice(0, 25).map((r) => String(r[i] ?? "").length))));
  const line = (cells: unknown[]) => cells.map((c, i) => String(c ?? "").slice(0, widths[i]).padEnd(widths[i])).join(" ");
  const more = table.length > 25 ? [`and ${table.length - 25} more rows in the CSV or XLSX`] : [];
  return {
    blob: pdfBlob([`${TITLES[name]}, ${scopeName}, ${year}`, line(header), ...table.slice(0, 25).map(line), ...more, "", SYNTHETIC]),
    filename,
  };
}
