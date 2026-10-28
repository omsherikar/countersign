import type { Region, Role, User } from "@/lib/types";
import { t } from "@/lib/copy";

/** Landing route per role (ARCHITECTURE section 4). */
export const LANDING: Record<Role, string> = {
  AICTE_ADMIN: "/aicte",
  RO_OFFICER: "/ro",
  INSTITUTION: "/college",
  STUDENT: "/student",
  UNIVERSITY: "/university",
  VERIFIER: "/verify",
};

/** Route prefixes each role may open. */
export const ROLE_PREFIXES: Record<Role, string[]> = {
  AICTE_ADMIN: ["/aicte", "/admin"],
  RO_OFFICER: ["/ro"],
  INSTITUTION: ["/college"],
  STUDENT: ["/student"],
  UNIVERSITY: ["/university"],
  VERIFIER: ["/verify"],
};

/** Plural nouns for "This page is for ...". */
export const ROLE_PLURAL: Record<Role, string> = {
  AICTE_ADMIN: "AICTE officers",
  RO_OFFICER: "regional officers",
  INSTITUTION: "registrars",
  STUDENT: "students",
  UNIVERSITY: "university controllers",
  VERIFIER: "verifiers",
};

/** Singular with article for "You are signed in as ...". */
export const ROLE_SINGULAR: Record<Role, string> = {
  AICTE_ADMIN: "an AICTE officer",
  RO_OFFICER: "a regional officer",
  INSTITUTION: "a registrar",
  STUDENT: "a student",
  UNIVERSITY: "a university controller",
  VERIFIER: "a verifier",
};

export const REGION_NAME: Record<Region, string> = {
  NORTH: "Northern",
  NORTH_WEST: "North-Western",
  CENTRAL: "Central",
  WEST: "Western",
  WEST_CENTRAL: "West-Central",
  SOUTH_WEST: "South-Western",
  SOUTH: "Southern",
  SOUTH_CENTRAL: "South-Central",
  EAST: "Eastern",
  NORTH_EAST: "North-Eastern",
};

export function landingFor(role: Role): string {
  return LANDING[role] ?? "/login";
}

/** Role in words for the user menu ("Regional officer, Western"). */
export function roleWord(user: Pick<User, "role" | "scope">): string {
  if (user.role === "RO_OFFICER") {
    const region = user.scope.region ? REGION_NAME[user.scope.region] : "";
    return t("shell.role.RO_OFFICER", { region_name: region });
  }
  if (user.role === "VERIFIER") return "Verifier";
  return t(`shell.role.${user.role}` as "shell.role.AICTE_ADMIN");
}

export function roleForPath(pathname: string): Role | null {
  for (const role of Object.keys(ROLE_PREFIXES) as Role[]) {
    if (role === "VERIFIER") continue;
    if (ROLE_PREFIXES[role].some((p) => pathname === p || pathname.startsWith(`${p}/`))) return role;
  }
  return null;
}
