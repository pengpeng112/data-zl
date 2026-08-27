import { http } from "@/utils/http";
import type { ApiResponse } from "./asset";

// ===== 144 S8 typed query-center API layer =====

export interface QueryVersion {
  id: number;
  query_code: string;
  version: number;
  status: string;
  is_active: boolean;
  certification_status?: string;
  dialect?: string;
  sql_sha256?: string;
  sql_available?: string;
  sql_text?: string;
  parameter_schema?: Record<string, unknown> | null;
  semantic_contract?: Record<string, unknown> | null;
  grain?: string | null;
  period_field?: string | null;
  limitations?: string[] | null;
  unresolved_reason?: string | null;
  validated_at?: string | null;
  validation_digest?: string | null;
}

export interface QueryDefinition {
  id: number;
  query_code: string;
  title: string;
  system_code?: string | null;
  source_code?: string | null;
  status: string;
  current_version_id?: number | null;
  ai_readable?: boolean;
  versions?: QueryVersion[];
}

export interface QueryRun {
  id: number;
  query_code: string;
  version: number;
  status: string;
  row_count?: number | null;
  truncated?: boolean;
  duration_ms?: number | null;
  result_digest?: string | null;
  schema_digest?: string | null;
  data_as_of?: string | null;
  data_as_of_source?: string | null;
  error_class?: string | null;
  error_message?: string | null;
  correlation_id?: string | null;
  parameters_hash?: string | null;
  safe_parameters_summary?: Record<string, unknown> | null;
  run_batch?: string | null;
  sample?: Array<Record<string, unknown>>;
}

export interface QueryValidationReport {
  schema_version: string;
  overall: string;
  layers: Array<{
    layer: string;
    status: string;
    findings?: Array<{ code?: string; message?: string }>;
    tables?: Array<{ schema_name: string; object_name: string }>;
    used_relations?: number[];
    contract?: Record<string, unknown>;
  }>;
  validation_digest?: string;
}

export interface MetricVersion {
  id: number;
  metric_code: string;
  version: number;
  status: string;
  is_active: boolean;
  certification_status?: string;
  calculation_type?: string;
  precision?: number;
  rounding_mode?: string;
  definition_text?: string | null;
  numerator_desc?: string | null;
  denominator_desc?: string | null;
  formula?: string | null;
  query_code?: string | null;
  query_version?: number | null;
}

export interface MetricResultRow {
  id: number;
  metric_code: string;
  version: number;
  period_key: string;
  dimensions?: Record<string, unknown> | null;
  metric_value?: string | null;
  metric_num?: number | null;
  numerator_value?: string | null;
  denominator_value?: string | null;
  status: string;
  run_batch?: string | null;
  is_recalc?: boolean;
  data_as_of?: string | null;
  result_digest?: string | null;
}

export interface DataProduct {
  product_code: string;
  title: string;
  product_type: string;
  query_code?: string | null;
  metric_code?: string | null;
  pin_version?: number | null;
  revision?: number;
  enabled: boolean;
  parameter_schema?: Record<string, unknown> | null;
}

export interface AnswerEventResult {
  answer_event_id: number;
  question_digest: string;
}

export interface FeedbackRow {
  feedback_id: number;
  answer_event_id: number;
  rating: string;
  error_types?: string[];
  status: string;
  reviewed_by?: string | null;
  revision_query_code?: string | null;
  evaluation_case_id?: number | null;
  resolved_at?: string | null;
}

export interface EvaluationRunSummary {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  evaluation_set_version?: string;
  cases?: Array<{ case_code: string; status: string; run_id: number }>;
  note?: string;
}

export interface AccuracyDashboard {
  schema_version: string;
  audited_feedback_total: number;
  feedback_rating_distribution: Record<string, number>;
  error_type_trend: Record<string, number>;
  golden_case_runs_window: string;
  golden_pass: number;
  golden_fail: number;
  golden_error: number;
  golden_pass_rate: number | null;
  unevaluated_feedback: number;
  notes: string;
}

