import type { GraphEdge, GraphNode } from "@/api/asset";
import { findGraphPath, matchesTableSearch } from "@/views/asset/graph/graphTransform";
import {
  nodeDisplayName,
  nodeUniqueKey,
  parsePhysicalKey,
} from "@/views/asset/graph/graphPhysical";

export type GraphGroupBy = "system" | "source" | "schema" | "domain";

export interface NormalizedGraphOptions {
  groupBy: GraphGroupBy;
  focusKeyword?: string;
  centerTable?: string;
  selectedNodeId?: string;
  showReviewLayer?: boolean;
  systemNames?: Record<string, string>;
  sourceNames?: Record<string, string>;
}

export interface NormalizedGraph {
  categories: { name: string; itemStyle: { color: string } }[];
  nodes: any[];
  edges: any[];
  topGroups: { name: string; count: number }[];
  passCount: number;
  candidateCount: number;
  dependencyCount: number;
  reviewHiddenCount: number;
  issues: { key: string; displayKey: string; reason: string }[];
}

const GRAPH_COLOR_NEUTRAL = "#475569";
const GROUP_COLORS = ["#e0a075", "#7cc4d8", GRAPH_COLOR_NEUTRAL, "#e8a04c", "#b9a3d4", "#5fa8a0", "#8fbfe6", "#d99a3d"];

const STATUS_COLORS: Record<string, string> = {
  verified: "#58a05c",
  sample_pass: "#58a05c",
  manual_reviewed: "#3f7cac",
  bounded: "#dd8b2e",
  needs_split: "#ef4444",
  rejected: "#991b1b",
  not_tested: "#94a3b8"
};

function displayName(node: GraphNode) {
  return node.category === "field" || node.object_type === "column"
    ? String(node.column_name_cn || node.column_name || node.label || node.id)
    : nodeDisplayName(node);
}

function groupName(node: GraphNode, groupBy: GraphGroupBy, options: NormalizedGraphOptions) {
  const system = node.system_code ? options.systemNames?.[node.system_code] || node.system_code : "";
  const sourceCode = node.source_code || node.source || "";
  const source = sourceCode ? options.sourceNames?.[sourceCode] || sourceCode : "";
  if (node.is_aggregate && node.category) {
    if (groupBy === "system") return options.systemNames?.[node.category] || node.category;
    if (groupBy === "source") return options.sourceNames?.[node.category] || node.category;
    return node.category;
  }
  if (groupBy === "system") return system || "未分业务系统";
  if (groupBy === "source") return source || "未分数据连接";
  if (groupBy === "domain") return node.business_domain || node.domain || "未分业务域";
  return node.schema_name || node.namespace_name || node.category || (parsePhysicalKey(node.id)?.schema) || node.id.split(".")[0] || "UNKNOWN";
}

function matchesKeyword(node: GraphNode, keyword?: string) {
  const key = keyword?.trim().toLowerCase();
  if (!key) return false;
  return [node.id, node.label, node.table_name, node.table_name_cn, node.business_domain, node.domain, node.system_code, node.source_code, node.source]
    .filter(Boolean)
    .some(item => String(item).toLowerCase().includes(key));
}

function isReviewOnly(edge: GraphEdge) {
  const confidence = (edge.confidence || "").toUpperCase();
  return Boolean(edge.is_deferred) || confidence === "D" || edge.relation_type === "candidate";
}

function edgeLineType(edge: GraphEdge) {
  const confidence = (edge.confidence || "").toUpperCase();
  if (edge.is_deferred || confidence === "D") return "dashed";
  if (edge.relation_type === "candidate") return "dashed";
  if (edge.relation_type === "dependency") return "dotted";
  if (confidence && confidence !== "A") return "dashed";
  return "solid";
}

function edgeColor(edge: GraphEdge) {
  const confidence = (edge.confidence || "").toUpperCase();
  if (edge.is_deferred || confidence === "D") return "#9b7ec8";
  if (edge.relation_type === "candidate") return "#9b7ec8";
  if (edge.relation_type === "dependency") return "#94a3b8";
  if (edge.validation_status) return STATUS_COLORS[edge.validation_status] || GRAPH_COLOR_NEUTRAL;
  if (confidence === "A") return "#3f7cac";
  if (confidence === "B" || confidence === "C") return "#dd8b2e";
  return GRAPH_COLOR_NEUTRAL;
}

function edgeWidth(edge: GraphEdge) {
  const confidence = (edge.confidence || "").toUpperCase();
  if (["verified", "sample_pass"].includes(edge.validation_status || "")) return 3;
  if (confidence === "A") return 2.4;
  if (confidence === "B" || confidence === "C") return 1.8;
  return 1.2;
}

function isHighlightedNode(nodeId: string, adjacent: Set<string>, pathNodes: Set<string>, selected?: string) {
  if (!selected) return true;
  if (pathNodes.size) return pathNodes.has(nodeId);
  return nodeId === selected || adjacent.has(nodeId);
}

