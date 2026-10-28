/**
 * Contract-exact fixtures for NEXT_PUBLIC_MOCK_API=1.
 * Shapes follow docs/API_CONTRACT.md section A and Addendum 1. Numbers are
 * small and deterministic; the ABC College CSE row carries the "132 against
 * 120" demo scenario with pools 114/6/6/12/18.
 */
import type {
  AdapterPing,
  AdmissionRoute,
  AuditVerify,
  Category,
  ChaosState,
  ConsentStatus,
  EnrolmentRow,
  Health,
  InstitutionDetail,
  InstitutionRow,
  InstitutionType,
  ProgrammeDetail,
  Region,
  RegionMeta,
  SeatPool,
  SeatRow,
  SeatType,
  StateMeta,
  StudentMe,
  User,
} from "@/lib/types";

export const MOCK_PASSWORD = "Countersign!2026";
export const ACADEMIC_YEAR = "2026-27";

export const REGIONS: RegionMeta[] = [
  { code: "CENTRAL", name: "Central", hq_city: "Bhopal" },
  { code: "EAST", name: "Eastern", hq_city: "Kolkata" },
  { code: "NORTH_EAST", name: "North-Eastern", hq_city: "Guwahati" },
  { code: "NORTH_WEST", name: "North-Western", hq_city: "Chandigarh" },
  { code: "NORTH", name: "Northern", hq_city: "Kanpur" },
  { code: "SOUTH_CENTRAL", name: "South-Central", hq_city: "Hyderabad" },
  { code: "SOUTH_WEST", name: "South-Western", hq_city: "Bengaluru" },
  { code: "SOUTH", name: "Southern", hq_city: "Chennai" },
  { code: "WEST_CENTRAL", name: "West-Central", hq_city: "Vadodara" },
  { code: "WEST", name: "Western", hq_city: "Mumbai" },
];

export const STATES: StateMeta[] = [
  { code: "AP", name: "Andhra Pradesh", region: "SOUTH_CENTRAL" },
  { code: "DL", name: "Delhi", region: "NORTH_WEST" },
  { code: "GA", name: "Goa", region: "WEST" },
  { code: "GJ", name: "Gujarat", region: "WEST_CENTRAL" },
  { code: "KA", name: "Karnataka", region: "SOUTH_WEST" },
  { code: "MH", name: "Maharashtra", region: "WEST" },
  { code: "MP", name: "Madhya Pradesh", region: "CENTRAL" },
  { code: "TN", name: "Tamil Nadu", region: "SOUTH" },
  { code: "TS", name: "Telangana", region: "SOUTH_CENTRAL" },
  { code: "UP", name: "Uttar Pradesh", region: "NORTH" },
  { code: "WB", name: "West Bengal", region: "EAST" },
];

export function regionName(code: Region): string {
  const r = REGIONS.find((x) => x.code === code);
  return r ? `${r.name} (${r.hq_city})` : code;
}

const IDS = {
  abc: "a0b1c2d3-1111-4222-8333-444455556666",
  xyz: "b1c2d3e4-2222-4333-8444-555566667777",
  mstu: "c3d4e5f6-2222-4333-8444-555566667777",
  annauniv: "d4e5f6a7-3333-4444-8555-666677778888",
  ravi: "e5f6a7b8-4444-4555-8666-777788889999",
};

