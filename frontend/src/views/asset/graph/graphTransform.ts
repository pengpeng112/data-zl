import type { GraphData, GraphEdge as ApiGraphEdge, GraphNode as ApiGraphNode } from "@/api/asset";

const GRAPH_COLOR_NEUTRAL = "#475569";
const GRAPH_COLOR_NEUTRAL_LIGHT = "#94a3b8";
const GRAPH_COLOR_NEUTRAL_DARK = "#334155";

export type GraphNodeType = "system" | "schema" | "domain" | "table";

export type GraphNode = {
  id: string;
  label: string;
  type: GraphNodeType;
  systemCode?: string;
  schemaName?: string;
  domain?: string;
  tableName?: string;
  tableNameCn?: string;
  role?: string;
  status?: string;
  count?: number;
};


export type GraphNodeStyle = {
  fill: string;
  stroke: string;
  textColor: string;
  shape: "rect" | "roundRect" | "ellipse" | "diamond";
  size: [number, number];
  lineDash?: number[];
  opacity?: number;
};

export const GRAPH_NODE_TYPE_STYLE: Record<GraphNodeType, GraphNodeStyle> = {
  system: { fill: "#0f3a66", stroke: "#00a6b8", textColor: "#ffffff", shape: "roundRect", size: [168, 58] },
  schema: { fill: "#00a6b8", stroke: "#0f3a66", textColor: "#ffffff", shape: "roundRect", size: [148, 52] },
  domain: { fill: "#d97706", stroke: "#92400e", textColor: "#ffffff", shape: "ellipse", size: [142, 50] },
  table: { fill: GRAPH_COLOR_NEUTRAL, stroke: GRAPH_COLOR_NEUTRAL_DARK, textColor: "#ffffff", shape: "rect", size: [126, 42] }
};

export function graphNodeStyle(type: GraphNodeType): GraphNodeStyle {
  return GRAPH_NODE_TYPE_STYLE[type];
}

export function isCoreFactNode(node: Partial<GraphNode & ApiGraphNode>) {
  const role = String(node.role || node.table_role || "").toLowerCase();
  return role.includes("核心事实") || role.includes("core_fact") || role.includes("core fact") || role === "fact" || role.includes("事实表");
}

export function isDimensionNode(node: Partial<GraphNode & ApiGraphNode>) {
  const role = String(node.role || node.table_role || "").toLowerCase();
  return role.includes("字典") || role.includes("维表") || role.includes("dimension") || role === "dim" || role.includes("dictionary") || role === "dict";
}

export function isExcludedNode(node: Partial<GraphNode & ApiGraphNode>) {
  const role = String(node.role || node.table_role || "").toLowerCase();
  const status = String(node.status || node.include_status || node.review_status || "").toLowerCase();
  return role.includes("排除") || role.includes("excluded") || status.includes("exclude") || status.includes("excluded") || status.includes("排除");
}

export function isCandidateNode(node: Partial<GraphNode & ApiGraphNode>) {
  const role = String(node.role || node.table_role || "").toLowerCase();
  const status = String(node.status || node.include_status || node.review_status || "").toLowerCase();
  return role.includes("候选") || role.includes("candidate") || status.includes("候选") || status.includes("待确认") || status.includes("candidate") || status.includes("pending") || status.includes("review");
}

export function isDeferredNode(node: Partial<GraphNode & ApiGraphNode>) {
  const role = String(node.role || node.table_role || "").toLowerCase();
  const status = String(node.status || node.include_status || node.review_status || "").toLowerCase();
  return role.includes("延后") || role.includes("待分析") || role.includes("deferred") || role === "d" || status.includes("延后") || status.includes("待分析") || status.includes("deferred") || status === "d";
}

