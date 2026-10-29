/**
 * Mock-mode signals (API_CONTRACT A4.19): two shared contact rings, one
 * dismissed ring and two unusual patterns for 2026-27, seen only by AICTE
 * and regional officers. A regional officer sees a signal when one of its
 * colleges is in the region; members and colleges outside it are counted,
 * not listed. Signals never change a record; lib/mock/cases.ts opens the
 * cases, which are the only way a signal reaches a record (R5).
 */
import { ApiError, type Query } from "@/lib/api";
import { ACADEMIC_YEAR, INSTITUTIONS, SEEDS } from "@/lib/mock/fixtures";
import { allFlags } from "@/lib/mock/flags";
import { withRecord } from "@/lib/mock/records";
import { entryById, rollFor, type RollEntry } from "@/lib/mock/roll";
import type {
  EvidenceFact,
  Page,
  Region,
  Role,
  SignalDetail,
  SignalFeature,
  SignalMember,
  SignalRow,
  SignalStatus,
  SignalType,
  User,
} from "@/lib/types";

const KARAD = "10000000-0004-4000-8000-000000000004";
const AHMEDABAD = "10000000-0005-4000-8000-000000000005";
const LUCKNOW = "10000000-0007-4000-8000-000000000007";
const PUNE = "10000000-0010-4000-8000-000000000010";
const GAYATRI = "10000000-0003-4000-8000-000000000003";
const ABC = "a0b1c2d3-1111-4222-8333-444455556666";
const XYZ = "b1c2d3e4-2222-4333-8444-555566667777";

export const RING_RULE =
  "Rule: students linked by a shared mobile number, email or address form a group; a group of 3 or more across 2 or more colleges, or of 5 or more in one college, is a signal.";
const PEERS = 50;
export const ANOMALY_RULE = `Model: Isolation Forest, contamination 5%, trained on this year's ${PEERS} colleges.`;

export interface StoredSignal {
  id: string;
  type: SignalType;
  academic_year: string;
  status: SignalStatus;
  score: number | null;
  institutionIds: string[];
  memberIds: string[];
  shared: SignalDetail["shared"];
  features: SignalFeature[];
  created_at: string;
  updated_at: string;
  note: string | null;
  decidedBy: { id: string; name: string } | null;
  decidedAt: string | null;
  /** Cases opened from it, one per college. */
  caseIds: { id: string; institution_id: string }[];
}

const nameOf = (id: string) => SEEDS.find((s) => s.id === id)?.name ?? "";
const regionOf = (id: string): Region => INSTITUTIONS.find((i) => i.id === id)!.region;
const OFFICERS: Role[] = ["AICTE_ADMIN", "RO_OFFICER"];

function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/** Deterministic members: active first-year records that no planted case uses, so the ring reads as its own story. */
function membersAt(institutionId: string, n: number, salt: string): RollEntry[] {
  return rollFor(institutionId)
    .filter((e) => !e.planted && e.row.status === "ACTIVE" && e.row.academic_year === ACADEMIC_YEAR)
    .sort((a, b) => hash(`${salt}:${a.row.id}`) - hash(`${salt}:${b.row.id}`))
    .slice(0, n);
}

/** "40 students across 3 colleges share 3 mobile numbers, 2 email addresses and 1 address." A count of 0 drops its clause. */
export function ringSummary(students: number, institutionIds: string[], shared: SignalDetail["shared"]): string {
  const count = (kind: "MOBILE" | "EMAIL" | "ADDRESS") => shared.filter((s) => s.kind === kind).length;
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  const parts = [
    count("MOBILE") ? plural(count("MOBILE"), "mobile number", "mobile numbers") : null,
    count("EMAIL") ? plural(count("EMAIL"), "email address", "email addresses") : null,
    count("ADDRESS") ? plural(count("ADDRESS"), "address", "addresses") : null,
  ].filter((p): p is string => Boolean(p));
  const joined = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
  return institutionIds.length > 1
    ? `${students} students across ${institutionIds.length} colleges share ${joined}.`
    : `${students} students at ${nameOf(institutionIds[0])} share ${joined}.`;
}

