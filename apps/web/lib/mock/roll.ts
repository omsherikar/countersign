/**
 * The mock roll: every enrolment of an institution for 2026-27, built
 * deterministically from its programmes, with the seat ledger run over the
 * first-year intake and the five checks evaluated with the exact sentences
 * of API_CONTRACT A2.14. Rolls are built on first use and kept for the
 * session, so a recheck changes what later requests see.
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
 */
import { ACADEMIC_YEAR, BASE_PROGRAMMES, IDS, SEAT_LETTER, SEEDS, STATES, durationOf, earlierYears, lateralEntrants, poolCapacities } from "@/lib/mock/fixtures";
import type {
  AdmissionRoute,
  Category,
  Check,
  CheckBrief,
  CheckStatus,
  CheckType,
  ConsentStatus,
  Countersign,
  EnrolmentDetail,
  EnrolmentRow,
  ProgrammeDetail,
  SeatRow,
  SeatType,
  StudentMe,
} from "@/lib/types";

export const CHECK_ORDER: CheckType[] = ["IDENTITY", "ADMISSION", "SEAT", "STUDYING", "STUDENT"];

export interface Special {
  identity?: "UNAVAILABLE" | "REVIEW" | "NOT_IN_REGISTRY" | "NAME";
  attempts?: number;
  studying?: "NONE" | "ONE_MISSING";
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
  /** The flag the SEAT and ADMISSION sentences point at when unseated. */
  seatFlagName: string;
  checks: Check[];
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
          countersign: { score: null, checks: [] },
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
    }
  }
}

/* ---- Checks (A2.14 sentences) ------------------------------------------- */

function check(type: CheckType, status: CheckStatus, source: Check["source"], summary: string, extra: Record<string, unknown> = {}, attempts = 0, at = CHECKED_AT): Check {
  return { type, status, source, checked_at: at, attempts, detail: { summary, ...extra } };
}

