/**
 * 193 B16：数据集 API（/api/v1/datasets，全部真实隔离/平台接口，无 mock）
 * 210 S8：数据集安全治理前端闭环——新增分类分级提案/审批、用途授权申请/审批/撤权、
 *        受控导出申请/审批/生成/下载（blob）接口与类型，均对接后端真实端点。
 */
import { http } from "@/utils/http";
import type { ApiResponse } from "./types";

// ---------- 目录（B16） ----------

export interface DatasetListItem {
  dataset_code: string;
  title: string;
  purpose_code: string;
  grain: string;
  status: string | null;
  version: number | null;
  readable?: boolean;
  decision?: string;
  /** 210：版本存在待定级 / 待审批分类时为 true */
  pending_classification?: boolean;
}

export const listDatasets = () =>
  http.request<ApiResponse<DatasetListItem[]>>("get", "/api/v1/datasets");

export interface BatchDetail {
  run_id: string;
  status: string;
  counters: Record<string, number>;
  checkpoint_keys: number;
  error_class: string | null;
}

export const getDatasetBatch = (runId: string) =>
  http.request<ApiResponse<BatchDetail>>("get", `/api/v1/datasets/batches/${encodeURIComponent(runId)}`);

// ---------- 分类分级（210 S8） ----------

export type ClassificationStatus =
  | "active"
  | "superseded"
  | "pending_approval"
  | "retired";
export type ClassificationLabelSource = "manual" | "candidate" | "confirmed";
/** 保护等级为工程草案口径（P1 已批准公开 / P2 内部 / P3 敏感 / P4 严格受限），非法定分级 */
export type ProtectionLevel = "P1" | "P2" | "P3" | "P4";
/** 与后端 dataset_security.VALID_PERSONAL_INFO 对齐 */
export type PersonalInfoKind =
  | "none"
  | "personal"
  | "sensitive_personal"
  | "pending";

export interface UsageConstraints {
  purposes: string[];
  export_allowed: boolean;
  training_allowed: boolean;
}

export interface ClassificationLabels {
  protection_level: ProtectionLevel;
  personal_info: PersonalInfoKind;
  usage_constraints: UsageConstraints;
}

export interface ClassificationItem {
  id: number;
  object_type: string;
  object_ref: string;
  version: number;
  status: ClassificationStatus;
  label_source: ClassificationLabelSource;
  protection_level: string;
  labels: Record<string, unknown> | null;
  classified_by: string;
  evidence: string | null;
  retention_until: string | null;
  created_at: string | null;
}

export interface ClassificationProposalBody {
  object_type: "dataset_version";
  object_ref: string;
  labels: ClassificationLabels;
  expected_version: number;
  label_source: "manual";
}

export interface ClassificationProposalResult {
  version: number;
  protection_level: string;
  status: string;
  needs_approval: boolean;
  reasons: string[];
}

export const listClassifications = (params?: { object_type?: string }) =>
  http.request<ApiResponse<ClassificationItem[]>>("get", "/api/v1/datasets/classifications", { params });

export const submitClassification = (body: ClassificationProposalBody) =>
  http.request<ApiResponse<ClassificationProposalResult>>(
    "post",
    "/api/v1/datasets/classifications",
    { data: body }
  );

export const reviewClassification = (
  id: number,
  body: { decision: "approve" | "reject"; note: string }
) =>
  http.request<ApiResponse<unknown>>(
    "post",
    `/api/v1/datasets/classifications/${id}/review`,
    { data: body }
  );

// ---------- 用途授权（210 S8） ----------

export type GrantStatus =
  | "pending"
  | "active"
  | "rejected"
  | "revoked"
  | "expired";
/** 与后端 dataset_security.VALID_OPERATIONS 对齐 */
export type GrantOperation = "read" | "export" | "train" | "derive";

export interface GrantItem {
  id: number;
  principal: string;
  purpose_code: string;
  resource_type: string;
  resource_ref: string;
  operations: string[];
  status: GrantStatus;
  row_scope: Record<string, unknown> | null;
  column_scope: Record<string, unknown> | null;
  valid_from: string | null;
  valid_until: string | null;
  requested_by: string;
  approved_by: string | null;
  grant_version: number;
}

export interface GrantCreateBody {
  principal: string;
  purpose_code: string;
  resource_ref: string;
  operations: GrantOperation[];
  legal_basis_ref: string;
  valid_hours: number;
  row_scope?: Record<string, unknown>;
  column_scope?: Record<string, unknown>;
}

export const listGrants = () =>
  http.request<ApiResponse<GrantItem[]>>("get", "/api/v1/datasets/grants");

export const createGrant = (body: GrantCreateBody) =>
  http.request<ApiResponse<unknown>>("post", "/api/v1/datasets/grants", { data: body });

export const reviewGrant = (id: number, body: { decision: "approve" | "reject" }) =>
  http.request<ApiResponse<unknown>>("post", `/api/v1/datasets/grants/${id}/review`, { data: body });

export const revokeGrant = (id: number, body: { reason: string }) =>
  http.request<ApiResponse<unknown>>("post", `/api/v1/datasets/grants/${id}/revoke`, { data: body });

// ---------- 受控导出（210 S8） ----------

export type ExportStatus =
  | "review_pending"
  | "approved"
  | "generated"
  | "revoked"
  | "expired"
  | "failed";

export interface ExportItem {
  export_code: string;
  status: ExportStatus;
  dataset_version_id: number;
  grant_id?: number;
  requested_by: string;
  approved_by: string | null;
  requested_fields: string[] | null;
  field_whitelist: string[] | null;
  expires_at: string | null;
  row_count: number | null;
  file_sha256: string | null;
  artifact_bytes: number | null;
  review_note: string | null;
  generation_error: string | null;
}

export interface ExportCreateResult {
  export_code: string;
  status: ExportStatus;
  expires_at: string | null;
}

export const listExports = () =>
  http.request<ApiResponse<ExportItem[]>>("get", "/api/v1/datasets/exports");

export const createExport = (
  code: string,
  versionId: number,
  body: { fields: string[]; project_code?: string | null }
) =>
  http.request<ApiResponse<ExportCreateResult>>(
    "post",
    `/api/v1/datasets/${encodeURIComponent(code)}/versions/${versionId}/exports`,
    { data: body }
  );

export const reviewExport = (
  exportCode: string,
  body: { decision: "approve" | "reject"; note: string }
) =>
  http.request<ApiResponse<unknown>>(
    "post",
    `/api/v1/datasets/exports/${encodeURIComponent(exportCode)}/review`,
    { data: body }
  );

export const generateExport = (exportCode: string) =>
  http.request<ApiResponse<unknown>>(
    "post",
    `/api/v1/datasets/exports/${encodeURIComponent(exportCode)}/generate`,
    { data: {} }
  );

/** 下载受控导出工件：响应为 CSV 字节流（blob），前端保存为 {export_code}.csv */
export const downloadExport = (exportCode: string) =>
  http.request<Blob>(
    "post",
    `/api/v1/datasets/exports/${encodeURIComponent(exportCode)}/download`,
    { data: {}, responseType: "blob", timeout: 120000 }
  );
