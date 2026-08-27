/**
 * Cross-cutting enum labels/tags (146 D2).
 *
 * View-local label modules stay where they are; anything shared by two or
 * more domains (relation validation, quality severity, sync diff, account
 * status, ops run status) lives here as the single fallback source. These
 * maps are labels for display only — option lists must stay backend-driven.
 */
export type TagType = "primary" | "success" | "warning" | "danger" | "info";

function labelOf(map: Record<string, string>, value?: string | null, fallback = "-"): string {
  return value ? map[value] ?? value : fallback;
}

function tagOf(map: Record<string, TagType>, value?: string | null): TagType {
  return value ? map[value] ?? "info" : "info";
}

// ── 关系验证 ──
const RELATION_VALIDATION: Record<string, string> = {
  verified: "已验证",
  A_rechecked: "复核确认 (A)",
  A: "抽样验证 (A)",
  B: "结构匹配 (B)",
  C: "文档推断 (C)",
  D: "跨系统待验证 (D)",
  candidate: "候选",
  rejected: "已驳回",
  draft: "草稿",
  active: "生效",
  inactive: "停用"
};
const RELATION_VALIDATION_TAG: Record<string, TagType> = {
  verified: "success",
  A_rechecked: "success",
  A: "success",
  B: "primary",
  C: "warning",
  D: "info",
  rejected: "danger",
  draft: "warning",
  active: "success",
  inactive: "info"
};
export const relationValidationLabel = (v?: string | null) => labelOf(RELATION_VALIDATION, v);
export const relationValidationTag = (v?: string | null) => tagOf(RELATION_VALIDATION_TAG, v);

// ── 质量严重度 ──
const QUALITY_SEVERITY: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低",
  info: "提示",
  major: "主要",
  minor: "次要"
};
const QUALITY_SEVERITY_TAG: Record<string, TagType> = {
  critical: "danger",
  major: "danger",
  high: "danger",
  medium: "warning",
  minor: "warning",
  low: "success",
  info: "info"
};
export const qualitySeverityLabel = (v?: string | null) => labelOf(QUALITY_SEVERITY, v);
export const qualitySeverityTag = (v?: string | null) => tagOf(QUALITY_SEVERITY_TAG, v);

// ── 同步差异处理状态 ──
const SYNC_DIFF_STATUS: Record<string, string> = {
  pending: "待处理",
  confirmed: "已确认",
  applied: "已应用",
  skipped: "已跳过",
  conflict: "冲突",
  resolved: "已解决"
};
export const syncDiffStatusLabel = (v?: string | null) => labelOf(SYNC_DIFF_STATUS, v);

// ── 账号状态 ──
const ACCOUNT_STATUS: Record<string, string> = {
  active: "在用",
  inactive: "停用",
  locked: "锁定",
  disabled: "已禁用",
  pending: "待生效",
  expired: "已过期"
};
const ACCOUNT_STATUS_TAG: Record<string, TagType> = {
  active: "success",
  inactive: "info",
  locked: "warning",
  disabled: "danger",
  pending: "warning",
  expired: "info"
};
export const accountStatusLabel = (v?: string | null) => labelOf(ACCOUNT_STATUS, v);
export const accountStatusTag = (v?: string | null) => tagOf(ACCOUNT_STATUS_TAG, v);

// ── 运维任务状态：succeeded 为唯一成功终态，executed 仅历史只读兼容 ──
const OPS_RUN_STATUS: Record<string, string> = {
  draft: "草稿",
  pending: "待审批",
  submitted: "已提交",
  approved: "已审批",
  rejected: "已驳回",
  executing: "执行中",
  succeeded: "成功",
  failed: "失败",
  cancelled: "已取消",
  executed: "成功（旧终态）"
};
const OPS_RUN_STATUS_TAG: Record<string, TagType> = {
  draft: "warning",
  pending: "warning",
  submitted: "warning",
  executing: "warning",
  succeeded: "success",
  approved: "success",
  rejected: "danger",
  failed: "danger",
  cancelled: "info",
  executed: "info"
};
export const opsRunStatusLabel = (v?: string | null) => labelOf(OPS_RUN_STATUS, v);
export const opsRunStatusTag = (v?: string | null) => tagOf(OPS_RUN_STATUS_TAG, v);
/** New writes must use `succeeded`; `executed` is read-only legacy. */
export const OPS_RUN_SUCCESS_TERMINAL = "succeeded";