export const FEATURE_WORD: Record<SignalFeature["name"], string> = {
  admission_growth: "admission growth on last year",
  nri_share: "NRI share of admissions",
  management_share: "management share of admissions",
  contradiction_rate: "records with a contradicted row",
  contact_sharing_rate: "students sharing a contact",
};

export function anomalySummary(institutionId: string, features: SignalFeature[]): string {
  const words = features.filter((f) => f.stands_out).map((f) => FEATURE_WORD[f.name]);
  const joined = words.length > 1 ? `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}` : words[0];
  return `${nameOf(institutionId)} stands out from ${PEERS - 1} similar colleges in ${ACADEMIC_YEAR} on ${joined}.`;
}

function feature(name: SignalFeature["name"], value: number, low: number, high: number, median: number, z: number): SignalFeature {
  return { name, value, peer_low: low, peer_high: high, peer_median: median, robust_z: z, stands_out: Math.abs(z) >= 3 };
}

let STORE: StoredSignal[] | null = null;

function ring(id: string, parts: [string, number][], shared: SignalDetail["shared"], at: string, status: SignalStatus = "NEW"): StoredSignal {
  const members = parts.flatMap(([inst, n]) => membersAt(inst, n, id));
  return {
    id,
    type: "GHOST_RING",
    academic_year: ACADEMIC_YEAR,
    status,
    score: null,
    institutionIds: parts.map(([inst]) => inst),
    memberIds: members.map((e) => e.row.id),
    shared,
    features: [],
    created_at: at,
    updated_at: at,
    note: null,
    decidedBy: null,
    decidedAt: null,
    caseIds: [],
  };
}

function anomaly(id: string, institutionId: string, score: number, features: SignalFeature[], at: string): StoredSignal {
  return {
    id,
    type: "ANOMALY",
    academic_year: ACADEMIC_YEAR,
    status: "NEW",
    score,
    institutionIds: [institutionId],
    memberIds: [],
    shared: [],
    features,
    created_at: at,
    updated_at: at,
    note: null,
    decidedBy: null,
    decidedAt: null,
    caseIds: [],
  };
}

export function allSignals(): StoredSignal[] {
  if (STORE) return STORE;
  const found = "2026-10-28T06:20:00Z";
  STORE = [
    ring(
      "5a000001-0001-4a00-8a00-000000000001",
      [
        [ABC, 18],
        [KARAD, 12],
        [AHMEDABAD, 10],
      ],
      [
        { kind: "MOBILE", masked: "XXXXXX4410", students: 14 },
        { kind: "MOBILE", masked: "XXXXXX7782", students: 13 },
        { kind: "MOBILE", masked: "XXXXXX1209", students: 13 },
        { kind: "EMAIL", masked: "a***@example.com", students: 9 },
        { kind: "EMAIL", masked: "k***@example.com", students: 7 },
        { kind: "ADDRESS", masked: "Same address", students: 11 },
      ],
      found,
    ),
    anomaly(
      "5a000002-0002-4a00-8a00-000000000002",
      PUNE,
      0.71,
      [
        feature("admission_growth", 0.12, 0.02, 0.09, 0.05, 1.4),
        feature("nri_share", 0.31, 0.02, 0.07, 0.04, 6.2),
        feature("management_share", 0.38, 0.08, 0.16, 0.12, 4.1),
        feature("contradiction_rate", 0.06, 0.02, 0.05, 0.03, 1.1),
        feature("contact_sharing_rate", 0.01, 0.0, 0.02, 0.01, 0.2),
      ],
      found,
    ),
    ring(
      "5a000003-0003-4a00-8a00-000000000003",
      [[XYZ, 6]],
      [
        { kind: "MOBILE", masked: "XXXXXX3318", students: 4 },
        { kind: "MOBILE", masked: "XXXXXX9024", students: 3 },
        { kind: "ADDRESS", masked: "Same address", students: 6 },
      ],
      "2026-10-28T06:21:00Z",
    ),
    anomaly(
      "5a000004-0004-4a00-8a00-000000000004",
      LUCKNOW,
      0.66,
      [
        feature("admission_growth", 0.48, 0.01, 0.11, 0.06, 5.3),
        feature("nri_share", 0.0, 0.0, 0.03, 0.01, -0.4),
        feature("management_share", 0.09, 0.05, 0.15, 0.1, -0.2),
        feature("contradiction_rate", 0.11, 0.02, 0.05, 0.03, 3.4),
        feature("contact_sharing_rate", 0.02, 0.0, 0.02, 0.01, 0.9),
      ],
      "2026-10-27T11:40:00Z",
    ),
    ring(
      "5a000005-0005-4a00-8a00-000000000005",
      [[GAYATRI, 5]],
      [{ kind: "ADDRESS", masked: "Same address", students: 5 }],
      "2026-10-27T11:41:00Z",
      "DISMISSED",
    ),
  ];
  const dismissed = STORE[4];
  dismissed.note = "Five students from one joint family share their home address; the college confirmed each admission.";
  dismissed.decidedBy = { id: "6f1c0a8e-0001-4c9a-9e51-1c2f1a0b7d33", name: "AICTE Administrator" };
  dismissed.decidedAt = "2026-10-28T05:10:00Z";
  dismissed.updated_at = dismissed.decidedAt;
  return STORE;
}

