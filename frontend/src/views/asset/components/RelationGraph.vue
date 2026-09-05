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

    <div
      ref="viewportEl"
      class="graph-viewport"
      :class="{ 'is-panning': panning.active }"
      :style="{ height }"
      @wheel.prevent="onWheel"
      @pointerdown="onPanStart"
      @pointermove="onPanMove"
      @pointerup="onPanEnd"
      @pointercancel="onPanEnd"
    >
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
              tabindex="0"
              @click.stop="emitNode(node.raw)"
              @dblclick.stop="emit('node-activate', node.raw)"
              @keydown.enter="emit('node-activate', node.raw)"
            >
              <circle :r="node.width / 2" />
              <text
                v-for="(line, lineIndex) in String(node.label || '').split('\n')"
                :key="`${node.id}:${lineIndex}`"
                class="node-title"
                text-anchor="middle"
                :y="node.width / 2 + 14 + lineIndex * 15"
              >{{ line }}</text>
              <!-- 146 E2（R5）：字段节点副标题 = 已计算的 node.meta（数据类型/键类型），长文本截断保证可读 -->
              <text
                v-if="node.meta && shouldRenderGraphMeta(node.meta)"
                class="node-meta"
                text-anchor="middle"
                :y="node.width / 2 + 14 + String(node.label || '').split('\n').length * 15 + 2"
              >{{ truncateGraphMeta(node.meta) }}</text>
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
import { formatGraphNodeLabel, linkAdjacentOverviewNodes, transformGraphByMode } from "@/views/asset/graph/graphTransform";
import { nodeDisplayName, parsePhysicalKey } from "@/views/asset/graph/graphPhysical";
import { computeCircularSpreadPositions, computeHierarchyPositions } from "@/views/asset/graph/hierarchyLayout";
import { shouldRenderGraphMeta, truncateGraphMeta } from "@/views/asset/components/graphNodeMeta";

type LayoutMode = "force" | "layered" | "grouped" | "radial" | "hierarchy";

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
    systemNames?: Record<string, string>;
    sourceNames?: Record<string, string>;
  }>(),
  {
    height: "620px",
    groupBy: "schema",
    focusKeyword: "",
    showReviewLayer: false,
    layoutMode: "force",
    aggregateGroups: false,
    aggregationThreshold: 10,
    viewMode: "table"
  }
);

const emit = defineEmits<{
  "node-click": [node: GraphNode];
  "node-activate": [node: GraphNode];
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
  showReviewLayer: props.showReviewLayer,
  systemNames: props.systemNames,
  sourceNames: props.sourceNames
}));

const transformValue = computed(() => `translate(${pan.value.x} ${pan.value.y}) scale(${zoom.value})`);
const viewBox = computed(() => `0 0 ${layout.value.width} ${layout.value.height}`);

function nodeGroup(node: any) {
  if (node.isAggregate) return node.category || node.schema_name || "UNKNOWN";
  const systemCode = node.system_code || node.systemCode;
  const sourceCode = node.source_code || node.sourceCode || node.source;
  if (props.groupBy === "system") return node.category || props.systemNames?.[systemCode] || systemCode || "未分业务系统";
  if (props.groupBy === "source") return node.category || props.sourceNames?.[sourceCode] || sourceCode || "未分数据连接";
  const physical = parsePhysicalKey(node.id || node.physical_key);
  if (physical?.schema) return physical.schema;
  return node.category || node.schema_name || node.display_id?.split(".")[0] || String(node.id || "").split(".")[0] || "UNKNOWN";
}

function compactLabel(node: any) {
  return formatGraphNodeLabel({
    ...node,
    display_id: node.display_id || node.name || node.nodeName || node.label,
    count: node.count ?? node.child_count ?? node.asset_count
  }) || String(node.table_name || node.label || node.id || "");
}

