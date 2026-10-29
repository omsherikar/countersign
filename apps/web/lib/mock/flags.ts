/**
 * Mock flags for 2026-27, wired to the planted students in roll.ts. Evidence
 * sentences follow API_CONTRACT A2.17 word for word; facts may carry an
 * audience and a flag may carry a summary for the institution, which the
 * handler applies (A2.16 redaction) and never sends on the wire.
 */
import { ACADEMIC_YEAR, IDS, RULE, SEEDS, STATES } from "@/lib/mock/fixtures";
import { sentenceDate } from "@/lib/mock/evidence";
import { REPORTING_DEADLINE, joinedCounts } from "@/lib/mock/joinings";
import { CHECKED_AT, deadlineOf, entryByName, joiningYearOf, programmesFor, rollFor, updateFilename, type RollEntry } from "@/lib/mock/roll";
import type { CheckType, DocsKind, EvidenceFact, FlagStatus, FlagType, Severity } from "@/lib/types";

export interface StoredFact extends EvidenceFact {
  audience?: "OFFICER" | "INSTITUTION";
}

export interface StoredFlag {
  id: string;
  type: FlagType;
  severity: Severity;
  status: FlagStatus;
  institutionId: string;
  programmeId: string | null;
  enrolmentId: string | null;
  academic_year: string;
  summary: string;
  summaryForInstitution?: string;
  facts: StoredFact[];
  related: string[];
  rule_source: string;
  created_at: string;
  updated_at: string;
  /** Where the case stands, for the record's next step (A4.3): the last document request and any escalation. */
  progress: { docs: { kind: DocsKind; due_on: string | null; responded_at: string | null } | null; escalated_at: string | null };
}

/** The row a case covers (A4.10), or null. */
export const COVERS: Partial<Record<FlagType, CheckType>> = {
  INVALID_APAAR: "IDENTITY",
  NAME_MISMATCH: "IDENTITY",
  EXCESS_ADMISSION: "SEAT",
  QUOTA_BREACH: "SEAT",
  ELIGIBILITY_BREACH: "SEAT",
  NOT_IN_JOINING_RECORD: "ADMISSION",
  NO_ACADEMIC_ACTIVITY: "STUDYING",
  STUDENT_DENIED: "STUDENT",
};

export const SEVERITY_RANK: Record<Severity, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };
export const UNRESOLVED: FlagStatus[] = ["OPEN", "DOCS_REQUESTED", "ESCALATED"];

const ID = (n: number) => (n === 1 ? "f1f1f1f1-7777-4888-8999-000011112222" : `f${String(n).padStart(7, "0")}-7777-4888-8999-000011112222`);
const KARAD = "10000000-0004-4000-8000-000000000004";
const KAVERI = "10000000-0006-4000-8000-000000000006";
const LUCKNOW = "10000000-0007-4000-8000-000000000007";
const PUNE = "10000000-0010-4000-8000-000000000010";
const GAYATRI = "10000000-0003-4000-8000-000000000003";

function nameOf(id: string) {
  return SEEDS.find((s) => s.id === id)!.name;
}
function stateNameOf(id: string) {
  const code = SEEDS.find((s) => s.id === id)!.state_code;
  return STATES.find((s) => s.code === code)!.name;
}

function flag(
  n: number,
  type: FlagType,
  severity: Severity,
  owner: RollEntry | { institutionId: string; programmeId: string },
  enrolment: RollEntry | null,
  summary: string,
  facts: StoredFact[],
  related: RollEntry[],
  rule_source: string,
  created_at: string,
  summaryForInstitution?: string,
): StoredFlag {
  const institutionId = owner.institutionId;
  const programmeId = "programmeId" in owner ? owner.programmeId : owner.programme.id;
  return {
    id: ID(n),
    type,
    severity,
    status: "OPEN",
    institutionId,
    programmeId,
    enrolmentId: enrolment?.row.id ?? null,
    academic_year: ACADEMIC_YEAR,
    summary,
    summaryForInstitution,
    facts,
    related: related.map((e) => e.row.id),
    rule_source,
    created_at,
    updated_at: created_at,
    progress: { docs: null, escalated_at: null },
  };
}

