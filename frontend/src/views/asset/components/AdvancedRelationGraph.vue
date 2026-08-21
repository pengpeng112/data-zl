<template>
  <div class="advanced-graph-shell">
    <div class="advanced-legend">
      <span><i class="node-chip chip-group" />系统/Schema 聚合</span>
      <span><i class="node-chip chip-table" />数据表</span>
      <span><i class="node-chip chip-view" />视图</span>
      <span><i class="edge-line solid primary" />A/正式关系</span>
      <span><i class="edge-line solid pass" />已验证</span>
      <span><i class="edge-line dashed orange" />B/C</span>
      <span><i class="edge-line dashed review" />D/待分析</span>
      <span><i class="edge-line dotted muted" />视图依赖</span>
    </div>
    <div ref="containerRef" class="advanced-graph-canvas" :style="{ height }" />
  </div>
</template>

<script setup lang="ts">
import { Graph, EdgeEvent, NodeEvent } from "@antv/g6";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { GraphEdge, GraphNode } from "@/api/asset";
import { normalizeGraphData, type GraphGroupBy } from "@/views/asset/graph/graphNormalize";
import {
  formatGraphNodeLabel,
  graphEdgeStyle,
  graphNodeVisualStyle,
  linkAdjacentOverviewNodes,
  transformGraphByMode
} from "@/views/asset/graph/graphTransform";
import { computeCircularSpreadPositions, computeHierarchyPositions } from "@/views/asset/graph/hierarchyLayout";

function graphCanvasPixelRatio(): number {
  const dpr = typeof window !== "undefined" ? Number(window.devicePixelRatio) || 1 : 1;
  return Math.min(Math.max(dpr, 2), 3);
}

type LayoutMode = "layered" | "grouped" | "radial" | "hierarchy";

type G6Graph = InstanceType<typeof Graph>;

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
    layoutMode: "layered",
    aggregateGroups: false,
    aggregationThreshold: 10,
    viewMode: "table"
  }
);

const emit = defineEmits<{
  "node-click": [node: GraphNode];
  "edge-click": [edge: GraphEdge];
  "render-error": [];
}>();

const containerRef = ref<HTMLDivElement>();
let graph: G6Graph | null = null;
let renderVersion = 0;
let renderQueue: Promise<void> = Promise.resolve();
let resizeObserver: ResizeObserver | null = null;
let lastCanvasSize = { width: 0, height: 0 };

function containerSize() {
  const el = containerRef.value;
  return {
    width: Math.max(320, el?.clientWidth || 960),
    height: Math.max(280, el?.clientHeight || 520)
  };
}

const transformed = computed(() => transformGraphByMode({ nodes: props.nodes, edges: props.edges }, props.viewMode, props.showReviewLayer));

const normalized = computed(() => normalizeGraphData(props.nodes, props.edges, {
  groupBy: props.groupBy,
  focusKeyword: props.focusKeyword,
  centerTable: props.centerTable,
  selectedNodeId: props.selectedNodeId,
  showReviewLayer: props.showReviewLayer,
  systemNames: props.systemNames,
  sourceNames: props.sourceNames
}));

function mappedSystem(node: any) {
  const code = node.system_code || node.systemCode;
  return props.systemNames?.[code] || code || "";
}

function mappedSource(node: any) {
  const code = node.source_code || node.sourceCode || node.source;
  return props.sourceNames?.[code] || code || "";
}

function mappedMeta(node: any) {
  const systemCode = node.system_code || node.systemCode;
  const sourceCode = node.source_code || node.sourceCode || node.source;
  return [
    props.systemNames?.[systemCode] && props.systemNames[systemCode] !== systemCode ? props.systemNames[systemCode] : "",
    props.sourceNames?.[sourceCode] && props.sourceNames[sourceCode] !== sourceCode ? props.sourceNames[sourceCode] : ""
  ].filter(Boolean).slice(0, 2).join(" / ");
}

