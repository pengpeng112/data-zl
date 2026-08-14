export const RULE_CATEGORY_OPTIONS = [
  { value: "UNIQUE", label: "唯一性" },
  { value: "COMPLETE", label: "缺失性" },
  { value: "RELATION", label: "关联性" },
  { value: "ACCURACY", label: "一致性" },
  { value: "STANDARD", label: "规范性" },
  { value: "CONNECTIVITY", label: "连通性" }
] as const;

export type RuleCategory = (typeof RULE_CATEGORY_OPTIONS)[number]["value"];

const CATEGORY_LABELS: Record<string, string> = Object.fromEntries(
  RULE_CATEGORY_OPTIONS.map(item => [item.value, item.label])
);

export function ruleCategoryLabel(cat?: string | null): string {
  return CATEGORY_LABELS[String(cat || "")] || cat || "-";
}

export function ruleCategoryTag(cat?: string | null): "primary" | "success" | "warning" | "danger" | "info" {
  const map: Record<string, "primary" | "success" | "warning" | "danger" | "info"> = {
    UNIQUE: "danger",
    COMPLETE: "warning",
    STANDARD: "primary",
    RELATION: "info",
    ACCURACY: "success",
    CONNECTIVITY: "info"
  };
  return map[String(cat || "")] || "info";
}

export function checkScopeLabel(scope?: string | null): string {
  const map: Record<string, string> = {
    TABLE_INNER: "表内",
    TABLE_RELATION: "表间",
    SYSTEM_CROSS: "跨系统",
    BUSINESS_LOGIC: "业务逻辑"
  };
  return map[String(scope || "")] || scope || "-";
}

export function constraintLevelLabel(level?: string | null): string {
  const map: Record<string, string> = {
    HARD: "硬约束",
    SOFT: "软约束",
    WARN: "提醒",
    INFO: "信息"
  };
  return map[String(level || "")] || level || "-";
}

export function executionModeLabel(mode?: string | null): string {
  const map: Record<string, string> = {
    metadata_only: "元数据",
    sql_template: "SQL 建议"
  };
  return map[String(mode || "")] || mode || "-";
}

export function formatFindingRate(errorRate?: number | null, metric?: string | null): string {
  if (metric && metric.includes("%")) {
    const match = metric.match(/(-?\d+(?:\.\d+)?)\s*%/);
    if (match) return `${match[1]}%`;
  }
  if (errorRate == null) return "-";
  const value = Number(errorRate);
  if (Number.isNaN(value)) return "-";
  return value <= 1 ? `${(value * 100).toFixed(1)}%` : `${value.toFixed(1)}%`;
}

export function findingTargetText(row: {
  target_display?: string | null;
  source_name_cn?: string | null;
  schema_name?: string | null;
  namespace_name?: string | null;
  table_name?: string | null;
  column_name?: string | null;
  target_ref?: string | null;
}): string {
  if (row.target_display) return row.target_display;
  if (row.source_name_cn) return row.source_name_cn;
  const parts = [row.schema_name || row.namespace_name, row.table_name, row.column_name].filter(Boolean);
  if (parts.length) return parts.join(".");
  return row.target_ref && !row.target_ref.includes("_oracle_") && !row.target_ref.includes("_10_10_")
    ? row.target_ref
    : "-";
}

export function findingDbText(row: {
  schema_name?: string | null;
  namespace_name?: string | null;
  source_name_cn?: string | null;
  related_schema?: string | null;
}): string {
  const left = row.schema_name || row.namespace_name || row.source_name_cn || "";
  if (row.related_schema && row.related_schema !== left) {
    return left ? `${left} → ${row.related_schema}` : row.related_schema;
  }
  return left || "-";
}

export function findingTableTitle(row: {
  table_name_cn?: string | null;
  table_name?: string | null;
  related_table_cn?: string | null;
  related_table?: string | null;
  source_name_cn?: string | null;
}): string {
  const left = row.table_name_cn || row.table_name || "";
  const right = row.related_table_cn || row.related_table || "";
  if (left && right) return `${left} → ${right}`;
  return left || row.source_name_cn || "-";
}

export function findingTableCode(row: {
  table_name_cn?: string | null;
  table_name?: string | null;
  related_table_cn?: string | null;
  related_table?: string | null;
}): string {
  const parts: string[] = [];
  if (row.table_name_cn && row.table_name) parts.push(row.table_name);
  if (row.related_table_cn && row.related_table) parts.push(row.related_table);
  return parts.join(" → ");
}

export function findingColumnText(row: {
  column_name?: string | null;
  related_field?: string | null;
}): string {
  const left = String(row.column_name || "").trim();
  const right = String(row.related_field || "").trim();
  if (left && right) return `${left} → ${right}`;
  return left || right || "-";
}

export function findingProblemText(row: {
  problem?: string | null;
  rule_name?: string | null;
  metric_value?: string | null;
  target_display?: string | null;
  table_name?: string | null;
  source_name_cn?: string | null;
}): string {
  if (row.problem) return row.problem;
  const title = row.rule_name || "质量问题";
  const target = row.target_display || row.source_name_cn || row.table_name || "";
  if (target) return `${title}：${target}`;
  return title;
}

export function ruleTargetText(row: {
  namespace_name?: string | null;
  target_table?: string | null;
  target_field?: string | null;
  related_table?: string | null;
  related_field?: string | null;
  business_domain?: string | null;
}): string {
  if (row.related_table) {
    const left = [row.target_table, row.target_field].filter(Boolean).join(".");
    const right = [row.related_table, row.related_field].filter(Boolean).join(".");
    return `${left || "-"} → ${right || "-"}`;
  }
  const parts = [row.namespace_name, row.target_table, row.target_field].filter(Boolean);
  if (parts.length) return parts.join(".");
  return row.business_domain || "平台元数据";
}
