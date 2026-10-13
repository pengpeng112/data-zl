import { http } from "@/utils/http";

/** 174 S7：质量治理台账 API 层（Control→Observation→Issue 闭环；裸 dict/分页响应）。 */

// ─────────────────────────── 类型 ───────────────────────────

export interface QualityIssueListItem {
  id: number;
  issue_code: string;
  control_id: number | null;
  issue_type: string;
  title: string;
  description: string | null;
  primary_system_code: string | null;
  object_name_snapshot: string | null;
  scope_key: string | null;
  severity: string | null;
  priority: string | null;
  status: string;
  responsible_dept_code: string | null;
  responsible_person_code: string | null;
  assignee_user_identifier: string | null;
  responsible_dept_name_snapshot: string | null;
  responsible_person_name_snapshot: string | null;
  assignee_name_snapshot: string | null;
  action_plan: string | null;
  due_at: string | null;
  wait_kind: string | null;
  latest_metric_value: number | null;
  latest_result_status: string | null;
  recurrence_no: number;
  recurrence_of_issue_id: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  lock_version: number;
  overdue: boolean;
  control_code: string | null;
  control_title: string | null;
  allowed_actions: string[];
  /** 207：列表项顺带的复测子状态（用于「复测受阻」快捷筛选），后端未下发时为 undefined。 */
  recheck_substatus?: string | null;
}

export interface QualityIssueDetail extends QualityIssueListItem {
  related_system_codes: string[] | null;
  object_key: string | null;
  duplicate_of_issue_id: number | null;
  resolution_summary: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  risk_reason: string | null;
  risk_approver: string | null;
  risk_review_at: string | null;
  suppressed_until: string | null;
  opened_control_version: number | null;
  external_ticket_ref: string | null;
  /** 207：厂商/督办/复测闭环字段。 */
  wait_note: string | null;
  primary_vendor_code: string | null;
  supervisor_user_identifier: string | null;
  vendor_promised_at: string | null;
  next_followup_at: string | null;
  original_due_at: string | null;
  remediation_submitted_at: string | null;
  last_verification_run_id: number | null;
  recheck_substatus: "none" | "pending" | "passed" | "failed" | "blocked" | string;
  recheck_note: string | null;
  recheck_pass_streak: number | string | null;
  escalation_level: number;
}

export interface QualityIssuePage {
  items: QualityIssueListItem[];
  total: number;
  page: number;
  page_size: number;
  scope: string;
}

export interface QualityIssueEvent {
  id: number;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  reason: string | null;
  observation_id: number | null;
  actor_user_identifier: string | null;
  occurred_at: string | null;
}

export interface QualityObservationItem {
  id: number;
  control_id: number;
  control_version: number;
  issue_id: number | null;
  run_key: string;
  scope_key: string;
  window_start: string | null;
  window_end: string | null;
  observed_at: string | null;
  result_status: string;
  metric_value: number | null;
  metric_unit: string | null;
  source_kind: string;
  source_record_ref: string | null;
  evidence_ref: string | null;
  historical_precision: string;
  /** 207：分子/分母（比率类指标溯源），旧观测可能为空。 */
  numerator?: number | null;
  denominator?: number | null;
}

export interface QualityControlDetector {
  id: number;
  detector_kind: string;
  detector_ref: string;
  detector_version: string;
  status: string;
  blocked_reason: string | null;
  /** 207 T08：value_domain 检测器携带列身份绑定（系统/物理源/schema/表/列） */
  result_mapping?: Record<string, string> | null;
}

export interface QualityControlItem {
  id: number;
  control_code: string;
  version: number;
  title: string;
  description: string | null;
  lifecycle_status: string;
  blocked_reason: string | null;
  dimension: string | null;
  category: string | null;
  primary_system_code: string | null;
  object_name_snapshot: string | null;
  metric_name: string | null;
  metric_unit: string | null;
  comparator: string | null;
  threshold_value: number | null;
  default_severity: string | null;
  default_priority: string | null;
  lock_version: number;
  detectors: QualityControlDetector[];
  /** 207：执行与复测计划字段。 */
  source_code: string | null;
  schedule_enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  freshness_hours: number | null;
  recheck_policy: "auto" | "manual" | string | null;
  sla_hours: number | null;
  /** 后端执行计划原文（调度表达式/时区/验证策略等），结构以后端为准。 */
  execution_plan: Record<string, unknown> | null;
  /** 验证策略（manual | auto_recheck_manual_close）；列表接口未下发时为空。 */
  verification_policy?: string | null;
}