export function normalizeGraphData(
  nodes: GraphNode[],
  edges: GraphEdge[],
  options: NormalizedGraphOptions
): NormalizedGraph {
  const showReviewLayer = Boolean(options.showReviewLayer);
  const visibleEdges = edges.filter(edge => showReviewLayer || !isReviewOnly(edge));
  const reviewHiddenCount = edges.length - visibleEdges.length;
  // 物理去重：同 display_id 的不同物理节点各自保留（108号 §四）
  const seenKeys = new Set<string>();
  const visibleNodes: GraphNode[] = [];
  for (const node of nodes) {
    // 知识图谱：API 返回的节点一律保留。孤立系统/Schema 没有跨组边，
    // 不能因为画面上存在 1 条边就把其余节点丢掉。
    const key = nodeUniqueKey(node);
    if (!key || seenKeys.has(key)) continue;
    seenKeys.add(key);
    visibleNodes.push(node);
  }
  // 无物理键节点不覆盖、不合并，仅计为问题（不影响正常节点渲染）
  const issues: { key: string; displayKey: string; reason: string }[] = [];
  for (const node of nodes) {
    if (!nodeUniqueKey(node)) {
      issues.push({ key: node.id, displayKey: node.display_id || node.id, reason: "missing_physical_key" });
    }
  }
  const groups = Array.from(new Set(visibleNodes.map(node => groupName(node, options.groupBy, options)))).sort();
  const categories = groups.map((name, index) => ({
    name,
    itemStyle: { color: GROUP_COLORS[index % GROUP_COLORS.length] }
  }));
  const colorByGroup = new Map(categories.map(item => [item.name, item.itemStyle.color]));

  const degreeMap = new Map<string, number>();
  const adjacent = new Set<string>();
  for (const edge of visibleEdges) {
    degreeMap.set(edge.source, (degreeMap.get(edge.source) || 0) + 1);
    degreeMap.set(edge.target, (degreeMap.get(edge.target) || 0) + 1);
    if (options.selectedNodeId && (edge.source === options.selectedNodeId || edge.target === options.selectedNodeId)) {
      adjacent.add(edge.source);
      adjacent.add(edge.target);
    }
  }
  const highlightedPath = options.centerTable && options.selectedNodeId
    ? findGraphPath({ edges: visibleEdges }, options.centerTable, options.selectedNodeId)
    : { nodeIds: [], edgeIds: [] };
  const pathNodes = new Set(highlightedPath.nodeIds);
  const pathEdges = new Set(highlightedPath.edgeIds);

  const normalizedNodes = visibleNodes.map(node => {
    const group = groupName(node, options.groupBy, options);
    const focused = matchesKeyword(node, options.focusKeyword);
    const isCenter = Boolean(options.centerTable && node.id === options.centerTable);
    const selected = Boolean(options.selectedNodeId && node.id === options.selectedNodeId);
    const active = isHighlightedNode(node.id, adjacent, pathNodes, options.selectedNodeId);
    const degree = degreeMap.get(node.id) || 0;
    return {
      ...node,
      id: node.id,
      name: displayName(node),
      category: group,
      symbol: isCenter || focused || selected ? "diamond" : "roundRect",
      symbolSize: isCenter || focused || selected ? 70 : Math.min(58, 32 + degree * 3),
      itemStyle: {
        color: colorByGroup.get(group) || GRAPH_COLOR_NEUTRAL,
        opacity: active ? 1 : 0.22,
        borderColor: isCenter || focused || selected ? "#00d5ff" : "#ffffff",
        borderWidth: isCenter || focused || selected ? 3 : 1.5,
        shadowBlur: isCenter || focused || selected ? 26 : 10,
        shadowColor: isCenter || focused || selected ? "rgba(0, 166, 184, 0.42)" : "rgba(15, 23, 42, 0.18)"
      },
      label: {
        show: true,
        formatter: displayName(node),
        color: "#0f172a",
        fontSize: isCenter || focused || selected ? 12 : 11,
        fontWeight: isCenter || focused || selected ? 700 : 500,
        overflow: "break",
        width: 160,
        opacity: active ? 1 : 0.35
      }
    };
  });

  const normalizedEdges = visibleEdges.map(edge => {
    const pathSelected = pathEdges.has(edge.id);
    const selected = pathSelected || Boolean(!pathEdges.size && options.selectedNodeId && (edge.source === options.selectedNodeId || edge.target === options.selectedNodeId));
    const dimmed = Boolean(options.selectedNodeId && !selected);
    return {
      ...edge,
      id: edge.id,
      source: edge.source,
      target: edge.target,
      lineStyle: {
        color: edgeColor(edge),
        width: selected ? edgeWidth(edge) + (pathSelected ? 2.8 : 2) : edgeWidth(edge),
        type: edgeLineType(edge),
        opacity: dimmed ? 0.1 : pathSelected ? 1 : edge.relation_type === "dependency" ? 0.46 : 0.86,
        curveness: 0.18
      },
      label: { show: selected, formatter: edge.label || edge.from_columns || "", color: pathSelected ? "#3f7cac" : "#0f172a", fontSize: 11, fontWeight: pathSelected ? 700 : 500 },
      emphasis: { lineStyle: { width: edgeWidth(edge) + 2, opacity: 1 } }
    };
  });

  const groupCount = new Map<string, number>();
  for (const node of visibleNodes) {
    const group = groupName(node, options.groupBy, options);
    groupCount.set(group, (groupCount.get(group) || 0) + 1);
  }

  return {
    categories,
    nodes: normalizedNodes,
    edges: normalizedEdges,
    topGroups: Array.from(groupCount.entries()).map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count).slice(0, 6),
    passCount: visibleEdges.filter(edge => ["sample_pass", "verified"].includes(edge.validation_status || "")).length,
    candidateCount: visibleEdges.filter(edge => edge.relation_type === "candidate").length,
    dependencyCount: visibleEdges.filter(edge => edge.relation_type === "dependency").length,
    reviewHiddenCount,
    issues
  };
}
