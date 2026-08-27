/** Shared enum labels for metadata change events (diff page + changes list). */
export type TagType = "primary" | "success" | "warning" | "danger" | "info";

export function changeTypeLabel(type?: string | null): string {
  const map: Record<string, string> = {
    table_added: "新增表",
    table_removed: "删除表",
    column_added: "新增字段",
    column_removed: "删除字段",
    column_data_type_changed: "字段类型变更",
    column_type_changed: "字段类型变更",
    column_length_changed: "字段长度变更",
    column_nullable_changed: "非空约束变更",
    column_comment_changed: "字段注释变更",
    column_renamed: "字段重命名"
  };
  return type ? map[type] ?? type : "-";
}

export function changeTypeColor(type?: string | null): TagType {
  if (!type) return "info";
  if (type.endsWith("_added")) return "success";
  if (type.endsWith("_removed")) return "danger";
  if (type.endsWith("_changed")) return "warning";
  return "info";
}

export function severityLabel(sev?: string | null): string {
  const map: Record<string, string> = {
    info: "提示",
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重"
  };
  return sev ? map[sev] ?? sev : "-";
}

export function severityColor(sev?: string | null): TagType {
  const map: Record<string, TagType> = {
    info: "info",
    low: "success",
    medium: "warning",
    high: "danger",
    critical: "danger"
  };
  return sev ? map[sev] ?? "info" : "info";
}

export function statusLabel(s?: string | null): string {
  const map: Record<string, string> = {
    open: "待处理",
    acknowledged: "已确认",
    ignored: "已忽略",
    resolved: "已解决"
  };
  return s ? map[s] ?? s : "-";
}

export function statusTagType(s?: string | null): TagType {
  const map: Record<string, TagType> = {
    open: "danger",
    acknowledged: "warning",
    ignored: "info",
    resolved: "success"
  };
  return s ? map[s] ?? "info" : "info";
}
