/**
 * 108 号物理节点规范化。
 *
 * 节点唯一身份 = id / physical_key（system|source|namespace|schema|table）。
 * display_id 只用于展示；同一 display_id 可对应多个物理节点（跨来源同名表），
 * 规范化不得按 display_id 去重。
 */
import type { GraphEdge, GraphNode } from "@/api/asset";

/** 从物理键解析五元组；非 5 段返回 null。 */
export function parsePhysicalKey(key: string | null | undefined): {
  system: string;
  source: string;
  namespace: string;
  schema: string;
  table: string;
} | null {
  if (!key) return null;
  const parts = key.split("|");
  if (parts.length !== 5) return null;
  return {
    system: parts[0],
    source: parts[1],
    namespace: parts[2],
    schema: parts[3],
    table: parts[4],
  };
}

/** 节点展示名（优先中文名，其次表名，再次 display_id）。 */
export function nodeDisplayName(node: GraphNode): string {
  return node.table_name_cn || node.table_name || node.display_id || node.label || node.id;
}

/** 节点唯一键：id 优先，其次 physical_key，回退到 id。 */
export function nodeUniqueKey(node: GraphNode): string {
  return node.id || node.physical_key || "";
}

export interface NormalizedPhysicalNode extends GraphNode {
  displayKey: string;
  nodeName: string;
}

/** 规范化节点：同 display_id 多物理节点各自保留，不覆盖。 */
export function normalizePhysicalNodes(nodes: GraphNode[]): NormalizedPhysicalNode[] {
  const seen = new Set<string>();
  const result: NormalizedPhysicalNode[] = [];
  for (const node of nodes) {
    const key = nodeUniqueKey(node);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push({
      ...node,
      displayKey: node.display_id || node.id,
      nodeName: nodeDisplayName(node),
    });
  }
  return result;
}

export interface PhysicalNodeIssue {
  key: string;
  displayKey: string;
  reason: "missing_physical_key" | "duplicate_id" | "orphan";
}

/** 节点体检：报告物理键缺失 / 重复 id / 孤儿（诊断用，不静默覆盖）。 */
export function inspectPhysicalNodes(nodes: GraphNode[]): {
  clean: NormalizedPhysicalNode[];
  issues: PhysicalNodeIssue[];
} {
  const seen = new Set<string>();
  const issues: PhysicalNodeIssue[] = [];
  const clean: NormalizedPhysicalNode[] = [];
  for (const node of nodes) {
    // 物理键缺失 = physical_key 为空 或 id 不含 5 段物理键结构
    const hasPhysicalKey = Boolean(node.physical_key) || Boolean(parsePhysicalKey(node.id));
    const key = hasPhysicalKey ? (node.physical_key || node.id) : "";
    const displayKey = node.display_id || node.id;
    if (!hasPhysicalKey || !key) {
      issues.push({ key: node.id, displayKey, reason: "missing_physical_key" });
      continue;
    }
    if (seen.has(key)) {
      issues.push({ key, displayKey, reason: "duplicate_id" });
      continue;
    }
    seen.add(key);
    clean.push({ ...node, displayKey, nodeName: nodeDisplayName(node) });
  }
  return { clean, issues };
}

export interface NormalizedEdge {
  id: string;
  source: string;
  target: string;
  displaySource: string;
  displayTarget: string;
}

/** 边规范化：source/target 使用物理键；展示用 display_source/display_target。 */
export function normalizePhysicalEdges(edges: GraphEdge[]): NormalizedEdge[] {
  return edges.map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    displaySource: edge.display_source || edge.source,
    displayTarget: edge.display_target || edge.target,
  }));
}

/** 从节点/边构建 display_id -> 物理节点集合的映射（同名表跨来源分组）。 */
export function groupNodesByDisplayId(nodes: GraphNode[]): Map<string, GraphNode[]> {
  const map = new Map<string, GraphNode[]>();
  for (const node of nodes) {
    const key = node.display_id || node.id;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(node);
  }
  return map;
}
