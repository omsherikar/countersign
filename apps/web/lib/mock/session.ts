/**
 * Mock-mode session. The real api sets an HttpOnly `cs_access` JWT; in mock
 * mode the browser writes a readable `cs_access=mock.<email>` cookie so the
 * proxy, the server layouts and the mock handler all see the same signed-in user.
 */
import { USERS } from "@/lib/mock/fixtures";
import type { User } from "@/lib/types";

export const COOKIE = "cs_access";
const PREFIX = "mock.";

export function userFromToken(token: string | undefined | null): User | null {
  if (!token || !token.startsWith(PREFIX)) return null;
  const email = decodeURIComponent(token.slice(PREFIX.length));
  return USERS.find((u) => u.email === email) ?? null;
}

export function tokenFor(email: string): string {
  return `${PREFIX}${encodeURIComponent(email)}`;
}

export function readBrowserToken(): string | null {
  if (typeof document === "undefined") return null;
  const hit = document.cookie.split("; ").find((c) => c.startsWith(`${COOKIE}=`));
  return hit ? hit.slice(COOKIE.length + 1) : null;
}

export function writeBrowserToken(token: string | null) {
  if (typeof document === "undefined") return;
  if (token === null) {
    document.cookie = `${COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
  } else {
    document.cookie = `${COOKIE}=${token}; Path=/; Max-Age=7200; SameSite=Lax`;
  }
}
