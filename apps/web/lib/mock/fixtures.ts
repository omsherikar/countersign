/**
 * Contract-exact fixtures for NEXT_PUBLIC_MOCK_API=1: regions, users and the
 * institutions with their programmes. Shapes follow docs/API_CONTRACT.md
 * sections A, Addendum 1 and Addendum 2. Numbers are deterministic; ABC
 * College CSE carries the "132 admitted against 120 approved" scenario.
 * The roll of students, the checks and the seat ledger are in roll.ts,
 * flags in flags.ts and upload batches in uploads.ts.
 */
import type {
  AdapterPing,
  AuditVerify,
  ChaosState,
  Discipline,
  Health,
  InstitutionDetail,
  InstitutionRow,
  InstitutionType,
  Level,
  ProgrammeDetail,
  ProgrammeMode,
  Region,
  RegionMeta,
  SeatPool,
  SeatType,
  StateMeta,
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

export const IDS = {
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

export const RULE = {
  REGULAR: "Approval record (approved_intake); minus NRI carve-out (APH 2024-27 cl. 2.8(b))",
  NRI: "APH 2024-27 cl. 2.8(b)",
  TFW: "APH 2024-27 cl. 6.42(d)(i), (d)(iii)",
  LATERAL: "APH 2024-27 cl. 6.13(a), 6.13(f)",
  INTERNATIONAL: "APH 2024-27 cl. 2.9; APH 2026-27 addendum keeps 15% for Engg Diploma/UG",
} satisfies Record<SeatType, string>;

/** Pool sizes for one approval; `assigned` and `free` are filled from the roll by lib/mock/roll.ts. */
export function poolCapacities(intake: number): Record<SeatType, number> {
  const nri = Math.round(intake * 0.05);
  return {
    REGULAR: intake - nri,
    NRI: nri,
    TFW: Math.round(intake * 0.05),
    LATERAL: Math.round(intake * 0.1),
    INTERNATIONAL: Math.round(intake * 0.15),
  };
}

function pools(intake: number): SeatPool[] {
  const cap = poolCapacities(intake);
  const make = (seat_type: SeatType, is_supernumerary: boolean, reserved_for: string | null): SeatPool => ({
    seat_type,
    capacity: cap[seat_type],
    is_supernumerary,
    assigned: 0,
    free: cap[seat_type],
    reserved_for,
    rule_source: RULE[seat_type],
  });
  return [
    make("REGULAR", false, null),
    make("NRI", false, null),
    make("TFW", true, null),
    make("LATERAL", true, null),
    make("INTERNATIONAL", true, "FN_OCI_PIO_CIWG"),
  ];
}

/** Years of study a programme runs for. */
export function durationOf(level: Level): number {
  return level === "PG" ? 2 : level === "DIPLOMA" ? 3 : 4;
}

/**
 * Students on roll in the earlier years of study, per programme. Year 1 is
 * the programme's intake enrolments; later years shrink a little and year 2
 * also carries lateral entrants (counted in the 2025-26 cohort, A2.18).
 */
export function earlierYears(intake: number, duration: number): { year: number; count: number }[] {
  const keep = [0, 0.93, 0.9, 0.86, 0.84];
  const out: { year: number; count: number }[] = [];
  for (let y = 2; y <= duration; y++) out.push({ year: y, count: Math.round(intake * keep[y]) });
  return out;
}
export function lateralEntrants(intake: number, level: Level): number {
  return level === "UG" ? Math.round(intake * 0.08) : 0;
}
export function onRollOf(p: ProgrammeDetail): number {
  const intake = p.approval.approved_intake;
  return p.enrolments + earlierYears(intake, durationOf(p.level)).reduce((a, y) => a + y.count, 0) + lateralEntrants(intake, p.level);
}

interface ProgrammeSpec {
  code: string;
  name: string;
  intake: number;
  /** First-year (2026-27 intake) enrolments: the programme's `enrolments` and its share of `admitted`. */
  firstYear: number;
  level?: Level;
  discipline?: Discipline;
  mode?: ProgrammeMode;
  shift?: "FIRST" | "SECOND";
}

function programme(institutionId: string, i: number, spec: ProgrammeSpec): ProgrammeDetail {
  return {
    id: `${institutionId.slice(0, 8)}-${String(i + 1).padStart(4, "0")}-4444-8555-666677778888`,
    code: spec.code,
    name: spec.name,
    level: spec.level ?? "UG",
    discipline: spec.discipline ?? "ENGINEERING",
    shift: spec.shift ?? "FIRST",
    mode: spec.mode ?? "PHYSICAL",
    approval: { academic_year: ACADEMIC_YEAR, approved_intake: spec.intake, cutoff_date: "2026-09-15" },
    enrolments: spec.firstYear,
    seated: 0,
    unseated: 0,
    pools: pools(spec.intake),
  };
}

const BTECH = (code: string, name: string, intake: number, firstYear: number, shift: "FIRST" | "SECOND" = "FIRST"): ProgrammeSpec => ({
  code,
  name: `B.Tech ${name}`,
  intake,
  firstYear,
  shift,
});

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
  programmes: ProgrammeSpec[];
}

export const SEEDS: InstitutionSeed[] = [
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
    // CSE first: the upload file lists it first, so Ravi Kumar Sharma is row 2 and R. K. Sharma row 133.
    programmes: [
      BTECH("CSE", "Computer Science and Engineering", 120, 132),
      BTECH("CIVIL", "Civil Engineering", 60, 38),
      BTECH("ECE", "Electronics and Communication Engineering", 120, 108),
      BTECH("EEE", "Electrical and Electronics Engineering", 60, 51),
      BTECH("IT", "Information Technology", 60, 58),
      BTECH("MECH", "Mechanical Engineering", 120, 92),
    ],
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
    programmes: [
      BTECH("CSE", "Computer Science and Engineering", 180, 171),
      BTECH("ECE", "Electronics and Communication Engineering", 120, 97),
      BTECH("MECH", "Mechanical Engineering", 60, 41),
      BTECH("AIDS", "Artificial Intelligence and Data Science", 60, 60, "SECOND"),
    ],
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
    programmes: [
      BTECH("CSE", "Computer Science and Engineering", 180, 176),
      BTECH("ECE", "Electronics and Communication Engineering", 120, 112),
      BTECH("EEE", "Electrical and Electronics Engineering", 60, 49),
      BTECH("MECH", "Mechanical Engineering", 120, 97),
      BTECH("CIVIL", "Civil Engineering", 60, 44),
      BTECH("IT", "Information Technology", 60, 58),
    ],
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
    programmes: [
      BTECH("CIVIL", "Civil Engineering", 60, 60),
      BTECH("CSE", "Computer Science and Engineering", 120, 120),
      BTECH("ECE", "Electronics and Communication Engineering", 60, 58),
      BTECH("EEE", "Electrical and Electronics Engineering", 60, 57),
      BTECH("MECH", "Mechanical Engineering", 120, 114),
    ],
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
    programmes: [
      { code: "MBA", name: "Master of Business Administration", intake: 180, firstYear: 164, level: "PG", discipline: "MANAGEMENT" },
      { code: "PGDM", name: "Post Graduate Diploma in Management", intake: 60, firstYear: 48, level: "PG", discipline: "MANAGEMENT" },
      { code: "MBAX", name: "Master of Business Administration (Executive)", intake: 60, firstYear: 36, level: "PG", discipline: "MANAGEMENT", shift: "SECOND" },
    ],
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
    programmes: [
      { code: "BPHARM", name: "Bachelor of Pharmacy", intake: 100, firstYear: 84, discipline: "PHARMACY" },
      { code: "DPHARM", name: "Diploma in Pharmacy", intake: 60, firstYear: 51, level: "DIPLOMA", discipline: "PHARMACY" },
    ],
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
    programmes: [
      { code: "BCA", name: "Bachelor of Computer Applications (Online)", intake: 120, firstYear: 104, discipline: "COMPUTER_APPLICATIONS", mode: "ONLINE" },
      { code: "MCA", name: "Master of Computer Applications", intake: 60, firstYear: 57, level: "PG", discipline: "COMPUTER_APPLICATIONS" },
    ],
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
    programmes: [BTECH("CSE", "Computer Science and Engineering", 60, 27), BTECH("ME", "Mechanical Engineering", 60, 18)],
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
    programmes: [
      { code: "BARCH", name: "Bachelor of Architecture", intake: 120, firstYear: 118, discipline: "ARCHITECTURE" },
      { code: "BPLAN", name: "Bachelor of Planning", intake: 60, firstYear: 58, discipline: "PLANNING" },
      { code: "MARCH", name: "Master of Architecture", intake: 60, firstYear: 60, level: "PG", discipline: "ARCHITECTURE" },
    ],
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
    programmes: [
      BTECH("CSE", "Computer Science and Engineering", 120, 118),
      BTECH("IT", "Information Technology", 60, 52),
      BTECH("MECH", "Mechanical Engineering", 120, 71),
      BTECH("CIVIL", "Civil Engineering", 60, 33),
    ],
  },
];