export function graphNodeVisualStyle(node: Partial<GraphNode & ApiGraphNode>): GraphNodeStyle {
  const base = graphNodeStyle(node.type || "table");
  if ((node.type || "table") === "table" && isExcludedNode(node)) {
    return { ...base, fill: GRAPH_COLOR_NEUTRAL_LIGHT, stroke: GRAPH_COLOR_NEUTRAL, textColor: "#ffffff", shape: "rect", size: [118, 38] };
  }
  if ((node.type || "table") === "table" && isDeferredNode(node)) {
    return { ...base, fill: "#7c6aa6", stroke: "#5b4b7a", textColor: "#ffffff", shape: "roundRect", size: [132, 44], lineDash: [8, 5], opacity: 0.78 };
  }
  if ((node.type || "table") === "table" && isCandidateNode(node)) {
    return { ...base, fill: "#d97706", stroke: "#92400e", textColor: "#ffffff", shape: "roundRect", size: [132, 44] };
  }
  if ((node.type || "table") === "table" && isCoreFactNode(node)) {
    return { ...base, fill: "#0f3a66", stroke: "#00d5ff", shape: "diamond", size: [154, 54] };
  }
  if ((node.type || "table") === "table" && isDimensionNode(node)) {
    return { ...base, fill: "#00a6b8", stroke: "#0f3a66", shape: "roundRect", size: [138, 46] };
  }
  return base;
}

function searchableNodeValues(node: Partial<GraphNode & ApiGraphNode>) {
  const schema = node.schemaName || node.schema_name || node.namespace_name || node.category || String(node.id || "").split(".")[0];
  const table = node.tableName || node.table_name || String(node.id || "").split(".").pop();
  return [
    node.id,
    node.label,
    node.tableName,
    node.table_name,
    node.tableNameCn,
    node.table_name_cn,
    schema,
    table,
    schema && table ? `${schema}.${table}` : undefined,
    node.systemCode,
    node.system_code,
    node.source_code,
    node.source,
    node.domain,
    node.business_domain
  ].filter(Boolean).map(item => String(item).toLowerCase());
}

export function matchesTableSearch(node: Partial<GraphNode & ApiGraphNode>, keyword?: string | null) {
  const key = String(keyword || "").trim().toLowerCase();
  if (!key) return false;
  return searchableNodeValues(node).some(value => value.includes(key));
}
export type GraphEdgeVisualStyle = {
  stroke: string;
  lineWidth: number;
  lineDash?: number[];
  opacity: number;
};

function edgeConfidence(edge: Partial<GraphEdge & ApiGraphEdge>) {
  return String(edge.confidence || "").toUpperCase();
}

function edgeRelationTypeValue(edge: Partial<GraphEdge & ApiGraphEdge>) {
  return edge.relationType || edge.relation_type || "formal";
}

function edgeValidationStatus(edge: Partial<GraphEdge & ApiGraphEdge>) {
  return edge.validationStatus || edge.validation_status || "";
}

export function isDeferredEdge(edge: Partial<GraphEdge & ApiGraphEdge>) {
  const confidence = edgeConfidence(edge);
  const relationType = edgeRelationTypeValue(edge);
  return Boolean(edge.deferred || edge.is_deferred) || confidence === "D" || relationType === "candidate";
}

export function isSamplePassEdge(edge: Partial<GraphEdge & ApiGraphEdge>) {
  return edgeValidationStatus(edge) === "sample_pass";
}

export function isHighConfidenceEdge(edge: Partial<GraphEdge & ApiGraphEdge>) {
  const confidence = edgeConfidence(edge);
  const relationType = edgeRelationTypeValue(edge);
  const status = edgeValidationStatus(edge);
  if (isDeferredEdge(edge) || relationType === "dependency") return false;
  return confidence === "A" || status === "verified" || isSamplePassEdge(edge);
}