export interface QualityControlPage {
  items: QualityControlItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AssignmentDepartment {
  dept_code: string;
  dept_name_cn: string;
  status: string;
}

export interface AssignmentPerson {
  person_code: string;
  person_name_cn: string | null;
  dept_code: string | null;
  dept_name_cn: string | null;
  employment_status: string | null;
  /** 207：是否具备登录账号（无登录账号则无法接收站内待办）。 */
  has_login: boolean;
}

export interface IssueCommandEnvelope {
  reason?: string;
  expected_lock_version?: number;
  correlation_id?: string;
}

// ─────────────────────────── 问题台账 ───────────────────────────

export interface QualityIssueFilters {
  scope?: string;
  status?: string;
  severity?: string;
  priority?: string;
  primary_system_code?: string;
  responsible_dept_code?: string;
  overdue?: boolean;
  keyword?: string;
  control_code?: string;
  issue_type?: string;
  /** 207：按厂商筛选（等厂商问题的责任厂商）。 */
  primary_vendor_code?: string;
}

export function listQualityIssues(
  params: QualityIssueFilters & { page?: number; page_size?: number }
) {
  return http.get<QualityIssuePage, object>("/api/v1/quality-issues", { params });
}

export function getQualityIssue(id: number) {
  return http.get<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}`);
}

export function getQualityIssueSummary() {
  return http.get<{ by_system: Record<string, Record<string, number>> }, object>(
    "/api/v1/quality-issues/summary"
  );
}

export function listQualityIssueEvents(id: number) {
  return http.get<{ items: QualityIssueEvent[]; total: number }, object>(
    `/api/v1/quality-issues/${id}/events`
  );
}

export function listQualityIssueObservations(id: number) {
  return http.get<{ items: QualityObservationItem[]; total: number }, object>(
    `/api/v1/quality-issues/${id}/observations`
  );
}

export function createQualityIssue(body: Record<string, unknown>) {
  return http.post<QualityIssueDetail, object>("/api/v1/quality-issues", { data: body });
}

export function patchQualityIssue(id: number, body: IssueCommandEnvelope & { fields: object }) {
  return http.patch<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}`, { data: body });
}

export function assignQualityIssue(id: number, body: Record<string, unknown>) {
  return http.post<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}/assign`, { data: body });
}

export function transitionQualityIssue(id: number, body: Record<string, unknown>) {
  return http.post<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}/transition`, {
    data: body
  });
}

export function requestQualityIssueVerification(
  id: number,
  body: Record<string, unknown>
) {
  return http.post<QualityIssueDetail, object>(
    `/api/v1/quality-issues/${id}/request-verification`,
    { data: body }
  );
}

export function verifyQualityIssue(id: number, body: Record<string, unknown>) {
  return http.post<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}/verify`, {
    data: body
  });
}

export function acceptQualityIssueRisk(id: number, body: Record<string, unknown>) {
  return http.post<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}/accept-risk`, {
    data: body
  });
}

export function markQualityIssueFalsePositive(
  id: number,
  body: Record<string, unknown>
) {
  return http.post<QualityIssueDetail, object>(
    `/api/v1/quality-issues/${id}/mark-false-positive`,
    { data: body }
  );
}

export function commentQualityIssue(id: number, body: { reason: string }) {
  return http.post<{ ok: boolean }, object>(`/api/v1/quality-issues/${id}/comment`, {
    data: body
  });
}

export function exportQualityIssues(body: QualityIssueFilters) {
  return http.request<Blob>("post", "/api/v1/quality-issues/export", {
    data: body,
    responseType: "blob",
    timeout: 120000
  });
}

// ─────────────────────────── 责任选择 ───────────────────────────

export function listAssignmentDepartments(keyword?: string) {
  return http.get<{ items: AssignmentDepartment[] }, object>(
    "/api/v1/quality-issues/assignment-options/departments",
    { params: keyword ? { keyword } : undefined }
  );
}

export function listAssignmentPersons(params?: {
  department_code?: string;
  keyword?: string;
}) {
  return http.get<{ items: AssignmentPerson[] }, object>(
    "/api/v1/quality-issues/assignment-options/persons",
    { params }
  );
}

// ─────────────────────────── 质控清单 ───────────────────────────

export function listQualityControls(
  params: {
    lifecycle_status?: string;
    primary_system_code?: string;
    category?: string;
    keyword?: string;
    page?: number;
    page_size?: number;
  } = {}
) {
  return http.get<QualityControlPage, object>("/api/v1/quality-controls", { params });
}

export function getQualityControl(id: number) {
  return http.get<QualityControlItem, object>(`/api/v1/quality-controls/${id}`);
}

