/**
 * The state admission authorities' joinings lists, as far as the mock needs
 * them (API_CONTRACT A4.18, A4.25 C.10): who joined each college but is not
 * in its uploads, and when each college first uploaded for 2026-27. Joinings
 * that match an uploaded record are counted from the roll itself.
 */
import { ACADEMIC_YEAR, IDS, SEEDS } from "@/lib/mock/fixtures";
import { joiningYearOf, rollFor } from "@/lib/mock/roll";
import type { DeadlineState, MissingStudent } from "@/lib/types";

export const REPORTING_DEADLINE = "2026-09-30";

const KARAD = "10000000-0004-4000-8000-000000000004";
const KAVERI = "10000000-0006-4000-8000-000000000006";
const DURGAPUR = "10000000-0008-4000-8000-000000000008";
const PUNE = "10000000-0010-4000-8000-000000000010";

/** The first DONE upload for 2026-27 per college; Karad and Durgapur reported after the deadline. */
export const FIRST_UPLOAD: Record<string, string> = {
  [IDS.abc]: "2026-09-22T06:30:00Z",
  [IDS.xyz]: "2026-09-18T05:12:00Z",
  "10000000-0003-4000-8000-000000000003": "2026-09-26T09:40:00Z",
  [KARAD]: "2026-10-03T07:05:00Z",
  "10000000-0005-4000-8000-000000000005": "2026-09-15T10:20:00Z",
  [KAVERI]: "2026-09-29T11:45:00Z",
  "10000000-0007-4000-8000-000000000007": "2026-09-20T08:00:00Z",
  [DURGAPUR]: "2026-10-12T06:55:00Z",
  "10000000-0009-4000-8000-000000000009": "2026-09-24T04:30:00Z",
  [PUNE]: "2026-09-25T12:10:00Z",
};

export function deadlineStateOf(institutionId: string): DeadlineState {
  const first = FIRST_UPLOAD[institutionId];
  if (!first) return new Date().toISOString().slice(0, 10) > REPORTING_DEADLINE ? "OVERDUE" : "NOT_DUE";
  return first.slice(0, 10) <= REPORTING_DEADLINE ? "ON_TIME" : "LATE";
}

const s = (name: string, roll_no: string | null, programme_code: string, joined_on: string, round: number | null, route: MissingStudent["route"], apaar_masked: string | null): MissingStudent => ({
  name,
  roll_no,
  programme_code,
  joined_on,
  round,
  route,
  apaar_masked,
});

/** Joined at the college in 2026-27 by the authority's list, but not in any of its uploads (D40). */
export const MISSING: Record<string, MissingStudent[]> = {
  [IDS.abc]: [
    s("Sneha Kulkarni", "MHCET-2026-007731", "CSE", "2026-08-04", 2, "COUNSELLING", "XXXX XXXX 8812"),
    s("Rohan Gaikwad", "MHCET-2026-007902", "CSE", "2026-08-04", 2, "COUNSELLING", "XXXX XXXX 1274"),
    s("Aisha Shaikh", null, "CSE", "2026-08-11", null, "MANAGEMENT", "XXXX XXXX 6630"),
    s("Kabir Jadhav", "MHCET-2026-008120", "CSE", "2026-08-12", 3, "COUNSELLING", null),
    s("Pooja Chavan", "MHCET-2026-005541", "MECH", "2026-08-02", 1, "COUNSELLING", "XXXX XXXX 3907"),
    s("Yash Sawant", null, "MECH", "2026-08-18", null, "SPOT", "XXXX XXXX 2215"),
    s("Divya Kale", "MHCET-2026-006017", "ECE", "2026-08-05", 2, "COUNSELLING", "XXXX XXXX 7468"),
    s("Harsh Mane", "MHCET-2026-006233", "ECE", "2026-08-05", 2, "COUNSELLING", "XXXX XXXX 5093"),
  ],
  [KARAD]: [
    s("Omkar Patil", "MHCET-2026-011304", "CIVIL", "2026-08-03", 1, "COUNSELLING", "XXXX XXXX 4120"),
    s("Riya Shinde", "MHCET-2026-011488", "CSE", "2026-08-06", 2, "COUNSELLING", "XXXX XXXX 9351"),
    s("Akash More", null, "MECH", "2026-08-21", null, "MANAGEMENT", null),
  ],
  [PUNE]: [
    s("Gauri Deshmukh", "MHCET-2026-013322", "CSE", "2026-08-04", 1, "COUNSELLING", "XXXX XXXX 6688"),
    s("Nikhil Kadam", "MHCET-2026-013540", "CSE", "2026-08-07", 2, "COUNSELLING", "XXXX XXXX 0412"),
    s("Tanvi Joshi", null, "IT", "2026-08-14", null, "MANAGEMENT", "XXXX XXXX 7725"),
    s("Varun Pawar", "MHCET-2026-013918", "IT", "2026-08-07", 2, "COUNSELLING", "XXXX XXXX 3146"),
    s("Swati Salunkhe", null, "MECH", "2026-08-20", null, "SPOT", "XXXX XXXX 5580"),
  ],
  [KAVERI]: [
    s("Kavya Hegde", "KCET-2026-020114", "BPHARM", "2026-08-08", 2, "COUNSELLING", "XXXX XXXX 2864"),
    s("Manish Gowda", null, "DPHARM", "2026-08-19", null, "MANAGEMENT", "XXXX XXXX 9907"),
  ],
};

/** The authorities that have published no 2026-27 joining record yet (Telangana, West Bengal). */
export function publishedFor(stateCode: string): boolean {
  return stateCode !== "TS" && stateCode !== "WB";
}

export const RECONCILED_AT = "2026-10-28T06:00:00Z";

/** Joinings of 2026-27 matched to an uploaded record, missing from the uploads, and uploaded but never joined. */
export function joinedCounts(institutionId: string): { published: boolean; joined: number; matched: number; missing: MissingStudent[]; notJoined: number } {
  const seed = SEEDS.find((x) => x.id === institutionId)!;
  const published = publishedFor(seed.state_code);
  const roll = rollFor(institutionId).filter((e) => joiningYearOf(e.row) === ACADEMIC_YEAR && e.row.admission_route !== "INTERNATIONAL");
  const admission = (e: (typeof roll)[number]) => e.checks.find((c) => c.type === "ADMISSION");
  const matched = published ? roll.filter((e) => admission(e)?.state === "CONFIRMED").length : 0;
  const notJoined = roll.filter((e) => e.row.status === "ACTIVE" && admission(e)?.detail.basis === "NOT_IN_JOINING_RECORD").length;
  const missing = published ? (MISSING[institutionId] ?? []) : [];
  return { published, joined: matched + missing.length, matched, missing, notJoined };
}