export function graphEdgeStyle(edge: Partial<GraphEdge & ApiGraphEdge>): GraphEdgeVisualStyle {
  const confidence = edgeConfidence(edge);
  const relationType = edgeRelationTypeValue(edge);
  const status = edgeValidationStatus(edge);
  if (isDeferredEdge(edge)) return { stroke: "#7c6aa6", lineWidth: 1.8, lineDash: [8, 5], opacity: 0.74 };
  if (relationType === "dependency") return { stroke: GRAPH_COLOR_NEUTRAL_LIGHT, lineWidth: 1.2, lineDash: [2, 5], opacity: 0.48 };
  if (["sample_pass", "verified"].includes(status)) return { stroke: "#00a6b8", lineWidth: 3, opacity: 0.9 };
  if (confidence === "B" || confidence === "C") return { stroke: "#d97706", lineWidth: 1.8, lineDash: [8, 5], opacity: 0.78 };
  if (confidence === "A") return { stroke: "#0f3a66", lineWidth: 2.4, opacity: 0.86 };
  return { stroke: GRAPH_COLOR_NEUTRAL, lineWidth: 1.2, opacity: 0.72 };
}

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence?: string;
  validationStatus?: string;
  relationType?: string;
  metrics?: Record<string, unknown>;
  deferred?: boolean;
  sourceEdges?: ApiGraphEdge[];
};

export type GraphNeighborDirection = "in" | "out" | "both";

export const GRAPH_NEIGHBOR_DIRECTION_LABELS: Record<GraphNeighborDirection, string> = {
  in: "只看上游",
  out: "只看下游",
  both: "双向"
};

export function normalizeGraphNeighborDirection(direction?: string | null): GraphNeighborDirection {
  return direction === "in" || direction === "out" || direction === "both" ? direction : "both";
}

export function graphNeighborDirectionLabel(direction?: string | null) {
  return GRAPH_NEIGHBOR_DIRECTION_LABELS[normalizeGraphNeighborDirection(direction)];
}

export function isOneHopDepth(depth?: number | string | null) {
  return Number(depth) === 1;
}

export function isTwoHopDepth(depth?: number | string | null) {
  return Number(depth) === 2;
}

function edgeMatchesDirection(edge: ApiGraphEdge, nodeId: string, directionValue: GraphNeighborDirection) {
  const direction = normalizeGraphNeighborDirection(directionValue);
  if (direction === "in") return edge.target === nodeId;
  if (direction === "out") return edge.source === nodeId;
  return edge.source === nodeId || edge.target === nodeId;
}

function nextNodeId(edge: ApiGraphEdge, nodeId: string, directionValue: GraphNeighborDirection) {
  const direction = normalizeGraphNeighborDirection(directionValue);
  if (direction === "in") return edge.source;
  if (direction === "out") return edge.target;
  return edge.source === nodeId ? edge.target : edge.source;
}

export function filterNeighborsByDepth(data: GraphData, centerId: string, depth: number, direction: GraphNeighborDirection = "both"): GraphData {
  const center = String(centerId || "").trim();
  if (!center) return { nodes: [], edges: [] };
  const maxDepth = Math.max(0, Math.floor(Number(depth) || 0));
  const nodeIds = new Set<string>([center]);
  const edgeIds = new Set<string>();
  let frontier = new Set<string>([center]);
  for (let hop = 0; hop < maxDepth && frontier.size; hop += 1) {
    const nextFrontier = new Set<string>();
    for (const edge of data.edges) {
      for (const nodeId of frontier) {
        if (!edgeMatchesDirection(edge, nodeId, direction)) continue;
        edgeIds.add(edge.id);
        const next = nextNodeId(edge, nodeId, direction);
        if (!nodeIds.has(next)) nextFrontier.add(next);
        nodeIds.add(edge.source);
        nodeIds.add(edge.target);
      }
    }
    frontier = nextFrontier;
  }
  return {
    nodes: data.nodes.filter(node => nodeIds.has(node.id)),
    edges: data.edges.filter(edge => edgeIds.has(edge.id))
  };
}

