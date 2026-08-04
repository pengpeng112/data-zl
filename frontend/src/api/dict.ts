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

// 诊断/手术编码体系
export function getMedicalCodeSets(params?: Record<string, unknown>) {
  return http.request<ApiResponse<unknown[]>>("get", "/api/v1/dict-medical/code-sets", { params });
}
export function upsertMedicalCodeSet(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-medical/code-sets", { data });
}
// 编码项
export function getMedicalItems(codeSetCode: string, params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", `/api/v1/dict-medical/code-sets/${codeSetCode}/items`, { params });
}
export function upsertMedicalItem(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-medical/items", { data });
}
// 对照关系
export function getMedicalMappings(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-medical/mappings", { params });
}
export function getMedicalMappingRows(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-medical/mapping-rows", { params });
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
  return http.request<ApiResponse<unknown>>("get", "/api/v1/dict-medical/push/config");
}
export function exportMedicalPushPreview(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("post", "/api/v1/dict-medical/push/export-preview", { data });
}
export function planMedicalPush(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("post", "/api/v1/dict-medical/push/plan", { data });
}
export function applyMedicalPushOne(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("post", "/api/v1/dict-medical/push/apply-one", { data });
}
export function stopMedicalPushOne(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("post", "/api/v1/dict-medical/push/stop-one", { data });
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
// ===== 通用字典 API（dict/general 页面使用）=====

export function getDictCategories() {
  return http.request<ApiResponse<unknown[]>>("get", "/api/v1/dict-general/categories");
}
export function upsertDictCategory(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-general/categories", { data });
}
export function getDictStandardItems(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-general/standard-items", { params });
}
export function upsertDictStandardItem(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-general/standard-items", { data });
}
export function getDictSystemItems(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-general/system-items", { params });
}
export function getDictItemMappings(params?: Record<string, unknown>) {
  return http.request<ApiResponse<PageData<unknown>>>("get", "/api/v1/dict-general/item-mappings", { params });
}
export function upsertDictItemMapping(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("put", "/api/v1/dict-general/item-mappings", { data });
}
export function importSystemDict(data: Record<string, unknown>) {
  return http.request<ApiResponse<unknown>>("post", "/api/v1/dict-general/import", { data });
}