function nodeGroup(node: any) {
  const id = String(node.id || "");
  if (props.groupBy === "system") return node.category || mappedSystem(node) || "未分业务系统";
  if (props.groupBy === "source") return node.category || mappedSource(node) || "未分数据连接";
  return node.category || node.schema_name || node.system_code || (id ? id.split(".")[0] : "") || "UNKNOWN";
}

function nodeLabel(node: any) {
  const formatted = formatGraphNodeLabel({
    ...node,
    display_id: node.display_id || (typeof node.label === "string" ? node.label : node.label?.formatter),
    count: node.count ?? node.table_count ?? node.child_count ?? node.asset_count
  });
  if (formatted) return formatted;
  const fallback = mappedSystem(node) || mappedMeta(node) || String(node.id || "");
  return fallback;
}

function aggregateData(nodes: any[], edges: any[]) {
  if (["system", "schema", "domain", "deferred"].includes(props.viewMode)) return { nodes: transformed.value.nodes, edges: transformed.value.edges };
  if (!props.aggregateGroups || props.selectedNodeId) return { nodes, edges };
  const grouped = new Map<string, any[]>();
  nodes.forEach(node => {
    const group = nodeGroup(node);
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group)!.push(node);
  });
  const alias = new Map<string, string>();
  const nextNodes: any[] = [];
  grouped.forEach((items, group) => {
    if (items.length >= props.aggregationThreshold) {
      const id = `__group__${group}`;
      items.forEach(node => alias.set(node.id, id));
      nextNodes.push({ id, label: group, table_name: group, category: group, count: items.length, isAggregate: true });
    } else {
      items.forEach(node => {
        alias.set(node.id, node.id);
        nextNodes.push(node);
      });
    }
  });
  const edgeMap = new Map<string, any>();
  edges.forEach(edge => {
    const source = alias.get(edge.source) || edge.source;
    const target = alias.get(edge.target) || edge.target;
    if (source === target) return;
    const key = `${source}->${target}:${edge.relation_type || "formal"}:${edge.confidence || ""}`;
    const existing = edgeMap.get(key);
    if (existing) {
      existing.edge_count = (existing.edge_count || 1) + 1;
      existing.label = `${existing.edge_count} 条关系`;
    } else {
      edgeMap.set(key, { ...edge, id: `agg:${key}`, source, target, label: edge.label || edge.from_columns || "" });
    }
  });
  return { nodes: nextNodes, edges: Array.from(edgeMap.values()) };
}

function usesPresetPositions() {
  return props.layoutMode === "hierarchy" || props.layoutMode === "layered";
}

// 130p2：Neo4j 知识图谱视觉——节点统一为圆点，度数（关联边数）越高圆越大，
// 枢纽表自然更醒目；聚合层（系统/Schema 等）用更大的圆区分层级语义。
function nodeCircleSize(node: any, degree: number, isCenter: boolean): number {
  if (isCenter) return 66;
  const category = String(node.category || "");
  const objectType = String(node.object_type || "");
  const isGroup = Boolean(node.is_aggregate || node.isAggregate) || ["system", "source", "schema", "domain"].includes(category);
  const isField = category === "field" || objectType === "column";
  const base = isGroup ? 56 : isField ? 32 : objectType === "view" ? 40 : 42;
  return base + Math.min(degree, 6) * 2;
}

function layoutOptions() {
  // 知识图谱/分层树状：坐标预计算后写入节点，不用 G6 force（会挤到中心重叠）。
  if (usesPresetPositions()) {
    return null;
  }
  if (props.layoutMode === "radial") {
    // 129号：知识图谱式中心辐射——中心表聚焦居中，关联节点按度数环绕
    return {
      type: "radial",
      focusNode: props.centerTable || null,
      unitRadius: 200,
      linkDistance: 220,
      preventOverlap: true,
      nodeSize: 150,
      nodeSpacing: 50,
      sortBy: "degree"
    };
  }
  if (props.layoutMode === "grouped") {
    return { type: "force-atlas2", preventOverlap: true, nodeSize: 132, nodeSpacing: 40, kr: 120, kg: 8 };
  }
  // 默认 layered → 改为 Neo4j 风格的 d3-force 力导向布局
  // 节点自然散布、弹簧连接、可拖拽交互，类似 Neo4j Browser 的图谱展示
  return {
    type: "force",
    linkDistance: 180,
    nodeStrength: -280,
    edgeStrength: 0.45,
    collideStrength: 1,
    preventOverlap: true,
    nodeSize: 88,
    nodeSpacing: 36,
    alpha: 0.35,
    alphaDecay: 0.022,
    alphaMin: 0.008,
    forceSimulation: undefined
  };
}