function nodeMeta(node: any) {
  if (node.isAggregate) return `${node.count} 张表`;
  if (node.category === "field" || node.object_type === "column") {
    const keyKind = node.is_primary_key ? "PK" : node.is_relation_key ? "关系键" : "";
    return [node.data_type, keyKind].filter(Boolean).join(" · ") || "字段";
  }
  const systemCode = node.system_code || node.systemCode;
  const sourceCode = node.source_code || node.sourceCode || node.source;
  const system = props.systemNames?.[systemCode] || systemCode;
  const source = props.sourceNames?.[sourceCode] || sourceCode;
  const parts = [system, source, node.schema_name, node.domain]
    .filter(Boolean)
    .slice(0, 2)
    .join(" / ");
  return parts || "-";
}

/**
 * 边标签必须是纯文本：normalizeGraphData 会把 label 包成
 * ECharts 风格对象（{show, formatter, ...}），直接 String() 会渲染成
 * "[object Object]"（171 P2 / 177 C4）。按 字符串 label → label.formatter →
 * from_columns 字符串 顺序取值，取不到返回空串。
 */
function edgeLabelText(edge: any): string {
  if (typeof edge?.label === "string") return edge.label;
  if (edge?.label && typeof edge.label === "object") {
    const fmt = (edge.label as Record<string, unknown>).formatter;
    if (typeof fmt === "string") return fmt;
  }
  return typeof edge?.from_columns === "string" ? edge.from_columns : "";
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
      edgeMap.set(key, { ...edge, id: `agg:${key}`, source, target, label: edgeLabelText(edge) });
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
  const kind = node.category === "field" || node.object_type === "column"
    ? "field"
    : node.object_type === "view"
      ? "view"
      : node.is_aggregate && ["system", "source", "schema"].includes(String(node.category))
        ? String(node.category)
        : "table";
  return [
    "graph-node",
    `node-${kind}`,
    active ? "is-active" : "is-muted",
    node.id === props.centerTable || node.id === props.selectedNodeId ? "is-center" : "",
    node.isAggregate ? "is-aggregate" : ""
  ].filter(Boolean).join(" ");
}

/**
 * 标签行数（compactLabel 以换行符拆行，上限 6：5 行名+计数/tech 行）。
 * 169 G4：行距必须装下标签栈（14 offset + 半径 ~28 + 行数×15 + 24 余量），
 * 固定 92px 曾致多行标签跨行压到下一行节点（round-3 P3）。
 */
function labelLineCount(node: any): number {
  const text = compactLabel(node) || "";
  return Math.min(6, Math.max(1, text.split("\n").length));
}

function layeredRowGap(items: any[]): number {
  const maxLines = Math.max(1, ...items.map(labelLineCount));
  return Math.max(92, 46 + maxLines * 15 + 24);
}