export const USERS: User[] = [
  {
    id: "6f1c0a8e-0001-4c9a-9e51-1c2f1a0b7d33",
    email: "admin@aicte.demo",
    name: "AICTE Administrator",
    role: "AICTE_ADMIN",
    scope: { institution_id: null, institution_name: null, region: null, student_id: null, university_id: null },
  },
  {
    id: "6f1c0a8e-0002-4c9a-9e51-1c2f1a0b7d33",
    email: "ro.west@aicte.demo",
    name: "Regional Officer, Western Region",
    role: "RO_OFFICER",
    scope: { institution_id: null, institution_name: null, region: "WEST", student_id: null, university_id: null },
  },
  {
    id: "6f1c0a8e-0003-4c9a-9e51-1c2f1a0b7d33",
    email: "ro.south@aicte.demo",
    name: "Regional Officer, Southern Region",
    role: "RO_OFFICER",
    scope: { institution_id: null, institution_name: null, region: "SOUTH", student_id: null, university_id: null },
  },
  {
    id: "6f1c0a8e-0004-4c9a-9e51-1c2f1a0b7d33",
    email: "registrar@abc.edu.demo",
    name: "Registrar, ABC College of Engineering",
    role: "INSTITUTION",
    scope: {
      institution_id: IDS.abc,
      institution_name: "ABC College of Engineering",
      region: "WEST",
      student_id: null,
      university_id: null,
    },
  },
  {
    id: "6f1c0a8e-0005-4c9a-9e51-1c2f1a0b7d33",
    email: "registrar@xyz.edu.demo",
    name: "Registrar, XYZ Institute of Technology",
    role: "INSTITUTION",
    scope: {
      institution_id: IDS.xyz,
      institution_name: "XYZ Institute of Technology",
      region: "SOUTH",
      student_id: null,
      university_id: null,
    },
  },
  {
    id: "6f1c0a8e-0006-4c9a-9e51-1c2f1a0b7d33",
    email: "student@demo",
    name: "Ravi Kumar Sharma",
    role: "STUDENT",
    scope: { institution_id: null, institution_name: null, region: null, student_id: IDS.ravi, university_id: null },
  },
  {
    id: "6f1c0a8e-0007-4c9a-9e51-1c2f1a0b7d33",
    email: "coe@univ.demo",
    name: "Controller of Examinations, Maharashtra State Technical University",
    role: "UNIVERSITY",
    scope: {
      institution_id: null,
      institution_name: null,
      region: null,
      student_id: null,
      university_id: IDS.mstu,
      university_name: "Maharashtra State Technical University",
    },
  },
];

/* ---- Seat pools from rules.yaml (APH 2024-27) ---------------------------- */

const RULE = {
  REGULAR: "Approval record (approved_intake); minus NRI carve-out (APH 2024-27 cl. 2.8(b))",
  NRI: "APH 2024-27 cl. 2.8(b)",
  TFW: "APH 2024-27 cl. 6.42(d)(i), (d)(iii)",
  LATERAL: "APH 2024-27 cl. 6.13(a), 6.13(f)",
  INTERNATIONAL: "APH 2024-27 cl. 2.9; APH 2026-27 addendum keeps 15% for Engg Diploma/UG",
} satisfies Record<SeatType, string>;

function pools(intake: number): SeatPool[] {
  const nri = Math.round(intake * 0.05);
  const make = (seat_type: SeatType, capacity: number, is_supernumerary: boolean, reserved_for: string | null): SeatPool => ({
    seat_type,
    capacity,
    is_supernumerary,
    assigned: 0,
    free: capacity,
    reserved_for,
    rule_source: RULE[seat_type],
  });
  return [
    make("REGULAR", intake - nri, false, null),
    make("NRI", nri, false, null),
    make("TFW", Math.round(intake * 0.05), true, null),
    make("LATERAL", Math.round(intake * 0.1), true, null),
    make("INTERNATIONAL", Math.round(intake * 0.15), true, "FN_OCI_PIO_CIWG"),
  ];
}

function programme(id: string, code: string, name: string, intake: number, enrolments: number, shift: "FIRST" | "SECOND" = "FIRST"): ProgrammeDetail {
  return {
    id,
    code,
    name,
    level: "UG",
    discipline: "ENGINEERING",
    shift,
    approval: { academic_year: ACADEMIC_YEAR, approved_intake: intake, cutoff_date: "2026-09-15" },
    enrolments,
    pools: pools(intake),
    // Week 1: the seed leaves every enrolment unseated.
    unseated: enrolments,
  };
}