function edgeStyle(edge: any, showLabel = false) {
  const visual = graphEdgeStyle(edge);
  const type = edge.lineStyle?.type;
  const stroke = edge.lineStyle?.color || visual.stroke;
  // Neo4j 式关系标签：白底圆角胶囊、随边着色，仅信息边展示
  const rawLabel = String(edge.label || "").trim();
  const labelText =
    showLabel && rawLabel && !/^object(\s+object)?$/i.test(rawLabel) && edge.relation_type !== "structure"
      ? rawLabel.slice(0, 16)
      : "";
  return {
    stroke,
    lineWidth: edge.lineStyle?.width || visual.lineWidth,
    lineDash: type === "dotted" ? [2, 5] : type === "dashed" ? [8, 5] : visual.lineDash,
    endArrow: edge.relation_type !== "structure",
    endArrowSize: 5.5,
    opacity: edge.lineStyle?.opacity ?? visual.opacity,
    labelText,
    labelFontSize: 12,
    labelFill: stroke,
    labelBackground: Boolean(labelText),
    labelBackgroundFill: "rgba(255,255,255,0.92)",
    labelBackgroundStroke: "rgba(148,163,184,0.38)",
    labelBackgroundLineWidth: 1,
    labelBackgroundRadius: 8
  };
}

function graphData() {
  const data = aggregateData(normalized.value.nodes, normalized.value.edges);
  const uniqueNodes = Array.from(
    new Map(data.nodes.filter(node => Boolean(node?.id)).map(node => [String(node.id), node])).values()
  );
  const nodeIds = new Set(uniqueNodes.map(node => String(node.id)));
  const validEdges = data.edges.filter(edge => {
    const source = String(edge?.source || "");
    const target = String(edge?.target || "");
    return source && target && source !== target && nodeIds.has(source) && nodeIds.has(target);
  });
  const hierarchyPos =
    props.layoutMode === "hierarchy"
      ? computeHierarchyPositions(uniqueNodes, validEdges, { xGap: 220, yGap: 170, maxPerRow: 8 }).positions
      : props.layoutMode === "layered"
        ? computeCircularSpreadPositions(uniqueNodes, {
          nodeSize: uniqueNodes.length > 24 ? 140 : 186,
          gap: uniqueNodes.length > 24 ? 88 : 72
        }).positions
        : null;
  const isSystemLayer = uniqueNodes.length > 1 && uniqueNodes.every(
    node => String(node.id || "").startsWith("overview|system|") || (node.is_aggregate && !node.schema_name && !node.table_name)
  );
  const renderEdges = isSystemLayer ? linkAdjacentOverviewNodes(uniqueNodes, validEdges) : validEdges;
  const showEdgeLabels = renderEdges.length <= 40;
  // 度数（关联边数）用于圆点大小：枢纽表更醒目（Neo4j 知识图谱习惯）
  const degreeMap = new Map<string, number>();
  for (const edge of validEdges) {
    degreeMap.set(String(edge.source), (degreeMap.get(String(edge.source)) || 0) + 1);
    degreeMap.set(String(edge.target), (degreeMap.get(String(edge.target)) || 0) + 1);
  }
  return {
    nodes: uniqueNodes.map(node => {
      const typeStyle = graphNodeVisualStyle(node);
      const preset = hierarchyPos?.get(String(node.id));
      const isCenter = Boolean(props.centerTable) && String(node.id) === String(props.centerTable);
      const labelText = nodeLabel(node);
      const degree = degreeMap.get(String(node.id)) || 0;
      return {
        id: node.id,
        type: "circle",
        data: { raw: node },
        style: {
          ...(preset ? { x: preset.x, y: preset.y } : {}),
          size: nodeCircleSize(node, degree, isCenter),
          fill: isCenter ? "#111827" : typeStyle.fill,
          fillOpacity: 1,
          stroke: isCenter ? "#f0b429" : typeStyle.stroke,
          lineWidth: isCenter || node.id === props.selectedNodeId ? 3.4 : 2.4,
          lineDash: typeStyle.lineDash,
          labelPlacement: "bottom",
          labelOffsetY: 8,
          labelText,
          labelFill: "#111827",
          labelFontSize: isCenter || Boolean(node.is_aggregate || node.isAggregate) ? 13 : 12,
          labelFontWeight: node.id === props.selectedNodeId ? 700 : 650,
          labelWordWrap: false,
          labelMaxWidth: 168,
          labelMaxLines: 5,
          labelTextOverflow: "clip",
          labelLineHeight: 18,
          labelTextAlign: "center",
          labelTextBaseline: "top",
          labelBackground: true,
          labelBackgroundFill: "rgba(255,255,255,0.92)",
          labelBackgroundRadius: 4,
          labelBackgroundPadding: [1, 4, 1, 4]
        }
      };
    }),
    edges: renderEdges.map((edge, index) => ({
      // Renderer ids are isolated from backend evidence ids. The original
      // relation remains in data.raw for the evidence drawer.
      id: `render-edge-${index}`,
      source: String(edge.source),
      target: String(edge.target),
      data: { raw: edge },
      style: edgeStyle(edge, showEdgeLabels)
    }))
  };
}

