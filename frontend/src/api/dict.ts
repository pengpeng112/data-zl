import { http } from "@/utils/http";


export type { ApiResponse, PageData } from "./types";
import type { ApiResponse, PageData } from "./types";

// 诊断/手术编码体系
// F8：medical 系列补实体类型（视图层消除 as any）。
export interface MedicalCodeSet {
  code_set_code: string;
  code_set_name_cn?: string | null;
  name_cn?: string | null;
  code_set_type?: string | null;
  category_code?: string | null;
  standard_system?: string | null;
  version_no?: string | null;
  enabled?: boolean | null;
  status?: string | null;
}

export interface MedicalCodeItem {
  id?: number;
  code_set_code: string;
  item_code: string;
  item_name_cn?: string | null;
  item_name_alias?: string | null;
  status?: string | null;
}

export interface MedicalPushConfig {
  push_enabled: boolean;
  default_hospital_no?: string | null;
  [key: string]: unknown;
}

export interface MedicalPushAction {
  action_type: string;
  target_system: string;
  target_table: string;
  item_code: string;
  item_name?: string | null;
  plan_status: string;
  meta?: Record<string, unknown>;
  params?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface MedicalPushPlan {
  action_count?: number;
  actions: MedicalPushAction[];
  summary?: Record<string, number> & { [key: string]: unknown };
  [key: string]: unknown;
}

export interface MedicalMappingRowItem {
  local_code?: string;
  local_name?: string | null;
  dict_attribute?: string | null;
  ybhm?: string | null;
  national_code?: string;
  national_name?: string;
  insurance_code?: string;
  insurance_name?: string;
  operation_level?: string | null;
  operation_category?: string | null;
  performance_level4_flag?: string | null;
  performance_minimally_invasive_flag?: string | null;
  restricted_tech_flag?: string | null;
  special_disease_code?: string | null;
  special_disease_name?: string | null;
  low_risk_category_code?: string | null;
  low_risk_disease_name?: string | null;
  infectious_disease_name?: string | null;
  source_file?: string | null;
  source_sheet?: string | null;
  status?: string | null;
  [key: string]: unknown;
}

export function getMedicalCodeSets(params?: Record<string, unknown>) {
  return http.request<ApiResponse<MedicalCodeSet[]>>("get", "/api/v1/dict-medical/code-sets", { params });
}
export function upsertMedicalCodeSet(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-medical/code-sets", { data });
}
// 编码项
export function getMedicalItems(codeSetCode: string, params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<MedicalCodeItem>>>("get", `/api/v1/dict-medical/code-sets/${codeSetCode}/items`, { params });
}
export function upsertMedicalItem(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-medical/items", { data });
}
// 对照关系
export function getMedicalMappings(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-medical/mappings", { params });
}
export function getMedicalMappingRows(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<MedicalMappingRowItem>>>("get", "/api/v1/dict-medical/mapping-rows", { params });
}
export function getMedicalMappingOptions(categoryCode: string) {
  return http.request<ApiResponse<Record<string, string[]>>>("get", "/api/v1/dict-medical/mapping-options", {
    params: { category_code: categoryCode }
  });
}
export function upsertMedicalMappingRow(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-medical/mapping-rows", { data });
}
export function exportMedicalMappingRows(params?: Record<string, unknown>) {
  return http.request<Blob>("get", "/api/v1/dict-medical/mapping-rows/export", {
    params,
    responseType: "blob",
    timeout: 120000
  });
}
export function upsertMedicalMapping(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-medical/mappings", { data });
}
// 同步差异
export function getMedicalSyncDiffs(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-medical/sync-diffs", { params });
}
export function runMedicalSync(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("post", "/api/v1/dict-medical/sync/run", { data });
}
export function updateMedicalSyncDiff(id: number, data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("patch", `/api/v1/dict-medical/sync-diffs/${id}`, { data });
}

// 诊断/手术下发 HIS / 海量（96：只增 + 单条停用）
export function getMedicalPushConfig() {
  return http.request<ApiResponse<MedicalPushConfig>>("get", "/api/v1/dict-medical/push/config");
}
export function exportMedicalPushPreview(data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/dict-medical/push/export-preview", { data });
}
export function planMedicalPush(data: Record<string, unknown>) {
  return http.request<ApiResponse<MedicalPushPlan>>("post", "/api/v1/dict-medical/push/plan", { data });
}
export function applyMedicalPushOne(data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/dict-medical/push/apply-one", { data });
}
export function stopMedicalPushOne(data: Record<string, unknown>) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/dict-medical/push/stop-one", { data });
}
// 版本
export function getDictVersions(params?: Record<string, unknown>) {
  return http.request<ApiResponse<unknown[]>>("get", "/api/v1/dict-medical/versions", { params });
}

// ===== 101号：诊断映射导入审核 API =====

export interface ImportRunInfo {
  id: number;
  batch_code: string;
  status: string;
  file_name: string;
  file_sha256: string;
  operator: string;
  created_at: string;
  row_stats: Record<string, number>;
}

export interface ImportRowItem {
  id: number;
  row_no: number;
  hospital_code: string;
  hospital_name: string;
  national_clinical_code: string;
  national_clinical_name: string;
  insurance_code: string;
  insurance_name: string;
  insurance_mapping_status: string;
  validation_status: string;
  validation_errors: string[] | null;
  diff_type: string;
  review_status: string;
  reviewer: string;
  review_note: string;
}