export const ABC_PROGRAMMES: ProgrammeDetail[] = [
  programme("p0000001-0001-4444-8555-666677778888", "CIVIL", "B.Tech Civil Engineering", 60, 38),
  programme("p0000001-0002-4444-8555-666677778888", "CSE", "B.Tech Computer Science and Engineering", 120, 132),
  programme("p0000001-0003-4444-8555-666677778888", "ECE", "B.Tech Electronics and Communication Engineering", 120, 108),
  programme("p0000001-0004-4444-8555-666677778888", "EEE", "B.Tech Electrical and Electronics Engineering", 60, 51),
  programme("p0000001-0005-4444-8555-666677778888", "IT", "B.Tech Information Technology", 60, 64),
  programme("p0000001-0006-4444-8555-666677778888", "MECH", "B.Tech Mechanical Engineering", 120, 92),
];

export const XYZ_PROGRAMMES: ProgrammeDetail[] = [
  programme("p0000002-0001-4444-8555-666677778888", "CSE", "B.Tech Computer Science and Engineering", 180, 171),
  programme("p0000002-0002-4444-8555-666677778888", "ECE", "B.Tech Electronics and Communication Engineering", 120, 97),
  programme("p0000002-0003-4444-8555-666677778888", "MECH", "B.Tech Mechanical Engineering", 60, 41),
  programme("p0000002-0004-4444-8555-666677778888", "AIDS", "B.Tech Artificial Intelligence and Data Science", 60, 60, "SECOND"),
];

function sum(list: ProgrammeDetail[], pick: (p: ProgrammeDetail) => number): number {
  return list.reduce((acc, p) => acc + pick(p), 0);
}

interface InstitutionSeed {
  id: string;
  aicte_permanent_id: string;
  name: string;
  type: InstitutionType;
  state_code: string;
  university_id: string | null;
  university_name: string | null;
  address_city: string;
  established_year: number;
  programmes: ProgrammeDetail[] | { count: number; approved: number; enrolments: number };
}

