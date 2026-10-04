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

/** 213 UI-09：数据集域枚举中文映射（状态/访问决策/用途/粒度）。 */
const DATASET_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
  revoked: "已撤销",
  archived: "已归档"
};

const DATASET_DECISION_LABELS: Record<string, string> = {
  deny_no_grant: "未授权拒绝",
  deny_no_purpose: "用途不匹配",
  deny_pending: "待授权",
  allow: "已授权"
};

const DATASET_PURPOSE_LABELS: Record<string, string> = {
  research: "科研",
  clinical: "临床",
  quality: "质控",
  management: "管理",
  teaching: "教学"
};

const DATASET_GRAIN_LABELS: Record<string, string> = {
  patient: "患者级",
  visit: "就诊级",
  record: "记录级",
  daily: "日级"
};

function lookupLabel(
  map: Record<string, string>,
  value?: string | null
): string | null {
  if (!value) return null;
  return map[value] ?? null;
}

/** 数据集状态中文（无映射时回退原值，便于新枚举可见）。 */
export function datasetStatusLabel(value?: string | null): string {
  return lookupLabel(DATASET_STATUS_LABELS, value) ?? value ?? "-";
}

/** 数据集访问决策中文。 */
export function datasetDecisionLabel(value?: string | null): string {
  return lookupLabel(DATASET_DECISION_LABELS, value) ?? value ?? "受限";
}

/** 数据集用途中文。 */
export function datasetPurposeLabel(value?: string | null): string {
  return lookupLabel(DATASET_PURPOSE_LABELS, value) ?? value ?? "-";
}

/** 数据集粒度中文。 */
export function datasetGrainLabel(value?: string | null): string {
  return lookupLabel(DATASET_GRAIN_LABELS, value) ?? value ?? "-";
}
