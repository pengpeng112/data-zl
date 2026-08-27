import type { DictImportItem } from "@/api/dict";

export interface ImportParseResult {
  items: DictImportItem[];
  error: string | null;
}

/**
 * Parse pasted dictionary items. Accepts a JSON array (optionally wrapped in
 * an object with an `items` key) or one `code,name` pair per line (comma or
 * tab separated, name optional -> falls back to code).
 */
export function parseImportText(text: string, limit = 1000): ImportParseResult {
  const trimmed = (text || "").trim();
  if (!trimmed) {
    return { items: [], error: "请粘贴 JSON 数组或每行 编码,名称 的 CSV 内容" };
  }
  if (trimmed.startsWith("[")) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(trimmed);
    } catch {
      return { items: [], error: "JSON 解析失败，请检查格式" };
    }
    if (!Array.isArray(parsed)) {
      return { items: [], error: "JSON 顶层必须是数组" };
    }
    const items: DictImportItem[] = [];
    for (const entry of parsed) {
      if (!entry || typeof entry !== "object") continue;
      const record = entry as Record<string, unknown>;
      items.push({
        system_item_code: String(record.system_item_code ?? record.code ?? "").trim(),
        system_item_name_cn: String(record.system_item_name_cn ?? record.name ?? "").trim(),
        source_table: record.source_table == null ? undefined : String(record.source_table)
      });
    }
    if (parsed.length > limit) {
      return { items: [], error: `条目数 ${parsed.length} 超过上限 ${limit}` };
    }
    return { items, error: null };
  }
  const lines = trimmed.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  if (lines.length > limit) {
    return { items: [], error: `条目数 ${lines.length} 超过上限 ${limit}` };
  }
  const items = lines.map(line => {
    const [code, ...rest] = line.split(/[,\t]/);
    const name = rest.join(",").trim();
    return {
      system_item_code: (code || "").trim(),
      system_item_name_cn: name || (code || "").trim()
    };
  });
  return { items, error: null };
}

export function rawStatusLabel(rawStatus?: string | null): string {
  return rawStatus || "-";
}

export function confidenceLabel(confidence?: string | null): string {
  if (confidence === "high") return "高";
  if (confidence === "medium") return "中";
  if (confidence === "low") return "低";
  return confidence || "-";
}
