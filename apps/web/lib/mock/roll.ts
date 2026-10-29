/**
 * The mock roll: every enrolment of an institution for 2026-27, built
 * deterministically from its programmes, with the seat ledger run over the
 * first-year intake and the five evidence rows written with the sentences of
 * API_CONTRACT A4.2 to A4.4 (copy deck §15). Rolls are built on first use and
 * kept for the session, so a recheck changes what later requests see. The
 * record status is computed when a record is read (lib/mock/records.ts),
 * because it also reads the cases that name the record.
 *
 * Planted scenarios (all at 2026-27):
 * - ABC CSE: 132 admitted against 120 approved, the last 12 rows unseated.
 * - ABC CSE row 133 "R. K. Sharma" duplicates row 2, Ravi Kumar Sharma.
 * - ABC IT "Meera Joshi" also studies online at the Lucknow department.
 * - ABC MECH year 2 "Kunal Bhosale" has no ABC credits.
 * - ABC ECE "Priya Nair": the APAAR registry did not answer (Identity pending).
 * - ABC EEE "Mohd. Faizan Shaikh" (name 82 of 100) and "Rahul Pawar" (APAAR not in the registry).
 * - XYZ "K. Subramanian" (name 68 of 100); "Arjun Iyer" active at XYZ and Kaveri.
 * - Pune ITM CSE: 9 NRI admissions against 6 NRI seats.
 * - GCE Karad MECH-R-031 refilled on 5 Oct, after the 15 Sep cutoff.
 * - ABC CSE "Sanika Ghorpade": the deck's sample card (joining record not
 *   found, the student disputes it after DigiLocker sign-in: Disputed).
 * - Five records the joining record does not hold (Not in joining record).
 * - The Telangana authority has published no joining record, and the
 *   Durgapur college's 2026-27 one is not out yet: those rows wait.
 * - Deccan Institute of Architecture issues its own credits (not independent).
 * - A few TFW rows without the income certificate (Seat pending).
 */
import { ACADEMIC_YEAR, BASE_PROGRAMMES, IDS, SEAT_LETTER, SEEDS, STATES, durationOf, earlierYears, lateralEntrants, poolCapacities } from "@/lib/mock/fixtures";
import { briefOf, makeRow, recordOf, sentenceDate, type RowSpec } from "@/lib/mock/evidence";
import type {
  AdmissionRoute,
  ApprovalRef,
  Category,
  CheckType,
  ConsentStatus,
  EnrolmentDetail,
  EnrolmentRow,
  EnrolmentVersion,
  EvidenceRow,
  ProgrammeDetail,
  SeatRow,
  SeatType,
  StudentMe,
} from "@/lib/types";

export interface Special {
  identity?: "UNAVAILABLE" | "REVIEW" | "NOT_IN_REGISTRY" | "NAME";
  attempts?: number;
  studying?: "NONE" | "ONE_MISSING";
  /** Not in the admission authority's joining record (A4.4 NOT_IN_JOINING_RECORD). */
  joining?: "NOT_FOUND";
  /** The deck's sample card. */
  sample?: boolean;
}

export interface RollEntry {
  row: EnrolmentRow;
  institutionId: string;
  programme: ProgrammeDetail;
  /** The pool the admission route maps to. */
  seatType: SeatType;
  seat: { id: string; seat_code: string; seat_type: SeatType; academic_year: string; assigned_at: string | null } | null;
  dob: string;
  gender: "M" | "F" | "O" | "U";
  mobileMasked: string | null;
  apaarLast4: string | null;
  nameScore: number;
  round: number;
  upload: { batch_id: string; filename: string; row_no: number | null } | null;
  special: Special;
  /** Set on the planted students so flags.ts finds them, not a generated namesake. */
  planted?: boolean;
  /** The case the Seat row points at when unseated. */
  seatFlagName: string;
  checks: EvidenceRow[];
}

/* ---- Batches the roll was uploaded in ---------------------------------- */

export const INITIAL_UPLOADED_AT = "2026-10-27T09:30:14Z";
export const CHECKED_AT = "2026-10-27T09:30:21Z";
export const UPDATE_UPLOADED_AT = "2026-10-28T08:15:40Z";

export function initialBatchId(institutionId: string): string {
  return institutionId === IDS.abc ? "b7c1d2e3-4444-4555-8666-777788889999" : `b${institutionId.slice(1, 8)}-4444-4555-8666-777788889999`;
}
export function updateBatchId(institutionId: string): string {
  return `c${institutionId.slice(1, 8)}-4444-4555-8666-777788889999`;
}
export function initialFilename(aicteId: string): string {
  return `${aicteId}_${ACADEMIC_YEAR}.csv`;
}
export function updateFilename(aicteId: string): string {
  return `${aicteId}_${ACADEMIC_YEAR}_update1.csv`;
}

/* ---- Words used inside check sentences (copy deck enum words) ---------- */

const ROUTE_WORD: Record<AdmissionRoute, string> = {
  COUNSELLING: "Counselling",
  MANAGEMENT: "Management",
  NRI: "NRI",
  SPOT: "Spot",
  LATERAL: "Lateral",
  INTERNATIONAL: "International",
  TFW: "TFW",
};
export const SEAT_TYPE_WORD: Record<SeatType, string> = {
  REGULAR: "Regular",
  NRI: "NRI",
  TFW: "TFW",
  LATERAL: "Lateral",
  INTERNATIONAL: "International",
};

/* ---- Names ------------------------------------------------------------- */

