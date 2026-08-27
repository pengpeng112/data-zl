export const RELATION_CLASS_TABS = [
  { value: "pending", label: "待复核" },
  { value: "confirmed", label: "已确认" },
  { value: "rejected", label: "已拒绝" },
  { value: "candidate", label: "视图推断" },
  { value: "lineage", label: "同步/镜像" },
  { value: "dependency", label: "视图依赖" },
  { value: "all", label: "全部关系" }
] as const;

export type RelationClassTab = (typeof RELATION_CLASS_TABS)[number]["value"];

const REVIEW_STATUS_BY_TAB: Record<string, string> = {
  pending: "draft",
  confirmed: "approved",
  rejected: "rejected"
};

export function normalizeRelationClass(value?: string | number | null): RelationClassTab {
  const raw = String(value ?? "").trim();
  if (!raw) return "pending";
  return RELATION_CLASS_TABS.some(tab => tab.value === raw) ? raw as RelationClassTab : "pending";
}

export function relationEvidenceKind(note?: string | null, fromColumns?: string | null, toColumns?: string | null): "view_ddl" | "sampled" | "sync" | "imported" {
  const text = String(note || "").toLowerCase();
  if (text.includes("pg_views") || text.includes("vastbase") || text.includes("all_dependencies")) return "view_ddl";
  if (text.includes("sample") || text.includes("抽样") || text.includes("bounded") || text.includes("evidence")) return "sampled";
  if (text.includes("sync") || text.includes("镜像") || text.includes("汇聚")) return "sync";
  if (!String(fromColumns || "").trim() && !String(toColumns || "").trim()) return "view_ddl";
  return "imported";
}

export function relationEvidenceLabel(kind: string): string {
  const map: Record<string, string> = {
    view_ddl: "视图解析，无 JOIN 字段",
    sampled: "库表抽样/证据",
    sync: "同步/镜像",
    imported: "资产导入"
  };
  return map[kind] || "关系";
}

export function displayRelationColumns(value?: string | null, inferred?: string | null): { text: string; inferred: boolean } {
  const raw = String(value || "").trim();
  if (raw) return { text: raw, inferred: false };
  const guess = String(inferred || "").trim();
  if (guess) return { text: `${guess}（推断）`, inferred: true };
  return { text: "未解析", inferred: false };
}

export function reviewStatusForTab(value?: string | null): string {
  return REVIEW_STATUS_BY_TAB[normalizeRelationClass(value)] || "";
}

export function relationClassQuery(value?: string | null): Record<string, string> {
  const tab = normalizeRelationClass(value);
  return tab === "pending" ? {} : { class: tab };
}
