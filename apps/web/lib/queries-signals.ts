"use client";

/**
 * Signals and reports (API_CONTRACT A4.19 and A4.21), officers only. Signals
 * never change a record's status; opening a case from one is the only way
 * they reach a record, so that mutation refetches the cases and records too.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, MOCK_API, API_BASE, toApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import type {
  ItemsEnvelope,
  Page,
  ReportFormat,
  ReportInfo,
  ReportName,
  ReportQuery,
  SignalDetail,
  SignalDismiss,
  SignalListQuery,
  SignalOpenCase,
  SignalOpenCaseResult,
  SignalRow,
} from "@/lib/types";

export const signalKeys = {
  list: (params: SignalListQuery) => ["signals", "list", params] as const,
  one: (id: string) => ["signals", id] as const,
  reports: ["reports", "list"] as const,
  preview: (name: ReportName, params: ReportQuery) => ["reports", "preview", name, params] as const,
};

export function useSignals(params: SignalListQuery, enabled = true) {
  return useQuery({
    queryKey: signalKeys.list(params),
    queryFn: ({ signal }) => api.get<Page<SignalRow>>("/signals", { ...params }, { signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useSignal(id: string | null | undefined) {
  return useQuery({
    queryKey: signalKeys.one(id ?? ""),
    queryFn: () => api.get<SignalDetail>(`/signals/${id}`),
    enabled: Boolean(id),
  });
}

/** 409 SIGNAL_ALREADY_HANDLED means another officer acted: show the signal as it is now. */
function onStale(qc: ReturnType<typeof useQueryClient>, id: string, err: unknown) {
  if (err instanceof ApiError && (err.code === "SIGNAL_ALREADY_HANDLED" || err.status === 404)) {
    void qc.invalidateQueries({ queryKey: signalKeys.one(id) });
    void qc.invalidateQueries({ queryKey: ["signals", "list"] });
  }
}

export function useOpenSignalCase(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SignalOpenCase) => api.post<SignalOpenCaseResult>(`/signals/${id}/open-case`, body),
    onSuccess: (result) => {
      qc.setQueryData(signalKeys.one(id), result.signal);
      void qc.invalidateQueries({ queryKey: ["signals", "list"] });
      // The records the new cases name read Under review from now on (R5).
      void qc.invalidateQueries({ queryKey: ["flags"] });
      void qc.invalidateQueries({ queryKey: ["enrolments"] });
      void qc.invalidateQueries({ queryKey: ["institutions"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => onStale(qc, id, err),
  });
}

export function useDismissSignal(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SignalDismiss) => api.post<SignalDetail>(`/signals/${id}/dismiss`, body),
    onSuccess: (signal) => {
      qc.setQueryData(signalKeys.one(id), signal);
      void qc.invalidateQueries({ queryKey: ["signals", "list"] });
      void qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (err) => onStale(qc, id, err),
  });
}

/* ---- Reports (A4.21) ------------------------------------------------------ */

export function useReports() {
  return useQuery({ queryKey: signalKeys.reports, queryFn: () => api.get<ItemsEnvelope<ReportInfo>>("/reports"), staleTime: 5 * 60_000 });
}

export function reportPath(name: ReportName, format: ReportFormat): string {
  return `/reports/${name}.${format}`;
}

/** `?academic_year=...` for a report link; the server fills the role's scope. */
export function reportQuery(params: ReportQuery): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** One CSV line into cells, with quoted fields and doubled quotes (RFC 4180). */
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (quoted) {
      if (c === '"' && line[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      out.push(cell);
      cell = "";
    } else cell += c;
  }
  out.push(cell);
  return out;
}

export interface ReportPreview {
  columns: string[];
  rows: string[][];
  total: number;
}

/** Parses a report CSV: a BOM and a leading synthetic-data line are skipped, the header is the first row with every column. */
export function parseReportCsv(text: string, limit: number): ReportPreview {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/).filter((l) => l.length > 0);
  let at = 0;
  while (at < lines.length && splitCsvLine(lines[at]).length < 2) at++;
  const columns = at < lines.length ? splitCsvLine(lines[at]) : [];
  const body = lines.slice(at + 1).map(splitCsvLine);
  return { columns, rows: body.slice(0, limit), total: body.length };
}

/**
 * The first rows of a report, read from its CSV: the contract has no
 * preview route, and the CSV is what the officer downloads, so the preview
 * shows exactly the file's columns and order.
 */
export function useReportPreview(name: ReportName | null, params: ReportQuery, limit = 25) {
  return useQuery({
    queryKey: signalKeys.preview(name ?? "summary", params),
    enabled: name !== null,
    retry: false,
    queryFn: async ({ signal }): Promise<ReportPreview> => {
      const path = `${reportPath(name!, "csv")}${reportQuery(params)}`;
      if (MOCK_API) {
        const { mockDownload } = await import("@/lib/mock/handler");
        const { blob } = await mockDownload(path);
        return parseReportCsv(await blob.text(), limit);
      }
      let res: Response;
      try {
        res = await fetch(`${API_BASE}${path}`, { credentials: "include", cache: "no-store", signal });
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") throw err;
        throw new ApiError(0, "NETWORK", t("err.NETWORK"));
      }
      const text = await res.text();
      if (!res.ok) {
        let body: unknown;
        try {
          body = JSON.parse(text);
        } catch {
          body = undefined;
        }
        throw toApiError(res.status, body);
      }
      return parseReportCsv(text, limit);
    },
  });
}