export interface ContextSnapshot {
  schema_version: string;
  context_id: string;
  generated_at: string;
  expires_at?: string;
  manifest_hash?: string;
  object_count?: number;
  query_count?: number;
  metric_count?: number;
  product_count?: number;
  truncated?: boolean;
  warnings?: string[];
  expired?: boolean;
}

export interface QueryGateResult {
  status: string;
  auto_activate?: boolean;
  errors?: string[];
  warnings?: string[];
}

export interface ScheduleItem {
  id?: number;
  query_code: string;
  source_code?: string | null;
  schedule_cron: string;
  enabled: boolean;
  result_storage?: string;
  last_status?: string | null;
  last_run_at?: string | null;
}

// ===== API functions =====

export function fetchQueries(params?: Record<string, unknown>) {
  return http.request<ApiResponse<{ items: QueryDefinition[]; total: number }>>(
    "get",
    "/api/v1/queries",
    { params }
  );
}

export function fetchQueryDetail(code: string) {
  return http.request<ApiResponse<QueryDefinition>>(
    "get",
    `/api/v1/queries/${encodeURIComponent(code)}`
  );
}

export function fetchQueryRuns(params: Record<string, unknown>) {
  return http.request<ApiResponse<{ items: QueryRun[]; total: number }>>(
    "get",
    "/api/v1/queries/runs/list",
    { params }
  );
}

export function fetchQueryRunDetail(runId: number) {
  return http.request<ApiResponse<QueryRun & { sample?: Array<Record<string, unknown>> }>>(
    "get",
    `/api/v1/queries/runs/${runId}`
  );
}

export function runQueryVersion(data: {
  query_code: string;
  version?: number;
  parameters?: Record<string, unknown>;
  result_storage?: string;
  max_rows?: number;
  recalc?: boolean;
  recalc_reason?: string;
}) {
  return http.request<ApiResponse<QueryRun & { sample?: unknown[] }>>(
    "post",
    "/api/v1/queries/run",
    { data }
  );
}

export function validateQueryVersion(code: string, version: number) {
  return http.request<ApiResponse<QueryValidationReport>>(
    "post",
    `/api/v1/queries/${encodeURIComponent(code)}/versions/${version}/validate`
  );
}

export function fetchQueryValidation(code: string, version: number) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "get",
    `/api/v1/queries/${encodeURIComponent(code)}/versions/${version}/validation`
  );
}

export function fetchMetrics(params?: Record<string, unknown>) {
  return http.request<ApiResponse<{ items: MetricVersion[]; total: number }>>(
    "get",
    "/api/v1/metrics",
    { params }
  );
}

export function calculateMetric(
  code: string,
  data: { version?: number; period_key: string; parameters?: Record<string, unknown>; dimensions?: Record<string, unknown> }
) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "post",
    `/api/v1/metrics/${encodeURIComponent(code)}/calculate`,
    { data }
  );
}

export function fetchMetricResults(code: string, params?: Record<string, unknown>) {
  return http.request<ApiResponse<{ items: MetricResultRow[]; total: number }>>(
    "get",
    `/api/v1/metrics/${encodeURIComponent(code)}/results`,
    { params }
  );
}

export function fetchDataProducts(params?: Record<string, unknown>) {
  return http.request<ApiResponse<{ items: DataProduct[]; total: number }>>(
    "get",
    "/api/v1/data-products",
    { params }
  );
}

export function executeDataProduct(
  code: string,
  data: { parameters?: Record<string, unknown>; execute_sql?: boolean; caller_id?: string }
) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "post",
    `/api/v1/data-products/${encodeURIComponent(code)}/execute`,
    { data }
  );
}

export function registerAnswerEvent(data: {
  question_summary: string;
  caller_id?: string;
  context_id?: string;
  query_code?: string;
  query_version?: number;
  run_id?: number;
  result_digest?: string;
  answer_text?: string;
}) {
  return http.request<ApiResponse<AnswerEventResult>>(
    "post",
    "/api/v1/ai/answers",
    { data }
  );
}