function stateOf(code: string): StateMeta {
  return STATES.find((s) => s.code === code) ?? { code, name: code, region: "WEST" };
}

/** Programmes per institution before the seat ledger runs (pools empty). */
export const BASE_PROGRAMMES: Record<string, ProgrammeDetail[]> = Object.fromEntries(
  SEEDS.map((s) => [s.id, s.programmes.map((spec, i) => programme(s.id, i, spec))]),
);

export function seedOf(id: string): InstitutionSeed | undefined {
  return SEEDS.find((s) => s.id === id);
}

/** List rows. `flags_open` is filled by the handler from the open flags. */
export const INSTITUTIONS: InstitutionRow[] = SEEDS.map((s) => {
  const st = stateOf(s.state_code);
  const progs = BASE_PROGRAMMES[s.id];
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
    programmes: progs.length,
    approved_seats: progs.reduce((a, p) => a + p.approval.approved_intake, 0),
    admitted: progs.reduce((a, p) => a + p.enrolments, 0),
    enrolments: progs.reduce((a, p) => a + onRollOf(p), 0),
    flags_open: 0,
    integrity_index: null,
  };
});

/** Detail without the ledger, flags or last upload; the handler completes it. */
export function institutionBase(id: string): Omit<InstitutionDetail, "programmes"> | null {
  const seed = seedOf(id);
  const row = INSTITUTIONS.find((r) => r.id === id);
  if (!seed || !row) return null;
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
    approved_seats: row.approved_seats,
    admitted: row.admitted,
    enrolments: row.enrolments,
    address_city: seed.address_city,
    established_year: seed.established_year,
    integrity_index: null,
    integrity_components: null,
    flags_open: 0,
    last_upload: null,
  };
}

export const SEAT_LETTER: Record<SeatType, string> = { REGULAR: "R", NRI: "N", TFW: "T", LATERAL: "L", INTERNATIONAL: "I" };

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
