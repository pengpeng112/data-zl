/** 资产目录导航：业务系统 → 连接 → schema/owner → 表 → 字段（plan 90） */

export type TreeKind = "system" | "connection" | "schema" | "table" | "column";

/** 十个一级业务系统标准码（展示名一律来自后端 system_name_cn） */
export const CANONICAL_SYSTEM_CODES = [
  "HIS_SOURCE",
  "HRP",
  "DATA_CENTER",
  "JHEMR_VASTBASE",
  "DOCARE",
  "MOBILE_NURSING",
  "LIS_SOURCE",
  "PACS_SOURCE",
  "PAPERLESS_CDMS",
  "ULTRASOUND_ENDOSCOPY"
] as const;

/** @deprecated 大类已废除；保留空映射避免旧 import 崩溃 */
export const CATEGORY_ORDER: readonly string[] = [];

/** @deprecated 禁止再展示「其他业务系统」等大类 */
export const CATEGORY_LABEL: Record<string, string> = {
  catalog_anomaly: "目录异常"
};

export function kindLabel(kind: TreeKind | string) {
  const labels: Record<string, string> = {
    system: "业务系统",
    connection: "数据库连接",
    schema: "Owner/Schema",
    table: "表",
    column: "字段",
    // 兼容旧 kind
    category: "业务系统"
  };
  return labels[kind] || kind;
}

export function kindTagType(
  kind: TreeKind | string
): "primary" | "success" | "info" | "warning" | "danger" {
  const types: Record<string, "primary" | "success" | "info" | "warning" | "danger"> = {
    system: "primary",
    connection: "success",
    schema: "info",
    table: "warning",
    column: "danger",
    category: "primary"
  };
  return types[kind] || "info";
}

/** 禁止出现在 UI 中的旧大类文案 */
export const FORBIDDEN_CATEGORY_LABELS = [
  "其他业务系统",
  "平台元数据系统",
  "HIS源端系统",
  "HIS 源端系统",
  "HRP源端系统",
  "HRP 源端系统",
  "ODS 数据中心系统",
  "ODS数据中心系统"
] as const;

export function isForbiddenCategoryLabel(label: string | null | undefined): boolean {
  if (!label) return false;
  return (FORBIDDEN_CATEGORY_LABELS as readonly string[]).includes(label.trim());
}
