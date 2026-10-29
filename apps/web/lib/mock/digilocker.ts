/**
 * Mock-mode DigiLocker sign-in (API_CONTRACT A4.12, A4.25 C.11 and C.12).
 * The real round trip is api start, mockgov's labelled Demo DigiLocker,
 * api callback; with the mock api the web's /auth/digilocker/demo page
 * stands in for mockgov and this module stands in for the api's callback:
 * a linked APAAR signs the student in, an account without one leaves a
 * pending claim (the api's cs_dl_claim cookie, here in sessionStorage).
 */
import type { User } from "@/lib/types";

export interface DemoAccount {
  role: "DEMO_STUDENT" | "PROVISIONAL_CLAIM" | "SOMEONE_ELSE";
  digilocker_id: string;
  name: string;
  dob: string;
  /** Masked as the account list shows it; null when no APAAR is linked. */
  apaar_masked: string | null;
  /** The student account this DigiLocker identity signs in as, once bound. */
  email: string;
}

/** Ravi first, as the demo account list must show him (A4.12). */
export const DEMO_ACCOUNTS: DemoAccount[] = [
  { role: "DEMO_STUDENT", digilocker_id: "DL-4417-RAVI-0001", name: "Ravi Kumar Sharma", dob: "2007-03-21", apaar_masked: "XXXX XXXX 4417", email: "student@demo" },
  { role: "PROVISIONAL_CLAIM", digilocker_id: "DL-8830-ASHA-0002", name: "Asha Patil", dob: "2008-01-14", apaar_masked: null, email: "asha.patil@digilocker.invalid" },
  { role: "SOMEONE_ELSE", digilocker_id: "DL-9035-MEER-0003", name: "Meera Nair", dob: "2007-06-02", apaar_masked: "XXXX XXXX 9035", email: "meera.nair@digilocker.invalid" },
];

/** Student accounts DigiLocker sign-in creates (synthetic `@digilocker.invalid` emails, no password). */
export const DIGILOCKER_USERS: User[] = [
  {
    id: "6f1c0a8e-0031-4c9a-9e51-1c2f1a0b7d33",
    email: "asha.patil@digilocker.invalid",
    name: "Asha Patil",
    role: "STUDENT",
    scope: { institution_id: null, institution_name: null, region: null, student_id: "e6f7a8b9-5555-4666-8777-000000000031", university_id: null },
  },
  {
    id: "6f1c0a8e-0032-4c9a-9e51-1c2f1a0b7d33",
    email: "meera.nair@digilocker.invalid",
    name: "Meera Nair",
    role: "STUDENT",
    scope: { institution_id: null, institution_name: null, region: null, student_id: "e6f7a8b9-5555-4666-8777-000000000032", university_id: null },
  },
];

export const DEMO_OTP = "123456";

export interface PendingClaim {
  sub: string;
  name: string;
  birthdate: string;
  next: string;
}

const CLAIM_KEY = "cs_mock_dl_claim";

export function readPendingClaim(): PendingClaim | null {
  try {
    const raw = typeof sessionStorage === "undefined" ? null : sessionStorage.getItem(CLAIM_KEY);
    return raw ? (JSON.parse(raw) as PendingClaim) : null;
  } catch {
    return null;
  }
}

export function writePendingClaim(claim: PendingClaim | null) {
  try {
    if (claim) sessionStorage.setItem(CLAIM_KEY, JSON.stringify(claim));
    else sessionStorage.removeItem(CLAIM_KEY);
  } catch {
    // Storage refused: the pending claim lasts for this page only.
  }
}

/** A path the api would accept as `next`: under /student, else /student (A4.12). */
export function studentNext(next: string | null): string {
  return next && next.startsWith("/student") && !next.startsWith("//") ? next : "/student";
}

export const isNoticePath = (next: string) => /^\/student\/notices\/[^/?#]+/.test(next);
