import type { GraphData, GraphEdge, GraphNode } from "@/api/asset";

export interface ExploreState {
  baseNodeIds: Set<string>;
  baseEdgeIds: Set<string>;
  expanded: Map<string, { nodeIds: Set<string>; edgeIds: Set<string> }>;
  nodeRefs: Map<string, number>;
  edgeRefs: Map<string, number>;
}

export function createExploreState(graph: GraphData): ExploreState {
  return {
    baseNodeIds: new Set(graph.nodes.map(node => node.id)),
    baseEdgeIds: new Set(graph.edges.map(edge => edge.id)),
    expanded: new Map(),
    nodeRefs: new Map(),
    edgeRefs: new Map()
  };
}

function increment(map: Map<string, number>, values: Iterable<string>) {
  for (const value of values) map.set(value, (map.get(value) || 0) + 1);
}

function decrement(map: Map<string, number>, values: Iterable<string>) {
  for (const value of values) {
    const next = (map.get(value) || 0) - 1;
    if (next > 0) map.set(value, next);
    else map.delete(value);
  }
}

export function mergeExpansion(current: GraphData, incoming: GraphData, sourceId: string, state: ExploreState): GraphData {
  if (state.expanded.has(sourceId)) return current;
  const nodeIds = new Set(incoming.nodes.map(node => node.id));
  const edgeIds = new Set(incoming.edges.map(edge => edge.id));
  increment(state.nodeRefs, nodeIds);
  increment(state.edgeRefs, edgeIds);
  state.expanded.set(sourceId, { nodeIds, edgeIds });
  const nodes = new Map<string, GraphNode>(current.nodes.map(node => [node.id, node]));
  const edges = new Map<string, GraphEdge>(current.edges.map(edge => [edge.id, edge]));
  incoming.nodes.forEach(node => nodes.set(node.id, { ...nodes.get(node.id), ...node }));
  incoming.edges.forEach(edge => edges.set(edge.id, { ...edges.get(edge.id), ...edge }));
  return { nodes: [...nodes.values()], edges: [...edges.values()], meta: incoming.meta || current.meta };
}

export function collapseExpansion(
  current: GraphData,
  sourceId: string,
  state: ExploreState,
  protectedNodeIds: Iterable<string> = []
): GraphData {
  const owned = state.expanded.get(sourceId);
  if (!owned) return current;
  state.expanded.delete(sourceId);
  decrement(state.nodeRefs, owned.nodeIds);
  decrement(state.edgeRefs, owned.edgeIds);
  const protectedIds = new Set(protectedNodeIds);
  const removeNodes = new Set([...owned.nodeIds].filter(id => !state.baseNodeIds.has(id) && !state.nodeRefs.has(id) && !protectedIds.has(id)));
  const removeEdges = new Set([...owned.edgeIds].filter(id => !state.baseEdgeIds.has(id) && !state.edgeRefs.has(id)));
  const edges = current.edges.filter(edge => !removeEdges.has(edge.id) && !removeNodes.has(edge.source) && !removeNodes.has(edge.target));
  return { ...current, nodes: current.nodes.filter(node => !removeNodes.has(node.id)), edges };
}
