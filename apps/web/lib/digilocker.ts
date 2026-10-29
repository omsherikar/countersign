import { API_BASE, MOCK_API } from "@/lib/api";

/**
 * Where "Sign in with DigiLocker" goes (API_CONTRACT A4.12): the api's
 * start route, which answers 302 to DigiLocker (in the demo, mockgov's
 * labelled simulator). With the mock api there is no server to redirect, so
 * the link opens the web's own stand-in for that simulator instead.
 */
export function signInUrl(next: string): string {
  const q = `?next=${encodeURIComponent(next)}`;
  return MOCK_API ? `/auth/digilocker/demo${q}` : `${API_BASE}/auth/digilocker/start${q}`;
}

/** A same-origin path to go to after sign-in; anything else becomes the student's home. */
export function safeNext(next: string | null | undefined, fallback = "/student"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}

/** In mock mode the api's sign-in link points at the stand-in simulator too. */
export function resolveSignInUrl(fromApi: string | null | undefined, next: string): string {
  if (MOCK_API || !fromApi) return signInUrl(next);
  return fromApi;
}