/* ---- Scope and views ------------------------------------------------------ */

function requireOfficer(user: User) {
  if (!OFFICERS.includes(user.role)) throw new ApiError(403, "FORBIDDEN", "Your role cannot access this resource.", { required_roles: OFFICERS });
}

const visibleInstitution = (user: User, id: string) => user.role === "AICTE_ADMIN" || regionOf(id) === user.scope.region;

export function signalInScope(user: User, id: string): StoredSignal {
  requireOfficer(user);
  const s = allSignals().find((x) => x.id === id);
  if (!s || !s.institutionIds.some((i) => visibleInstitution(user, i))) throw new ApiError(404, "NOT_FOUND", "Signal not found.");
  return s;
}

export function summaryOf(s: StoredSignal): string {
  return s.type === "GHOST_RING" ? ringSummary(s.memberIds.length, s.institutionIds, s.shared) : anomalySummary(s.institutionIds[0], s.features);
}

export function ruleOf(s: StoredSignal): string {
  return s.type === "GHOST_RING" ? RING_RULE : ANOMALY_RULE;
}

export function signalRow(user: User, s: StoredSignal): SignalRow {
  const seen = s.institutionIds.filter((i) => visibleInstitution(user, i));
  const members = s.memberIds.filter((id) => {
    const e = entryById(id);
    return e && visibleInstitution(user, e.institutionId);
  });
  return {
    id: s.id,
    type: s.type,
    academic_year: s.academic_year,
    status: s.status,
    summary: summaryOf(s),
    member_count: s.memberIds.length,
    members_hidden: s.memberIds.length - members.length,
    score: s.score,
    institutions: seen.map((id) => {
      const row = INSTITUTIONS.find((i) => i.id === id)!;
      return { id, name: row.name, aicte_permanent_id: row.aicte_permanent_id, state_code: row.state_code, region: row.region };
    }),
    institutions_hidden: s.institutionIds.length - seen.length,
    rule: ruleOf(s),
    cases: s.caseIds
      .filter((c) => visibleInstitution(user, c.institution_id))
      .map((c) => ({ id: c.id, institution_id: c.institution_id, status: allFlags().find((f) => f.id === c.id)?.status ?? "OPEN" })),
    created_at: s.created_at,
    updated_at: s.updated_at,
  };
}

function percent(v: number): string {
  return `${Math.round(v * 100)}%`;
}