const FIRST_M = ["Aarav", "Arjun", "Deepak", "Farhan", "Harsh", "Kabir", "Manish", "Nikhil", "Pranav", "Rohan", "Varun", "Yash", "Siddharth", "Aditya", "Vikram", "Sameer", "Tushar", "Omkar", "Akash", "Gaurav"];
const FIRST_F = ["Aisha", "Ananya", "Bhavna", "Divya", "Gauri", "Ishita", "Kavya", "Pooja", "Riya", "Sana", "Sneha", "Tanvi", "Neha", "Shruti", "Priyanka", "Anjali", "Swati", "Rutuja", "Komal", "Nandini"];
const LAST: Record<string, string[]> = {
  MH: ["Deshmukh", "Kulkarni", "Patil", "Pawar", "Shinde", "Gaikwad", "Chavan", "Jadhav", "More", "Kale", "Sawant", "Joshi", "Mane", "Salunkhe", "Kadam"],
  TN: ["Iyer", "Subramanian", "Krishnan", "Raman", "Murugan", "Natarajan", "Pillai", "Balaji", "Sundaram", "Venkatesh"],
  KA: ["Gowda", "Rao", "Hegde", "Shetty", "Bhat", "Kamath", "Naik", "Kulkarni"],
  AP: ["Reddy", "Naidu", "Rao", "Varma", "Chowdary", "Prasad"],
  TS: ["Reddy", "Rao", "Goud", "Varma", "Yadav", "Sharma"],
  UP: ["Verma", "Srivastava", "Mishra", "Tiwari", "Yadav", "Shukla", "Pandey"],
  WB: ["Das", "Ghosh", "Banerjee", "Mukherjee", "Sen", "Bose", "Roy"],
  GJ: ["Patel", "Shah", "Desai", "Mehta", "Trivedi", "Parikh"],
};
const COUNSELLING_PREFIX: Record<string, string> = { MH: "MHCET", TN: "TNEA", KA: "KCET", AP: "APEAPCET", TS: "TSEAMCET", UP: "UPTAC", WB: "WBJEE", GJ: "ACPC" };
const CATEGORIES: Category[] = ["GENERAL", "OBC", "GENERAL", "OBC", "EWS", "SC", "GENERAL", "ST", "OBC", "GENERAL"];

const hash = (n: number) => (n * 2654435761) >>> 0;
const pad = (n: number, w: number) => String(n).padStart(w, "0");
const yearLabel = (start: number) => `${start}-${pad((start + 1) % 100, 2)}`;

function routePool(route: AdmissionRoute): SeatType {
  if (route === "NRI" || route === "TFW" || route === "LATERAL" || route === "INTERNATIONAL") return route;
  return "REGULAR";
}

/* ---- Building one institution's roll ------------------------------------ */

const ROLLS = new Map<string, RollEntry[]>();
const BY_ID = new Map<string, RollEntry>();

function planRoute(instCode: string, p: ProgrammeDetail, idx: number, used: Record<SeatType, number>, cap: Record<SeatType, number>): AdmissionRoute {
  if (instCode === "1-ABC-0001" && p.code === "CSE") {
    if ([10, 30, 50, 70, 90, 110].includes(idx)) return "NRI";
    if (idx % 4 === 3) return "MANAGEMENT";
    if (idx % 13 === 6) return "SPOT";
    return "COUNSELLING";
  }
  if (instCode === "1-9001127734" && p.code === "CSE") {
    if (idx % 12 === 5 && idx < 108) return "NRI";
    return idx % 4 === 3 ? "MANAGEMENT" : "COUNSELLING";
  }
  const want: AdmissionRoute | null =
    idx % 20 === 7 ? "NRI" : idx % 25 === 12 ? "TFW" : idx % 41 === 19 && p.discipline === "ENGINEERING" ? "INTERNATIONAL" : null;
  if (want && used[routePool(want)] < cap[routePool(want)]) return want;
  if (idx % 4 === 3) return "MANAGEMENT";
  if (idx % 13 === 6) return "SPOT";
  return "COUNSELLING";
}

function buildRoll(instIdx: number): RollEntry[] {
  const seed = SEEDS[instIdx];
  const lastNames = LAST[seed.state_code] ?? LAST.MH;
  const prefix = COUNSELLING_PREFIX[seed.state_code] ?? "CET";
  const batchId = initialBatchId(seed.id);
  const filename = initialFilename(seed.aicte_permanent_id);
  const entries: RollEntry[] = [];
  let rowNo = 2;

  BASE_PROGRAMMES[seed.id].forEach((p, pi) => {
    const intake = p.approval.approved_intake;
    const cap = poolCapacities(intake);
    const used: Record<SeatType, number> = { REGULAR: 0, NRI: 0, TFW: 0, LATERAL: 0, INTERNATIONAL: 0 };
    const cohorts: { year: number; count: number; lateral?: boolean }[] = [
      { year: 1, count: p.enrolments },
      ...earlierYears(intake, durationOf(p.level)),
    ];
    const lat = lateralEntrants(intake, p.level);
    if (lat > 0) cohorts.push({ year: 2, count: lat, lateral: true });

    for (const c of cohorts) {
      const start = 2026 - (c.year - 1);
      const cohort = yearLabel(start);
      const priorUsed: Record<SeatType, number> = { REGULAR: 0, NRI: 0, TFW: 0, LATERAL: 0, INTERNATIONAL: 0 };
      for (let idx = 0; idx < c.count; idx++) {
        const n = instIdx * 100000 + pi * 10000 + c.year * 1000 + (c.lateral ? 500 : 0) + idx;
        const h = hash(n + 7);
        const route: AdmissionRoute = c.lateral ? "LATERAL" : c.year === 1 ? planRoute(seed.aicte_permanent_id, p, idx, used, cap) : planRoute("", p, idx, priorUsed, cap);
        const pool = routePool(route);
        const female = h % 2 === 0;
        const first = (female ? FIRST_F : FIRST_M)[(h >>> 3) % 20];
        const last = lastNames[(h >>> 9) % lastNames.length];
        const international = route === "INTERNATIONAL";
        let consent: ConsentStatus = "LINKED";
        if (international) consent = "INTERNATIONAL";
        else if (idx % 23 === 11) consent = "REFUSED";
        else if (idx % 29 === 17) consent = "PENDING";
        const linked = consent === "LINKED";
        const last4 = linked ? pad((h >>> 5) % 10000, 4) : null;

        // Seat ledger: the first-year intake against this approval's pools, in row order.
        let seat: RollEntry["seat"] = null;
        const counter = c.year === 1 ? used : priorUsed;
        if (c.year > 1 || counter[pool] < cap[pool]) {
          counter[pool] += 1;
          const code = `${p.code}-${SEAT_LETTER[pool]}-${pad(counter[pool], 3)}`;
          seat = {
            id: `${p.id.slice(0, 8)}-${SEAT_LETTER[pool]}${pad(counter[pool], 3)}-4${pad(start % 1000, 3)}-8000-000000000000`,
            seat_code: code,
            seat_type: pool,
            academic_year: cohort,
            assigned_at: c.year === 1 ? "2026-10-27T09:30:16Z" : `${start}-08-20T10:00:00Z`,
          };
        }

        const idHead = `e${instIdx.toString(16)}${pi}${c.lateral ? 5 : c.year}${pad(idx, 4)}`;
        const admissionDate = `${start}-0${7 + (idx % 2)}-${pad(2 + (idx % 27), 2)}`;
        const row: EnrolmentRow = {
          id: `${idHead}-5555-4666-8777-888899990000`,
          student: {
            id: `s${idHead.slice(1)}-5555-4666-8777-888899990000`,
            name: `${first} ${last}`,
            apaar_masked: last4 ? `XXXX XXXX ${last4}` : null,
            consent_status: consent,
            provisional_id: linked ? null : `PRV-${(hash(n + 11) >>> 0).toString(16).toUpperCase().padStart(8, "0").slice(0, 8)}`,
            nationality: international ? (idx % 2 === 0 ? "NP" : "BD") : "IN",
          },
          programme_id: p.id,
          programme_code: p.code,
          academic_year: ACADEMIC_YEAR,
          cohort_year: cohort,
          year_of_study: c.year,
          admission_route: route,
          counselling_ref:
            route === "COUNSELLING" || route === "LATERAL"
              ? `${route === "LATERAL" ? `DSE-${seed.state_code}` : prefix}-${start}-R${1 + (idx % 3)}-${pad((h >>> 7) % 1000000, 6)}`
              : null,
          category: CATEGORIES[(h >>> 13) % CATEGORIES.length],
          seat_code: seat?.seat_code ?? null,
          status: "ACTIVE",
          admission_date: admissionDate,
          status_date: "2026-10-27",
          uploaded_at: INITIAL_UPLOADED_AT,
          upload_batch_id: batchId,
          source_row_no: rowNo,
          eligibility: {
            tfw_income_certified: route === "TFW" ? (idx % 9 === 4 ? null : true) : null,
            nri_sponsored: route === "NRI" ? true : null,
            ciwg: null,
          },
          record_status: null,
          status_reason: null,
          next_step: null,
          record_status_at: null,
          checks: [],
          flags: [],
        };
        const entry: RollEntry = {
          row,
          institutionId: seed.id,
          programme: p,
          seatType: pool,
          seat,
          dob: `${start - 18 - (idx % 2)}-${pad(1 + (idx % 12), 2)}-${pad(1 + ((h >>> 4) % 28), 2)}`,
          gender: female ? "F" : "M",
          mobileMasked: `XXXXXX${pad((h >>> 11) % 10000, 4)}`,
          apaarLast4: last4,
          nameScore: idx % 9 === 4 ? 96 : idx % 11 === 5 ? 93 : 100,
          round: 1 + (idx % 3),
          upload: { batch_id: batchId, filename, row_no: rowNo },
          special: {},
          seatFlagName: pool === "REGULAR" || pool === "NRI" ? (seed.aicte_permanent_id === "1-9001127734" && pool === "NRI" ? "Quota breach" : "Excess admission") : "Quota breach",
          checks: [],
        };
        rowNo += 1;
        entries.push(entry);
      }
    }
  });

  applyScenarios(seed.aicte_permanent_id, entries);
  for (const e of entries) evaluate(e);
  return entries;
}

