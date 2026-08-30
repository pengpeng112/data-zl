/**
 * 146 E10（R5）：质量页共享类型与展示工具。
 * 从 1857 行的 quality/index.vue 抽出的纯函数/类型，供页面与测试复用；
 * 业务逻辑保持原样，只做结构性拆分（不重写行为）。
 */

export interface SystemSummaryItem {
  system_code: string;
  system_name_cn?: string;
  total_findings: number;
  open_count: number;
  resolved_count: number;
  critical_count: number;
}

export interface RuleItem {
  id: number;
  rule_code: string;
  rule_name: string;
  rule_category: string;
  check_scope: string;
  constraint_level: string;
  business_domain: string;
  execution_mode: string;
  system_code?: string;
  namespace_name?: string;
  target_table: string;
  target_field: string;
  related_table?: string;
  related_field?: string;
  check_sql: string;
  description: string;
  enabled: boolean;
}

export interface RuleCreateForm {
  rule_code: string;
  rule_name: string;
  rule_category: string;
  check_scope: string;
  constraint_level: string;
  business_domain: string;
  execution_mode: string;
  target_table: string;
  target_field: string;
  check_sql: string;
  description: string;
  enabled: boolean;
}

export interface CheckRunItem {
  id: number;
  task_id: string;
  system_code: string;
  system_name_cn?: string;
  started_at: string;
  triggered_by: string;
  total_rules: number;
  total_findings: number;
  total_records: number;
  error_records: number;
  pass_rate: number | null;
  status: string;
  failed_reason: string;
}

export interface FindingItem {
  id: number;
  rule_code: string;
  rule_name?: string;
  rule_category?: string;
  rule_description?: string;
  problem?: string;
  target_display?: string;
  target_ref?: string;
  system_name_cn?: string;
  source_name_cn?: string;
  schema_name?: string;
  namespace_name?: string;
  table_name: string;
  table_name_cn?: string;
  column_name: string;
  related_schema?: string;
  related_table?: string;
  related_table_cn?: string;
  related_field?: string;
  severity: string;
  status: string;
  metric_value?: string;
  error_cnt: number;
  error_rate: number | null;
  assigned_to: string;
  sample_data: any;
}

export interface MetricsData {
  total_rules: number;
  enabled_rules?: number;
  suggested_rules?: number;
  sql_rules: number;
  pass_rate: number | null;
  rules_pass_rate?: number | null;
  resolution_rate?: number | null;
  rule_categories: { category: string; count: number }[];
  top_tables: { table: string; count: number }[];
}

export type QualityTagType = "primary" | "success" | "warning" | "danger" | "info";

export function runStatusLabel(status?: string | null): string {
  const map: Record<string, string> = {
    success: "成功",
    failed: "失败",
    running: "运行中",
    pending: "待执行"
  };
  return map[status || ""] || status || "-";
}

export function severityLabel(severity?: string | null): string {
  const map: Record<string, string> = {
    critical: "严重",
    major: "重要",
    minor: "一般",
    info: "信息"
  };
  return map[severity || ""] || severity || "";
}

export function severityTag(severity?: string | null): QualityTagType {
  const map: Record<string, QualityTagType> = {
    critical: "danger",
    major: "warning",
    minor: "primary",
    info: "info"
  };
  return map[severity ?? ""] || "info";
}

export function findingStatusLabel(status?: string | null): string {
  const map: Record<string, string> = {
    open: "待处理",
    assigned: "已分派",
    confirmed: "已确认",
    fixed: "已修复",
    rechecked: "已复核",
    acknowledged: "已确认",
    resolved: "已解决",
    ignored: "已忽略",
    rule_error: "规则错误"
  };
  return map[status ?? ""] || status || "";
}

export function findingStatusTag(status?: string | null): QualityTagType {
  const map: Record<string, QualityTagType> = {
    open: "danger",
    assigned: "warning",
    confirmed: "primary",
    fixed: "success",
    rechecked: "success",
    acknowledged: "warning",
    resolved: "success",
    ignored: "info",
    rule_error: "danger"
  };
  return map[status ?? ""] || "info";
}

export function formatPercent(value: number | null | undefined): string {
  return value == null ? "-" : `${Number(value).toFixed(1)}%`;
}

export function passRateTone(rate: number | null | undefined): "accent" | "warning" | "danger" {
  if (rate == null) return "warning";
  if (rate >= 95) return "accent";
  if (rate >= 80) return "warning";
  return "danger";
}

export function passRateClass(rate: number | null | undefined): string {
  return `metric-${passRateTone(rate)}`;
}

export function formatSampleData(data: unknown): string {
  if (!data) return "无";
  try {
    return typeof data === "string" ? data : JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}