const SEEDS: InstitutionSeed[] = [
  {
    id: IDS.abc,
    aicte_permanent_id: "1-ABC-0001",
    name: "ABC College of Engineering",
    type: "PRIVATE_SELF_FINANCED",
    state_code: "MH",
    university_id: IDS.mstu,
    university_name: "Maharashtra State Technical University",
    address_city: "Pune",
    established_year: 2004,
    programmes: ABC_PROGRAMMES,
  },
  {
    id: IDS.xyz,
    aicte_permanent_id: "1-XYZ-0002",
    name: "XYZ Institute of Technology",
    type: "PRIVATE_SELF_FINANCED",
    state_code: "TN",
    university_id: IDS.annauniv,
    university_name: "Tamil Nadu Technical University",
    address_city: "Coimbatore",
    established_year: 1998,
    programmes: XYZ_PROGRAMMES,
  },
  {
    id: "10000000-0003-4000-8000-000000000003",
    aicte_permanent_id: "1-8437201389",
    name: "Gayatri Vidya Technological Institute, Vijayawada",
    type: "PRIVATE_SELF_FINANCED",
    state_code: "AP",
    university_id: null,
    university_name: "Andhra Technical University",
    address_city: "Vijayawada",
    established_year: 2001,
    programmes: { count: 6, approved: 600, enrolments: 571 },
  },
  {
    id: "10000000-0004-4000-8000-000000000004",
    aicte_permanent_id: "1-2209318840",
    name: "Government College of Engineering, Karad",
    type: "GOVERNMENT",
    state_code: "MH",
    university_id: IDS.mstu,
    university_name: "Maharashtra State Technical University",
    address_city: "Karad",
    established_year: 1960,
    programmes: { count: 5, approved: 420, enrolments: 402 },
  },
  {
    id: "10000000-0005-4000-8000-000000000005",
    aicte_permanent_id: "1-5521093317",
    name: "Sardar Patel Institute of Management, Ahmedabad",
    type: "GOVERNMENT_AIDED",
    state_code: "GJ",
    university_id: null,
    university_name: "Gujarat Technological University",
    address_city: "Ahmedabad",
    established_year: 1986,
    programmes: { count: 3, approved: 300, enrolments: 248 },
  },
  {
    id: "10000000-0006-4000-8000-000000000006",
    aicte_permanent_id: "1-7710245519",
    name: "Kaveri School of Pharmacy, Mysuru",
    type: "PRIVATE_SELF_FINANCED",
    state_code: "KA",
    university_id: null,
    university_name: "Karnataka Health and Technical University",
    address_city: "Mysuru",
    established_year: 2009,
    programmes: { count: 2, approved: 120, enrolments: 97 },
  },
  {
    id: "10000000-0007-4000-8000-000000000007",
    aicte_permanent_id: "1-3390218806",
    name: "Department of Computer Applications, Lucknow",
    type: "UNIVERSITY_DEPARTMENT",
    state_code: "UP",
    university_id: null,
    university_name: "Awadh University",
    address_city: "Lucknow",
    established_year: 1992,
    programmes: { count: 2, approved: 180, enrolments: 163 },
  },
  {
    id: "10000000-0008-4000-8000-000000000008",
    aicte_permanent_id: "1-0699740684",
    name: "Shaheed Bhagat Singh Institute of Science and Technology, Durgapur",
    type: "PRIVATE_SELF_FINANCED",
    state_code: "WB",
    university_id: null,
    university_name: "Durgapur University of Technology",
    address_city: "Durgapur",
    established_year: 2007,
    programmes: { count: 2, approved: 120, enrolments: 45 },
  },
  {
    id: "10000000-0009-4000-8000-000000000009",
    aicte_permanent_id: "1-4418830271",
    name: "Deccan Institute of Architecture, Hyderabad",
    type: "DEEMED",
    state_code: "TS",
    university_id: null,
    university_name: "Deccan Deemed University",
    address_city: "Hyderabad",
    established_year: 1994,
    programmes: { count: 3, approved: 240, enrolments: 236 },
  },
  {
    id: "10000000-0010-4000-8000-000000000010",
    aicte_permanent_id: "1-9001127734",
    name: "Pune Institute of Technology and Management",
    type: "PRIVATE_SELF_FINANCED",
    state_code: "MH",
    university_id: IDS.mstu,
    university_name: "Maharashtra State Technical University",
    address_city: "Pune",
    established_year: 2011,
    programmes: { count: 4, approved: 360, enrolments: 287 },
  },
];

function stateOf(code: string): StateMeta {
  return STATES.find((s) => s.code === code) ?? { code, name: code, region: "WEST" };
}

export const INSTITUTIONS: InstitutionRow[] = SEEDS.map((s) => {
  const st = stateOf(s.state_code);
  const progs = s.programmes;
  const detailed = Array.isArray(progs);
  return {
    id: s.id,
    aicte_permanent_id: s.aicte_permanent_id,
    name: s.name,
    type: s.type,
    state_code: st.code,
    state_name: st.name,
    region: st.region,
    region_name: regionName(st.region),
    university_id: s.university_id,
    university_name: s.university_name,
    programmes: detailed ? progs.length : progs.count,
    approved_seats: detailed ? sum(progs, (p) => p.approval.approved_intake) : progs.approved,
    enrolments: detailed ? sum(progs, (p) => p.enrolments) : progs.enrolments,
    flags_open: 0,
    integrity_index: null,
  };
});

export function institutionDetail(id: string): InstitutionDetail | null {
  const seed = SEEDS.find((s) => s.id === id);
  const row = INSTITUTIONS.find((r) => r.id === id);
  if (!seed || !row) return null;
  const programmes = Array.isArray(seed.programmes)
    ? seed.programmes
    : Array.from({ length: seed.programmes.count }, (_, i) => {
        const p = seed.programmes as { count: number; approved: number; enrolments: number };
        const intake = Math.round(p.approved / p.count);
        const codes = ["CSE", "ECE", "MECH", "CIVIL", "IT", "EEE"];
        return programme(`${id.slice(0, 8)}-p00${i}-4444-8555-666677778888`, codes[i % codes.length], `B.Tech programme ${codes[i % codes.length]}`, intake, Math.round(p.enrolments / p.count));
      });
  return {
    id: row.id,
    aicte_permanent_id: row.aicte_permanent_id,
    name: row.name,
    type: row.type,
    state_code: row.state_code,
    state_name: row.state_name,
    region: row.region,
    region_name: row.region_name,
    university_id: row.university_id,
    university_name: row.university_name,
    address_city: seed.address_city,
    established_year: seed.established_year,
    integrity_index: null,
    integrity_components: null,
    flags_open: 0,
    last_upload: null,
    programmes,
  };
}

