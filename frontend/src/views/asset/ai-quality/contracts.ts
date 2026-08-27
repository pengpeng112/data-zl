import type { AiQualityPreview, AiQualityStatus } from "@/api/asset";

export const AI_QUALITY_MAX_FINDINGS = 50;

export function limitFindingIds(ids: number[]) {
  return Array.from(new Set(ids.filter(Number.isFinite))).slice(0, AI_QUALITY_MAX_FINDINGS);
}

export function canSubmitAiQuality(status: AiQualityStatus | null, preview: AiQualityPreview | null) {
  const provider = status?.provider;
  return Boolean(
    (provider === "hospital_llm" || provider === "dify")
    && status.enabled
    && status.configured
    && preview?.input_digest
    && (preview.item_count == null || preview.item_count <= AI_QUALITY_MAX_FINDINGS)
  );
}

export function usesHospitalLlm(status: AiQualityStatus | null) {
  return status?.provider === "hospital_llm";
}

export function aiQualityStatusLabel(status: AiQualityStatus | null) {
  if (!status?.enabled) return "已关闭";
  if (!status.configured) return "未配置";
  if (status.reachable === false) return "连接失败";
  return "可用";
}

export function aiQualityErrorLabel(errorClass?: string | null) {
  if (errorClass === "contract") return "结果被安全校验拦住，请看右侧已生成内容，或再分析一次";
  if (errorClass === "timeout") return "院内模型超时，请稍后再试";
  if (errorClass === "network") return "院内模型网络中断，请稍后再试";
  if (errorClass === "stale_running") return "上次分析未正常结束，请重新点分析";
  return errorClass ? `分析中断：${errorClass}` : "分析中断";
}