function find(entries: RollEntry[], code: string, year: number, idx: number): RollEntry {
  const list = entries.filter((e) => e.programme.code === code && e.row.year_of_study === year && e.row.admission_route !== "LATERAL");
  return list[Math.min(idx, list.length - 1)];
}

function patchStudent(e: RollEntry, patch: Partial<EnrolmentRow["student"]>, extra: Partial<RollEntry> = {}) {
  e.row.student = { ...e.row.student, ...patch };
  Object.assign(e, extra, { planted: true });
}

function applyScenarios(aicte: string, entries: RollEntry[]) {
  if (aicte === "1-ABC-0001") {
    const ravi = find(entries, "CSE", 1, 0);
    ravi.row.id = "e0000000-0000-4666-8777-888899990000";
    patchStudent(
      ravi,
      { id: IDS.ravi, name: "Ravi Kumar Sharma", apaar_masked: "XXXX XXXX 4417", consent_status: "LINKED", provisional_id: null, nationality: "IN" },
      { dob: "2007-03-21", gender: "M", mobileMasked: "XXXXXX4521", apaarLast4: "4417", nameScore: 100, round: 1 },
    );
    Object.assign(ravi.row, { counselling_ref: "MHCET-2026-R1-004512", category: "GENERAL", admission_date: "2026-08-02" });

    const rk = find(entries, "CSE", 1, 131);
    patchStudent(rk, { name: "R. K. Sharma", apaar_masked: null, consent_status: "PENDING", provisional_id: "PRV-7Q2M9XKD" }, {
      dob: "2007-03-21",
      gender: "M",
      mobileMasked: "XXXXXX4521",
      apaarLast4: null,
      round: 1,
    });
    Object.assign(rk.row, { admission_route: "COUNSELLING", counselling_ref: "MHCET-2026-R1-004512", category: "GENERAL", admission_date: "2026-08-09" });

    const meera = find(entries, "IT", 1, 4);
    patchStudent(meera, { name: "Meera Joshi", apaar_masked: "XXXX XXXX 2290", consent_status: "LINKED", provisional_id: null }, { gender: "F", apaarLast4: "2290", dob: "2007-11-02" });

    const kunal = find(entries, "MECH", 2, 3);
    patchStudent(kunal, { name: "Kunal Bhosale", apaar_masked: "XXXX XXXX 6158", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "6158",
      special: { studying: "NONE" },
    });

    const priya = find(entries, "ECE", 1, 6);
    patchStudent(priya, { name: "Priya Nair", apaar_masked: "XXXX XXXX 3302", consent_status: "LINKED", provisional_id: null }, {
      gender: "F",
      apaarLast4: "3302",
      special: { identity: "UNAVAILABLE", attempts: 2 },
    });

    const faizan = find(entries, "EEE", 1, 9);
    patchStudent(faizan, { name: "Mohd. Faizan Shaikh", apaar_masked: "XXXX XXXX 5864", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "5864",
      nameScore: 82,
      special: { identity: "REVIEW" },
    });

    const rahul = find(entries, "EEE", 1, 14);
    patchStudent(rahul, { name: "Rahul Pawar", apaar_masked: "XXXX XXXX 9031", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "9031",
      special: { identity: "NOT_IN_REGISTRY" },
    });

    const sample = find(entries, "CSE", 1, 20);
    patchStudent(sample, { name: "Sanika Ghorpade", apaar_masked: "XXXX XXXX 6021", consent_status: "LINKED", provisional_id: null }, {
      gender: "F",
      apaarLast4: "6021",
      dob: "2008-02-11",
      nameScore: 100,
      special: { joining: "NOT_FOUND", sample: true },
    });
    Object.assign(sample.row, { admission_route: "COUNSELLING", counselling_ref: "MHCET-2026-R2-018833", admission_date: "2026-08-06", category: "GENERAL" });
    laterVersion(sample, "2026-10-28T08:15:46Z", 9, [
      { field: "admission_date", before: "2026-08-04", after: "2026-08-06" },
      { field: "category", before: "OBC", after: "GENERAL" },
    ]);
    laterVersion(ravi, "2026-10-28T08:15:44Z", 3, [{ field: "counselling_ref", before: "MHCET-2026-R1-004521", after: "MHCET-2026-R1-004512" }]);

    const tejas = find(entries, "MECH", 1, 21);
    patchStudent(tejas, { name: "Tejas More", apaar_masked: "XXXX XXXX 3348", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "3348",
      special: { joining: "NOT_FOUND" },
    });

    const ishaan = find(entries, "CIVIL", 3, 2);
    patchStudent(ishaan, { name: "Ishaan Rao", apaar_masked: "XXXX XXXX 1176", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "1176",
      special: { studying: "ONE_MISSING" },
    });
  }
  if (aicte === "1-XYZ-0002") {
    const k = find(entries, "CSE", 1, 8);
    patchStudent(k, { name: "K. Subramanian", apaar_masked: "XXXX XXXX 8812", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "8812",
      nameScore: 68,
      special: { identity: "NAME" },
    });
    const arjun = find(entries, "ECE", 1, 5);
    patchStudent(arjun, { name: "Arjun Iyer", apaar_masked: "XXXX XXXX 7731", consent_status: "LINKED", provisional_id: null }, { gender: "M", apaarLast4: "7731", dob: "2008-01-14" });
    const lakshmi = find(entries, "CSE", 1, 30);
    patchStudent(lakshmi, { name: "Lakshmi Narayanan", apaar_masked: "XXXX XXXX 5507", consent_status: "LINKED", provisional_id: null }, {
      gender: "F",
      apaarLast4: "5507",
      special: { joining: "NOT_FOUND" },
    });
  }
  if (aicte === "1-9001127734") {
    const pranav = find(entries, "IT", 1, 12);
    patchStudent(pranav, { name: "Pranav Salunkhe", apaar_masked: "XXXX XXXX 2716", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "2716",
      special: { joining: "NOT_FOUND" },
    });
  }
  if (aicte === "1-8437201389") {
    const sai = find(entries, "ECE", 1, 9);
    patchStudent(sai, { name: "Sai Varma", apaar_masked: "XXXX XXXX 9184", consent_status: "LINKED", provisional_id: null }, {
      gender: "M",
      apaarLast4: "9184",
      special: { joining: "NOT_FOUND" },
    });
  }
  if (aicte === "1-7710245519") {
    const arjun = find(entries, "BPHARM", 1, 3);
    patchStudent(arjun, { name: "Arjun Iyer", apaar_masked: "XXXX XXXX 7731", consent_status: "LINKED", provisional_id: null }, { gender: "M", apaarLast4: "7731", dob: "2008-01-14" });
  }
  if (aicte === "1-3390218806") {
    const meera = find(entries, "BCA", 1, 2);
    patchStudent(meera, { name: "Meera Joshi", apaar_masked: "XXXX XXXX 2290", consent_status: "LINKED", provisional_id: null }, { gender: "F", apaarLast4: "2290", dob: "2007-11-02" });
  }
  if (aicte === "1-2209318840") {
    const refill = entries.find((e) => e.seat?.seat_code === "MECH-R-031" && e.row.year_of_study === 1);
    if (refill) {
      patchStudent(refill, { name: "Omkar Jadhav", apaar_masked: "XXXX XXXX 6640", consent_status: "LINKED", provisional_id: null }, {
        gender: "M",
        apaarLast4: "6640",
        upload: { batch_id: updateBatchId(refill.institutionId), filename: updateFilename(aicte), row_no: 4 },
      });
      Object.assign(refill.row, {
        admission_route: "MANAGEMENT",
        counselling_ref: null,
        admission_date: "2026-10-05",
        uploaded_at: UPDATE_UPLOADED_AT,
        upload_batch_id: updateBatchId(refill.institutionId),
        source_row_no: 4,
      });
      if (refill.seat) refill.seat.assigned_at = "2026-10-28T08:15:52Z";
      laterVersion(refill, "2026-10-28T08:15:52Z", 4, [
        { field: "admission_route", before: "SPOT", after: "MANAGEMENT" },
        { field: "counselling_ref", before: "MHCET-2026-SPOT-000311", after: null },
        { field: "admission_date", before: "2026-09-12", after: "2026-10-05" },
      ]);
    }
  }
}

