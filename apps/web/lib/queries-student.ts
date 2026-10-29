"use client";

/**
 * TanStack Query hooks for the student notice, wallet, privacy, verifier and
 * university certificate integration pages (API_CONTRACT Addenda 3 and 4). Same pattern as
 * lib/queries.ts: one hook per endpoint, keys start with the path.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { keys } from "@/lib/queries";
import type {
  AccessLogRow,
  CertificatePrint,
  ConsentPurpose,
  ConsentsView,
  ConsentWithdrawResult,
  CredentialCard,
  CredentialDetail,
  DataRequestCreate,
  DataRequestRow,
  GraduateListQuery,
  GraduateRow,
  NoticePublic,
  NoticeRespondRequest,
  Page,
  PresentationCreated,
  PresentRequest,
  PrivacyNotice,
  VerifyResult,
} from "@/lib/types";

export const studentKeys = {
  notice: (token: string) => ["notices", token] as const,
  credentials: ["credentials", "list"] as const,
  credential: (id: string) => ["credentials", id] as const,
  privacyNotice: ["privacy", "notice"] as const,
  consents: ["students", "me", "consents"] as const,
  accessLog: ["students", "me", "access-log"] as const,
  dataRequests: ["students", "me", "data-requests"] as const,
  verifyCode: (code: string) => ["verify", "code", code] as const,
  verifyDegree: (jws: string) => ["verify", "d", jws] as const,
  verifyLookup: (shortId: string) => ["verify", "completion", shortId] as const,
  graduates: (params: GraduateListQuery) => ["university", "graduates", params] as const,
  certificate: (enrolmentId: string) => ["university", "certificates", enrolmentId] as const,
};

/** Every answer of a public or student route is final (404, 409, 410, 429); only a dropped connection is worth one more try. */
const once = { retry: false } as const;

/* ---- Public notice (A3.3, A3.4) ------------------------------------------ */

export function useNotice(token: string) {
  return useQuery({
    queryKey: studentKeys.notice(token),
    queryFn: () => api.get<NoticePublic>(`/notices/${encodeURIComponent(token)}`, undefined, { redirectOn401: false }),
    ...once,
  });
}

export function useRespondNotice(token: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NoticeRespondRequest) =>
      api.post<NoticePublic>(`/notices/${encodeURIComponent(token)}/respond`, body, { redirectOn401: false }),
    onSuccess: (notice) => qc.setQueryData(studentKeys.notice(token), notice),
  });
}

/* ---- Wallet (A3.16, A3.17) ----------------------------------------------- */

export function useCredentials() {
  return useQuery({
    queryKey: studentKeys.credentials,
    queryFn: () => api.get<Page<CredentialCard>>("/credentials", { page_size: 50 }),
  });
}

export function useCredential(id: string, enabled: boolean) {
  return useQuery({
    queryKey: studentKeys.credential(id),
    queryFn: () => api.get<CredentialDetail>(`/credentials/${id}`),
    enabled,
  });
}

export function usePresent(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PresentRequest) => api.post<PresentationCreated>(`/credentials/${id}/present`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: studentKeys.credentials });
      qc.invalidateQueries({ queryKey: studentKeys.consents });
    },
  });
}

/* ---- Privacy (A3.22) ----------------------------------------------------- */

export function usePrivacyNotice() {
  return useQuery({ queryKey: studentKeys.privacyNotice, queryFn: () => api.get<PrivacyNotice>("/privacy/notice"), staleTime: Infinity });
}

export function useConsents() {
  return useQuery({ queryKey: studentKeys.consents, queryFn: () => api.get<ConsentsView>("/students/me/consents") });
}

export function useWithdrawConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (purpose: Extract<ConsentPurpose, "NOTICE" | "CREDENTIAL_SHARE">) =>
      api.post<ConsentWithdrawResult>(`/students/me/consents/${purpose}/withdraw`),
    onSuccess: (view) => {
      qc.setQueryData(studentKeys.consents, { current: view.current, items: view.items });
      qc.invalidateQueries({ queryKey: studentKeys.credentials });
      qc.invalidateQueries({ queryKey: keys.studentMe, exact: true });
    },
  });
}

/** The access log, one page of 25 at a time; "Show older" asks for the next page. */
export function useAccessLog(page: number) {
  return useQuery({
    queryKey: [...studentKeys.accessLog, page],
    queryFn: () => api.get<Page<AccessLogRow>>("/students/me/access-log", { page, page_size: 25 }),
    placeholderData: keepPreviousData,
  });
}

export function useDataRequests() {
  return useQuery({
    queryKey: studentKeys.dataRequests,
    queryFn: () => api.get<Page<DataRequestRow>>("/students/me/data-requests", { page_size: 50 }),
  });
}

export function useCreateDataRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DataRequestCreate) => api.post<DataRequestRow>("/students/me/data-requests", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: studentKeys.dataRequests }),
  });
}

/* ---- Verifier (A3.20), public -------------------------------------------- */

export function useVerifyCode(code: string) {
  return useQuery({
    queryKey: studentKeys.verifyCode(code),
    queryFn: () => api.get<VerifyResult>(`/verify/${encodeURIComponent(code)}`, undefined, { redirectOn401: false }),
    // Every call counts as a check in the student's history: never refetch on our own.
    staleTime: Infinity,
    ...once,
  });
}

export function useVerifyPaste() {
  return useMutation({
    mutationFn: (presentation: string) => api.post<VerifyResult>("/verify", { presentation }, { redirectOn401: false }),
  });
}

export function useVerifyDegree(jws: string) {
  return useQuery({
    queryKey: studentKeys.verifyDegree(jws),
    queryFn: () => api.get<VerifyResult>(`/verify/d/${jws}`, undefined, { redirectOn401: false }),
    staleTime: Infinity,
    ...once,
  });
}

export function useVerifyLookup(shortId: string) {
  return useQuery({
    queryKey: studentKeys.verifyLookup(shortId),
    queryFn: () => api.get<VerifyResult>(`/verify/completion/${encodeURIComponent(shortId)}`, undefined, { redirectOn401: false }),
    staleTime: Infinity,
    ...once,
  });
}

/* ---- University certificate integration (A3.21, A4.15) -------------------- */

export function useGraduates(params: GraduateListQuery) {
  return useQuery({
    queryKey: studentKeys.graduates(params),
    queryFn: ({ signal }) => api.get<Page<GraduateRow>>("/university/graduates", { ...params }, { signal }),
    placeholderData: keepPreviousData,
  });
}

export function useIssueCompletion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enrolmentId: string) => api.post<CertificatePrint>(`/university/certificates/${enrolmentId}/issue`),
    onSuccess: (print) => {
      qc.setQueryData(studentKeys.certificate(print.enrolment_id), print);
      qc.invalidateQueries({ queryKey: ["university", "graduates"] });
    },
  });
}

export function useCertificatePrint(enrolmentId: string) {
  return useQuery({ queryKey: studentKeys.certificate(enrolmentId), queryFn: () => api.get<CertificatePrint>(`/university/certificates/${enrolmentId}`) });
}
