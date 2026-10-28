import type { ApiErrorBody } from "@/lib/types";
import { t } from "@/lib/copy";

/**
 * Typed fetch client for the Countersign API.
 *
 * The browser only ever calls `/api/*` on its own origin; next.config.ts
 * rewrites that to API_INTERNAL_URL with cookies passed through. Every
 * non-2xx response is unwrapped from the `{"error": {...}}` envelope into an
 * ApiError. A 401 sends the browser to /login with a `next` back-link.
 *
 * With NEXT_PUBLIC_MOCK_API=1 the same calls are answered by contract-exact
 * fixtures in lib/mock, so every page renders without the backend.
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";
export const MOCK_API = process.env.NEXT_PUBLIC_MOCK_API === "1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** `details.fields` on 422 (Addendum 1.9). */
  get fields(): { field: string; message: string }[] {
    const f = this.details.fields;
    return Array.isArray(f) ? (f as { field: string; message: string }[]) : [];
  }

  /** `details.retry_after` on 429 (Addendum 1.5). */
  get retryAfter(): number | null {
    const r = this.details.retry_after;
    return typeof r === "number" ? r : null;
  }
}

export type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
  /** Set false where a 401 is an expected answer (the /me probe, the login form). */
  redirectOn401?: boolean;
}

export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

function isEnvelope(body: unknown): body is ApiErrorBody {
  return (
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof (body as ApiErrorBody).error === "object" &&
    (body as ApiErrorBody).error !== null
  );
}

export function toApiError(status: number, body: unknown): ApiError {
  if (isEnvelope(body)) {
    const { code, message, details } = body.error;
    return new ApiError(status, code ?? "INTERNAL", message ?? t("err.INTERNAL"), details ?? {});
  }
  return new ApiError(status, "INTERNAL", t("err.INTERNAL"));
}

function redirectToLogin() {
  if (typeof window === "undefined") return;
  const here = `${window.location.pathname}${window.location.search}`;
  if (window.location.pathname.startsWith("/login")) return;
  // A full navigation on purpose: this runs outside React and must drop all cached query data.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(here)}&expired=1`);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", query, body, signal, redirectOn401 = true } = options;

  if (MOCK_API) {
    const { mockRequest } = await import("@/lib/mock/handler");
    try {
      return (await mockRequest(method, path, query, body)) as T;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && redirectOn401) redirectToLogin();
      throw err;
    }
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(query)}`, {
      method,
      credentials: "include",
      headers: body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "NETWORK", t("err.NETWORK"));
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = undefined;
    }
  }

  if (!res.ok) {
    const error = toApiError(res.status, parsed);
    if (res.status === 401 && redirectOn401) redirectToLogin();
    throw error;
  }
  return parsed as T;
}

export const api = {
  get: <T>(path: string, query?: Query, options?: Omit<RequestOptions, "method" | "query" | "body">) =>
    request<T>(path, { ...options, method: "GET", query }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body: body ?? {} }),
};
