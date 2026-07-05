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

// 元数据采集
export function collectMetadata(sourceCode: string, data?: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", `/api/v1/sources/${sourceCode}/collect-metadata`, { data });
}
export function getSourceSnapshots(sourceCode: string, params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", `/api/v1/sources/${sourceCode}/snapshots`, { params });
}
// 变更事件
export function getMetadataChanges(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/metadata-changes", { params });
}
export function updateMetadataChange(id: number, params: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/metadata-changes/${id}`, { params });
}
export function getChangesSummary() {
  return http.request<ApiResponse<any>>("get", "/api/v1/metadata-changes/summary");
}
export function getChangeImpact(id: number) {
  return http.request<ApiResponse<any>>("get", `/api/v1/metadata-changes/${id}/impact`);
}
// diff 对比
export function runMetadataDiff(params: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/metadata-changes/diff", { params });
}