export function filterOneHopNeighbors(data: GraphData, centerId: string, direction: GraphNeighborDirection = "both"): GraphData {
  return filterNeighborsByDepth(data, centerId, 1, direction);
}

export function filterTwoHopNeighbors(data: GraphData, centerId: string, direction: GraphNeighborDirection = "both"): GraphData {
  return filterNeighborsByDepth(data, centerId, 2, direction);
}

export type GraphPathHighlight = {
  nodeIds: string[];
  edgeIds: string[];
};

export function findGraphPath(data: Pick<GraphData, "edges">, fromId?: string | null, toId?: string | null): GraphPathHighlight {
  const start = String(fromId || "").trim();
  const end = String(toId || "").trim();
  if (!start || !end) return { nodeIds: [], edgeIds: [] };
  if (start === end) return { nodeIds: [start], edgeIds: [] };
  const adjacency = new Map<string, { nodeId: string; edgeId: string }[]>();
  for (const edge of data.edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, []);
    adjacency.get(edge.source)!.push({ nodeId: edge.target, edgeId: edge.id });
    adjacency.get(edge.target)!.push({ nodeId: edge.source, edgeId: edge.id });
  }
  const queue = [start];
  const visited = new Set<string>([start]);
  const previous = new Map<string, { nodeId: string; edgeId: string }>();
  while (queue.length) {
    const current = queue.shift()!;
    for (const next of adjacency.get(current) || []) {
      if (visited.has(next.nodeId)) continue;
      visited.add(next.nodeId);
      previous.set(next.nodeId, { nodeId: current, edgeId: next.edgeId });
      if (next.nodeId === end) {
        queue.length = 0;
        break;
      }
      queue.push(next.nodeId);
    }
  }
  if (!previous.has(end)) return { nodeIds: [], edgeIds: [] };
  const nodeIds = [end];
  const edgeIds: string[] = [];
  let cursor = end;
  while (cursor !== start) {
    const item = previous.get(cursor);
    if (!item) return { nodeIds: [], edgeIds: [] };
    edgeIds.unshift(item.edgeId);
    nodeIds.unshift(item.nodeId);
    cursor = item.nodeId;
  }
  return { nodeIds, edgeIds };
}
export type GraphTransformLevel = GraphNodeType;

export type GraphTransformResult = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphTransformOptions = {
  level: GraphTransformLevel;
  showDeferred?: boolean;
  includeIsolated?: boolean;
};

const UNKNOWN = "未分组";

function clean(value?: string | null) {
  const text = String(value || "").trim();
  return text || undefined;
}

function fullTableName(schemaName?: string | null, tableName?: string | null, fallback?: string | null) {
  const schema = clean(schemaName);
  const table = clean(tableName);
  if (schema && table) return `${schema}.${table}`;
  return clean(fallback) || UNKNOWN;
}

function tableLabel(node: ApiGraphNode) {
  return clean(node.table_name_cn) || clean(node.table_name) || clean(node.label) || node.id;
}

function nodeSystem(node: ApiGraphNode) {
  return clean(node.system_code) || clean(node.source_code) || clean(node.source) || UNKNOWN;
}

function nodeSchema(node: ApiGraphNode) {
  const physical = clean(node.schema_name) || clean(node.namespace_name) || clean(node.category);
  if (physical) return physical;
  const display = clean(node.display_id) || node.id;
  return display.split(".")[0] || UNKNOWN;
}

function nodeDomain(node: ApiGraphNode) {
  return clean(node.business_domain) || clean(node.domain) || UNKNOWN;
}

function toTableNode(node: ApiGraphNode): GraphNode {
  return {
    id: buildGraphNodeKey(node, "table"),
    label: tableLabel(node),
    type: "table",
    systemCode: clean(node.system_code),
    schemaName: clean(node.schema_name) || clean(node.namespace_name),
    domain: clean(node.business_domain) || clean(node.domain),
    tableName: clean(node.table_name) || clean(node.display_id)?.split(".").pop(),
    tableNameCn: clean(node.table_name_cn),
    role: clean(node.table_role),
    status: clean(node.include_status) || clean(node.review_status),
    count: 1
  };
}

