<template>
  <div class="graph-shell">
    <div class="graph-legend">
      <span class="legend-item"><i class="edge-line solid primary" />A/正式关系</span>
      <span class="legend-item"><i class="edge-line solid pass" />已验证/样本通过</span>
      <span class="legend-item"><i class="edge-line dashed orange" />B/C 有边界</span>
      <span class="legend-item"><i class="edge-line dashed review" />D/候选待分析</span>
      <span class="legend-item"><i class="edge-line dotted muted" />视图依赖</span>
      <span class="legend-item"><i class="node-dot center" />定位/高亮节点</span>
    </div>

    <div ref="viewportEl" class="graph-viewport" :style="{ height }" @wheel.prevent="onWheel">
      <svg class="graph-svg" :viewBox="viewBox" role="img" aria-label="数据资产关系图谱">
        <defs>
          <marker id="arrow-primary" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--re-text-secondary)" />
          </marker>
        </defs>

        <g :transform="transformValue">
          <g v-for="band in layout.bands" :key="band.name" class="group-band">
            <rect :x="band.x" :y="band.y" :width="band.width" :height="band.height" rx="8" />
            <text :x="band.x + 12" :y="band.y + 22">{{ band.name }} {{ band.count }}</text>
          </g>

          <g class="edge-layer">
            <path
              v-for="edge in layout.edges"
              :key="`${edge.id}:hit`"
              :d="edge.path"
              class="graph-edge-hit"
              @click.stop="emitEdge(edge.raw)"
            />
            <path
              v-for="edge in layout.edges"
              :key="edge.id"
              :d="edge.path"
              :class="edge.className"
              :marker-end="edge.markerEnd"
              @click.stop="emitEdge(edge.raw)"
            />
            <text
              v-for="edge in layout.edges"
              v-show="edge.showLabel"
              :key="`${edge.id}:label`"
              :x="edge.labelX"
              :y="edge.labelY"
              class="edge-label"
            >{{ edge.label }}</text>
          </g>

          <g class="node-layer">
            <g
              v-for="node in layout.nodes"
              :key="node.id"
              :class="node.className"
              :transform="`translate(${node.x}, ${node.y})`"
              @click.stop="emitNode(node.raw)"
            >
              <rect :width="node.width" :height="node.height" :x="-node.width / 2" :y="-node.height / 2" rx="7" />
              <text class="node-title" text-anchor="middle" y="-4">{{ node.label }}</text>
              <text class="node-meta" text-anchor="middle" y="14">{{ node.meta }}</text>
            </g>
          </g>
        </g>
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { GraphEdge, GraphNode } from "@/api/asset";
import { normalizeGraphData, type GraphGroupBy } from "@/views/asset/graph/graphNormalize";
import { transformGraphByMode } from "@/views/asset/graph/graphTransform";
import { nodeDisplayName, parsePhysicalKey } from "@/views/asset/graph/graphPhysical";

type LayoutMode = "layered" | "grouped" | "radial";

interface LayoutNode {
  id: string;
  label: string;
  meta: string;
  x: number;
  y: number;
  width: number;
  height: number;
  className: string;
  raw: GraphNode;
}

interface LayoutEdge {
  id: string;
  path: string;
  label: string;
  labelX: number;
  labelY: number;
  showLabel: boolean;
  className: string;
  markerEnd: string;
  raw: GraphEdge;
}

interface LayoutBand {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  count: number;
}

const props = withDefaults(
  defineProps<{
    nodes: GraphNode[];
    edges: GraphEdge[];
    height?: string;
    centerTable?: string;
    focusKeyword?: string;
    groupBy?: GraphGroupBy;
    selectedNodeId?: string;
    showReviewLayer?: boolean;
    layoutMode?: LayoutMode;
    aggregateGroups?: boolean;
    aggregationThreshold?: number;
    viewMode?: string;
  }>(),
  {
    height: "620px",
    groupBy: "schema",
    focusKeyword: "",
    showReviewLayer: false,
    layoutMode: "layered",
    aggregateGroups: false,
    aggregationThreshold: 10,
    viewMode: "table"
  }
);

const emit = defineEmits<{
  "node-click": [node: GraphNode];
  "edge-click": [edge: GraphEdge];
}>();

const viewportEl = ref<HTMLElement>();
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });

