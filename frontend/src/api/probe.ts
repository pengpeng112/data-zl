import { http } from "@/utils/http";

/** 166 D1：探查发现 API 层（165 E4 契约消费面；分页沿用 {items,total,page,page_size}）。 */

export interface ProbeFindingListItem {
  id: number;
  probe_type: string;
  system_pair: string;
  object_desc: string;
  metric_name: string;
  metric_value: number | null;
  metric_unit: string | null;
  threshold: number | null;
  window_start: string | null;
  window_end: string | null;
  severity: string | null;
  status: string;
  first_seen_run: string | null;
  last_seen_run: string | null;
  relapse_count: number;
  note: string | null;
}

export interface ProbeFindingDetail extends ProbeFindingListItem {
  evidence_sql: string | null;
  evidence_digest: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProbeRun {
  id: number;
  run_id: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  probe_count: number;
  finding_new: number;
  finding_updated: number;
  relapse_count: number;
  error_summary: string | null;
  created_by: string | null;
  created_at?: string | null;
  metrics_summary?: Record<string, unknown> | null;
}

export interface ProbeFindingPage {
  items: ProbeFindingListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProbeRunPage {
  items: ProbeRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProbeFindingFilters {
  probe_type?: string;
  system_pair?: string;
  severity?: string;
  status?: string;
  source?: string;
  window_start_from?: string;
  window_start_to?: string;
}

/** 探查发现列表（筛选+分页；165 E4 裸分页响应——无 ApiResponse 包装，body 即分页对象） */
export function listProbeFindings(
  params: ProbeFindingFilters & { page?: number; page_size?: number }
) {
  return http.get<ProbeFindingPage, object>("/api/v1/probe-findings", {
    params
  });
}

/** 探查发现详情（含 evidence_sql/evidence_digest；裸 dict 响应） */
export function getProbeFinding(id: number) {
  return http.get<ProbeFindingDetail, object>(
    `/api/v1/probe-findings/${id}`
  );
}

/** 探查 run 列表（详情抽屉 runs Tab，最近 10 条；裸分页响应） */
export function listProbeRuns(params?: { page?: number; page_size?: number; status?: string }) {
  return http.get<ProbeRunPage, object>("/api/v1/probe-runs", { params });
}

/** 166 F5：人工终态流转（action=confirm/false_positive/resolve/reopen/reclassify；reason 必填） */
export function transitionProbeFinding(
  id: number,
  body: { action: string; reason: string; to_status?: string }
) {
  return http.post<ProbeFindingDetail, object>(
    `/api/v1/probe-findings/${id}/transition`,
    { data: body }
  );
}

/** 166 F6：探查发现 CSV 导出（POST+body 筛选，B12：防 SQL 文本进代理日志） */
export function exportProbeFindings(body: ProbeFindingFilters) {
  return http.request<Blob>("post", "/api/v1/probe-findings/export", {
    data: body,
    responseType: "blob",
    timeout: 120000
  });
}
