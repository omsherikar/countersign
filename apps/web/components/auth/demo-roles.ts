import type { CopyId } from "@/lib/copy";
import type { Role } from "@/lib/types";

export const DEMO_PASSWORD = "Countersign!2026";

export interface DemoRole {
  key: string;
  email: string;
  role: Role;
  /** "Role / Scope" from the copy deck. */
  card: CopyId;
  /** Students sign in only through DigiLocker; their card is a link, never a password (A4.12). */
  digilocker?: boolean;
}

/**
 * Role cards on /login (ARCHITECTURE section 7). ro.south@aicte.demo is left
 * off on purpose to keep six cards; it still works when typed.
 */
export const DEMO_ROLES: DemoRole[] = [
  { key: "admin", email: "admin@aicte.demo", role: "AICTE_ADMIN", card: "login.card.admin" },
  { key: "ro_west", email: "ro.west@aicte.demo", role: "RO_OFFICER", card: "login.card.ro_west" },
  { key: "abc", email: "registrar@abc.edu.demo", role: "INSTITUTION", card: "login.card.abc" },
  { key: "xyz", email: "registrar@xyz.edu.demo", role: "INSTITUTION", card: "login.card.xyz" },
  { key: "student", email: "", role: "STUDENT", card: "login.card.student", digilocker: true },
  { key: "university", email: "coe@univ.demo", role: "UNIVERSITY", card: "login.card.university" },
];