function resolveElementId(event: any) {
  return event?.target?.id || event?.target?.attributes?.id || event?.target?.data?.id || event?.itemId;
}

function resolveRawElement(id: string | undefined, type: "node" | "edge") {
  if (!id) return undefined;
  const data = graphData();
  const item = type === "node" ? data.nodes.find(node => node.id === id) : data.edges.find(edge => edge.id === id);
  return item?.data?.raw;
}

function displayEdge(raw: any) {
  return raw?.sourceEdges?.[0] || raw;
}

function createGraph() {
  if (!containerRef.value || graph) return graph;
  const layout = layoutOptions();
  const view = containerSize();
  const instance = new Graph({
    container: containerRef.value,
    width: view.width,
    height: view.height,
    devicePixelRatio: graphCanvasPixelRatio(),
    autoFit: false,
    animation: false,
    zoomRange: [0.18, 2.8],
    // 分层模式 layout 为 null：不配置布局引擎，使用节点自带坐标
    ...(layout ? { layout } : {}),
    // 130p2：Neo4j 知识图谱视觉——圆点节点 + 二次曲线边；
    // hover 高亮一度邻居（active），其余元素淡出（inactive）
    node: {
      type: "circle",
      state: {
        active: { lineWidth: 3.4, labelFill: "#0f172a" },
        inactive: { opacity: 0.14 }
      }
    },
    edge: {
      type: "quadratic",
      state: {
        active: { opacity: 1 },
        inactive: { opacity: 0.07 }
      }
    },
    behaviors: [
      "drag-canvas",
      "zoom-canvas",
      "drag-element",
      { type: "hover-activate", degree: 1, state: "active", inactiveState: "inactive", animation: false }
    ]
  } as any);
  instance.on(NodeEvent.CLICK, (event: any) => {
      const id = resolveElementId(event);
      const raw = resolveRawElement(id, "node") || normalized.value.nodes.find(node => node.id === id);
      if (raw) emit("node-click", raw as GraphNode);
    });
  instance.on(EdgeEvent.CLICK, (event: any) => {
      const id = resolveElementId(event);
      const raw = displayEdge(resolveRawElement(id, "edge")) || normalized.value.edges.find(edge => edge.id === id);
      if (raw) emit("edge-click", raw as GraphEdge);
    });
  graph = instance;
  return instance;
}