const normalized = computed(() => normalizeGraphData(props.nodes, props.edges, {
  groupBy: props.groupBy,
  focusKeyword: props.focusKeyword,
  centerTable: props.centerTable,
  selectedNodeId: props.selectedNodeId,
  showReviewLayer: props.showReviewLayer
}));

const transformValue = computed(() => `translate(${pan.value.x} ${pan.value.y}) scale(${zoom.value})`);
const viewBox = computed(() => `0 0 ${layout.value.width} ${layout.value.height}`);

function nodeGroup(node: any) {
  if (node.isAggregate) return node.category || node.schema_name || "UNKNOWN";
  const physical = parsePhysicalKey(node.id || node.physical_key);
  if (physical?.schema) return physical.schema;
  return node.category || node.schema_name || node.display_id?.split(".")[0] || node.id.split(".")[0] || "UNKNOWN";
}

function compactLabel(value: unknown) {
  const str = typeof value === "string" ? value : String(value || "");
  const raw = str.includes(".") ? str.split(".").pop() || str : str;
  return raw.length > 18 ? `${raw.slice(0, 16)}...` : raw;
}

function nodeMeta(node: any) {
  if (node.isAggregate) return `${node.count} 张表`;
  const parts = [node.system_code, node.source_code || node.source, node.schema_name, node.domain]
    .filter(Boolean)
    .slice(0, 2)
    .join(" / ");
  return parts || "-";
}

function aggregateData(nodes: any[], edges: any[]) {
  if (["system", "schema", "domain", "deferred"].includes(props.viewMode)) {
    const transformed = transformGraphByMode({ nodes: props.nodes, edges: props.edges }, props.viewMode, props.showReviewLayer);
    return { nodes: transformed.nodes, edges: transformed.edges };
  }
  if (!props.aggregateGroups || props.selectedNodeId) return { nodes, edges };
  const groupMap = new Map<string, any[]>();
  for (const node of nodes) {
    const group = nodeGroup(node);
    if (!groupMap.has(group)) groupMap.set(group, []);
    groupMap.get(group)!.push(node);
  }
  const nodeAlias = new Map<string, string>();
  const nextNodes: any[] = [];
  for (const [group, groupNodes] of groupMap.entries()) {
    if (groupNodes.length >= props.aggregationThreshold) {
      const id = `__group__${group}`;
      groupNodes.forEach(node => nodeAlias.set(node.id, id));
      nextNodes.push({
        id,
        label: group,
        category: group,
        schema_name: group,
        table_name: group,
        source: group,
        count: groupNodes.length,
        isAggregate: true
      });
    } else {
      groupNodes.forEach(node => {
        nodeAlias.set(node.id, node.id);
        nextNodes.push(node);
      });
    }
  }
  const edgeMap = new Map<string, any>();
  for (const edge of edges) {
    const source = nodeAlias.get(edge.source) || edge.source;
    const target = nodeAlias.get(edge.target) || edge.target;
    if (source === target) continue;
    const key = `${source}->${target}:${edge.relation_type || "formal"}:${edge.confidence || ""}`;
    const existing = edgeMap.get(key);
    if (existing) {
      existing.edge_count = (existing.edge_count || 1) + 1;
      existing.label = `${existing.edge_count} 条关系`;
    } else {
      edgeMap.set(key, { ...edge, id: `agg:${key}`, source, target, label: edge.label || edge.from_columns || "" });
    }
  }
  return { nodes: nextNodes, edges: Array.from(edgeMap.values()) };
}

function isActiveNode(id: string) {
  if (!props.selectedNodeId) return true;
  if (id === props.selectedNodeId) return true;
  return normalized.value.edges.some(edge =>
    (edge.source === props.selectedNodeId && edge.target === id) ||
    (edge.target === props.selectedNodeId && edge.source === id)
  );
}

function edgeClass(edge: any) {
  const confidence = String(edge.confidence || "").toUpperCase();
  const active = !props.selectedNodeId || edge.source === props.selectedNodeId || edge.target === props.selectedNodeId;
  return [
    "graph-edge",
    active ? "is-active" : "is-muted",
    edge.relation_type === "dependency" ? "is-dependency" : "",
    edge.relation_type === "candidate" || confidence === "D" ? "is-review" : "",
    confidence === "B" || confidence === "C" ? "is-bounded" : "",
    ["verified", "sample_pass"].includes(edge.validation_status || "") ? "is-pass" : ""
  ].filter(Boolean).join(" ");
}

