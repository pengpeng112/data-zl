import { http } from "@/utils/http";

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface PageData<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
  stats?: {
    total?: number;
    active?: number;
    inactive?: number;
    source_count?: number;
  };
}

// 科室基线
export function getDepartments(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/identity/departments", { params });
}
export function getDepartmentDetail(deptCode: string) {
  return http.request<ApiResponse<any>>("get", `/api/v1/identity/departments/${deptCode}`);
}
// 人员
export function getPersons(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/identity/persons", { params });
}
export function getPersonProfile(personCode: string) {
  return http.request<ApiResponse<any>>("get", `/api/v1/identity/persons/${personCode}`);
}

export function createProfileChangeRequest(personCode: string, data: { profile_summary?: string | null; profile_tags: string[]; reason: string }) {
  return http.request<ApiResponse<any>>("post", `/api/v1/identity/persons/${personCode}/profile-change-requests`, { data });
}
export function getProfileChangeRequests(personCode: string) {
  return http.request<ApiResponse<any[]>>("get", `/api/v1/identity/persons/${personCode}/profile-change-requests`);
}
// 账号
export function getAccounts(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/identity/accounts", { params });
}
export function bindAccount(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/identity/accounts/bind", { data });
}
// 同步差异
export function getIdentitySyncRuns(params?: Record<string, any>) {
  return http.request<ApiResponse<any>>("get", "/api/v1/identity-sync/runs", { params });
}
export function getIdentitySyncRun(runId: string) {
  return http.request<ApiResponse<any>>("get", `/api/v1/identity-sync/runs/${runId}`);
}
export function getSyncDiffs(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/identity/sync-diffs", { params });
}
export function collectSources(data?: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/collect-sources", { data });
}
export function runIdentitySync(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/sync/run", { data });
}
export function updateIdentitySyncDiff(id: number, data: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/identity/sync-diffs/${id}`, { data });
}
/** L16：从差异提出主档变更（默认仅创建 change_request，需审批后 execute） */
export function proposeMasterFromDiff(diffId: number, data?: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", `/api/v1/identity/sync-diffs/${diffId}/propose-master`, {
    data: data ?? { use_prefer_source: true }
  });
}
/** L16 批量提出（最多 50） */
export function batchProposeMasterFromDiffs(data: {
  diff_ids: number[];
  use_prefer_source?: boolean;
}) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/sync-diffs/batch-propose-master", {
    data: { use_prefer_source: true, ...data }
  });
}
/** 批量更新差异状态 */
export function batchUpdateSyncDiffStatus(data: {
  diff_ids: number[];
  status: "open" | "resolved" | "ignored";
  note?: string;
}) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/sync-diffs/batch-status", { data });
}
export function batchApproveIdentityChangeRequests(data: { ids: number[]; note?: string }) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/change-requests/batch-approve", {
    data
  });
}
export function batchExecuteIdentityChangeRequests(data: { ids: number[] }) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/change-requests/batch-execute", {
    data
  });
}
export function syncHisIdentity(params?: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/sync/his", { params });
}
/** L13：生成复核差异，不自动覆盖主数据 */
export function generateIdentityReview(params?: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/review/generate", { params });
}
// 变更请求 (复用 asset_govern_change_requests, module='identity')
export function createIdentityChangeRequest(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/change-requests", { data });
}
export function listIdentityChangeRequests(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/identity/change-requests", { params });
}
export function approveIdentityChangeRequest(id: number, data: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/identity/change-requests/${id}/approve`, { data });
}
export function executeIdentityChangeRequest(id: number) {
  return http.request<ApiResponse<any>>("post", `/api/v1/identity/change-requests/${id}/execute`);
}
export function getInconsistencies(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/identity/inconsistencies", { params });
}