async function performRender(version: number) {
  await nextTick();
  if (version !== renderVersion || !containerRef.value) return;
  try {
    if (usesPresetPositions() && graph) {
      try {
        graph.destroy();
      } catch {
        // 销毁失败不阻断重建
      }
      graph = null;
    }
    const instance = createGraph();
    if (!instance || version !== renderVersion) return;
    instance.setData(graphData() as any);
    const layout = layoutOptions();
    if (layout) instance.setOptions({ layout } as any);
    await instance.render();
    lastCanvasSize = { width: containerRef.value.clientWidth, height: containerRef.value.clientHeight };
    await instance.fitView({ padding: 56 } as any, false);
    const MIN_ZOOM = 0.28;
    if (instance.getZoom() < MIN_ZOOM) {
      await instance.zoomTo(MIN_ZOOM, false);
      await instance.fitCenter(false);
    }
  } catch (err) {
    console.error("[AdvancedRelationGraph] render failed:", err);
    try {
      graph?.destroy();
    } catch {
      // 失败实例不得继续接收后续 setData。
    }
    graph = null;
    emit("render-error");
  }
}

function renderGraph() {
  const version = ++renderVersion;
  renderQueue = renderQueue.then(() => performRender(version));
  return renderQueue;
}

function bindResizeObserver() {
  if (typeof ResizeObserver === "undefined" || !containerRef.value) return;
  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(() => {
    const el = containerRef.value;
    if (!el || !graph) return;
    const width = el.clientWidth;
    const height = el.clientHeight;
    if (width < 40 || height < 40) return;
    if (Math.abs(width - lastCanvasSize.width) < 8 && Math.abs(height - lastCanvasSize.height) < 8) return;
    lastCanvasSize = { width, height };
    graph.resize();
    if (usesPresetPositions()) {
      void renderGraph().catch(() => emit("render-error"));
    }
  });
  resizeObserver.observe(containerRef.value);
}

onMounted(() => {
  const el = containerRef.value;
  if (el) lastCanvasSize = { width: el.clientWidth, height: el.clientHeight };
  bindResizeObserver();
  void renderGraph().catch(() => emit("render-error"));
});

watch(() => [props.nodes, props.edges, props.groupBy, props.focusKeyword, props.centerTable, props.selectedNodeId, props.showReviewLayer, props.layoutMode, props.aggregateGroups, props.viewMode], () => {
  void renderGraph().catch(() => emit("render-error"));
}, { deep: true });

onBeforeUnmount(() => {
  renderVersion += 1;
  resizeObserver?.disconnect();
  resizeObserver = null;
  try {
    graph?.destroy();
  } catch {
    // destroy 异常不阻断卸载
  }
  graph = null;
});
</script>

<style scoped>
.advanced-graph-shell { border: 1px solid #d8e0ec; border-radius: 10px; background: #ffffff; overflow: hidden; }
.advanced-legend { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 9px 12px; border-bottom: 1px solid #e2e8f0; color: #334155; font-size: 12px; background: #ffffff; }
.advanced-legend span { display: inline-flex; align-items: center; gap: 5px; }
/* 130p2：Neo4j 式点阵画布（浅灰底 + 规则圆点网格） */
.advanced-graph-canvas {
  width: 100%;
  min-height: 420px;
  background-color: #fbfcfe;
  background-image: radial-gradient(circle, #ccd5e1 1px, transparent 1px);
  background-size: 24px 24px;
}
.advanced-graph-canvas :deep(canvas) {
  display: block;
}
.edge-line { display: inline-block; width: 24px; border-top-width: 2px; border-top-style: solid; }
.edge-line.solid { border-top-style: solid; }
.edge-line.dashed { border-top-style: dashed; }
.edge-line.dotted { border-top-style: dotted; }
.edge-line.primary { border-color: #3f7cac; }
.edge-line.pass { border-color: #58a05c; }
.edge-line.orange { border-color: #dd8b2e; }
.edge-line.review { border-color: #9b7ec8; }
.edge-line.muted { border-color: #94a3b8; }
.node-chip { display: inline-block; width: 11px; height: 11px; border-radius: 50%; border: 2px solid; }
.chip-group { background: #5a9628; border-color: #365f14; }
.chip-table { background: #2f7eb8; border-color: #184468; }
.chip-view { background: #e6ddf5; border-color: #b6a3dd; }
</style>