/* ---- Enrolments (ABC College) ------------------------------------------- */

const FIRST = ["Aarav", "Aisha", "Ananya", "Arjun", "Bhavna", "Deepak", "Divya", "Farhan", "Gauri", "Harsh", "Ishita", "Kabir", "Kavya", "Manish", "Meera", "Nikhil", "Pooja", "Pranav", "Riya", "Rohan", "Sana", "Sneha", "Tanvi", "Varun", "Yash"];
const LAST = ["Agarwal", "Bhosale", "Chavan", "Deshmukh", "Gaikwad", "Iyer", "Joshi", "Kulkarni", "Mehta", "Nair", "Patil", "Pawar", "Rao", "Shaikh", "Shinde"];
const ROUTES: AdmissionRoute[] = ["COUNSELLING", "COUNSELLING", "COUNSELLING", "COUNSELLING", "MANAGEMENT", "MANAGEMENT", "NRI", "TFW", "LATERAL", "SPOT"];
const CATEGORIES: Category[] = ["GENERAL", "GENERAL", "OBC", "OBC", "EWS", "SC", "ST", "GENERAL"];

function hex8(n: number): string {
  return ((n * 2654435761) >>> 0).toString(16).toUpperCase().padStart(8, "0").slice(0, 8);
}

function makeEnrolments(): EnrolmentRow[] {
  const rows: EnrolmentRow[] = [];
  const cse = ABC_PROGRAMMES[1];
  rows.push({
    id: "e0000000-0000-4666-8777-888899990000",
    student: { id: IDS.ravi, name: "Ravi Kumar Sharma", apaar_masked: "XXXX XXXX 4417", consent_status: "LINKED", provisional_id: null, nationality: "IN" },
    programme_id: cse.id,
    programme_code: cse.code,
    academic_year: ACADEMIC_YEAR,
    year_of_study: 1,
    admission_route: "COUNSELLING",
    counselling_ref: "MHCET-2026-R1-004512",
    category: "GENERAL",
    seat_code: null,
    status: "ACTIVE",
    uploaded_at: "2026-07-14T09:30:00Z",
    upload_batch_id: null,
    source_row_no: 1,
    countersign: { score: null, checks: [] },
    flags: [],
  });
  for (let i = 1; i < 64; i++) {
    const prog = ABC_PROGRAMMES[i % ABC_PROGRAMMES.length];
    let consent: ConsentStatus = "LINKED";
    if (i % 11 === 0) consent = "REFUSED";
    else if (i % 13 === 0) consent = "PENDING";
    else if (i % 17 === 0) consent = "INTERNATIONAL";
    const route: AdmissionRoute = consent === "INTERNATIONAL" ? "INTERNATIONAL" : ROUTES[i % ROUTES.length];
    const last4 = String((i * 7919) % 10000).padStart(4, "0");
    const year = route === "LATERAL" ? 2 : (i % 4) + 1;
    rows.push({
      id: `e${String(i).padStart(7, "0")}-0000-4666-8777-888899990000`,
      student: {
        id: `s${String(i).padStart(7, "0")}-0000-4666-8777-888899990000`,
        name: consent === "INTERNATIONAL" ? "Aisha Rahman" : `${FIRST[i % FIRST.length]} ${LAST[(i * 3) % LAST.length]}`,
        apaar_masked: consent === "LINKED" ? `XXXX XXXX ${last4}` : null,
        consent_status: consent,
        provisional_id: consent === "LINKED" ? null : `PRV-${hex8(i)}`,
        nationality: consent === "INTERNATIONAL" ? "BD" : "IN",
      },
      programme_id: prog.id,
      programme_code: prog.code,
      academic_year: ACADEMIC_YEAR,
      year_of_study: year,
      admission_route: route,
      counselling_ref: route === "COUNSELLING" ? `MHCET-${2027 - year}-R1-${String(i * 37).padStart(6, "0")}` : null,
      category: CATEGORIES[i % CATEGORIES.length],
      seat_code: null,
      status: "ACTIVE",
      uploaded_at: "2026-07-14T09:30:00Z",
      upload_batch_id: null,
      source_row_no: i + 1,
      countersign: { score: null, checks: [] },
      flags: [],
    });
  }
  return rows.sort((a, b) => a.student.name.localeCompare(b.student.name));
}