function buildLayered(nodes: any[], edges: any[]) {
  const groupNames = Array.from(new Set(nodes.map(nodeGroup))).sort();
  const byGroup = groupNames.map(group => nodes.filter(node => nodeGroup(node) === group));
  const width = Math.max(1100, groupNames.length * 260 + 120);
  // 高度按各组自身行距求和（列内 y 连续排布），取最长的组
  const groupGaps = byGroup.map(items => layeredRowGap(items));
  const maxRows = Math.max(...byGroup.map(items => items.length), 1);
  const height = Math.max(620, maxRows * Math.max(...groupGaps, 92) + 140);
  const positions = new Map<string, { x: number; y: number }>();
  const bands: LayoutBand[] = [];
  byGroup.forEach((items, col) => {
    const x = 110 + col * 260;
    const gap = groupGaps[col];
    bands.push({ name: groupNames[col], x: x - 96, y: 58, width: 210, height: height - 118, count: items.length });
    items.forEach((node, row) => {
      positions.set(node.id, { x, y: 116 + row * gap });
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
  const height = 760;
  const cx = width / 2;
  const cy = height / 2;
  const positions = new Map<string, { x: number; y: number }>();
  const centerId = props.selectedNodeId || props.centerTable;
  const centerNode = nodes.find(node => node.id === centerId);
  const outer = centerNode ? nodes.filter(node => node.id !== centerNode.id) : nodes;
  if (centerNode) positions.set(centerNode.id, { x: cx, y: cy });
  outer.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(outer.length, 1) - Math.PI / 2;
    const radius = centerNode ? 300 : 320;
    positions.set(node.id, { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius });
  });
  return materializeLayout(nodes, edges, positions, [], width, height);
}

function materializeLayout(nodes: any[], edges: any[], positions: Map<string, { x: number; y: number }>, bands: LayoutBand[], width: number, height: number) {
  // 度数（关联边数）用于圆点大小：枢纽表更醒目（与 G6 版一致）
  const degreeMap = new Map<string, number>();
  for (const edge of edges) {
    degreeMap.set(String(edge.source), (degreeMap.get(String(edge.source)) || 0) + 1);
    degreeMap.set(String(edge.target), (degreeMap.get(String(edge.target)) || 0) + 1);
  }
  const layoutNodes: LayoutNode[] = nodes.map(node => {
    const p = positions.get(node.id) || { x: 80, y: 80 };
    const isCenter = Boolean(props.centerTable) && String(node.id) === String(props.centerTable);
    // 130p2：Neo4j 圆点节点——width 即直径（模板渲染 circle r=width/2）
    const isGroup = Boolean(node.is_aggregate || node.isAggregate);
    const objectType = String(node.object_type || "");
    const base = isCenter ? 66 : isGroup ? 52 : objectType === "view" ? 40 : 42;
    const diameter = isCenter ? base : base + Math.min(degreeMap.get(String(node.id)) || 0, 6) * 2;
    return {
      id: node.id,
      label: compactLabel(node),
      meta: node.category === "field" || node.object_type === "column" ? nodeMeta(node) : "",
      x: p.x,
      y: p.y,
      width: diameter,
      height: diameter,
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
        label: edgeLabelText(edge).slice(0, 16),
        labelX: midX,
        labelY: midY - 8,
        // 129号：辐射模式下显示全部边标签（知识图谱样式）；其他模式仅选中节点相关边
        showLabel: props.layoutMode === "radial" || Boolean(props.selectedNodeId && (edge.source === props.selectedNodeId || edge.target === props.selectedNodeId)),
        className: edgeClass(edge),
        markerEnd: "url(#arrow-primary)",
        raw: edge
      };
    })
    .filter(Boolean) as LayoutEdge[];
  return { width, height, bands, nodes: layoutNodes, edges: layoutEdges };
}

/**
 * 分层树状布局：业务系统 → 数据连接 → Schema → 表 逐级分层（与 G6 版共用算法）。
 */
function buildHierarchy(nodes: any[], edges: any[]) {
  const { positions, width, height } = computeHierarchyPositions(nodes, edges, { xGap: 220, yGap: 170, maxPerRow: 8 });
  return materializeLayout(nodes, edges, positions, [], width, height);
}

function buildCircular(nodes: any[], edges: any[]) {
  const isSystemLayer = nodes.length > 1 && nodes.every(
    (node: any) => String(node.id || "").startsWith("overview|system|") || (node.is_aggregate && !node.schema_name && !node.table_name)
  );
  const linked = isSystemLayer ? linkAdjacentOverviewNodes(nodes, edges) : edges;
  const { positions, width, height } = computeCircularSpreadPositions(nodes, { nodeSize: 186, gap: 72 });
  return materializeLayout(nodes, linked, positions, [], width, height);
}

const layout = computed(() => {
  const data = aggregateData(normalized.value.nodes, normalized.value.edges);
  if (props.layoutMode === "grouped") return buildGrouped(data.nodes, data.edges);
  if (props.layoutMode === "radial") return buildRadial(data.nodes, data.edges);
  if (props.layoutMode === "hierarchy") return buildHierarchy(data.nodes, data.edges);
  // 169 G4：SVG 降级时 explore（force 语义）不该落成网格——有中心表走 radial
  // 中心辐射（与 G6 radial 配置对齐），无中心表的 force 才落分层网格。
  if (props.layoutMode === "force" && props.viewMode === "explore" && props.centerTable) {
    return buildRadial(data.nodes, data.edges);
  }
  return buildLayered(data.nodes, data.edges);
});

function onWheel(event: WheelEvent) {
  const next = zoom.value + (event.deltaY > 0 ? -0.08 : 0.08);
  zoom.value = Math.max(0.45, Math.min(1.8, next));
}

// 146 E2：画布内 pointer pan（空白处拖拽平移，不拦截节点/边点击）
const panning = ref({ active: false, startX: 0, startY: 0, baseX: 0, baseY: 0 });

function onPanStart(event: PointerEvent) {
  if (event.button !== 0) return;
  const target = event.target as HTMLElement;
  if (target.closest(".node-layer, .edge-layer, .group-band")) return;
  panning.value = {
    active: true,
    startX: event.clientX,
    startY: event.clientY,
    baseX: pan.value.x,
    baseY: pan.value.y
  };
  (event.currentTarget as HTMLElement)?.setPointerCapture?.(event.pointerId);
}

function onPanMove(event: PointerEvent) {
  if (!panning.value.active) return;
  pan.value = {
    x: panning.value.baseX + (event.clientX - panning.value.startX),
    y: panning.value.baseY + (event.clientY - panning.value.startY)
  };
}

function onPanEnd() {
  panning.value.active = false;
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
  background: #ffffff;
}

.graph-viewport {
  width: 100%;
  min-height: 360px;
  overflow: auto;
  cursor: grab;
  /* 130p2：Neo4j 式点阵画布 */
  background-color: #fbfcfe;
  background-image: radial-gradient(circle, #ccd5e1 1px, transparent 1px);
  background-size: 24px 24px;
}

.graph-viewport.is-panning {
  cursor: grabbing;
  user-select: none;
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

.edge-line.primary { border-color: #3f7cac; }
.edge-line.pass { border-color: #58a05c; }
.edge-line.orange { border-color: #dd8b2e; }
.edge-line.review { border-color: #9b7ec8; }
.edge-line.muted { border-color: #94a3b8; }
.edge-line.dashed { border-top-style: dashed; }
.edge-line.dotted { border-top-style: dotted; }

.node-dot {
  width: 11px;
  height: 11px;
  border: 2px solid #f0b429;
  border-radius: 50%;
  background: #111827;
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
  stroke: #3f7cac;
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

.graph-edge.is-pass { stroke: #58a05c; stroke-width: 2.6; }
.graph-edge.is-bounded { stroke: #dd8b2e; stroke-dasharray: 8 5; }
.graph-edge.is-review { stroke: #9b7ec8; stroke-dasharray: 7 6; }
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

/* 130p2：Neo4j 圆点节点——彩色圆心 + 同色系描边环 */
.graph-node circle {
  fill: #2f7eb8;
  stroke: #184468;
  stroke-width: 2.4;
}

.graph-node.node-system circle { fill: #d96a1a; stroke: #8a3d0c; }
.graph-node.node-source circle { fill: #c9a116; stroke: #7a6308; }
.graph-node.node-schema circle { fill: #5a9628; stroke: #365f14; }
.graph-node.node-view circle { fill: #7a55c4; stroke: #4c2d86; }
.graph-node.node-field circle { fill: #5a8f32; stroke: #365c1c; }

.graph-node.is-center circle {
  stroke: #f0b429;
  stroke-width: 3;
  fill: #111827;
}

.graph-node.is-aggregate circle {
  fill: #2a8f99;
  stroke: #16565c;
}

.graph-node.is-muted {
  opacity: 0.24;
}

.graph-node:hover circle {
  stroke: #3f7cac;
  stroke-width: 3;
}

.node-title {
  fill: #111827;
  font-size: 13px;
  font-weight: 650;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.94);
  stroke-width: 4px;
  stroke-linejoin: round;
}

/* 146 E2（R5）：字段节点副标题（node.meta）——次要信息弱化展示 */
.node-meta {
  fill: #475569;
  font-size: 11px;
  font-weight: 500;
  paint-order: stroke;
  stroke: rgba(255, 255, 255, 0.94);
  stroke-width: 3px;
  stroke-linejoin: round;
}
</style>