function nodeClass(node: any) {
  const active = isActiveNode(node.id);
  return [
    "graph-node",
    active ? "is-active" : "is-muted",
    node.id === props.centerTable || node.id === props.selectedNodeId ? "is-center" : "",
    node.isAggregate ? "is-aggregate" : ""
  ].filter(Boolean).join(" ");
}

function buildLayered(nodes: any[], edges: any[]) {
  const groupNames = Array.from(new Set(nodes.map(nodeGroup))).sort();
  const byGroup = groupNames.map(group => nodes.filter(node => nodeGroup(node) === group));
  const width = Math.max(1100, groupNames.length * 260 + 120);
  const maxRows = Math.max(...byGroup.map(items => items.length), 1);
  const height = Math.max(620, maxRows * 92 + 140);
  const positions = new Map<string, { x: number; y: number }>();
  const bands: LayoutBand[] = [];
  byGroup.forEach((items, col) => {
    const x = 110 + col * 260;
    bands.push({ name: groupNames[col], x: x - 96, y: 58, width: 210, height: height - 118, count: items.length });
    items.forEach((node, row) => {
      positions.set(node.id, { x, y: 116 + row * 92 });
    });
  });
  return materializeLayout(nodes, edges, positions, bands, width, height);
}

function buildGrouped(nodes: any[], edges: any[]) {
  const groups = Array.from(new Set(nodes.map(nodeGroup))).sort();
  const width = 1180;
  const height = Math.max(680, groups.length * 210);
  const positions = new Map<string, { x: number; y: number }>();
  const bands: LayoutBand[] = [];
  groups.forEach((group, index) => {
    const items = nodes.filter(node => nodeGroup(node) === group);
    const bandY = 70 + index * 210;
    bands.push({ name: group, x: 52, y: bandY - 42, width: width - 104, height: 176, count: items.length });
    items.forEach((node, itemIndex) => {
      const col = itemIndex % 5;
      const row = Math.floor(itemIndex / 5);
      positions.set(node.id, { x: 150 + col * 205, y: bandY + row * 72 });
    });
  });
  return materializeLayout(nodes, edges, positions, bands, width, height);
}

function buildRadial(nodes: any[], edges: any[]) {
  const width = 1100;
  const height = 720;
  const cx = width / 2;
  const cy = height / 2;
  const positions = new Map<string, { x: number; y: number }>();
  const centerId = props.selectedNodeId || props.centerTable;
  const centerNode = nodes.find(node => node.id === centerId);
  const outer = centerNode ? nodes.filter(node => node.id !== centerNode.id) : nodes;
  if (centerNode) positions.set(centerNode.id, { x: cx, y: cy });
  outer.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(outer.length, 1) - Math.PI / 2;
    const radius = centerNode ? 260 : 285;
    positions.set(node.id, { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius });
  });
  return materializeLayout(nodes, edges, positions, [], width, height);
}

function materializeLayout(nodes: any[], edges: any[], positions: Map<string, { x: number; y: number }>, bands: LayoutBand[], width: number, height: number) {
  const layoutNodes: LayoutNode[] = nodes.map(node => {
    const p = positions.get(node.id) || { x: 80, y: 80 };
    return {
      id: node.id,
      label: compactLabel(node.name || node.nodeName || node.table_name || node.label || node.id),
      meta: nodeMeta(node),
      x: p.x,
      y: p.y,
      width: node.isAggregate ? 156 : 138,
      height: node.isAggregate ? 58 : 52,
      className: nodeClass(node),
      raw: node
    };
  });
  const layoutEdges: LayoutEdge[] = edges
    .map(edge => {
      const s = positions.get(edge.source);
      const t = positions.get(edge.target);
      if (!s || !t) return null;
      const midX = (s.x + t.x) / 2;
      const midY = (s.y + t.y) / 2;
      const dx = t.x - s.x;
      const curve = Math.max(-70, Math.min(70, dx * 0.12));
      return {
        id: edge.id,
        path: `M ${s.x} ${s.y} C ${midX + curve} ${s.y}, ${midX - curve} ${t.y}, ${t.x} ${t.y}`,
        label: edge.label || edge.from_columns || "",
        labelX: midX,
        labelY: midY - 8,
        showLabel: Boolean(props.selectedNodeId && (edge.source === props.selectedNodeId || edge.target === props.selectedNodeId)),
        className: edgeClass(edge),
        markerEnd: "url(#arrow-primary)",
        raw: edge
      };
    })
    .filter(Boolean) as LayoutEdge[];
  return { width, height, bands, nodes: layoutNodes, edges: layoutEdges };
}

