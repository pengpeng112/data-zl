export function personTypeLabel(value?: string | null): string {
  const map: Record<string, string> = {
    formal: "正式",
    temporary: "临时",
    doctor: "医生",
    nurse: "护士",
    technician: "技师",
    admin: "行政",
    other: "其他"
  };
  return map[String(value || "")] || value || "-";
}

export function employmentLabel(value?: string | null): string {
  const map: Record<string, string> = {
    active: "在职",
    inactive: "停用",
    retired: "离职",
    unknown: "未标注"
  };
  return map[String(value || "")] || value || "未标注";
}

export function classificationLabel(value?: string | null): string {
  const map: Record<string, string> = {
    doctor: "医生",
    nurse: "护士",
    pharmacist: "药师",
    excluded_outsource: "外包排除",
    excluded_management: "管理排除",
    classification_conflict: "分类冲突",
    status_conflict: "状态冲突",
    legacy_unmanaged: "历史未纳管",
    master_data_missing: "主数据缺失"
  };
  return map[String(value || "")] || value || "-";
}

export function deptDisplay(row: { dept_name_cn?: string | null; dept_code?: string | null }): string {
  if (row.dept_name_cn) return row.dept_name_cn;
  return row.dept_code || "-";
}
