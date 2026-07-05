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

// 运维工具模板
export function getOpsTools(params?: Record<string, any>) {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/ops/tools", { params });
}
export function upsertOpsTool(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/ops/tools", { data });
}
// 运维任务申请
export function createOpsRun(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/ops/runs", { data });
}
export function getOpsRuns(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/ops/runs", { params });
}
export function approveOpsRun(runId: number, data: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/ops/runs/${runId}/approve`, { data });
}
export function rejectOpsRun(runId: number, params: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/ops/runs/${runId}/reject`, { params });
}
export function executeOpsRun(runId: number) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/runs/${runId}/execute`);
}
export function getOpsRunAudit(runId: number) {
  return http.request<ApiResponse<any>>("get", `/api/v1/ops/runs/${runId}/audit`);
}
