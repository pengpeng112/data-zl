import { http } from "@/utils/http";


export type { ApiResponse, PageData } from "./types";
import type { ApiResponse, PageData } from "./types";

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
export interface DiffPreviewItem {
  namespace: string | null;
  table_name: string;
  object_type: "column" | "table";
  object_name: string;
  field_name: string | null;
  change_type: string;
  severity: string;
  before_value: string | null;
  after_value: string | null;
  quality_impact: string | null;
}

export interface DiffPreviewData {
  source: string;
  snapshot_from: { id: number; label: string | null };
  snapshot_to: { id: number; label: string | null };
  summary: {
    total: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
    tables_affected: number;
  };
  total: number;
  page: number;
  page_size: number;
  items: DiffPreviewItem[];
}

/** Zero-write field-level preview (146 C3): never persists events or findings. */
export function diffMetadataPreview(data: {
  source: string;
  from: number;
  to: number;
  type?: string;
  severity?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}) {
  return http.request<ApiResponse<DiffPreviewData>>("post", "/api/v1/metadata-changes/diff-preview", { data });
}

/** Explicit governance action: persist change events (idempotent per object key). */
export function runMetadataDiff(params: { snapshot_id_from: number; snapshot_id_to: number; source_code?: string }) {
  return http.request<ApiResponse<{
    snapshot_from: { id: number; label: string | null; source_code: string };
    snapshot_to: { id: number; label: string | null; source_code: string };
    total_changes: number;
    skipped_existing: number;
    linked_to_quality_findings: number;
  }>>("post", "/api/v1/metadata-changes/diff", { params });
}

// ===== 146 E9：快照分页/归档/详情 与 变更批量 =====
export interface MetadataSnapshotItem {
  id: number;
  label: string | null;
  source_code: string | null;
  snapshot_time: string | null;
  table_count: number | null;
  column_count: number | null;
  relation_count: number | null;
  archived_at?: string | null;
  archived_by?: string | null;
}

export function getMetadataSnapshots(params?: {
  source_code?: string;
  include_archived?: boolean;
  page?: number;
  page_size?: number;
}) {
  return http.request<ApiResponse<PageData<MetadataSnapshotItem>>>("get", "/api/v1/metadata-snapshots", { params });
}

export function getMetadataSnapshotDetail(id: number) {
  return http.request<ApiResponse<MetadataSnapshotItem & {
    column_sample_truncated: boolean;
    column_sample: Array<{ namespace_name: string | null; table_name: string; column_name: string; data_type: string | null; nullable: string | null }>;
  }>>("get", `/api/v1/metadata-snapshots/${id}`);
}

export function archiveMetadataSnapshot(id: number) {
  return http.request<ApiResponse<MetadataSnapshotItem>>("post", `/api/v1/metadata-snapshots/${id}/archive`);
}

export function batchUpdateMetadataChanges(data: {
  ids: number[];
  action: "acknowledge" | "ignore" | "resolve" | "reopen";
  assigned_to?: string;
  note?: string;
}) {
  return http.request<ApiResponse<{ updated: number; missing: number[]; status: string }>>("post", "/api/v1/metadata-changes/batch", { data });
}