export function createQualityControl(body: Record<string, unknown>) {
  return http.post<QualityControlItem, object>("/api/v1/quality-controls", { data: body });
}

export function patchQualityControl(id: number, body: Record<string, unknown>) {
  return http.patch<QualityControlItem, object>(`/api/v1/quality-controls/${id}`, {
    data: body
  });
}

export function activateQualityControl(id: number) {
  return http.post<QualityControlItem, object>(`/api/v1/quality-controls/${id}/activate`);
}

export function deprecateQualityControl(id: number) {
  return http.post<QualityControlItem, object>(`/api/v1/quality-controls/${id}/deprecate`);
}

export function runQualityControl(
  id: number,
  body?: {
    expected_control_version?: number;
    idempotency_key?: string;
    window_start?: string;
    window_end?: string;
  }
) {
  return http.post<QualityRunAccepted, object>(`/api/v1/quality-controls/${id}/run`, {
    data: body || {}
  });
}

// ─────────────────────────── 运行单与覆盖（207） ───────────────────────────

export interface QualityPreflightDetector {
  detector_id: number;
  detector_kind: string;
  detector_ref: string;
  status: string;
  executable: boolean;
  blocked_reason: string | null;
}

export interface QualityPreflightResult {
  executable: boolean;
  manual_required: boolean;
  blocked_reasons: string[];
  warnings: string[];
  detectors: QualityPreflightDetector[];
  scope_summary: {
    scope_key: string;
    system_code: string | null;
    source_code: string | null;
    object_key: string | null;
    granularity: string | null;
  };
  window: {
    in_window: boolean;
    allowed_hours: number[] | string | null;
    next_window_at: string | null;
  };
}

export interface QualityRunAccepted {
  status: "queued" | "waiting_window" | "blocked" | "manual_required" | string;
  run_id: number | null;
  run_code?: string;
  next_window_at: string | null;
  blocked_reasons: string[];
  duplicate: boolean;
  children: {
    run_id: number;
    run_code: string;
    detector_kind: string;
    detector_ref: string;
    status: string;
  }[];
}

export interface QualityRunItem {
  id: number;
  run_code: string;
  control_id: number;
  parent_run_id: number | null;
  issue_id: number | null;
  purpose: "check" | "recheck" | string;
  trigger_kind: string;
  status: string;
  detector_kind: string | null;
  detector_ref: string | null;
  started_at: string | null;
  finished_at: string | null;
  heartbeat_at: string | null;
  attempt: number | null;
  max_attempts: number | null;
  next_window_at: string | null;
  result_summary: string | null;
  error_code: string | null;
  error_message_sanitized: string | null;
  cancel_requested: boolean;
  lock_version: number;
}

