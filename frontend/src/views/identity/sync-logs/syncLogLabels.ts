import { formatTime } from "@/utils/format";

export function syncStatusLabel(value?: string | null): string {
  const map: Record<string, string> = {
    success: "成功",
    partial_success: "部分成功",
    failed: "失败",
    skipped: "已跳过",
    running: "进行中",
    overdue: "超时未跑",
    misconfigured: "调度配置异常",
    pending: "等待中",
    planned: "已计划",
    executed: "已执行",
    rolled_back: "已回滚"
  };
  return map[String(value || "")] || value || "-";
}

export function syncStatusTag(value?: string | null): "success" | "warning" | "danger" | "info" {
  const map: Record<string, "success" | "warning" | "danger" | "info"> = {
    success: "success",
    executed: "success",
    partial_success: "warning",
    running: "warning",
    overdue: "danger",
    failed: "danger",
    misconfigured: "danger",
    skipped: "info",
    pending: "info",
    planned: "info"
  };
  return map[String(value || "")] || "info";
}

export function formatDuration(ms?: number | null): string {
  if (ms == null || Number(ms) < 0) return "-";
  const total = Math.round(Number(ms) / 1000);
  if (total < 60) return `${total} 秒`;
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分`;
}

// F7：私有 replace("T"," ") 副本收编 → utils/format formatTime 单份实现。
export const formatDateTime = formatTime;
