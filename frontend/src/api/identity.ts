import { http } from "@/utils/http";


export type { ApiResponse, PageData } from "./types";
import type { ApiResponse, PageData } from "./types";

// ===== F2：实体 interface（字段名以平台 openapi 为准，防漂移） =====

export interface IdentityDepartment {
  dept_code: string;
  dept_name_cn?: string | null;
  parent_dept_code?: string | null;
  source_code?: string | null;
  status?: string | null;
  last_source_sync_at?: string | null;
  [key: string]: unknown;
}

export interface IdentityPerson {
  person_code: string;
  person_name_cn?: string | null;
  dept_code?: string | null;
  title_code?: string | null;
  practice_no?: string | null;
  person_tags?: string[] | null;
  status?: string | null;
  [key: string]: unknown;
}

export interface IdentityAccount {
  id: number;
  system_code?: string | null;
  account_code?: string | null;
  person_code?: string | null;
  account_name?: string | null;
  status?: string | null;
  last_verified_at?: string | null;
  [key: string]: unknown;
}

export interface IdentitySyncRun {
  run_id?: string | number;
  status?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  scanned?: number;
  diffs_created?: number;
  [key: string]: unknown;
}

export interface IdentitySyncDiff {
  id: number;
  entity_type?: string | null;
  diff_type?: string | null;
  severity?: string | null;
  status?: string | null;
  source_code?: string | null;
  payload?: Record<string, unknown> | null;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface IdentityChangeRequest {
  id: number;
  request_kind?: string | null;
  target_user_identifier?: string | null;
  approval_status?: string | null;
  request_payload?: Record<string, unknown> | null;
  created_at?: string | null;
  [key: string]: unknown;
}

// ===== 端点 =====

// 科室基线
export function getDepartments(params?: Record<string, unknown>) {
  return http.request<ApiResponse<IdentityDepartment[]>>("get", "/api/v1/identity/departments", { params });
}
export function getDepartmentDetail(deptCode: string) {
  return http.request<ApiResponse<IdentityDepartment>>("get", `/api/v1/identity/departments/${deptCode}`);
}
// 人员
export function getPersons(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<IdentityPerson>>>("get", "/api/v1/identity/persons", { params });
}
export function getPersonProfile(personCode: string) {
  return http.request<ApiResponse<IdentityPerson>>("get", `/api/v1/identity/persons/${personCode}`);
}

export function createProfileChangeRequest(personCode: string, data: { profile_summary?: string | null; profile_tags: string[]; reason: string }) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", `/api/v1/identity/persons/${personCode}/profile-change-requests`, { data });
}
export function getProfileChangeRequests(personCode: string) {
  return http.request<ApiResponse<Record<string, unknown>[]>>("get", `/api/v1/identity/persons/${personCode}/profile-change-requests`);
}
// 账号
export function getAccounts(params?: { system_code?: string; keyword?: string; page?: number; page_size?: number }) {
  return http.request<ApiResponse<PageData<IdentityAccount>>>("get", "/api/v1/identity/accounts", { params });
}
export function unbindAccount(accountId: number, reason?: string) {
  return http.request<ApiResponse<{ id: number; person_code: null }>>("delete", `/api/v1/identity/accounts/${accountId}/binding`, { data: { reason } });
}
export function bindAccount(data: Record<string, unknown>) {
  return http.request<ApiResponse<IdentityAccount>>("put", "/api/v1/identity/accounts/bind", { data });
}
// 同步差异
export function getIdentitySyncRuns(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<IdentitySyncRun>>>("get", "/api/v1/identity-sync/runs", { params });
}
export function getIdentitySyncRun(runId: string) {
  return http.request<ApiResponse<Record<string, unknown>>>("get", `/api/v1/identity-sync/runs/${runId}`);
}
export function getSyncDiffs(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<IdentitySyncDiff>>>("get", "/api/v1/identity/sync-diffs", { params });
}
export function collectSources(data?: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/collect-sources", { data });
}
export function runIdentitySync(data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/sync/run", { data });
}
export function updateIdentitySyncDiff(id: number, data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("patch", `/api/v1/identity/sync-diffs/${id}`, { data });
}
/** L16：从差异提出主档变更（默认仅创建 change_request，需审批后 execute） */
export function proposeMasterFromDiff(diffId: number, data?: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", `/api/v1/identity/sync-diffs/${diffId}/propose-master`, {
    data: data ?? { use_prefer_source: true }
  });
}
/** L16 批量提出（最多 50） */
export function batchProposeMasterFromDiffs(data: {
  diff_ids: number[];
  use_prefer_source?: boolean;
}) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/sync-diffs/batch-propose-master", {
    data: { use_prefer_source: true, ...data }
  });
}
/** 批量更新差异状态 */
export function batchUpdateSyncDiffStatus(data: {
  diff_ids: number[];
  status: "open" | "resolved" | "ignored";
  note?: string;
}) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/sync-diffs/batch-status", { data });
}
export function batchApproveIdentityChangeRequests(data: { ids: number[]; note?: string }) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/change-requests/batch-approve", {
    data
  });
}
export function batchExecuteIdentityChangeRequests(data: { ids: number[] }) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/change-requests/batch-execute", {
    data
  });
}
export function syncHisIdentity(params?: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/sync/his", { params });
}
/** L13：生成复核差异，不自动覆盖主数据 */
export function generateIdentityReview(params?: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/review/generate", { params });
}
// 变更请求 (复用 asset_govern_change_requests, module='identity')
export function createIdentityChangeRequest(data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/identity/change-requests", { data });
}
export function listIdentityChangeRequests(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<IdentityChangeRequest>>>("get", "/api/v1/identity/change-requests", { params });
}
export function approveIdentityChangeRequest(id: number, data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("patch", `/api/v1/identity/change-requests/${id}/approve`, { data });
}
export function executeIdentityChangeRequest(id: number) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", `/api/v1/identity/change-requests/${id}/execute`);
}
