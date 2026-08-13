import type { AiQualityPreview, AiQualityStatus } from "@/api/asset";

export const AI_QUALITY_MAX_FINDINGS = 50;

export function limitFindingIds(ids: number[]) {
  return Array.from(new Set(ids.filter(Number.isFinite))).slice(0, AI_QUALITY_MAX_FINDINGS);
}

export function canSubmitAiQuality(status: AiQualityStatus | null, preview: AiQualityPreview | null) {
  return Boolean(status?.enabled && status.configured && preview?.input_digest && (preview.item_count == null || preview.item_count <= AI_QUALITY_MAX_FINDINGS));
}

export function sameFindingDomain(rows: { system_code?: string | null; source_code?: string | null; namespace_name?: string | null; schema_name?: string | null; table_name?: string | null; rule_code?: string | null }[]) {
  if (!rows.length) return false;
  if (rows.some(row => [row.system_code, row.source_code, row.schema_name, row.table_name, row.rule_code].some(value => !String(value || "").trim()))) return false;
  const keys = rows.map(row => [row.system_code, row.source_code, row.namespace_name || "", row.schema_name, row.table_name, row.rule_code].join("|"));
  return new Set(keys).size === 1;
}

export function aiQualityStatusLabel(status: AiQualityStatus | null) {
  if (!status?.enabled) return "已关闭";
  if (!status.configured) return "未配置";
  if (status.reachable === false) return "连接失败";
  return "可用";
}
