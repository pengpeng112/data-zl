<template>
  <div class="advanced-graph-shell">
    <div class="advanced-legend">
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
import { graphEdgeStyle, graphNodeVisualStyle, transformGraphByMode } from "@/views/asset/graph/graphTransform";

type LayoutMode = "layered" | "grouped" | "radial";

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

const transformed = computed(() => transformGraphByMode({ nodes: props.nodes, edges: props.edges }, props.viewMode, props.showReviewLayer));

const normalized = computed(() => normalizeGraphData(props.nodes, props.edges, {
  groupBy: props.groupBy,
  focusKeyword: props.focusKeyword,
  centerTable: props.centerTable,
  selectedNodeId: props.selectedNodeId,
  showReviewLayer: props.showReviewLayer
}));

function nodeGroup(node: any) {
  const id = String(node.id || "");
  return node.category || node.schema_name || node.system_code || (id ? id.split(".")[0] : "") || "UNKNOWN";
}

function nodeLabel(node: any) {
  // normalizeGraphData 会把节点 label 覆盖为 echarts 风格对象 {show, formatter, ...}，
  // 必须把对象形态的 label 排除/取 formatter，否则 G6 文本布局对非字符串调 .split 抛 TypeError。
  const labelField =
    typeof node.label === "string" ? node.label : (node.label?.formatter ?? "");
  const primary = String(node.table_name_cn || node.tableNameCn || labelField || node.table_name || node.display_id || node.id || "");
  const shorten = (value: string, max: number) => value.length > max ? `${value.slice(0, max - 1)}…` : value;
  // 技术名保存在 data.raw/节点详情中；labelText 保持单字符串，避免 G6 文本布局
  // 在旧版本中把换行对象误判为数组而触发 split 运行时异常。
  return shorten(primary, 23);
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

function layoutOptions() {
  if (props.layoutMode === "radial") {
    return { type: "radial", nodeSize: 132, preventOverlap: true, nodeSpacing: 60, linkDistance: 170 };
  }
  // force-atlas2 依赖节点尺寸做重叠排除，在大节点（132 宽 rect）下比 d3-force 收敛更稳定
  return { type: "force-atlas2", preventOverlap: true, nodeSize: 132, nodeSpacing: 40, kr: 120, kg: 8 };
}

function edgeStyle(edge: any) {
  const visual = graphEdgeStyle(edge);
  const type = edge.lineStyle?.type;
  return {
    stroke: edge.lineStyle?.color || visual.stroke,
    lineWidth: edge.lineStyle?.width || visual.lineWidth,
    lineDash: type === "dotted" ? [2, 5] : type === "dashed" ? [8, 5] : visual.lineDash,
    endArrow: true,
    opacity: edge.lineStyle?.opacity ?? visual.opacity,
    labelText: ""
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
  return {
    nodes: uniqueNodes.map(node => {
      const typeStyle = graphNodeVisualStyle(node);
      return {
        id: node.id,
        type: typeStyle.shape === "diamond" ? "diamond" : typeStyle.shape === "ellipse" ? "circle" : "rect",
        data: { raw: node },
        style: {
          size: node.isAggregate ? [132, 50] : typeStyle.size,
          radius: typeStyle.shape === "rect" ? 4 : 8,
          fill: typeStyle.fill,
          fillOpacity: node.itemStyle?.opacity ?? typeStyle.opacity ?? 1,
          stroke: typeStyle.stroke,
          lineWidth: node.itemStyle?.borderWidth || (typeStyle.shape === "diamond" ? 2.6 : 1.5),
          lineDash: typeStyle.lineDash,
          labelText: nodeLabel(node),
          labelFill: typeStyle.textColor,
          labelFontSize: node.is_aggregate ? 13 : 13,
          labelFontWeight: node.id === props.selectedNodeId ? 700 : 500
        }
      };
    }),
    edges: validEdges.map((edge, index) => ({
      // Renderer ids are isolated from backend evidence ids. The original
      // relation remains in data.raw for the evidence drawer.
      id: `render-edge-${index}`,
      source: String(edge.source),
      target: String(edge.target),
      data: { raw: edge },
      style: edgeStyle(edge)
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
  const instance = new Graph({
      container: containerRef.value,
      // 默认概览由服务端控制节点数量；禁用无限 autoFit，避免 127 个节点再次缩成不可读方块。
      autoFit: false,
      animation: false,
      layout: layoutOptions(),
      node: { type: "rect" },
      edge: { type: "line" },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element", "hover-activate"]
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
    const instance = createGraph();
    if (!instance || version !== renderVersion) return;
    instance.setData(graphData() as any);
    instance.setOptions({ layout: layoutOptions() } as any);
    await instance.render();
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

onMounted(() => {
  void renderGraph().catch(() => emit("render-error"));
});

watch(() => [props.nodes, props.edges, props.groupBy, props.focusKeyword, props.centerTable, props.selectedNodeId, props.showReviewLayer, props.layoutMode, props.aggregateGroups, props.viewMode], () => {
  void renderGraph().catch(() => emit("render-error"));
}, { deep: true });

onBeforeUnmount(() => {
  renderVersion += 1;
  try {
    graph?.destroy();
  } catch {
    // destroy 异常不阻断卸载
  }
  graph = null;
});
</script>

<style scoped>
.advanced-graph-shell { border: 1px solid #dbe3ef; border-radius: 8px; background: #f8fafc; overflow: hidden; }
.advanced-legend { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 9px 12px; border-bottom: 1px solid #e2e8f0; color: #334155; font-size: 12px; background: #ffffff; }
.advanced-legend span { display: inline-flex; align-items: center; gap: 5px; }
.advanced-graph-canvas { width: 100%; min-height: 420px; background: #f8fafc; }
.edge-line { display: inline-block; width: 24px; border-top-width: 2px; border-top-style: solid; }
.edge-line.solid { border-top-style: solid; }
.edge-line.dashed { border-top-style: dashed; }
.edge-line.dotted { border-top-style: dotted; }
.edge-line.primary { border-color: #0f3a66; }
.edge-line.pass { border-color: #00a6b8; }
.edge-line.orange { border-color: #d97706; }
.edge-line.review { border-color: #7c6aa6; }
.edge-line.muted { border-color: #94a3b8; }
</style>
