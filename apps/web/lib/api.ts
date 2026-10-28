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

/* ---- Multipart upload and file downloads (API_CONTRACT A2.1) ------------- */

export interface UploadOptions {
  /** Bytes sent so far as a whole percentage, 0 to 100. */
  onProgress?: (pct: number) => void;
  signal?: AbortSignal;
}

function parseJson(text: string): unknown {
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

/**
 * POST multipart/form-data with upload progress. fetch cannot report bytes
 * sent, so this uses XMLHttpRequest. The browser writes the Content-Type
 * with its boundary; the /api proxy forwards the body as a stream.
 */
export async function upload<T>(path: string, form: FormData, options: UploadOptions = {}): Promise<T> {
  const { onProgress, signal } = options;

  if (MOCK_API) {
    const { mockUpload } = await import("@/lib/mock/handler");
    // Stand-in for bytes on the wire so the progress bar moves as it will against the api.
    for (const pct of [8, 27, 51, 74, 92, 100]) {
      if (signal?.aborted) throw new DOMException("Upload cancelled", "AbortError");
      await new Promise((r) => setTimeout(r, 110));
      onProgress?.(pct);
    }
    try {
      return (await mockUpload(path, form)) as T;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) redirectToLogin();
      throw err;
    }
  }

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100)));
    };
    xhr.onload = () => {
      const parsed = parseJson(xhr.responseText);
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress?.(100);
        resolve(parsed as T);
        return;
      }
      if (xhr.status === 401) redirectToLogin();
      reject(toApiError(xhr.status, parsed));
    };
    xhr.onerror = () => reject(new ApiError(0, "NETWORK", t("err.NETWORK")));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}

/** `attachment; filename="x.csv"` to `x.csv`. */
export function filenameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  if (star) return decodeURIComponent(star[1].trim());
  const plain = /filename="?([^";]+)"?/i.exec(disposition);
  return plain ? plain[1].trim() : fallback;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * GET a file (errors.csv, the templates) and save it under the name in
 * Content-Disposition. Errors come back as the usual envelope, so a 404 or
 * 403 shows as a message instead of a page of JSON.
 */
export async function download(path: string, fallbackName: string): Promise<string> {
  if (MOCK_API) {
    const { mockDownload } = await import("@/lib/mock/handler");
    const { blob, filename } = await mockDownload(path);
    saveBlob(blob, filename);
    return filename;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { credentials: "include", cache: "no-store" });
  } catch {
    throw new ApiError(0, "NETWORK", t("err.NETWORK"));
  }
  if (!res.ok) {
    if (res.status === 401) redirectToLogin();
    throw toApiError(res.status, parseJson(await res.text()));
  }
  const filename = filenameFrom(res.headers.get("Content-Disposition"), fallbackName);
  saveBlob(await res.blob(), filename);
  return filename;
}

export const api = {
  get: <T>(path: string, query?: Query, options?: Omit<RequestOptions, "method" | "query" | "body">) =>
    request<T>(path, { ...options, method: "GET", query }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body: body ?? {} }),
  upload,
  download,
};