/* ---- Evidence rows (A4.2 to A4.4, copy deck §15) ------------------------- */

/** Joining records the state admission authorities have published (A4.25 C.9): Telangana none; West Bengal not 2026-27 yet. */
function joiningPublished(stateCode: string, joiningYear: string): boolean {
  if (stateCode === "TS") return false;
  if (stateCode === "WB" && joiningYear === ACADEMIC_YEAR) return false;
  return true;
}

/** Colleges that issue their own credits in ABC (D38): a deemed university here. */
const SELF_ISSUING = new Set(["1-4418830271"]);

/** The reporting deadline of a joining year (rules.yaml `reporting.deadline`). */
export function deadlineOf(joiningYear: string): string {
  return `${joiningYear.slice(0, 4)}-09-30`;
}

/** When ABC last received this cohort's results: 20 Jan and 20 Jul each year. */
function creditsUploadedAt(yearOfStudy: number): string {
  return yearOfStudy > 1 ? "2026-07-20T00:00:00Z" : "";
}

export function joiningYearOf(r: EnrolmentRow): string {
  return r.admission_route === "LATERAL" ? ACADEMIC_YEAR : r.cohort_year;
}

export function issuerNameOf(institutionId: string): string {
  const seed = SEEDS.find((s) => s.id === institutionId)!;
  return SELF_ISSUING.has(seed.aicte_permanent_id) ? seed.name : (seed.university_name ?? "ABC");
}

