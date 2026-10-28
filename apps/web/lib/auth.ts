import "server-only";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { MOCK_API } from "@/lib/api";
import { userFromToken } from "@/lib/mock/session";
import { landingFor } from "@/lib/roles";
import type { Role, User, UserEnvelope } from "@/lib/types";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/**
 * Server-side GET /me for layouts and redirects. Passes the incoming
 * cs_access cookie straight to the api (ARCHITECTURE section 3).
 * Returns null when signed out or the session has ended.
 */
export async function getMe(): Promise<User | null> {
  const store = await cookies();
  const token = store.get("cs_access")?.value;
  if (!token) return null;
  if (MOCK_API) return userFromToken(token);
  try {
    const res = await fetch(`${API_INTERNAL_URL}/me`, {
      headers: { Cookie: `cs_access=${token}`, Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as UserEnvelope;
    return body.user;
  } catch {
    return null;
  }
}

/**
 * Guard for a role route group. Signed out goes to /login with a back-link;
 * the wrong role goes to its own landing route with `denied` set so the
 * shell can say why.
 */
export async function requireRole(role: Role, fallbackPath: string): Promise<User> {
  const here = (await headers()).get("x-pathname") ?? fallbackPath;
  const me = await getMe();
  if (!me) redirect(`/login?next=${encodeURIComponent(here)}`);
  if (me.role !== role) redirect(`${landingFor(me.role)}?denied=${role}`);
  return me;
}