export function signalDetail(user: User, s: StoredSignal): SignalDetail {
  const row = signalRow(user, s);
  const members: SignalMember[] = s.memberIds
    .map((id) => entryById(id))
    .filter((e): e is RollEntry => Boolean(e) && visibleInstitution(user, e!.institutionId))
    .map((e) => ({
      enrolment_id: e.row.id,
      student: { id: e.row.student.id, name: e.row.student.name, apaar_masked: e.row.student.apaar_masked, provisional_id: e.row.student.provisional_id },
      institution: { id: e.institutionId, name: nameOf(e.institutionId) },
      programme_code: e.row.programme_code,
      record_status: withRecord(e).record_status,
    }));
  let facts: EvidenceFact[];
  if (s.type === "GHOST_RING") {
    const per = s.institutionIds
      .filter((i) => visibleInstitution(user, i))
      .map((i) => `${nameOf(i)} (${s.memberIds.filter((id) => entryById(id)?.institutionId === i).length})`);
    if (row.institutions_hidden > 0) per.push(`${row.institutions_hidden} ${row.institutions_hidden === 1 ? "college" : "colleges"} in another region`);
    const count = (kind: string) => String(s.shared.filter((x) => x.kind === kind).length);
    facts = [
      { label: "Students", value: String(s.memberIds.length), source: "Countersign signals" },
      { label: "Colleges", value: per.join("; "), source: "College uploads" },
      { label: "Shared mobile numbers", value: count("MOBILE"), source: "College uploads, contact hashes" },
      { label: "Shared email addresses", value: count("EMAIL"), source: "College uploads, contact hashes" },
      { label: "Shared addresses", value: count("ADDRESS"), source: "College uploads, contact hashes" },
    ];
  } else {
    facts = [
      { label: "Colleges", value: nameOf(s.institutionIds[0]), source: "College uploads" },
      { label: "Similar colleges compared", value: String(PEERS - 1), source: "Countersign signals" },
      { label: "Model score", value: s.score?.toFixed(2) ?? "", source: "Isolation Forest" },
    ];
  }
  return {
    ...row,
    facts,
    shared: s.shared,
    features: s.features,
    members,
    dismissal: s.status === "DISMISSED" && s.note && s.decidedBy && s.decidedAt ? { note: s.note, by: s.decidedBy, at: s.decidedAt } : null,
  };
}

function paginate<T>(items: T[], query?: Query): Page<T> {
  const page = Math.max(1, Number(query?.page ?? 1));
  const pageSize = Math.min(200, Math.max(1, Number(query?.page_size ?? 25)));
  return { items: items.slice((page - 1) * pageSize, page * pageSize), total: items.length, page, page_size: pageSize };
}

export function listSignals(user: User, query?: Query): Page<SignalRow> {
  requireOfficer(user);
  let rows = allSignals().filter((s) => s.institutionIds.some((i) => visibleInstitution(user, i)));
  if (query?.academic_year) rows = rows.filter((s) => s.academic_year === query.academic_year);
  if (query?.type) rows = rows.filter((s) => s.type === query.type);
  if (query?.status) rows = rows.filter((s) => s.status === query.status);
  if (query?.institution_id) rows = rows.filter((s) => s.institutionIds.includes(String(query.institution_id)));
  if (query?.state) rows = rows.filter((s) => s.institutionIds.some((i) => INSTITUTIONS.find((x) => x.id === i)?.state_code === query.state));
  if (String(query?.sort ?? "newest") === "score") {
    rows = [...rows].sort((a, b) => (a.type === b.type ? (a.type === "ANOMALY" ? (b.score ?? 0) - (a.score ?? 0) : b.memberIds.length - a.memberIds.length) : a.type === "ANOMALY" ? -1 : 1));
  } else {
    rows = [...rows].sort((a, b) => b.created_at.localeCompare(a.created_at) || a.id.localeCompare(b.id));
  }
  return paginate(
    rows.map((s) => signalRow(user, s)),
    query,
  );
}

/** Members at one college, for the case a signal opens there. */
export function membersOf(s: StoredSignal, institutionId: string): string[] {
  return s.memberIds.filter((id) => entryById(id)?.institutionId === institutionId);
}

/** "Admission growth on last year: 48% (similar colleges 1% to 11%)" for the anomaly case's facts. */
export function featureFacts(s: StoredSignal): EvidenceFact[] {
  return s.features
    .filter((f) => f.stands_out)
    .map((f) => ({ label: FEATURE_WORD[f.name].replace(/^./, (c) => c.toUpperCase()), value: `${percent(f.value)} (similar colleges ${percent(f.peer_low)} to ${percent(f.peer_high)})`, source: "Isolation Forest" }));
}

export function dismissSignal(user: User, s: StoredSignal, note: string, at: string) {
  if (s.status !== "NEW") throw new ApiError(409, "SIGNAL_ALREADY_HANDLED", "This signal already has a case or was dismissed.", { status: s.status });
  s.status = "DISMISSED";
  s.note = note;
  s.decidedBy = { id: user.id, name: user.name };
  s.decidedAt = at;
  s.updated_at = at;
}

export const REGION_OF = regionOf;
