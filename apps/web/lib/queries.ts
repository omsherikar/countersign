"use client";

/**
 * TanStack Query hooks, one per endpoint. Keys start with the path so a
 * mutation can invalidate a whole family (e.g. ["institutions"]).
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type {
  AdapterPing,
  AuditVerify,
  ChaosRequest,
  ChaosState,
  DashboardSummary,
  EnrolmentListParams,
  EnrolmentRow,
  Health,
  InstitutionDetail,
  InstitutionListParams,
  InstitutionRow,
  ItemsEnvelope,
  LoginRequest,
  Page,
  RegionMeta,
  SeatListParams,
  SeatRow,
  StateMeta,
  StudentMe,
  User,
  UserEnvelope,
} from "@/lib/types";

const FOREVER = Number.POSITIVE_INFINITY;

export const keys = {
  me: ["me"] as const,
  summary: (academicYear?: string) => ["dashboard", "summary", academicYear ?? "current"] as const,
  institutions: (params: InstitutionListParams) => ["institutions", "list", params] as const,
  institution: (id: string) => ["institutions", id] as const,
  seats: (id: string, params: SeatListParams) => ["institutions", id, "seats", params] as const,
  enrolments: (id: string, params: EnrolmentListParams) => ["institutions", id, "enrolments", params] as const,
  studentMe: ["students", "me"] as const,
  ping: ["admin", "adapters", "ping"] as const,
  chaos: ["admin", "chaos"] as const,
  health: ["healthz"] as const,
  regions: ["meta", "regions"] as const,
  states: ["meta", "states"] as const,
};

/* ---- Session ------------------------------------------------------------- */

/** GET /me without the 401 redirect: a signed-out visitor is a normal answer (null). */
export async function fetchMe(): Promise<User | null> {
  try {
    const res = await api.get<UserEnvelope>("/me", undefined, { redirectOn401: false });
    return res.user;
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export function useMeQuery(enabled = true) {
  return useQuery({ queryKey: keys.me, queryFn: fetchMe, staleTime: FOREVER, enabled, retry: false });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) => api.post<UserEnvelope>("/auth/login", body, { redirectOn401: false }),
    onSuccess: (res) => {
      qc.clear();
      qc.setQueryData(keys.me, res.user);
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout", {}, { redirectOn401: false }),
    onSettled: () => qc.clear(),
  });
}

/* ---- Meta ---------------------------------------------------------------- */

export function useRegions() {
  return useQuery({
    queryKey: keys.regions,
    queryFn: () => api.get<ItemsEnvelope<RegionMeta>>("/meta/regions"),
    staleTime: FOREVER,
    select: (d) => d.items,
  });
}

export function useStates() {
  return useQuery({
    queryKey: keys.states,
    queryFn: () => api.get<ItemsEnvelope<StateMeta>>("/meta/states"),
    staleTime: FOREVER,
    select: (d) => d.items,
  });
}

/* ---- Dashboard and institutions ------------------------------------------ */

export function useDashboardSummary(academicYear?: string) {
  return useQuery({
    queryKey: keys.summary(academicYear),
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary", { academic_year: academicYear }),
  });
}

export function useInstitutions(params: InstitutionListParams, enabled = true) {
  return useQuery({
    queryKey: keys.institutions(params),
    queryFn: ({ signal }) => api.get<Page<InstitutionRow>>("/institutions", { ...params }, { signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useInstitution(id: string | null | undefined) {
  return useQuery({
    queryKey: keys.institution(id ?? ""),
    queryFn: () => api.get<InstitutionDetail>(`/institutions/${id}`),
    enabled: Boolean(id),
  });
}

export function useInstitutionSeats(id: string, params: SeatListParams, enabled = true) {
  return useQuery({
    queryKey: keys.seats(id, params),
    queryFn: ({ signal }) => api.get<Page<SeatRow>>(`/institutions/${id}/seats`, { ...params }, { signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useInstitutionEnrolments(id: string, params: EnrolmentListParams, enabled = true) {
  return useQuery({
    queryKey: keys.enrolments(id, params),
    queryFn: ({ signal }) => api.get<Page<EnrolmentRow>>(`/institutions/${id}/enrolments`, { ...params }, { signal }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

/* ---- Student ------------------------------------------------------------- */

export function useStudentMe() {
  return useQuery({ queryKey: keys.studentMe, queryFn: () => api.get<StudentMe>("/students/me") });
}

/* ---- Admin --------------------------------------------------------------- */

/** Sources health; refreshes every 60 s and on window focus (page 2, Sources panel). */
export function useAdapterPing(enabled = true) {
  return useQuery({
    queryKey: keys.ping,
    queryFn: () => api.get<AdapterPing>("/admin/adapters/ping"),
    enabled,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    retry: false,
  });
}

/** Walks the whole chain, so it runs on a button press, not on load. */
export function useAuditVerify() {
  return useMutation({ mutationFn: () => api.get<AuditVerify>("/admin/audit/verify") });
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: () => api.get<Health>("/healthz"), retry: false });
}

export function useChaos(enabled = true) {
  return useQuery({ queryKey: keys.chaos, queryFn: () => api.get<ChaosState>("/admin/chaos"), enabled, retry: false });
}

export function useApplyChaos() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ChaosRequest) => api.post<Partial<ChaosState>>("/admin/chaos", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.chaos });
      void qc.invalidateQueries({ queryKey: keys.ping });
    },
  });
}

export function useResetChaos() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ChaosState>("/admin/chaos/reset", {}),
    onSuccess: (data) => {
      qc.setQueryData(keys.chaos, data);
      void qc.invalidateQueries({ queryKey: keys.ping });
    },
  });
}