function build(): StoredFlag[] {
  const flags: StoredFlag[] = [];

  /* ABC College: CSE excess admission (the panel demo). */
  const abc = rollFor(IDS.abc);
  const cse = programmesFor(IDS.abc).find((p) => p.code === "CSE")!;
  const cseIntake = abc.filter((e) => e.programme.id === cse.id && e.row.cohort_year === ACADEMIC_YEAR);
  const withinIntake = cseIntake.filter((e) => e.seatType === "REGULAR" || e.seatType === "NRI");
  const unseated = withinIntake.filter((e) => !e.seat);
  const seated = withinIntake.length - unseated.length;
  flags.push(
    flag(
      1,
      "EXCESS_ADMISSION",
      "HIGH",
      { institutionId: IDS.abc, programmeId: cse.id },
      null,
      `${withinIntake.length} admitted against ${cse.approval.approved_intake} approved seats in CSE (${ACADEMIC_YEAR}); ${unseated.length} without a seat.`,
      [
        { label: "Approved intake", value: String(cse.approval.approved_intake), source: `AICTE approval ${ACADEMIC_YEAR}` },
        { label: "Admitted (active)", value: String(withinIntake.length), source: "College uploads, Regular and NRI routes" },
        { label: "Seated", value: String(seated), source: "Seat ledger" },
        { label: "Unseated", value: String(unseated.length), source: "Seat ledger" },
      ],
      unseated,
      RULE.REGULAR,
      "2026-10-27T09:30:24Z",
    ),
  );

  /* ABC College: R. K. Sharma, row 133, is Ravi Kumar Sharma, row 2. */
  const ravi = entryByName(IDS.abc, "Ravi Kumar Sharma");
  const rk = entryByName(IDS.abc, "R. K. Sharma");
  const file = ravi.upload!.filename;
  flags.push(
    flag(
      2,
      "DUPLICATE_WITHIN_UPLOAD",
      "MEDIUM",
      rk,
      rk,
      `Rows ${ravi.row.source_row_no} and ${rk.row.source_row_no} of ${file} describe the same student.`,
      [
        { label: "Match on", value: "Name (71 of 100), date of birth and mobile", source: "Duplicate detection" },
        { label: "Row A", value: `${file}, row ${ravi.row.source_row_no}`, source: "College upload" },
        { label: "Row B", value: `${file}, row ${rk.row.source_row_no}`, source: "College upload" },
        { label: "Names as uploaded", value: "Ravi Kumar Sharma / R. K. Sharma", source: "College upload" },
      ],
      [ravi],
      "Upload validation",
      "2026-10-27T09:30:23Z",
    ),
  );

  /* ABC College: an APAAR the registry does not know. */
  const rahul = entryByName(IDS.abc, "Rahul Pawar");
  flags.push(
    flag(
      3,
      "INVALID_APAAR",
      "HIGH",
      rahul,
      rahul,
      "APAAR ending 9031 is not in the APAAR registry.",
      [
        { label: "APAAR (masked)", value: "XXXX XXXX 9031", source: "College upload" },
        { label: "Registry reply", value: "Not found", source: "APAAR registry" },
        { label: "Checked at", value: "27 Oct 2026", source: "APAAR registry" },
      ],
      [],
      "APAAR verification",
      "2026-10-27T09:30:22Z",
    ),
  );

  /* ABC College: a name close to the registry but not a clear match. */
  const faizan = entryByName(IDS.abc, "Mohd. Faizan Shaikh");
  flags.push(
    flag(
      4,
      "NAME_MISMATCH",
      "LOW",
      faizan,
      faizan,
      "Name on upload differs from the APAAR registry (similarity 82 of 100).",
      [
        { label: "Name on upload", value: "Mohd. Faizan Shaikh", source: "College upload" },
        { label: "Similarity", value: "82 of 100", source: "APAAR registry" },
        { label: "Date of birth match", value: "Yes", source: "APAAR registry" },
        { label: "Checked at", value: "27 Oct 2026", source: "APAAR registry" },
      ],
      [],
      "APAAR verification",
      "2026-10-27T09:30:22Z",
    ),
  );

  /* ABC College: a second-year student with no ABC credits. */
  const kunal = entryByName(IDS.abc, "Kunal Bhosale", 2);
  flags.push(
    flag(
      5,
      "NO_ACADEMIC_ACTIVITY",
      "MEDIUM",
      kunal,
      kunal,
      "No credits recorded in ABC for 2 semesters while enrolled in year 2.",
      [
        { label: "Semesters checked", value: "2 (2025-26 to 2025-26)", source: "ABC" },
        { label: "Credits found", value: "Sem 1: 0, Sem 2: 0", source: "ABC" },
        { label: "Last ABC entry", value: "None", source: "ABC" },
      ],
      [],
      "ABC credit record",
      "2026-10-27T09:30:22Z",
    ),
  );

  /* ABC College and the Lucknow department: one physical, one online enrolment (allowed). */
  const meeraAbc = entryByName(IDS.abc, "Meera Joshi");
  const meeraLko = entryByName(LUCKNOW, "Meera Joshi");
  const dual = (n: number, a: RollEntry, b: RollEntry, created: string) =>
    flag(
      n,
      "DUAL_ENROLMENT_ALLOWED",
      "LOW",
      a,
      a,
      "The student holds two enrolments; one is distance or online, which is permitted.",
      [
        { label: "Enrolment A mode", value: `${nameOf(a.institutionId)}: ${a.programme.code}, ${modeWord(a)}`, source: "College upload" },
        { label: "Enrolment B mode", value: `${nameOf(b.institutionId)}: ${b.programme.code}, ${modeWord(b)}`, source: "College upload", audience: "OFFICER" },
        {
          label: "Enrolment B mode",
          value: `Another institution in ${stateNameOf(b.institutionId)}: ${b.programme.code}, ${modeWord(b)}`,
          source: "College upload",
          audience: "INSTITUTION",
        },
        { label: "UGC notification", value: "Pursuing two academic programmes simultaneously, 2022", source: "UGC" },
      ],
      [b],
      "UGC dual-degree guidelines 2022",
      created,
    );
  flags.push(dual(6, meeraAbc, meeraLko, "2026-10-27T09:30:23Z"), dual(7, meeraLko, meeraAbc, "2026-10-26T11:04:09Z"));

  /* XYZ Institute: a name the registry scores 68. */
  const k = entryByName(IDS.xyz, "K. Subramanian");
  flags.push(
    flag(
      8,
      "NAME_MISMATCH",
      "MEDIUM",
      k,
      k,
      "Name on upload differs from the APAAR registry (similarity 68 of 100).",
      [
        { label: "Name on upload", value: "K. Subramanian", source: "College upload" },
        { label: "Similarity", value: "68 of 100", source: "APAAR registry" },
        { label: "Date of birth match", value: "Yes", source: "APAAR registry" },
        { label: "Checked at", value: "27 Oct 2026", source: "APAAR registry" },
      ],
      [],
      "APAAR verification",
      "2026-10-27T09:31:02Z",
    ),
  );

  /* XYZ Institute and Kaveri School: the same APAAR active at both. */
  const arjunXyz = entryByName(IDS.xyz, "Arjun Iyer");
  const arjunKav = entryByName(KAVERI, "Arjun Iyer");
  const cross = (n: number, a: RollEntry, b: RollEntry, upA: string, upB: string, created: string) =>
    flag(
      n,
      "DUPLICATE_CROSS_INSTITUTION",
      "HIGH",
      a,
      a,
      `The same student appears as active at ${nameOf(a.institutionId)} and ${nameOf(b.institutionId)} (${ACADEMIC_YEAR}).`,
      [
        { label: "Match on", value: "Same APAAR", source: "Duplicate detection" },
        { label: "Institution A programme", value: `${nameOf(a.institutionId)}: ${a.programme.code}`, source: `College upload ${upA}` },
        { label: "Institution B programme", value: `${nameOf(b.institutionId)}: ${b.programme.code}`, source: `College upload ${upB}`, audience: "OFFICER" },
        {
          label: "Institution B programme",
          value: `Another institution in ${stateNameOf(b.institutionId)}: ${b.programme.code}`,
          source: `College upload ${upB}`,
          audience: "INSTITUTION",
        },
        { label: "Uploaded on", value: `${upA} and ${upB}`, source: "College uploads" },
      ],
      [b],
      "One active full-time enrolment per student",
      created,
      `The same student appears as active here and at another institution in ${stateNameOf(b.institutionId)} (${ACADEMIC_YEAR}).`,
    );
  flags.push(
    cross(9, arjunXyz, arjunKav, "27 Oct 2026", "26 Oct 2026", "2026-10-27T09:31:05Z"),
    cross(10, arjunKav, arjunXyz, "26 Oct 2026", "27 Oct 2026", "2026-10-27T09:31:05Z"),
  );

  /* Pune ITM: nine NRI admissions against six NRI seats. */
  const pune = rollFor(PUNE);
  const puneCse = programmesFor(PUNE).find((p) => p.code === "CSE")!;
  const nri = pune.filter((e) => e.programme.id === puneCse.id && e.row.cohort_year === ACADEMIC_YEAR && e.seatType === "NRI");
  const nriUnseated = nri.filter((e) => !e.seat);
  const nriPool = puneCse.pools.find((p) => p.seat_type === "NRI")!;
  flags.push(
    flag(
      11,
      "QUOTA_BREACH",
      nriUnseated.length > 2 ? "HIGH" : "MEDIUM",
      { institutionId: PUNE, programmeId: puneCse.id },
      null,
      `${nri.length} NRI admissions against ${nriPool.capacity} NRI seats in CSE (${ACADEMIC_YEAR}).`,
      [
        { label: "Pool", value: "NRI", source: "Seat ledger" },
        { label: "Capacity", value: String(nriPool.capacity), source: "AICTE approval rules" },
        { label: "Admitted via route", value: `${nri.length} (NRI)`, source: "College uploads" },
        { label: "Unseated", value: String(nriUnseated.length), source: "Seat ledger" },
        { label: "Rule percentage", value: `5% of approved intake ${puneCse.approval.approved_intake}`, source: "AICTE approval rules" },
      ],
      nriUnseated,
      RULE.NRI,
      "2026-10-26T15:42:10Z",
    ),
  );

  /* GCE Karad: a released seat filled after the cutoff. */
  const refill = rollFor(KARAD).find((e) => e.seat?.seat_code === "MECH-R-031" && e.row.year_of_study === 1)!;
  flags.push(
    flag(
      12,
      "LATE_REFILL",
      "MEDIUM",
      refill,
      refill,
      "Seat MECH-R-031 assigned on 5 Oct 2026, after the last admission date 15 Sep 2026.",
      [
        { label: "Seat", value: "MECH-R-031", source: "Seat ledger" },
        { label: "Released on", value: "28 Sep 2026", source: "Seat ledger" },
        { label: "Assigned on", value: "5 Oct 2026", source: `College upload ${updateFilename("1-2209318840")}, row 4` },
        { label: "Last admission date", value: "15 Sep 2026", source: "AICTE admission schedule" },
      ],
      [],
      `Last admission date for ${ACADEMIC_YEAR} (AICTE admission schedule)`,
      "2026-10-28T08:15:55Z",
    ),
  );

  /* Records the state admission authority's joining record does not hold, after the 30 Sep deadline. */
  const notJoined: [string, string][] = [
    [IDS.abc, "Ananya Deshmukh"],
    [IDS.abc, "Tejas More"],
    [IDS.xyz, "Lakshmi Narayanan"],
    [PUNE, "Pranav Salunkhe"],
    [GAYATRI, "Sai Varma"],
  ];
  notJoined.forEach(([home, name], i) => {
    const e = entryByName(home, name);
    const year = joiningYearOf(e.row);
    const deadline = sentenceDate(deadlineOf(year));
    const state = stateNameOf(home);
    flags.push(
      flag(
        40 + i,
        "NOT_IN_JOINING_RECORD",
        "MEDIUM",
        e,
        e,
        `Not found in the ${state} admission authority's joining record for ${e.programme.code} (${year}) after the reporting deadline of ${deadline}.`,
        [
          { label: "Programme and year", value: `${e.programme.code} (${year})`, source: "College upload" },
          { label: "Joining record", value: "Not found", source: "State admission authority" },
          { label: "Checked on", value: sentenceDate(CHECKED_AT), source: "State admission authority" },
          { label: "Reporting deadline", value: deadline, source: "AICTE reporting schedule" },
        ],
        [],
        "State admission authority joining record",
        CHECKED_AT,
      ),
    );
  });

  /* Colleges whose uploads leave out students the authority lists as joined (D40). */
  [IDS.abc, KARAD, PUNE, KAVERI].forEach((home, i) => {
    const c = joinedCounts(home);
    if (c.missing.length === 0) return;
    const share = c.joined ? Math.round((c.matched / c.joined) * 1000) / 10 : 0;
    const state = stateNameOf(home);
    const ids = c.missing.map((m) => m.apaar_masked ?? `Roll XXXX${(m.roll_no ?? "").slice(-4)}`).join(", ");
    flags.push({
      ...flag(
        50 + i,
        "MISSING_FROM_UPLOAD",
        "MEDIUM",
        { institutionId: home, programmeId: "" },
        null,
        `${c.missing.length} students the ${state} admission authority lists as joined at ${nameOf(home)} in ${ACADEMIC_YEAR} are not in the college's uploads.`,
        [
          { label: "Joined (authority)", value: String(c.joined), source: "State admission authority" },
          { label: "Uploaded and joined", value: String(c.matched), source: "Reconciliation" },
          { label: "Missing", value: String(c.missing.length), source: "Reconciliation" },
          { label: "Completeness", value: `${share}%`, source: "Reconciliation" },
          { label: "Reporting deadline", value: sentenceDate(REPORTING_DEADLINE), source: "AICTE reporting schedule" },
          { label: "Missing students", value: ids, source: "State admission authority" },
        ],
        [],
        `State admission authority joining record; reporting deadline ${sentenceDate(REPORTING_DEADLINE)}`,
        "2026-10-28T06:00:00Z",
      ),
      programmeId: null,
    });
  });

  return flags;
}

function modeWord(e: RollEntry): string {
  return e.programme.mode === "ODL" ? "open and distance learning" : e.programme.mode === "ONLINE" ? "online" : "physical";
}

let FLAGS: StoredFlag[] | null = null;

export function allFlags(): StoredFlag[] {
  if (!FLAGS) FLAGS = build();
  return FLAGS;
}

export function flagById(id: string): StoredFlag | undefined {
  return allFlags().find((f) => f.id === id);
}

/** Unresolved flags per institution, the `flags_open` count everywhere in the api. */
export function openFlagCount(institutionId: string): number {
  return allFlags().filter((f) => f.institutionId === institutionId && UNRESOLVED.includes(f.status)).length;
}