const layout = computed(() => {
  const data = aggregateData(normalized.value.nodes, normalized.value.edges);
  if (props.layoutMode === "grouped") return buildGrouped(data.nodes, data.edges);
  if (props.layoutMode === "radial") return buildRadial(data.nodes, data.edges);
  return buildLayered(data.nodes, data.edges);
});

function onWheel(event: WheelEvent) {
  const next = zoom.value + (event.deltaY > 0 ? -0.08 : 0.08);
  zoom.value = Math.max(0.45, Math.min(1.8, next));
}

function emitNode(node: GraphNode) {
  emit("node-click", node);
}

function emitEdge(edge: GraphEdge) {
  emit("edge-click", edge);
}

watch(() => [props.nodes, props.edges, props.selectedNodeId, props.layoutMode, props.aggregateGroups, props.viewMode, props.showReviewLayer], () => {
  pan.value = { x: 0, y: 0 };
  zoom.value = 1;
});
</script>

<style scoped>
.graph-shell {
  position: relative;
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #f8fafc;
}

.graph-viewport {
  width: 100%;
  min-height: 360px;
  overflow: auto;
  cursor: default;
}

.graph-svg {
  display: block;
  width: 100%;
  min-width: 980px;
  height: 100%;
}

.graph-legend {
  position: absolute;
  z-index: 2;
  top: 10px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-width: calc(100% - 24px);
  padding: 7px 10px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.edge-line {
  display: inline-block;
  width: 24px;
  height: 0;
  border-top: 2px solid var(--re-text-secondary);
}

.edge-line.primary { border-color: #0f3a66; }
.edge-line.pass { border-color: #00a6b8; }
.edge-line.orange { border-color: #d97706; }
.edge-line.review { border-color: #7c6aa6; }
.edge-line.muted { border-color: #94a3b8; }
.edge-line.dashed { border-top-style: dashed; }
.edge-line.dotted { border-top-style: dotted; }

.node-dot {
  width: 11px;
  height: 11px;
  border: 2px solid #00d5ff;
  border-radius: 3px;
  background: #0f3a66;
  transform: rotate(45deg);
}

.group-band rect {
  fill: rgba(226, 232, 240, 0.46);
  stroke: rgba(148, 163, 184, 0.35);
}

.group-band text {
  fill: #475569;
  font-size: 12px;
  font-weight: 700;
}

.graph-edge {
  fill: none;
  stroke: #0f3a66;
  stroke-width: 2.2;
  opacity: 0.82;
  cursor: pointer;
}

.graph-edge-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 14;
  cursor: pointer;
}

.graph-edge.is-pass { stroke: #00a6b8; stroke-width: 3; }
.graph-edge.is-bounded { stroke: #d97706; stroke-dasharray: 8 5; }
.graph-edge.is-review { stroke: #7c6aa6; stroke-dasharray: 7 6; }
.graph-edge.is-dependency { stroke: #94a3b8; stroke-dasharray: 2 5; }
.graph-edge.is-muted { opacity: 0.12; }
.graph-edge:hover { opacity: 1; stroke-width: 4; }

.edge-label {
  fill: #334155;
  font-size: 11px;
  paint-order: stroke;
  stroke: #fff;
  stroke-width: 3px;
  stroke-linejoin: round;
}

.graph-node {
  cursor: pointer;
}

.graph-node rect {
  fill: #ffffff;
  stroke: #0f3a66;
  stroke-width: 1.6;
  filter: drop-shadow(0 8px 16px rgba(15, 23, 42, 0.12));
}

.graph-node.is-center rect {
  stroke: #00d5ff;
  stroke-width: 3;
  fill: #ecfeff;
}

.graph-node.is-aggregate rect {
  fill: #eff6ff;
  stroke: var(--re-text-secondary);
  stroke-dasharray: 5 4;
}

.graph-node.is-muted {
  opacity: 0.24;
}

.graph-node:hover rect {
  stroke: #00a6b8;
  stroke-width: 3;
}

.node-title {
  fill: #0f172a;
  font-size: 12px;
  font-weight: 700;
}

.node-meta {
  fill: var(--re-text-secondary);
  font-size: 10px;
}
</style>
