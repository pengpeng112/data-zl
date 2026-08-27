import { http } from "@/utils/http";


export type { ApiResponse, PageData } from "./types";
import type { ApiResponse, PageData } from "./types";

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
  return http.request<ApiResponse<PageData<OpsTool>>>("get", "/api/v1/ops/tools", { params });
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

// ── SQL 工作台 ──

export function validateOpsSql(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/ops/sql/validate", { data });
}

export function createSqlTemplate(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/ops/sql/templates", { data });
}

export function submitSqlTemplate(toolCode: string, data: Record<string, any> = {}) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/sql/templates/${toolCode}/submit`, { data });
}

export function approveSqlTemplate(toolCode: string, data: Record<string, any> = {}) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/sql/templates/${toolCode}/approve`, { data });
}

export function rejectSqlTemplate(toolCode: string, data: Record<string, any> = {}) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/sql/templates/${toolCode}/reject`, { data });
}

export function createSqlRun(data: Record<string, any>) {
  return http.request<ApiResponse<any>>("post", "/api/v1/ops/sql/runs", { data });
}

export function previewSqlRun(runId: number) {
  return http.request<ApiResponse<any>>("post", `/api/v1/ops/sql/runs/${runId}/preview`);
}

export function getOpsConfig() {
  return http.request<ApiResponse<{
    ops_write_enabled: boolean;
    ops_approval_ui_enabled: boolean;
    write_scope: string;
  }>>("get", "/api/v1/ops/config");
}

export function listConnectionTargets() {
  return http.request<ApiResponse<any[]>>("get", "/api/v1/connections-targets");
}

export function listSqlRuns(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/ops/sql/runs", { params });
}

export function getSqlRun(runId: number) {
  return http.request<ApiResponse<any>>("get", `/api/v1/ops/sql/runs/${runId}`);
}

export function listOpsEvents(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/ops/events", { params });
}

// 146 D3：治理审计与平台健康（视图层不再裸 http.request）
export function getGovernAuditLogs(params?: Record<string, any>) {
  return http.request<ApiResponse<PageData<any>>>("get", "/api/v1/govern/audit-logs", { params });
}

export function getAuditLogsSummary(params?: Record<string, any>) {
  return http.request<ApiResponse<{ total: number; by_module: Record<string, number>; by_action: Record<string, number>; by_operator: Record<string, number> }>>("get", "/api/v1/govern/audit-logs/summary", { params });
}

export function exportAuditLogs(params?: Record<string, any>) {
  return http.request<Blob>("get", "/api/v1/govern/audit-logs/export", { params, responseType: "blob" });
}

export function getPlatformHealth() {
  return http.request<ApiResponse<Record<string, unknown>>>("get", "/api/v1/health");
}