export const ENROLMENTS: EnrolmentRow[] = makeEnrolments();

/* ---- Seats: every seat free in Week 1 ------------------------------------ */

const LETTER: Record<SeatType, string> = { REGULAR: "R", NRI: "N", TFW: "T", LATERAL: "L", INTERNATIONAL: "I" };

export function seatsFor(detail: InstitutionDetail): SeatRow[] {
  const rows: SeatRow[] = [];
  for (const p of detail.programmes) {
    for (const pool of p.pools) {
      const ciwg = pool.seat_type === "INTERNATIONAL" ? Math.round(pool.capacity / 3) : 0;
      for (let n = 1; n <= pool.capacity; n++) {
        rows.push({
          id: `${p.id.slice(0, 8)}-${LETTER[pool.seat_type]}${String(n).padStart(3, "0")}-4000-8000-000000000000`,
          seat_code: `${p.code}-${LETTER[pool.seat_type]}-${String(n).padStart(3, "0")}`,
          academic_year: p.approval.academic_year,
          programme_code: p.code,
          seat_type: pool.seat_type,
          status: "FREE",
          reserved_for: n <= ciwg ? "CIWG" : null,
          enrolment_id: null,
          student_name: null,
          assigned_at: null,
        });
      }
    }
  }
  return rows;
}

/* ---- Student, sources, audit, health ------------------------------------- */

export const STUDENT_ME: StudentMe = {
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
      id: "e0000000-0000-4666-8777-888899990000",
      institution_id: IDS.abc,
      institution_name: "ABC College of Engineering",
      programme_code: "CSE",
      programme_name: "B.Tech Computer Science and Engineering",
      academic_year: ACADEMIC_YEAR,
      year_of_study: 1,
      status: "ACTIVE",
      countersign: { score: null, checks: [] },
    },
  ],
  notices: [],
  credentials: [],
};

export function adapterPing(chaos: ChaosState): AdapterPing {
  const base = { apaar: 12, counselling: 9, abc: 14, digilocker: 8, sii: 11 };
  const sources = Object.fromEntries(
    (Object.keys(base) as (keyof typeof base)[]).map((k) => {
      const c = chaos[k];
      if (c.down) return [k, { status: "UNAVAILABLE", latency_ms: 3004, detail: "timeout after 3000 ms" }];
      return [k, { status: "OK", latency_ms: base[k] + c.latency_ms, detail: null }];
    }),
  ) as AdapterPing["sources"];
  return { adapter: "mockgov", sources, checked_at: new Date().toISOString().replace(/\.\d+Z$/, "Z") };
}

export function auditVerify(): AuditVerify {
  return { ok: true, length: 1842, first_broken_seq: null, checked_at: new Date().toISOString().replace(/\.\d+Z$/, "Z") };
}

export const HEALTH: Health = { status: "ok", db: "ok", redis: "ok", version: "0.1.0" };

export function zeroChaos(): ChaosState {
  const zero = { latency_ms: 0, fail_rate: 0, down: false };
  return { apaar: { ...zero }, counselling: { ...zero }, abc: { ...zero }, digilocker: { ...zero }, sii: { ...zero } };
}