export interface QualityRunPage {
  items: QualityRunItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface QualityRunObservation {
  id: number;
  result_status: string;
  metric_value: number | null;
  numerator: number | null;
  denominator: number | null;
  observed_at: string | null;
  run_key: string;
  scope_key: string;
  evidence_ref: string | null;
  error?: string | null;
}

export interface QualityRunDetail extends QualityRunItem {
  children: QualityRunItem[];
  observations: QualityRunObservation[];
}

export interface QualityCoverage {
  statistics_time: string | null;
  applicable_instances: number;
  effective_instances: number;
  executable_coverage_pct: number | null;
  latest_status_counts: {
    pass: number;
    fail: number;
    no_data: number;
    error: number;
    blocked: number;
    skipped: number;
  };
  data_pass_rate_pct: number | null;
  issues: {
    active: number;
    resolved: number;
    recurrence: number;
    remediation_pass_rate_pct: number | null;
    recurrence_rate_pct: number | null;
  };
  uncovered: {
    control_id: number;
    control_code: string;
    detector: string;
    reason: string;
    last_observed_at: string | null;
  }[];
  uncovered_total: number;
  note: string | null;
}

export function preflightQualityControl(id: number) {
  return http.post<QualityPreflightResult, object>(
    `/api/v1/quality-controls/${id}/preflight`
  );
}

export function listQualityRuns(
  params: {
    control_id?: number;
    issue_id?: number;
    status?: string;
    purpose?: string;
    page?: number;
    page_size?: number;
  } = {}
) {
  return http.get<QualityRunPage, object>("/api/v1/quality-runs", { params });
}

export function getQualityRun(id: number) {
  return http.get<QualityRunDetail, object>(`/api/v1/quality-runs/${id}`);
}

export function cancelQualityRun(
  id: number,
  body: { expected_lock_version: number; reason: string }
) {
  return http.post<QualityRunItem, object>(`/api/v1/quality-runs/${id}/cancel`, {
    data: body
  });
}

export function retryQualityRun(id: number, body?: { reason?: string }) {
  return http.post<Record<string, unknown>, object>(`/api/v1/quality-runs/${id}/retry`, {
    data: body || {}
  });
}

export function getQualityCoverage(params?: {
  system_code?: string;
  source_code?: string;
}) {
  return http.get<QualityCoverage, object>("/api/v1/quality-controls/coverage", {
    params
  });
}

// ─────────────────────────── 观测记录 ───────────────────────────

export function listQualityObservations(
  params: {
    control_id?: number;
    issue_id?: number;
    result_status?: string;
    source_kind?: string;
    window_from?: string;
    window_to?: string;
    page?: number;
    page_size?: number;
  } = {}
) {
  return http.get<
    { items: QualityObservationItem[]; total: number; page: number; page_size: number },
    object
  >("/api/v1/quality-observations", { params });
}

// ─────────────────────────── 台账命令（207） ───────────────────────────

export interface QualityBatchAssignItemResult {
  issue_id: number;
  ok: boolean;
  error?: string;
  status_code?: number;
  issue_code?: string;
  lock_version?: number;
}

export interface QualityBatchAssignResult {
  items: QualityBatchAssignItemResult[];
  total: number;
  ok: number;
  failed: number;
}

export function batchAssignQualityIssues(body: {
  items: { issue_id: number; expected_lock_version: number }[];
  responsible_dept_code?: string;
  responsible_person_code?: string;
  assignee_user_identifier?: string;
  reason?: string;
  idempotency_key?: string;
}) {
  return http.post<QualityBatchAssignResult, object>("/api/v1/quality-issues/batch-assign", {
    data: body
  });
}

export function followupQualityIssue(
  id: number,
  body: {
    kind: "progress" | "ticket" | "commitment" | "remind" | string;
    note: string;
    vendor_code?: string;
    external_ticket_ref?: string;
    vendor_promised_at?: string;
    next_followup_at?: string;
    root_cause?: string;
    remediation_plan?: string;
    evidence_ref?: string;
    change_due_at?: string;
    change_due_reason?: string;
  }
) {
  return http.post<QualityIssueDetail, object>(`/api/v1/quality-issues/${id}/followups`, {
    data: body
  });
}

export function remindQualityIssue(id: number, body: { reason: string }) {
  return http.post<QualityIssueDetail & { notification_created: boolean }, object>(
    `/api/v1/quality-issues/${id}/remind`,
    { data: body }
  );
}

// ─────────────────────────── 厂商档案（207） ───────────────────────────

export interface QualityVendorItem {
  id: number;
  vendor_code: string;
  vendor_name: string;
  status: string;
  contact_note: string | null;
  related_system_codes: string[] | null;
  remark: string | null;
  lock_version: number;
}

export function listQualityVendors(
  params: { keyword?: string; status?: string; page?: number; page_size?: number } = {}
) {
  return http.get<{ items: QualityVendorItem[]; total: number }, object>(
    "/api/v1/quality-vendors",
    { params }
  );
}

export function createQualityVendor(body: {
  vendor_code: string;
  vendor_name: string;
  status?: string;
  contact_note?: string;
  related_system_codes?: string[];
  remark?: string;
}) {
  return http.post<QualityVendorItem, object>("/api/v1/quality-vendors", { data: body });
}

export function patchQualityVendor(
  id: number,
  body: {
    expected_lock_version: number;
    vendor_name?: string;
    status?: string;
    contact_note?: string;
    related_system_codes?: string[];
    remark?: string;
    reason?: string;
  }
) {
  return http.patch<QualityVendorItem, object>(`/api/v1/quality-vendors/${id}`, {
    data: body
  });
}

// ─────────────────────────── 站内待办（207） ───────────────────────────

export interface QualityNotificationItem {
  id: number;
  issue_id: number | null;
  run_id: number | null;
  recipient: string;
  notify_type: string;
  payload: { issue_code?: string } & Record<string, unknown>;
  read_at: string | null;
  created_at: string | null;
}

export function listQualityNotifications(
  params: { unread_only?: boolean; page?: number; page_size?: number } = {}
) {
  return http.get<
    { items: QualityNotificationItem[]; total: number; unread: number },
    object
  >("/api/v1/quality-notifications", { params });
}

export function readQualityNotification(id: number) {
  return http.post<{ ok: boolean }, object>(`/api/v1/quality-notifications/${id}/read`);
}

export function readAllQualityNotifications() {
  return http.post<{ ok: boolean; updated?: number }, object>(
    "/api/v1/quality-notifications/read-all"
  );
}
