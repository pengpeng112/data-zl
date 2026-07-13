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

export interface OpsTool {
  id?: number;
  tool_code: string;
  tool_name_cn: string;
  system_code: string;
  source_code?: string | null;
  tool_type: string;
  risk_level: string;
  input_schema?: Record<string, any>;
  execution_mode: string;
  sql_or_endpoint_ref?: string | null;
  allowed_tables?: string[];
  allowed_operations?: string[];
  require_audit?: boolean;
  dry_run_sql?: string | null;
  max_affected_rows?: number;
  write_credential_ref?: string | null;
  require_approval: boolean;
  require_second_confirm: boolean;
  enabled: boolean;
  description_cn?: string | null;
  rollback_note_cn?: string | null;
}

export interface OpsRun {
  id: number;
  tool_code: string;
  requested_by: string;
  approved_by?: string | null;
  approval_status: string;
  affected_count?: number | null;
  risk_scan?: Record<string, any> | null;
  execution_summary?: string | null;
  created_at?: string | null;
}

export function getOpsTools(params?: Record<string, any>) {
  return http.request<ApiResponse<OpsTool[]>>("get", "/api/v1/ops/tools", { params });
}

export function upsertOpsTool(data: Partial<OpsTool>) {
  return http.request<ApiResponse<any>>("put", "/api/v1/ops/tools", { data });
}

export function createOpsRun(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/ops/runs", { data });
}

export function getOpsRuns(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<OpsRun>>>("get", "/api/v1/ops/runs", { params });
}

export function submitOpsRun(runId: number, data: Record<string, any> = {}) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/runs/${runId}/submit`, { data });
}

export function approveOpsRun(runId: number, data: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/ops/runs/${runId}/approve`, { data });
}

export function rejectOpsRun(runId: number, data: Record<string, any>) {
  return http.request<ApiResponse<any>>("patch", `/api/v1/ops/runs/${runId}/reject`, { data });
}

export function dryRunOpsRun(runId: number, data: Record<string, any> = {}) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/runs/${runId}/dry-run`, { data });
}

export function executeOpsRun(runId: number, data: Record<string, any> = {}) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/runs/${runId}/execute`, { data });
}

export function getOpsRunAudit(runId: number) {
  return http.request<ApiResponse<any[]>>("get", `/api/v1/ops/runs/${runId}/audit`);
}