export function evaluate(e: RollEntry) {
  const r = e.row;
  const seed = SEEDS.find((s) => s.id === e.institutionId)!;
  const stateName = STATES.find((s) => s.code === seed.state_code)?.name ?? seed.state_code;
  const code = r.programme_code;
  const seatWord = SEAT_TYPE_WORD[e.seatType];
  const routeWord = ROUTE_WORD[r.admission_route];
  const linked = r.student.consent_status === "LINKED";
  const international = r.student.consent_status === "INTERNATIONAL";
  const checked = sentenceDate(CHECKED_AT);
  const sp = e.special;
  const rows: EvidenceRow[] = [];
  const add = (type: CheckType, spec: RowSpec, at = CHECKED_AT) => rows.push(makeRow(type, spec, at));

  // IDENTITY: the APAAR registry, Study in India, or nothing until the student claims the record.
  const apaar = { supplied_by: "APAAR registry", observed_at: CHECKED_AT, independent: true, source: "APAAR" as const };
  if (international)
    add("IDENTITY", { state: "CONFIRMED", basis: "SII_MATCH", source: "SII", supplied_by: "Study in India", observed_at: CHECKED_AT, independent: true, source_line: `Study in India · ${checked}`, summary: "Study in India confirms the passport holder's identity." });
  else if (!linked)
    add("IDENTITY", {
      state: "NOT_APPLICABLE",
      basis: "NO_APAAR",
      source: "APAAR",
      source_line: "APAAR not linked; alternative route not used yet",
      summary: "APAAR not linked, and the student has not claimed the record through DigiLocker yet. Admission is not blocked.",
    });
  else if (sp.identity === "UNAVAILABLE")
    add(
      "IDENTITY",
      {
        state: "SOURCE_UNAVAILABLE",
        basis: "SOURCE_UNAVAILABLE",
        source: "APAAR",
        supplied_by: "APAAR registry",
        observed_at: "2026-10-28T09:12:44Z",
        attempts: sp.attempts ?? 1,
        source_line: `APAAR registry did not respond · ${sentenceDate("2026-10-28T09:12:44Z")}`,
        summary: "APAAR registry did not respond. This row is asked again at the next recheck or the next upload.",
        detail: { source_unavailable: true, source_error: "HTTP 503" },
      },
      "2026-10-28T09:12:44Z",
    );
  else if (sp.identity === "REVIEW")
    add("IDENTITY", {
      ...apaar,
      state: "PENDING",
      basis: "NAME_REVIEW",
      finding: "needs review",
      source_line: `APAAR verification · ${checked}`,
      summary: `Name on upload is close to the APAAR registry but not a clear match (similarity ${e.nameScore} of 100); an officer should review. Name matching supports a decision; it never makes one.`,
      detail: { needs_review: true, name_score: e.nameScore, dob_match: true, apaar_last4: e.apaarLast4 ?? undefined, case_type: "NAME_MISMATCH" },
    });
  else if (sp.identity === "NOT_IN_REGISTRY")
    add("IDENTITY", {
      ...apaar,
      state: "CONTRADICTED",
      basis: "APAAR_UNKNOWN",
      finding: "APAAR not found",
      source_line: `APAAR verification · ${checked}`,
      summary: `APAAR ending ${e.apaarLast4} is not in the APAAR registry.`,
      detail: { apaar_last4: e.apaarLast4 ?? undefined, case_type: "INVALID_APAAR" },
    });
  else if (sp.identity === "NAME")
    add("IDENTITY", {
      ...apaar,
      state: "CONTRADICTED",
      basis: "NAME_MISMATCH",
      finding: "name differs",
      source_line: `APAAR verification · ${checked}`,
      summary: `Name on upload differs from the APAAR registry (similarity ${e.nameScore} of 100).`,
      detail: { name_score: e.nameScore, dob_match: true, apaar_last4: e.apaarLast4 ?? undefined, case_type: "NAME_MISMATCH" },
    });
  else
    add("IDENTITY", {
      ...apaar,
      state: "CONFIRMED",
      basis: "APAAR_MATCH",
      source_line: `APAAR verification · ${checked}`,
      summary: `Name and date of birth match the APAAR registry (similarity ${e.nameScore} of 100).`,
      detail: { name_score: e.nameScore, dob_match: true, apaar_last4: e.apaarLast4 ?? undefined },
    });

  // SEAT: derived by the Seat Ledger from the cohort's approval version; never independent evidence.
  const version = r.cohort_year === ACADEMIC_YEAR ? e.programme.approval.version : 1;
  const ledger = `AICTE approval v${version}, ${r.cohort_year} (Seat Ledger, derived)`;
  const seatBase = { source: "SEAT_LEDGER" as const, supplied_by: ledger, observed_at: CHECKED_AT, source_line: ledger };
  const approvalKeys = { approval_id: e.programme.approval.id, approval_version: version };
  if (e.seat && e.seat.seat_type === "TFW" && r.eligibility.tfw_income_certified === null)
    add("SEAT", {
      ...seatBase,
      state: "PENDING",
      basis: "TFW_NOT_REPORTED",
      finding: "TFW income certificate not reported",
      summary: "TFW income certificate not reported; the seat is held until the college reports it.",
      detail: { ...approvalKeys, seat_code: e.seat.seat_code, seat_type: e.seat.seat_type, eligibility_rule: "TFW_INCOME", reported: r.eligibility },
    });
  else if (e.seat)
    add("SEAT", {
      ...seatBase,
      state: "CONFIRMED",
      basis: "FITS",
      finding: "fits approved intake",
      summary: `Holds seat ${e.seat.seat_code} (${SEAT_TYPE_WORD[e.seat.seat_type]}, AICTE approval v${version}, ${r.cohort_year}).`,
      detail: { ...approvalKeys, seat_code: e.seat.seat_code, seat_type: e.seat.seat_type },
    });
  else {
    const flagType = e.seatFlagName === "Quota breach" ? "QUOTA_BREACH" : "EXCESS_ADMISSION";
    add("SEAT", {
      ...seatBase,
      state: "CONTRADICTED",
      basis: "NO_SEAT",
      finding: "beyond approved intake",
      summary: `No ${seatWord} seat is free in ${code} (${r.cohort_year}); see the ${e.seatFlagName} case.`,
      detail: { ...approvalKeys, seat_type: e.seatType, flag_type: flagType, case_type: flagType },
    });
  }

  // ADMISSION: the state admission authority's joining record, or Study in India.
  const joiningYear = joiningYearOf(r);
  const deadline = deadlineOf(joiningYear);
  const authority = { source: "ADMISSION_AUTHORITY" as const, supplied_by: "State admission authority", observed_at: CHECKED_AT };
  if (international)
    add("ADMISSION", {
      state: "CONFIRMED",
      basis: "SII_ADMITTED",
      source: "SII",
      supplied_by: "Study in India",
      observed_at: CHECKED_AT,
      independent: true,
      source_line: `Study in India · ${checked}`,
      summary: `Study in India confirms this admission to ${code} (${r.cohort_year}).`,
    });
  else if (!joiningPublished(seed.state_code, joiningYear))
    add("ADMISSION", {
      ...authority,
      state: "PENDING",
      basis: "NOT_PUBLISHED_LATE",
      finding: "not published yet",
      source_line: `Published by ${sentenceDate(deadline)}`,
      summary: `The ${stateName} admission authority has not published its joining record for ${joiningYear}; it was due by ${sentenceDate(deadline)}.`,
      detail: { joining_year: joiningYear, deadline, published: false },
    });
  else if (sp.joining === "NOT_FOUND")
    add("ADMISSION", {
      ...authority,
      independent: true,
      state: "CONTRADICTED",
      basis: "NOT_IN_JOINING_RECORD",
      finding: "not found",
      source_line: `State admission authority · ${checked}`,
      summary: `Not found in the ${stateName} admission authority's joining record for ${code} (${joiningYear}) after the reporting deadline of ${sentenceDate(deadline)}.`,
      detail: { joining_year: joiningYear, deadline, published: true, case_type: "NOT_IN_JOINING_RECORD" },
    });
  else {
    const counselled = r.admission_route === "COUNSELLING" || r.admission_route === "LATERAL";
    const roundWords = counselled ? `round ${e.round}` : `${routeWord} admission approved by the state`;
    add("ADMISSION", {
      ...authority,
      independent: true,
      state: "CONFIRMED",
      basis: "JOINED",
      finding: `joined ${sentenceDate(r.admission_date)}`,
      source_line: `State admission authority · ${checked}`,
      summary: `The ${stateName} admission authority records that the student joined ${code} at this college on ${sentenceDate(r.admission_date)} (${roundWords}).`,
      detail: { joining_year: joiningYear, joined_on: r.admission_date, round: counselled ? e.round : null, route: r.admission_route, deadline, published: true },
    });
  }

  // STUDYING: ABC credits, with the body that issued them.
  const expected = (r.year_of_study - 1) * 2;
  const selfIssued = SELF_ISSUING.has(seed.aicte_permanent_id);
  const issuerName = issuerNameOf(e.institutionId);
  const abcAt = creditsUploadedAt(r.year_of_study);
  const abcLine = selfIssued ? `ABC, issued by ${seed.name} itself · ${sentenceDate(abcAt)}` : `ABC, issued by ${issuerName} · ${sentenceDate(abcAt)}`;
  const abc = { source: "ABC" as const, supplied_by: selfIssued ? `ABC, issued by ${seed.name} (the college itself)` : `ABC, issued by ${issuerName}`, observed_at: abcAt || null };
  const lateral = r.admission_route === "LATERAL";
  if (r.year_of_study === 1 || (lateral && r.year_of_study === 2))
    add("STUDYING", {
      state: "NOT_YET_DUE",
      basis: lateral ? "LATERAL_FIRST_YEAR" : "FIRST_YEAR",
      source: "ABC",
      source_line: lateral ? "Lateral entry; first semester here not complete" : "First semester not complete",
      summary: lateral ? "Lateral entry into year 2; no semester result here is due yet." : "First year; no semester result is due yet.",
    });
  else if (!linked)
    add("STUDYING", { state: "NOT_APPLICABLE", basis: "NO_APAAR", source: "ABC", source_line: "APAAR not linked; ABC cannot be checked", summary: "APAAR not linked; ABC credits cannot be checked." });
  else if (sp.studying === "NONE")
    add("STUDYING", {
      ...abc,
      independent: !selfIssued,
      state: "CONTRADICTED",
      basis: "NO_ACADEMIC_ACTIVITY",
      finding: `no credits for ${expected} semesters`,
      source_line: abcLine,
      summary: `No credits recorded in ABC for ${expected} of ${expected} semesters since admission.`,
      detail: {
        expected,
        missing: expected,
        issuer_name: issuerName,
        case_type: "NO_ACADEMIC_ACTIVITY",
        semesters: [
          { academic_year: "2025-26", sem: 1, credits: 0, issuer: "MSTU" },
          { academic_year: "2025-26", sem: 2, credits: 0, issuer: "MSTU" },
        ],
      },
    });
  else if (sp.studying === "ONE_MISSING")
    add("STUDYING", {
      ...abc,
      state: "PENDING",
      basis: "ONE_SEMESTER_MISSING",
      finding: `waiting for semester ${expected}`,
      source_line: abcLine,
      summary: `No credits recorded in ABC for semester ${expected} (2025-26); waiting for the next results.`,
      detail: { expected, missing: 1, awaiting_semester: expected, issuer_name: issuerName },
    });
  else
    add("STUDYING", {
      ...abc,
      independent: !selfIssued,
      state: "CONFIRMED",
      basis: selfIssued ? "CREDITS_SELF_ISSUED" : "CREDITS",
      finding: `credits for ${expected} semesters`,
      source_line: abcLine,
      summary: selfIssued
        ? `Credits recorded in ABC for all ${expected} semesters, issued by the college itself. They do not count as evidence independent of the college.`
        : `Credits recorded in ABC for all ${expected} semesters since admission, issued by ${issuerName}.`,
      detail: { expected, missing: 0, issuer_name: issuerName, self_issued: selfIssued },
    });

  // STUDENT: the notice loop (lib/mock/cases.ts) replaces this row with the student's answer.
  add("STUDENT", {
    state: "PENDING",
    basis: "NOT_SENT",
    source: "STUDENT_NOTICE",
    finding: "notice not sent yet",
    source_line: "No notice sent yet",
    summary: "Notice not sent yet.",
    detail: { notice_state: "NOT_SENT" },
  });

  setRows(e, rows);
}

