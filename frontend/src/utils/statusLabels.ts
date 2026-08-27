/**
 * 153 F5：状态映射与鉴权提示的共享工具（仅收敛既有重复，不造新抽象层）。
 */
import type { TagType } from "@/views/metadata-changes/labels";

export type { TagType };

/** 通用状态中文标签（open/assigned/resolved…，多页共用口径）。 */
export function commonStatusLabel(value?: string | null): string {
  const map: Record<string, string> = {
    open: "未处理",
    assigned: "已分派",
    confirmed: "已确认",
    fixed: "已修复",
    rechecked: "已复核",
    acknowledged: "已确认",
    resolved: "已解决",
    ignored: "已忽略",
    rule_error: "规则错误",
    active: "启用",
    inactive: "停用",
    enabled: "启用",
    disabled: "停用",
    pending: "待处理",
    approved: "已批准",
    rejected: "已驳回",
    executed: "已执行",
    draft: "草稿",
    success: "成功",
    failed: "失败",
    running: "运行中"
  };
  return map[value ?? ""] ?? value ?? "-";
}

/** 通用状态标签色。 */
export function commonStatusTag(value?: string | null): TagType {
  const map: Record<string, TagType> = {
    open: "danger",
    assigned: "warning",
    confirmed: "primary",
    fixed: "success",
    rechecked: "success",
    acknowledged: "warning",
    resolved: "success",
    ignored: "info",
    rule_error: "danger",
    active: "success",
    inactive: "info",
    enabled: "success",
    disabled: "info",
    pending: "danger",
    approved: "warning",
    executed: "success",
    rejected: "info",
    draft: "danger",
    success: "success",
    failed: "danger",
    running: "warning"
  };
  return map[value ?? ""] ?? "info";
}

/**
 * 401/403 → 鉴权提示文案（返回 null 表示非鉴权错误）。
 * 此前在 dict/medical 与 dict/mappings 各自内联 3 份。
 */
export function authHintForStatus(
  status?: number
): "接口未授权：请先登录并使用部署脚本生成的 Token。" | "API Token 无效或已禁用：请联系管理员重新生成并绑定 Token。" | null {
  if (status === 401) return "接口未授权：请先登录并使用部署脚本生成的 Token。";
  if (status === 403) return "API Token 无效或已禁用：请联系管理员重新生成并绑定 Token。";
  return null;
}
