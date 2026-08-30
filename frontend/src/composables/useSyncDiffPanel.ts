/**
 * 146 E8（R5）：identity/sync-diffs 与 dict/sync-diffs 共享的同步差异面板工具。
 *
 * 两个差异页共用：状态/严重度中文标签与 tag 色、before/after 字段级 diff、
 * 前端串行批量处理（明确汇总部分失败，不伪造后端批量接口），
 * 以及按状态取全量 summary（服务端 total）。
 */
import { extractErrorDetail } from "@/utils/errorMessage";

export type SyncDiffTagTone = "success" | "warning" | "info";

export function syncDiffStatusLabel(value?: string | null): string {
  const map: Record<string, string> = { open: "未处理", resolved: "已解决", ignored: "已忽略" };
  return map[value || ""] || value || "-";
}

export function syncDiffStatusTag(value?: string | null): SyncDiffTagTone {
  return value === "resolved" ? "success" : value === "ignored" ? "info" : "warning";
}

export function syncSeverityLabel(value?: string | null): string {
  const map: Record<string, string> = { high: "高", medium: "中", low: "低" };
  return map[value || ""] || value || "-";
}

export function syncSeverityTag(value?: string | null): "danger" | "warning" | "info" {
  return value === "high" ? "danger" : value === "medium" ? "warning" : "info";
}

export interface SyncDiffFieldRow {
  field: string;
  before: string;
  after: string;
  changed: boolean;
}

function diffCellText(value: unknown): string {
  if (value === undefined) return "（无）";
  if (value === null) return "-";
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

/** 字段级 diff：取 before/after 键并集，逐字段给出差异前后值与是否变化。 */
export function buildSyncDiffFieldDiff(before: unknown, after: unknown, maxFields = 50): SyncDiffFieldRow[] {
  const beforeMap = (before && typeof before === "object" ? before : {}) as Record<string, unknown>;
  const afterMap = (after && typeof after === "object" ? after : {}) as Record<string, unknown>;
  const fields = Array.from(new Set([...Object.keys(beforeMap), ...Object.keys(afterMap)])).sort();
  return fields.slice(0, maxFields).map(field => {
    const beforeValue = field in beforeMap ? beforeMap[field] : undefined;
    const afterValue = field in afterMap ? afterMap[field] : undefined;
    return {
      field,
      before: diffCellText(beforeValue),
      after: diffCellText(afterValue),
      changed: diffCellText(beforeValue) !== diffCellText(afterValue)
    };
  });
}

export interface SerialBatchResult {
  done: number;
  failed: number;
  lastError: string;
}

/**
 * 前端串行批量处理：逐条执行并统计成功/失败；任何一条失败不中断剩余条目。
 * 用于后端无批量接口时的明确串行语义（146 E8：批量处理汇总部分失败）。
 */
export async function runSerialBatch<T>(
  items: T[],
  action: (item: T, index: number) => Promise<void>
): Promise<SerialBatchResult> {
  const result: SerialBatchResult = { done: 0, failed: 0, lastError: "" };
  for (const [index, item] of items.entries()) {
    try {
      await action(item, index);
      result.done += 1;
    } catch (error) {
      result.failed += 1;
      result.lastError = extractErrorDetail(error, "单条处理失败");
    }
  }
  return result;
}

export type SyncDiffTotals = Record<string, number>;

/**
 * 全量 summary：按状态各取一次 page_size=1 的 total（服务端统计，不受当前页影响）。
 * 某状态查询失败时以 -1 占位，页面显示“未知”而非伪造 0。
 */
export async function loadSyncDiffTotals(
  fetcher: (params: { page: number; page_size: number; status?: string }) => Promise<{ total: number }>,
  statuses: string[] = ["open", "resolved", "ignored"]
): Promise<SyncDiffTotals> {
  const entries = await Promise.all(
    statuses.map(status =>
      fetcher({ page: 1, page_size: 1, status })
        .then(data => [status, data.total ?? 0] as const)
        .catch(() => [status, -1] as const)
    )
  );
  return Object.fromEntries(entries);
}