/** Stores the rows, the brief rows lists carry, and the status the rows alone give (cases are added on read). */
export function setRows(e: RollEntry, rows: EvidenceRow[]) {
  e.checks = rows;
  e.row.checks = briefOf(rows);
  if (e.row.status !== "ACTIVE") return;
  const record = recordOf(rows, [], recordContext(e));
  Object.assign(e.row, record, { record_status_at: e.row.record_status_at ?? CHECKED_AT });
}

/** What the next step reads besides the rows (A4.3). */
export function recordContext(e: RollEntry) {
  const student = e.checks.find((c) => c.type === "STUDENT");
  const sentAt = student?.detail.notice_state === "SENT" ? String(student.detail.sent_at ?? "") || null : null;
  return {
    noticeSentAt: sentAt,
    issuerName: issuerNameOf(e.institutionId),
    deadline: deadlineOf(joiningYearOf(e.row)),
    nextSemester: (e.row.year_of_study - 1) * 2 + 1,
  };
}

/* ---- Access ------------------------------------------------------------- */

export function rollFor(institutionId: string): RollEntry[] {
  const cached = ROLLS.get(institutionId);
  if (cached) return cached;
  const idx = SEEDS.findIndex((s) => s.id === institutionId);
  if (idx < 0) return [];
  const built = buildRoll(idx);
  ROLLS.set(institutionId, built);
  for (const e of built) BY_ID.set(e.row.id, e);
  return built;
}