export function submitFeedback(data: {
  answer_event_id: number;
  rating: string;
  error_types?: string[];
  comment?: string;
  suggested_revision?: string;
}) {
  return http.request<ApiResponse<FeedbackRow>>("post", "/api/v1/ai/feedback", { data });
}

export function reviewFeedback(
  id: number,
  data: { action: string; review_note?: string; revision_query_code?: string; revision_query_version?: number }
) {
  return http.request<ApiResponse<FeedbackRow>>(
    "patch",
    `/api/v1/ai/feedback/${id}/review`,
    { data }
  );
}

export function fetchFeedback(id: number) {
  return http.request<ApiResponse<FeedbackRow>>("get", `/api/v1/ai/feedback/${id}`);
}

export function runEvaluation(data: {
  query_code?: string;
  query_version?: number;
  evaluation_set_version?: string;
}) {
  return http.request<ApiResponse<EvaluationRunSummary>>(
    "post",
    "/api/v1/ai/evaluations/run",
    { data }
  );
}

export function fetchAccuracyDashboard() {
  return http.request<ApiResponse<AccuracyDashboard>>(
    "get",
    "/api/v1/ai/evaluations/dashboard"
  );
}

export function resolveContext(data: {
  question_summary?: string;
  system_code?: string;
  business_domain?: string;
  max_objects?: number;
}) {
  return http.request<ApiResponse<ContextSnapshot>>(
    "post",
    "/api/v1/ai/context/resolve",
    { data }
  );
}

export function fetchContext(contextId: string) {
  return http.request<ApiResponse<ContextSnapshot>>(
    "get",
    `/api/v1/ai/context/${encodeURIComponent(contextId)}`
  );
}

export function fetchLineageImpact(params: { object_key?: string; table?: string; direction?: string }) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "get",
    "/api/v1/lineage/impact",
    { params }
  );
}

export function previewQueryGate(data: {
  sql_text: string;
  dialect: string;
  source_code: string;
}) {
  return http.request<ApiResponse<QueryGateResult>>("post", "/api/v1/queries/gate", { data });
}

export function ingestQuery(data: Record<string, unknown>) {
  return http.request<ApiResponse<{ idempotent?: boolean; version?: QueryVersion }>>(
    "post",
    "/api/v1/queries/ingest",
    { data }
  );
}

export function ingestMetric(data: Record<string, unknown>) {
  return http.request<ApiResponse<{ version?: MetricVersion }>>(
    "post",
    "/api/v1/metrics/ingest",
    { data }
  );
}

export function fetchMetricDetail(code: string) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "get",
    `/api/v1/metrics/${encodeURIComponent(code)}`
  );
}

export function publishCoreDataProducts() {
  return http.request<ApiResponse<{ count: number }>>(
    "post",
    "/api/v1/data-products/publish-core"
  );
}

export function fetchMetricBoard(params?: { period_from?: string; period_to?: string }) {
  return http.request<ApiResponse<{
    periods: string[];
    metrics: Array<Record<string, unknown>>;
    cells: Record<string, Record<string, Record<string, unknown>>>;
    total_results: number;
  }>>("get", "/api/v1/metrics/board/overview", { params });
}

export function fetchSchedules() {
  return http.request<ApiResponse<ScheduleItem[]>>(
    "get",
    "/api/v1/queries/schedules/list"
  );
}

export function seedCoreSchedules() {
  return http.request<ApiResponse<{ count: number }>>(
    "post",
    "/api/v1/queries/schedules/seed-core"
  );
}

export function upsertSchedule(data: {
  query_code: string;
  schedule_cron: string;
  source_code?: string | null;
  enabled: boolean;
  result_storage: string;
}) {
  return http.request<ApiResponse<Record<string, unknown>>>(
    "post",
    "/api/v1/queries/schedules",
    { data }
  );
}

export function fetchQuerySourceCapabilities() {
  return http.request<ApiResponse<{ items: Array<Record<string, unknown>> }>>(
    "get",
    "/api/v1/queries/sources/capabilities"
  );
}