export function evaluate(e: RollEntry) {
  const r = e.row;
  const seed = SEEDS.find((s) => s.id === e.institutionId)!;
  const stateName = STATES.find((s) => s.code === seed.state_code)?.name ?? seed.state_code;
  const start = Number(r.cohort_year.slice(0, 4));
  const code = r.programme_code;
  const seatWord = SEAT_TYPE_WORD[e.seatType];
  const routeWord = ROUTE_WORD[r.admission_route];
  const linked = r.student.consent_status === "LINKED";
  const international = r.student.consent_status === "INTERNATIONAL";
  const checks: Check[] = [];

  // IDENTITY (APAAR)
  const sp = e.special;
  if (international) checks.push(check("IDENTITY", "NOT_APPLICABLE", "APAAR", "International student; identity is checked through the passport, not APAAR."));
  else if (!linked) checks.push(check("IDENTITY", "NOT_APPLICABLE", "APAAR", "APAAR not linked; admission is not blocked."));
  else if (sp.identity === "UNAVAILABLE")
    checks.push(check("IDENTITY", "SOURCE_UNAVAILABLE", "APAAR", "APAAR registry did not respond. This check stays pending until a recheck or the next upload.", { source_unavailable: true, source_error: "HTTP 503" }, sp.attempts ?? 1, "2026-10-28T09:12:44Z"));
  else if (sp.identity === "REVIEW")
    checks.push(
      check("IDENTITY", "PENDING", "APAAR", `Name on upload is close to the APAAR registry but not a clear match (similarity ${e.nameScore} of 100); an officer should review.`, {
        needs_review: true,
        name_score: e.nameScore,
        dob_match: true,
        apaar_last4: e.apaarLast4,
      }),
    );
  else if (sp.identity === "NOT_IN_REGISTRY")
    checks.push(check("IDENTITY", "CONTRADICTED", "APAAR", `APAAR ending ${e.apaarLast4} is not in the APAAR registry.`, { apaar_last4: e.apaarLast4 }));
  else if (sp.identity === "NAME")
    checks.push(
      check("IDENTITY", "CONTRADICTED", "APAAR", `Name on upload differs from the APAAR registry (similarity ${e.nameScore} of 100).`, {
        name_score: e.nameScore,
        dob_match: true,
        apaar_last4: e.apaarLast4,
      }),
    );
  else
    checks.push(
      check("IDENTITY", "CONFIRMED", "APAAR", `Name and date of birth match the APAAR registry (similarity ${e.nameScore} of 100).`, {
        name_score: e.nameScore,
        dob_match: true,
        apaar_last4: e.apaarLast4,
      }),
    );

  // ADMISSION
  if (r.admission_route === "COUNSELLING" || r.admission_route === "LATERAL")
    checks.push(
      check("ADMISSION", "CONFIRMED", "COUNSELLING", `Found in the ${stateName} counselling allotments for ${code} (${start}), round ${e.round}.`, {
        round: e.round,
        allotment_ref: r.counselling_ref,
        ref_mismatch: false,
      }),
    );
  else if (r.admission_route === "INTERNATIONAL")
    checks.push(check("ADMISSION", "CONFIRMED", "SII", `Study in India confirms this admission to ${code} (${r.cohort_year}).`));
  else if (e.seat)
    checks.push(check("ADMISSION", "CONFIRMED", "SEAT_LEDGER", `${routeWord} admission is allowed for ${code} and holds a ${seatWord} seat.`, { seat_type: e.seatType }));
  else
    checks.push(check("ADMISSION", "CONTRADICTED", "SEAT_LEDGER", `${routeWord} admission has no ${seatWord} seat in ${code} (${r.cohort_year}).`, { seat_type: e.seatType }));

  // SEAT
  if (e.seat)
    checks.push(
      check("SEAT", "CONFIRMED", "SEAT_LEDGER", `Holds seat ${e.seat.seat_code} (${SEAT_TYPE_WORD[e.seat.seat_type]}, ${e.seat.academic_year} approval).`, {
        seat_code: e.seat.seat_code,
        seat_type: e.seat.seat_type,
      }),
    );
  else
    checks.push(
      check("SEAT", "CONTRADICTED", "SEAT_LEDGER", `No ${seatWord} seat is free in ${code} (${r.cohort_year}); see the ${e.seatFlagName} flag.`, {
        flag_type: e.seatFlagName === "Quota breach" ? "QUOTA_BREACH" : "EXCESS_ADMISSION",
      }),
    );

  // STUDYING (ABC)
  const expected = (r.year_of_study - 1) * 2;
  if (r.year_of_study === 1) checks.push(check("STUDYING", "NOT_YET_DUE", "ABC", "First year, no result yet."));
  else if (!linked) checks.push(check("STUDYING", "NOT_APPLICABLE", "ABC", "APAAR not linked; ABC credits cannot be checked."));
  else if (sp.studying === "NONE")
    checks.push(
      check("STUDYING", "CONTRADICTED", "ABC", `No credits recorded in ABC for ${expected} of ${expected} semesters since admission.`, {
        expected,
        missing: expected,
        semesters: [
          { academic_year: "2025-26", sem: 1, credits: 0 },
          { academic_year: "2025-26", sem: 2, credits: 0 },
        ],
      }),
    );
  else if (sp.studying === "ONE_MISSING")
    checks.push(
      check("STUDYING", "PENDING", "ABC", `No credits recorded in ABC for semester ${expected} (2025-26); waiting for the next upload.`, {
        expected,
        missing: 1,
        awaiting_semester: expected,
      }),
    );
  else checks.push(check("STUDYING", "CONFIRMED", "ABC", `Credits recorded in ABC for all ${expected} semesters since admission.`, { expected, missing: 0 }));

  // STUDENT
  checks.push(check("STUDENT", "PENDING", "STUDENT_NOTICE", "Notice not sent yet."));

  e.checks = checks;
  r.countersign = compact(checks);
}

export function compact(checks: Check[]): Countersign {
  if (checks.length === 0) return { score: null, checks: [] };
  const brief: CheckBrief[] = CHECK_ORDER.map((t) => {
    const c = checks.find((x) => x.type === t)!;
    return { type: t, status: c.status };
  });
  const applicable = brief.filter((c) => c.status !== "NOT_APPLICABLE" && c.status !== "NOT_YET_DUE").length;
  const passes = brief.filter((c) => c.status === "CONFIRMED").length;
  return { score: { passes, applicable }, checks: brief };
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
    countersign: r.countersign,
    checks: e.checks,
  };
}

/** POST /enrolments/{id}/recheck: re-runs PENDING and SOURCE_UNAVAILABLE checks except STUDENT; a source that answers now passes. */
export function recheck(e: RollEntry) {
  const before = e.checks.map((c) => ({ type: c.type, status: c.status }));
  if (e.special.identity === "UNAVAILABLE") e.special = { ...e.special, identity: undefined };
  evaluate(e);
  const now = new Date().toISOString().replace(/\.\d+Z$/, "Z");
  const results = before
    .filter((b) => (b.status === "PENDING" || b.status === "SOURCE_UNAVAILABLE") && b.type !== "STUDENT")
    .map((b) => {
      const after = e.checks.find((c) => c.type === b.type)!;
      after.checked_at = now;
      return { type: b.type, before: b.status, after: after.status };
    });
  return results;
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
        countersign: ravi.row.countersign,
      },
    ],
    notices: [],
    credentials: [],
  };
}