export function buildGraphNodeKey(source: ApiGraphNode, level: GraphTransformLevel) {
  const system = clean(source.system_code) || clean(source.source_code) || clean(source.source) || UNKNOWN;
  if (level === "system") return `system:${system}`;
  if (level === "schema") return `schema:${system}:${nodeSchema(source)}`;
  if (level === "domain") return `domain:${system}:${nodeDomain(source)}`;
  const table = clean(source.table_name) || clean(source.display_id)?.split(".").pop() || source.id.split(".").pop() || source.id;
  return `table:${system}:${nodeSchema(source)}:${table}`;
}

function aggregateNodeFor(source: ApiGraphNode, level: GraphTransformLevel): GraphNode {
  if (level === "table") return toTableNode(source);
  if (level === "system") {
    const label = nodeSystem(source);
    return {
      id: buildGraphNodeKey(source, "system"),
      label,
      type: "system",
      systemCode: label,
      count: 0
    };
  }
  if (level === "schema") {
    const schemaName = nodeSchema(source);
    return {
      id: buildGraphNodeKey(source, "schema"),
      label: schemaName,
      type: "schema",
      systemCode: nodeSystem(source),
      schemaName,
      count: 0
    };
  }
  const domain = nodeDomain(source);
  return {
    id: buildGraphNodeKey(source, "domain"),
    label: domain,
    type: "domain",
    systemCode: nodeSystem(source),
    domain,
    count: 0
  };
}

function endpointNode(edge: ApiGraphEdge, side: "source" | "target"): ApiGraphNode {
  if (side === "source") {
    const display = clean(edge.display_source) || edge.source;
    const schemaName = clean(edge.from_schema_name) || display.split(".")[0];
    const tableName = clean(edge.from_table_name) || display.split(".").slice(1).join(".");
    return {
      id: edge.source,
      display_id: clean(edge.display_source) || edge.source,
      label: clean(edge.from_table_name_cn) || tableName || edge.source,
      system_code: clean(edge.from_system_code),
      source_code: clean(edge.from_source_code),
      schema_name: schemaName,
      table_name: tableName,
      table_name_cn: clean(edge.from_table_name_cn),
      table_role: clean(edge.from_table_role),
      include_status: clean(edge.from_include_status),
      business_domain: clean(edge.business_domain),
      domain: clean(edge.business_domain)
    };
  }
  const display = clean(edge.display_target) || edge.target;
  const schemaName = clean(edge.to_schema_name) || display.split(".")[0];
  const tableName = clean(edge.to_table_name) || display.split(".").slice(1).join(".");
  return {
    id: edge.target,
    display_id: clean(edge.display_target) || edge.target,
    label: clean(edge.to_table_name_cn) || tableName || edge.target,
    system_code: clean(edge.to_system_code),
    source_code: clean(edge.to_source_code),
    schema_name: schemaName,
    table_name: tableName,
    table_name_cn: clean(edge.to_table_name_cn),
    table_role: clean(edge.to_table_role),
    include_status: clean(edge.to_include_status),
    business_domain: clean(edge.business_domain),
    domain: clean(edge.business_domain)
  };
}

function parseMetrics(value?: string | null): Record<string, unknown> | undefined {
  const text = clean(value);
  if (!text) return undefined;
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : { value: parsed };
  } catch {
    return { text };
  }
}

function isDeferred(edge: ApiGraphEdge) {
  return Boolean(edge.is_deferred) || (edge.confidence || "").toUpperCase() === "D" || edge.relation_type === "candidate";
}

