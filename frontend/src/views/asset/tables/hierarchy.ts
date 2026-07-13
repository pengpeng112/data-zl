/** 资产五层导航：系统大类 -> 系统/库 -> schema/owner -> 表 -> 字段 */

export type TreeKind = "category" | "system" | "schema" | "table" | "column";

export const CATEGORY_ORDER = [
  "ods_center",
  "his_source",
  "external_business",
  "hrp_source",
  "platform_asset"
] as const;

export const CATEGORY_LABEL: Record<string, string> = {
  ods_center: "ODS 数据中心系统",
  his_source: "HIS 源端系统",
  hrp_source: "HRP 源端系统",
  external_business: "其他业务系统",
  platform_asset: "平台元数据系统"
};

export function kindLabel(kind: TreeKind) {
  const labels: Record<TreeKind, string> = {
    category: "大类",
    system: "系统/库",
    schema: "Owner",
    table: "表",
    column: "字段"
  };
  return labels[kind];
}

export function kindTagType(
  kind: TreeKind
): "primary" | "success" | "info" | "warning" | "danger" {
  const types = {
    category: "primary",
    system: "success",
    schema: "info",
    table: "warning",
    column: "danger"
  } as const;
  return types[kind];
}
