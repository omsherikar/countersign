"use client";

/**
 * TanStack Query hooks for officer case work, the college response, the
 * audit log, data requests and notice resends (API_CONTRACT A3.5, A3.10 to
 * A3.14, A3.22 and A3.23). Keys start with the path, as in lib/queries.ts,
 * so an action can invalidate a whole family.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import { keys } from "@/lib/queries";
import type {
  AuditListQuery,
  AuditRow,
  CaseActionRequest,
  CaseActionResult,
  CaseAttachment,
  DataRequestAdminRow,
  DataRequestListQuery,
  DataRequestResolve,
  DryRunResult,
  FlagDetail,
  NoticeResendResult,
  OfficerRow,
  Page,
} from "@/lib/types";

export const caseKeys = {
  officers: (flagId?: string) => ["users", "officers", flagId ?? "all"] as const,
  audit: (params: AuditListQuery) => ["admin", "audit", params] as const,
  dataRequests: (params: DataRequestListQuery) => ["data-requests", params] as const,
};

/** A decided flag changes its lists, the enrolments it names and the dashboard counts. */
function afterCaseChange(qc: QueryClient, flag?: FlagDetail) {
  if (flag) qc.setQueryData(keys.flag(flag.id), flag);
  void qc.invalidateQueries({ queryKey: ["flags", "list"] });
  void qc.invalidateQueries({ queryKey: ["enrolments"] });
  void qc.invalidateQueries({ queryKey: ["institutions"] });
  void qc.invalidateQueries({ queryKey: ["dashboard"] });
}

/** 409 FLAG_TRANSITION_INVALID means someone decided meanwhile: show the latest status. */
function refetchOnStale(qc: QueryClient, flagId: string, err: unknown) {
  if (err instanceof ApiError && (err.code === "FLAG_TRANSITION_INVALID" || err.status === 404)) {
    void qc.invalidateQueries({ queryKey: keys.flag(flagId) });
    void qc.invalidateQueries({ queryKey: ["flags", "list"] });
  }
}

/**
 * POST /flags/{id}/actions (A4.9): the case after the action and its
 * `effects`. A decision changes records, seats and attestations, so every
 * record, list and count that might show them is refetched.
 */
export function useCaseAction(flagId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CaseActionRequest) => api.post<CaseActionResult>(`/flags/${flagId}/actions`, { ...body, dry_run: undefined }),
    onSuccess: (result) => {
      const { effects: _effects, ...flag } = result;
      void _effects;
      afterCaseChange(qc, flag);
      void qc.invalidateQueries({ queryKey: ["students", "me"] });
      void qc.invalidateQueries({ queryKey: ["signals"] });
      void qc.invalidateQueries({ queryKey: ["university"] });
    },
    onError: (err) => {
      refetchOnStale(qc, flagId, err);
      // The records a case names changed under the officer: show the case as it is now.
      if (err instanceof ApiError && err.code === "WITHDRAW_NOT_NAMED") void qc.invalidateQueries({ queryKey: keys.flag(flagId) });
    },
  });
}

/**
 * The consequences of a decision before it is made (A4.9 `dry_run`): the
 * same checks and effects as the real action, rolled back. The sheet sends
 * the body it would submit; nothing is stored, audited or emailed.
 */
export function useDecisionPreview(flagId: string, body: CaseActionRequest | null) {
  return useQuery({
    queryKey: ["flags", flagId, "preview", body] as const,
    queryFn: ({ signal }) => api.post<DryRunResult>(`/flags/${flagId}/actions`, { ...body, dry_run: true }, { signal }),
    enabled: body !== null,
    retry: false,
    staleTime: 0,
    gcTime: 30_000,
    select: (d) => d.effects,
  });
}

export interface CollegeResponseInput {
  note: string;
  files: File[];
  onProgress?: (pct: number) => void;
}

