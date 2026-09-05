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
}

export interface QualityControlDetector {
  id: number;
  detector_kind: string;
  detector_ref: string;
  detector_version: string;
  status: string;
  blocked_reason: string | null;
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

export function runQualityControl(id: number) {
  return http.post<Record<string, unknown>, object>(`/api/v1/quality-controls/${id}/run`);
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
