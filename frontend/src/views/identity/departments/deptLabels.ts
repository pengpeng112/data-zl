export const DEPT_TYPE_OPTIONS = [
  { value: "0", label: "门诊" },
  { value: "1", label: "住院" },
  { value: "2", label: "门诊住院" },
  { value: "3", label: "医技" },
  { value: "9", label: "其他" }
];

const TYPE_LABELS: Record<string, string> = Object.fromEntries(
  DEPT_TYPE_OPTIONS.map(item => [item.value, item.label])
);

export function deptTypeLabel(value?: string | null): string {
  const raw = String(value ?? "").trim();
  return TYPE_LABELS[raw] || raw || "-";
}

export function deptStatusLabel(value?: string | null): string {
  const map: Record<string, string> = {
    active: "启用",
    inactive: "停用",
    stopped: "停用",
    disabled: "停用"
  };
  return map[String(value || "").toLowerCase()] || value || "-";
}

export function deptReviewLabel(value?: string | null): string {
  const map: Record<string, string> = {
    unreviewed: "未复核",
    reviewed: "已复核",
    confirmed: "已确认"
  };
  return map[String(value || "").toLowerCase()] || value || "-";
}

export function formatSyncTime(value?: string | null): string {
  if (!value) return "-";
  return String(value).replace("T", " ").slice(0, 19);
}