export function entryById(id: string): RollEntry | undefined {
  if (!BY_ID.has(id)) for (const s of SEEDS) rollFor(s.id);
  return BY_ID.get(id);
}

/** Finds a planted student by name (scenario wiring in flags.ts); generated namesakes are skipped. */
export function entryByName(institutionId: string, name: string, year = 1): RollEntry {
  const hit = rollFor(institutionId).find((e) => e.planted && e.row.student.name === name && e.row.year_of_study === year);
  if (!hit) throw new Error(`mock roll: no ${name} at ${institutionId}`);
  return hit;
}

/** Programmes with the ledger run: pool assignments, seated and unseated from the first-year intake. */
export function programmesFor(institutionId: string): ProgrammeDetail[] {
  const roll = rollFor(institutionId);
  return (BASE_PROGRAMMES[institutionId] ?? []).map((p) => {
    const intake = roll.filter((e) => e.programme.id === p.id && e.row.cohort_year === ACADEMIC_YEAR && e.row.status === "ACTIVE");
    const pools = p.pools.map((pool) => {
      const assigned = intake.filter((e) => e.seat?.seat_type === pool.seat_type).length;
      return { ...pool, assigned, free: pool.capacity - assigned };
    });
    const seated = pools.reduce((a, x) => a + x.assigned, 0);
    return { ...p, pools, seated, unseated: intake.filter((e) => !e.seat).length };
  });
}

/** Seats of the 2026-27 approvals with their holders (A.8, Addendum 1.10). */
export function seatsFor(institutionId: string): SeatRow[] {
  const roll = rollFor(institutionId);
  const holders = new Map(roll.filter((e) => e.seat && e.row.cohort_year === ACADEMIC_YEAR).map((e) => [e.seat!.seat_code, e]));
  const rows: SeatRow[] = [];
  for (const p of programmesFor(institutionId)) {
    for (const pool of p.pools) {
      const ciwg = pool.seat_type === "INTERNATIONAL" ? Math.round(pool.capacity / 3) : 0;
      for (let n = 1; n <= pool.capacity; n++) {
        const code = `${p.code}-${SEAT_LETTER[pool.seat_type]}-${pad(n, 3)}`;
        const holder = holders.get(code);
        rows.push({
          id: `${p.id.slice(0, 8)}-${SEAT_LETTER[pool.seat_type]}${pad(n, 3)}-4026-8000-000000000000`,
          seat_code: code,
          academic_year: p.approval.academic_year,
          programme_code: p.code,
          seat_type: pool.seat_type,
          status: holder ? "ASSIGNED" : "FREE",
          reserved_for: n <= ciwg ? "CIWG" : null,
          enrolment_id: holder?.row.id ?? null,
          student_name: holder?.row.student.name ?? null,
          assigned_at: holder?.seat?.assigned_at ?? null,
        });
      }
    }
  }
  return rows;
}

/** GET /enrolments/{id} without flags (the handler adds them with redaction). */
export function enrolmentDetail(e: RollEntry): Omit<EnrolmentDetail, "flags"> {
  const seed = SEEDS.find((s) => s.id === e.institutionId)!;
  const state = STATES.find((s) => s.code === seed.state_code)!;
  const r = e.row;
  return {
    id: r.id,
    institution: {
      id: seed.id,
      name: seed.name,
      aicte_permanent_id: seed.aicte_permanent_id,
      state_code: state.code,
      state_name: state.name,
      region: state.region,
    },
    student: { ...r.student, dob: e.dob, gender: e.gender, mobile_masked: e.mobileMasked },
    programme: {
      id: e.programme.id,
      code: e.programme.code,
      name: e.programme.name,
      level: e.programme.level,
      mode: e.programme.mode,
      duration_years: durationOf(e.programme.level),
    },
    academic_year: r.academic_year,
    cohort_year: r.cohort_year,
    notices: [],
    resend: { allowed: false, blocked_by: "NO_CHANNEL", resends_left: 0 },
    credentials: [],
    year_of_study: r.year_of_study,
    admission_route: r.admission_route,
    counselling_ref: r.counselling_ref,
    category: r.category,
    status: r.status,
    status_date: r.status_date,
    admission_date: r.admission_date,
    uploaded_at: r.uploaded_at,
    upload: e.upload,
    seat: e.seat,
    eligibility: r.eligibility,
    approval: approvalRef(e),
    claim: r.student.consent_status === "REFUSED" || r.student.consent_status === "PENDING" ? { claimed: false, claimed_at: null } : null,
    record_status: r.record_status,
    status_reason: r.status_reason,
    next_step: r.next_step,
    record_status_at: r.record_status_at,
    checks: e.checks,
    versions: versionsOf(e).slice(0, 20),
    history_count: versionsOf(e).length,
  };
}

