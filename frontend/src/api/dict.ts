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

// 诊断/手术编码体系
export function getMedicalCodeSets(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/dict-medical/code-sets", { params });
}
export function upsertMedicalCodeSet(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/dict-medical/code-sets", { data });
}
// 编码项
export function getMedicalItems(codeSetCode: string, params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", `/api/v1/dict-medical/code-sets/${codeSetCode}/items`, { params });
}
export function upsertMedicalItem(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/dict-medical/items", { data });
}
// 对照关系
export function getMedicalMappings(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/dict-medical/mappings", { params });
}
export function upsertMedicalMapping(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/dict-medical/mappings", { data });
}
// 同步差异
export function getMedicalSyncDiffs(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/dict-medical/sync-diffs", { params });
}
// 版本
export function getDictVersions(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/dict-medical/versions", { params });
}
// 变更请求
export function createMedicalChangeRequest(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/dict-medical/change-requests", { data });
}
export function listMedicalChangeRequests(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/dict-medical/change-requests", { params });
}

// 通用字典
export function getDictCategories(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/dictionaries/categories", { params });
}
export function upsertDictCategory(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/dictionaries/categories", { data });
}
export function getDictStandardItems(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/dictionaries/standard-items", { params });
}
export function upsertDictStandardItem(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/dictionaries/standard-items", { data });
}
export function getDictSystemItems(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/dictionaries/system-items", { params });
}
export function getDictItemMappings(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/dictionaries/mappings", { params });
}
export function upsertDictItemMapping(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/dictionaries/mappings", { data });
}
export function importSystemDict(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/dictionaries/import", { data });
}
