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
// 账号
export function getAccounts(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/identity/accounts", { params });
}
export function bindAccount(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/identity/accounts/bind", { data });
}
// 同步差异
export function getSyncDiffs(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/identity/sync-diffs", { params });
}
export function collectSources() {
  return http.request<ApiResponse<any>>("post", "/api/v1/identity/collect-sources");
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
