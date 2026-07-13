import type { GraphEdge, GraphFieldMapping } from "@/api/asset";

export interface GraphEvidenceMetricRow {
  key: string;
  label: string;
  value: string;
}

const METRIC_LABELS: Record<string, string> = {
  coverage_rate: "覆盖率",
  cover_rate: "覆盖率",
  matched_rate: "覆盖率",
  pass_rate: "通过率",
  orphan_rate: "孤儿率",
  source_orphan_rate: "来源孤儿率",
  target_orphan_rate: "目标孤儿率",
  orphan_count: "孤儿数",
  matched_rows: "匹配行数",
  source_rows: "来源行数",
  target_rows: "目标行数",
  sample_size: "样本量",
  sample_rows: "样本行数",
  distinct_source_keys: "来源去重键数",
  distinct_target_keys: "目标去重键数",
  source_document: "来源文档",
  source_file: "来源文件",
  source_view: "来源视图"
};

function clean(value?: string | number | boolean | null) {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function splitColumns(value?: string | null) {
  return String(value || "")
    .split(/[;,，、|]/)
    .map(item => item.trim())
    .filter(Boolean);
}

function parseMetricsObject(value?: string | null): Record<string, unknown> | null {
  const text = clean(value);
  if (!text) return null;
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : { value: parsed };
  } catch {
    return null;
  }
}

function formatMetricValue(key: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") {
    const lower = key.toLowerCase();
    if ((lower.includes("rate") || lower.includes("ratio")) && value >= 0 && value <= 1) return `${(value * 100).toFixed(2)}%`;
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function buildFieldMappingRows(edge: GraphEdge): GraphFieldMapping[] {
  if (edge.field_mappings?.length) return edge.field_mappings;
  const fromColumns = splitColumns(edge.from_columns);
  const toColumns = splitColumns(edge.to_columns);
  const length = Math.max(fromColumns.length, toColumns.length);
  if (!length) return [];
  return Array.from({ length }, (_, index) => ({
    from_column: fromColumns[index] || null,
    to_column: toColumns[index] || null
  }));
}

export function fieldMappingSummary(edge: GraphEdge) {
  const rows = buildFieldMappingRows(edge);
  if (rows.length) return rows.map(item => `${item.from_column || "-"} -> ${item.to_column || "-"}`).join("; ");
  return `${edge.from_columns || "-"} -> ${edge.to_columns || "-"}`;
}

export function buildEvidenceMetricRows(edge: GraphEdge): GraphEvidenceMetricRow[] {
  const parsed = parseMetricsObject(edge.validation_metrics);
  if (!parsed) return [];
  return Object.entries(parsed).map(([key, value]) => {
    const normalizedKey = key.toLowerCase();
    return {
      key,
      label: METRIC_LABELS[normalizedKey] || key,
      value: formatMetricValue(normalizedKey, value)
    };
  });
}

export function rawEvidenceMetrics(edge: GraphEdge) {
  return clean(edge.validation_metrics) || "-";
}

export function evidenceSourceText(edge: GraphEdge) {
  const parsed = parseMetricsObject(edge.validation_metrics);
  const fromMetrics = parsed ? clean(parsed.source_document as string) || clean(parsed.source_file as string) || clean(parsed.source_view as string) : undefined;
  return fromMetrics || clean(edge.note) || clean(edge.validation_note) || "-";
}
export const DEFERRED_RELATION_VERIFICATION_TEXT = "等待 EMR/LIS/PACS/护理/手麻源库验证；验证前不能作为正式血缘/ER 依据。";

export function deferredRelationVerificationText() {
  return DEFERRED_RELATION_VERIFICATION_TEXT;
}