function edgeLabel(edge: ApiGraphEdge) {
  return clean(edge.label) || clean(edge.join_condition) || clean(edge.from_columns) || clean(edge.relation_type) || "关系";
}

function normalizeEdge(edge: ApiGraphEdge, source: string, target: string, id: string): GraphEdge {
  return {
    id,
    source,
    target,
    label: edgeLabel(edge),
    confidence: clean(edge.confidence),
    validationStatus: clean(edge.validation_status),
    relationType: clean(edge.relation_type),
    metrics: parseMetrics(edge.validation_metrics),
    deferred: isDeferred(edge),
    sourceEdges: [edge]
  };
}

function addOrIncrementNode(nodes: Map<string, GraphNode>, node: GraphNode) {
  const existing = nodes.get(node.id);
  if (existing) {
    existing.count = (existing.count || 0) + (node.count || 1);
    existing.tableNameCn ||= node.tableNameCn;
    existing.role ||= node.role;
    existing.status ||= node.status;
    return existing;
  }
  nodes.set(node.id, { ...node, count: node.count || 1 });
  return node;
}

function mergeEdge(existing: GraphEdge, next: GraphEdge) {
  existing.deferred = Boolean(existing.deferred || next.deferred);
  existing.confidence ||= next.confidence;
  existing.validationStatus ||= next.validationStatus;
  existing.relationType ||= next.relationType;
  if (existing.label !== next.label) existing.label = `${existing.label} / ${next.label}`.slice(0, 80);
  existing.metrics = existing.metrics || next.metrics;
  existing.sourceEdges = [...(existing.sourceEdges || []), ...(next.sourceEdges || [])];
}

export function transformGraphData(data: GraphData, options: GraphTransformOptions): GraphTransformResult {
  const showDeferred = Boolean(options.showDeferred);
  const includeIsolated = options.includeIsolated ?? true;
  const sourceNodes = new Map(data.nodes.map(node => [node.id, node]));
  const nodes = new Map<string, GraphNode>();
  const edges = new Map<string, GraphEdge>();

  if (includeIsolated) {
    data.nodes.forEach(node => addOrIncrementNode(nodes, aggregateNodeFor(node, options.level)));
  }

  data.edges.forEach(edge => {
    const deferred = isDeferred(edge);
    if (deferred && !showDeferred) return;
    const rawSource = sourceNodes.get(edge.source) || endpointNode(edge, "source");
    const rawTarget = sourceNodes.get(edge.target) || endpointNode(edge, "target");
    const source = addOrIncrementNode(nodes, aggregateNodeFor(rawSource, options.level));
    const target = addOrIncrementNode(nodes, aggregateNodeFor(rawTarget, options.level));
    if (source.id === target.id) return;
    const key = `${source.id}->${target.id}:${edge.relation_type || "formal"}:${edge.confidence || ""}:${deferred ? "deferred" : "formal"}`;
    const next = normalizeEdge(edge, source.id, target.id, key);
    const existing = edges.get(key);
    if (existing) mergeEdge(existing, next);
    else edges.set(key, next);
  });

  return {
    nodes: Array.from(nodes.values()).sort((a, b) => a.type.localeCompare(b.type) || a.label.localeCompare(b.label)),
    edges: Array.from(edges.values())
  };
}

export function transformGraphByMode(data: GraphData, modeCode: string, showDeferred = false): GraphTransformResult {
  const level: GraphTransformLevel = modeCode === "system" ? "system" : modeCode === "schema" ? "schema" : modeCode === "domain" ? "domain" : "table";
  return transformGraphData(data, { level, showDeferred: showDeferred || modeCode === "deferred" || modeCode === "review" });
}

export function endpointTableName(edge: ApiGraphEdge, side: "source" | "target") {
  return side === "source"
    ? fullTableName(edge.from_schema_name, edge.from_table_name, edge.source)
    : fullTableName(edge.to_schema_name, edge.to_table_name, edge.target);
}