export function uploadDiagnosisMapping(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return http.request<ApiResponse<{
    import_run_id: number;
    batch_code: string;
    status: string;
    row_count: number;
    staged: number;
    sheet: string;
    file_sha256: string;
  }>>("post", "/api/v1/dict-medical/imports/diagnosis-mapping", {
    data: formData,
    headers: { "Content-Type": "multipart/form-data" }
  });
}

export function getImportRun(runId: number) {
  return http.request<ApiResponse<ImportRunInfo>>("get", `/api/v1/dict-medical/imports/${runId}`);
}

export function getImportRows(runId: number, params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<ImportRowItem>>>("get", `/api/v1/dict-medical/imports/${runId}/rows`, { params });
}

export function reviewImportRows(runId: number, data: { row_ids: number[]; action: string; review_note?: string }) {
  return http.request<ApiResponse<{ reviewed: number; blocked: number }>>("post", `/api/v1/dict-medical/imports/${runId}/rows/review`, { data });
}

export function mergeImportRun(runId: number) {
  return http.request<ApiResponse<Record<string, number>>>("post", `/api/v1/dict-medical/imports/${runId}/merge`);
}
// ===== 通用字典 API（dict/general 页面使用，canonical /api/v1/dictionaries）=====

export interface DictCategory {
  id: number;
  category_code: string;
  category_name_cn: string;
  standard_system?: string | null;
  enabled: boolean;
}

export interface DictStandardItem {
  id: number;
  category_code: string;
  standard_code: string;
  standard_name_cn: string;
  status?: string | null;
}

export interface DictSystemItem {
  id: number;
  category_code: string;
  system_code: string;
  system_item_code: string;
  system_item_name_cn: string;
  source_table?: string | null;
  raw_status?: string | null;
  enabled: boolean;
  last_sync_at?: string | null;
}

export interface DictItemMapping {
  id: number;
  category_code: string;
  standard_code?: string | null;
  system_code: string;
  system_item_code: string;
  mapping_type?: string | null;
  confidence?: string | null;
  review_status?: string | null;
}

export interface DictImportItem {
  system_item_code: string;
  system_item_name_cn: string;
  source_table?: string | null;
  source_key_column?: string | null;
  source_name_column?: string | null;
}

export interface DictImportResult {
  dry_run: boolean;
  created: number;
  updated: number;
  rejected: number;
  errors: Array<{ index: number; system_item_code: string; reason: string }>;
}

export function getDictCategories() {
  return http.request<ApiResponse<DictCategory[]>>("get", "/api/v1/dictionaries/categories");
}
export function upsertDictCategory(data: {
  category_code: string;
  category_name_cn: string;
  standard_system?: string | null;
  enabled: boolean;
}) {
  return http.request<ApiResponse<{ id: number; category_code: string }>>("put", "/api/v1/dictionaries/categories", { data });
}
export function getDictStandardItems(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<DictStandardItem>>>("get", "/api/v1/dictionaries/standard-items", { params });
}
export function upsertDictStandardItem(data: {
  category_code: string;
  standard_code: string;
  standard_name_cn: string;
  status?: string | null;
}) {
  return http.request<ApiResponse<{ id: number }>>("put", "/api/v1/dictionaries/standard-items", { data });
}
export function getDictSystemItems(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<DictSystemItem>>>("get", "/api/v1/dictionaries/system-items", { params });
}
export function upsertDictSystemItem(data: {
  category_code: string;
  system_code: string;
  system_item_code: string;
  system_item_name_cn: string;
  enabled: boolean;
}) {
  return http.request<ApiResponse<{ id: number; created: boolean }>>("put", "/api/v1/dictionaries/system-items", { data });
}
export function setDictSystemItemEnabled(id: number, enabled: boolean) {
  return http.request<ApiResponse<{ id: number; enabled: boolean }>>("patch", `/api/v1/dictionaries/system-items/${id}/enabled`, { data: { enabled } });
}
export function getDictItemMappings(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<DictItemMapping>>>("get", "/api/v1/dictionaries/mappings", { params });
}
export function upsertDictItemMapping(data: {
  category_code: string;
  standard_code?: string | null;
  system_code: string;
  system_item_code: string;
  mapping_type?: string | null;
  confidence?: string | null;
}) {
  return http.request<ApiResponse<{ id: number }>>("put", "/api/v1/dictionaries/mappings", { data });
}
export function importSystemDict(data: {
  category_code: string;
  system_code: string;
  items: DictImportItem[];
  dry_run?: boolean;
}) {
  return http.request<ApiResponse<DictImportResult>>("post", "/api/v1/dictionaries/import", { data });
}

// 146 D3：导入运行列表与推送计划向导（视图层不再裸 http.request）
export function getMedicalImportRuns(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<ImportRunInfo>>>("get", "/api/v1/dict-medical/import-runs", { params });
}

export function createMedicalPushPlan(data: { category_code: string; target_systems: string[] }) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", "/api/v1/dict-medical/push/plans", { data });
}
export function approveMedicalPushPlan(planId: number, note?: string) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", `/api/v1/dict-medical/push/plans/${planId}/approve`, { data: { note } });
}
export function executeMedicalPushPlan(planId: number) {
  return http.request<ApiResponse<Record<string, unknown>>>("post", `/api/v1/dict-medical/push/plans/${planId}/execute`);
}