/** The cohort approval the Seat row was checked against, at its current version (A4.6). */
export function approvalRef(e: RollEntry): ApprovalRef {
  const a = e.programme.approval;
  if (e.row.cohort_year === a.academic_year) {
    return { id: a.id, academic_year: a.academic_year, version: a.version, approved_intake: a.approved_intake, effective_from: a.effective_from, source: a.source };
  }
  const start = e.row.cohort_year.slice(0, 4);
  return {
    id: `${a.id.slice(0, 24)}${start}0000dddd`,
    academic_year: e.row.cohort_year,
    version: 1,
    approved_intake: a.approved_intake,
    effective_from: `${start}-03-15`,
    source: `AICTE EoA ${e.row.cohort_year}`,
  };
}

const VERSIONED: (keyof EnrolmentRow["student"] | keyof EnrolmentRow | "dob" | "tfw_income_certified" | "nri_sponsored" | "ciwg")[] = [
  "name", "dob", "apaar_masked", "consent_status", "year_of_study", "admission_route", "counselling_ref", "category",
  "admission_date", "status", "status_date", "tfw_income_certified", "nri_sponsored", "ciwg",
];

/** The record's versions, newest first (A4.7): the upload that created it, then any later change. */
export function versionsOf(e: RollEntry): EnrolmentVersion[] {
  const r = e.row;
  const value = (field: string): unknown => {
    if (field === "name" || field === "apaar_masked" || field === "consent_status") return r.student[field];
    if (field === "dob") return e.dob;
    if (field === "tfw_income_certified" || field === "nri_sponsored" || field === "ciwg") return r.eligibility[field];
    return (r as unknown as Record<string, unknown>)[field];
  };
  const batch = { id: initialBatchId(e.institutionId), filename: initialFilename(SEEDS.find((s) => s.id === e.institutionId)!.aicte_permanent_id), row_no: e.upload?.row_no ?? r.source_row_no };
  const fromFile = e.institutionId === IDS.abc;
  const registrar = { id: "6f1c0a8e-0004-4c9a-9e51-1c2f1a0b7d33", name: "Registrar, ABC College of Engineering", role: "INSTITUTION" as const };
  const later = LATER_VERSIONS.get(r.id) ?? [];
  // Version 1 holds the values as first uploaded: later changes are rolled back from today's values.
  const first = new Map<string, unknown>(VERSIONED.map((field) => [field, value(field)]));
  for (const v of [...later].reverse()) for (const c of v.changes) first.set(c.field, c.before);
  const created: EnrolmentVersion = {
    version: 1,
    at: INITIAL_UPLOADED_AT,
    source: fromFile ? "UPLOAD" : "SEED",
    actor: fromFile ? registrar : null,
    batch,
    case: null,
    changes: VERSIONED.map((field) => ({ field, before: null, after: first.get(field) })),
  };
  return [...later].reverse().concat(created);
}

/** Changes after the first upload, oldest first; decisions add theirs here too. */
export const LATER_VERSIONS = new Map<string, EnrolmentVersion[]>();

/** A change the college's update file made to a record (A4.7 UPLOAD version). */
function laterVersion(e: RollEntry, at: string, rowNo: number, changes: EnrolmentVersion["changes"]) {
  const seed = SEEDS.find((s) => s.id === e.institutionId)!;
  const list = LATER_VERSIONS.get(e.row.id) ?? [];
  list.push({
    version: list.length + 2,
    at,
    source: "UPLOAD",
    actor: { id: e.institutionId === IDS.abc ? "6f1c0a8e-0004-4c9a-9e51-1c2f1a0b7d33" : `6f1c0a8e-${e.institutionId.slice(-4)}-4c9a-9e51-1c2f1a0b7d33`, name: `Registrar, ${seed.name}`, role: "INSTITUTION" },
    batch: { id: updateBatchId(e.institutionId), filename: updateFilename(seed.aicte_permanent_id), row_no: rowNo },
    case: null,
    changes,
  });
  LATER_VERSIONS.set(e.row.id, list);
}

const RECHECKED: EvidenceRow["state"][] = ["PENDING", "NOT_YET_DUE", "SOURCE_UNAVAILABLE"];

/**
 * POST /enrolments/{id}/recheck (A4.6): re-runs every IDENTITY, SEAT, ADMISSION
 * and STUDYING row that is Pending, Not yet due or Source unavailable; a source
 * that answers now gives its fact. The Student row and decided rows are kept.
 */
export function recheck(e: RollEntry) {
  const before = e.checks;
  if (e.special.identity === "UNAVAILABLE") e.special = { ...e.special, identity: undefined };
  evaluate(e);
  const now = new Date().toISOString().replace(/\.\d+Z$/, "Z");
  const rows = e.checks.map((fresh) => {
    const old = before.find((b) => b.type === fresh.type);
    if (!old || fresh.type === "STUDENT" || !RECHECKED.includes(old.state)) return old ?? fresh;
    return fresh.state === old.state ? { ...old, checked_at: now } : { ...fresh, checked_at: now, observed_at: fresh.observed_at ? now : null };
  });
  setRows(e, rows);
  return before
    .filter((b) => b.type !== "STUDENT" && RECHECKED.includes(b.state))
    .map((b) => ({ type: b.type, before: b.state, after: e.checks.find((c) => c.type === b.type)!.state }));
}

export function studentMe(): StudentMe {
  const ravi = entryById("e0000000-0000-4666-8777-888899990000")!;
  return {
    id: IDS.ravi,
    name: "Ravi Kumar Sharma",
    apaar_masked: "XXXX XXXX 4417",
    consent_status: "LINKED",
    provisional_id: null,
    dob: "2007-03-21",
    email: "ravi.sharma@example.demo",
    mobile_masked: "XXXXXX4521",
    signed_in_with: "DIGILOCKER",
    enrolments: [
      {
        id: ravi.row.id,
        institution_id: IDS.abc,
        institution_name: "ABC College of Engineering",
        programme_code: "CSE",
        programme_name: "B.Tech Computer Science and Engineering",
        academic_year: ACADEMIC_YEAR,
        year_of_study: 1,
        status: "ACTIVE",
        record_status: ravi.row.record_status,
        status_reason: ravi.row.status_reason,
        next_step: ravi.row.next_step,
        checks: ravi.row.checks,
        response: null,
        can_respond: true,
        claimed: false,
        decision: null,
      },
    ],
    notices: [],
    credentials: [],
  };
}