/** POST /flags/{id}/response as multipart/form-data (A3.11): a note and up to three files named "files". */
export function useCollegeResponse(flagId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ note, files, onProgress }: CollegeResponseInput) => {
      const form = new FormData();
      form.append("note", note);
      for (const file of files) form.append("files", file, file.name);
      return api.upload<FlagDetail>(`/flags/${flagId}/response`, form, { onProgress });
    },
    onSuccess: (flag) => afterCaseChange(qc, flag),
    onError: (err) => refetchOnStale(qc, flagId, err),
  });
}

/** GET /flags/{id}/attachments/{attachment_id} (A3.12), saved under its own name. Each download is audited. */
export function downloadAttachment(flagId: string, attachment: CaseAttachment): Promise<string> {
  return api.download(`/flags/${flagId}/attachments/${attachment.id}`, attachment.filename);
}

/** GET /users for the assignee picker and the audit Actor filter (A3.14). Officers only. */
export function useOfficers(flagId?: string, enabled = true) {
  return useQuery({
    queryKey: caseKeys.officers(flagId),
    queryFn: () => api.get<Page<OfficerRow>>("/users", { role: "AICTE_ADMIN,RO_OFFICER", flag_id: flagId, page_size: 200 }),
    staleTime: 5 * 60_000,
    select: (d) => d.items,
    enabled,
  });
}

/* ---- Audit (A3.23) -------------------------------------------------------- */

export function useAudit(params: AuditListQuery) {
  return useQuery({
    queryKey: caseKeys.audit(params),
    queryFn: ({ signal }) => api.get<Page<AuditRow>>("/admin/audit", { ...params }, { signal }),
    placeholderData: keepPreviousData,
  });
}

/* ---- Data requests (A3.22) ------------------------------------------------ */

export function useDataRequests(params: DataRequestListQuery) {
  return useQuery({
    queryKey: caseKeys.dataRequests(params),
    queryFn: ({ signal }) => api.get<Page<DataRequestAdminRow>>("/data-requests", { ...params }, { signal }),
    placeholderData: keepPreviousData,
  });
}

/**
 * POST /data-requests/{id}/resolve. The resolved row is written into the
 * lists in place, so it stays in view with its new status and date until the
 * officer changes the filter; the lists refetch on their next use.
 */
export function useResolveDataRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: DataRequestResolve }) => api.post<DataRequestAdminRow>(`/data-requests/${id}/resolve`, body),
    onSuccess: (row) => {
      qc.setQueriesData<Page<DataRequestAdminRow>>({ queryKey: ["data-requests"] }, (old) =>
        old ? { ...old, items: old.items.map((r) => (r.id === row.id ? row : r)) } : old,
      );
      void qc.invalidateQueries({ queryKey: ["data-requests"], refetchType: "none" });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 409) void qc.invalidateQueries({ queryKey: ["data-requests"] });
    },
  });
}

/* ---- Notices (A3.5) ------------------------------------------------------- */

/**
 * The student's comment on a No reaches officers only through the Student
 * denied flag's evidence (A3.7, A3.8); the enrolment never carries it. Shares
 * the flag detail cache.
 */
export function useStudentComment(flagId: string | undefined, label: string) {
  return useQuery({
    queryKey: keys.flag(flagId ?? ""),
    queryFn: () => api.get<FlagDetail>(`/flags/${flagId}`),
    enabled: Boolean(flagId),
    select: (flag) => flag.evidence.facts.find((f) => f.label === label)?.value ?? null,
  });
}

/** POST /enrolments/{id}/notices/resend; the enrolment refetches so the block and the Student check follow. */
export function useResendNotice(enrolmentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<NoticeResendResult>(`/enrolments/${enrolmentId}/notices/resend`, {}),
    onSettled: () => void qc.invalidateQueries({ queryKey: keys.enrolment(enrolmentId) }),
  });
}

/** POST /credentials/{id}/revoke (AICTE only); the enrolment refetches so its proofs list follows. */
export function useRevokeCredential(enrolmentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.post<unknown>(`/credentials/${id}/revoke`, { reason }),
    onSettled: () => void qc.invalidateQueries({ queryKey: keys.enrolment(enrolmentId) }),
  });
}
