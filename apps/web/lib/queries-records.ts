"use client";

/**
 * Query hooks for the record pages (API_CONTRACT Addendum 4): the record's
 * history, completeness and missing students, the saved column mapping and
 * approval versions. Same pattern as lib/queries.ts.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, request } from "@/lib/api";
import type {
  ApprovalVersions,
  ColumnMapping,
  ColumnMappingPut,
  CompletenessPage,
  CompletenessQuery,
  EnrolmentVersion,
  InstitutionCompleteness,
  Page,
} from "@/lib/types";

export const recordKeys = {
  history: (id: string, page: number) => ["enrolments", id, "history", page] as const,
  completeness: (institutionId: string, academicYear: string) => ["institutions", institutionId, "completeness", academicYear] as const,
  completenessList: (params: CompletenessQuery) => ["completeness", "list", params] as const,
  mapping: (institutionId: string) => ["institutions", institutionId, "column-mapping"] as const,
  approval: (approvalId: string) => ["approvals", approvalId, "versions"] as const,
};

/** GET /enrolments/{id}/history (A4.7): versions, newest first. */
export function useEnrolmentHistory(id: string, page: number, enabled = true) {
  return useQuery({
    queryKey: recordKeys.history(id, page),
    queryFn: ({ signal }) => api.get<Page<EnrolmentVersion>>(`/enrolments/${id}/history`, { page, page_size: 25 }, { signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** GET /institutions/{id}/completeness (A4.18). */
export function useCompleteness(institutionId: string | null | undefined, academicYear: string) {
  return useQuery({
    queryKey: recordKeys.completeness(institutionId ?? "", academicYear),
    queryFn: () => api.get<InstitutionCompleteness>(`/institutions/${institutionId}/completeness`, { academic_year: academicYear }),
    enabled: Boolean(institutionId),
  });
}

/** GET /completeness (A4.18), officers only. */
export function useCompletenessList(params: CompletenessQuery, enabled = true) {
  return useQuery({
    queryKey: recordKeys.completenessList(params),
    queryFn: ({ signal }) => api.get<CompletenessPage>("/completeness", { ...params }, { signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** GET /institutions/{id}/column-mapping (A4.16). */
export function useColumnMapping(institutionId: string | null | undefined) {
  return useQuery({
    queryKey: recordKeys.mapping(institutionId ?? ""),
    queryFn: () => api.get<ColumnMapping>(`/institutions/${institutionId}/column-mapping`),
    enabled: Boolean(institutionId),
  });
}

/** PUT /institutions/{id}/column-mapping: replaces the whole mapping; `{}` clears it. */
export function useSaveColumnMapping(institutionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ColumnMappingPut) => request<ColumnMapping>(`/institutions/${institutionId}/column-mapping`, { method: "PUT", body }),
    onSuccess: (data) => qc.setQueryData(recordKeys.mapping(institutionId), data),
  });
}

/** GET /approvals/{id}/versions (A4.17). */
export function useApprovalVersions(approvalId: string | null | undefined) {
  return useQuery({
    queryKey: recordKeys.approval(approvalId ?? ""),
    queryFn: () => api.get<ApprovalVersions>(`/approvals/${approvalId}/versions`),
    enabled: Boolean(approvalId),
  });
}
