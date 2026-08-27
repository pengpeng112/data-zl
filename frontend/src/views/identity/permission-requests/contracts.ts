import type { PermissionRequestItem } from "@/api/permissions";

type RequestRow = Pick<PermissionRequestItem, "entity_type"> & {
  request_content?: Record<string, unknown> | null;
  request_payload?: Record<string, unknown> | null;
};

/** Human-readable summary of what a permission request asks for. */
export function requestContentLabel(row: RequestRow): string {
  const content = (row.request_content || row.request_payload || {}) as Record<string, unknown>;
  if (row.entity_type === "user_role") {
    return `角色：${content.role_code || "-"}`;
  }
  const parts = [content.scope_type, content.system_code, content.source_code, content.schema_name, content.domain]
    .filter(Boolean)
    .join(" / ");
  return `数据范围：${parts || "-"}`;
}

const REQUEST_STATUS_LABELS: Record<string, string> = {
  pending: "待审批",
  approved: "已通过",
  rejected: "已驳回",
  executed: "已执行",
  revoked: "已撤销"
};

export function requestStatusLabel(status?: string): string {
  return status ? REQUEST_STATUS_LABELS[status] || status : "-";
}
