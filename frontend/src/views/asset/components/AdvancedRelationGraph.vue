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

const transformed = computed(() => transformGraphByMode({ nodes: props.nodes, edges: props.edges }, props.viewMode, props.showReviewLayer));

const normalized = computed(() => normalizeGraphData(props.nodes, props.edges, {
  groupBy: props.groupBy,
  focusKeyword: props.focusKeyword,
  centerTable: props.centerTable,
  selectedNodeId: props.selectedNodeId,
  showReviewLayer: props.showReviewLayer
}));

function nodeGroup(node: any) {
  return node.category || node.schema_name || node.system_code || node.id.split(".")[0] || "UNKNOWN";
}

function nodeLabel(node: any) {
  const raw = node.table_name || node.label || node.id;
  return raw.length > 18 ? `${raw.slice(0, 16)}...` : raw;
}

function nodeMeta(node: any) {
  if (node.isAggregate) return `${node.count} 张表`;
  return [node.system_code, node.source_code || node.source, node.schema_name, node.business_domain || node.domain].filter(Boolean).slice(0, 2).join(" / ") || "-";
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

function layoutType() {
  if (props.layoutMode === "radial") return "radial";
  if (props.layoutMode === "grouped") return "force";
  return "dagre";
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
    labelText: edge.label?.formatter || edge.label || "",
    labelFontSize: 10,
    labelFill: "#334155",
    labelBackground: true,
    labelBackgroundFill: "rgba(255,255,255,0.82)",
    labelBackgroundRadius: 4
  };
}

function graphData() {
  const data = aggregateData(normalized.value.nodes, normalized.value.edges);
  return {
    nodes: data.nodes.map(node => {
      const typeStyle = graphNodeVisualStyle(node);
      return {
        id: node.id,
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
          labelFontSize: 11,
          labelFontWeight: node.id === props.selectedNodeId ? 700 : 500,
          badges: [{ text: nodeMeta(node), placement: "bottom", fill: "#ffffff", fillOpacity: 0.92, fontSize: 9, color: "#334155" }]
        }
      };
    }),
    edges: data.edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
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

function initGraph() {
  if (!containerRef.value || graph) return;
  try {
    graph = new Graph({
      container: containerRef.value,
      autoFit: "view",
      animation: false,
      data: graphData() as any,
      layout: { type: layoutType(), rankdir: "LR", nodeSize: [132, 58], preventOverlap: true, nodeSpacing: 36, ranksep: 90 },
      node: { type: "rect" },
      edge: { type: "line" },
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element", "hover-activate"]
    } as any);
    graph.on(NodeEvent.CLICK, (event: any) => {
      const id = resolveElementId(event);
      const raw = resolveRawElement(id, "node") || normalized.value.nodes.find(node => node.id === id);
      if (raw) emit("node-click", raw as GraphNode);
    });
    graph.on(EdgeEvent.CLICK, (event: any) => {
      const id = resolveElementId(event);
      const raw = displayEdge(resolveRawElement(id, "edge")) || normalized.value.edges.find(edge => edge.id === id);
      if (raw) emit("edge-click", raw as GraphEdge);
    });
    void graph.render().catch(() => emit("render-error"));
  } catch (err) {
    console.error("[AdvancedRelationGraph] init failed:", err);
    emit("render-error");
  }
}

async function renderGraph() {
  await nextTick();
  try {
    if (!graph) {
      initGraph();
      return;
    }
    graph.setData(graphData() as any);
    graph.setOptions({ layout: { type: layoutType(), rankdir: "LR", nodeSize: [132, 58], preventOverlap: true, nodeSpacing: 36, ranksep: 90 } } as any);
    await graph.render();
  } catch (err) {
    console.error("[AdvancedRelationGraph] render failed:", err);
    emit("render-error");
  }
}

onMounted(() => {
  void renderGraph().catch(() => emit("render-error"));
});

watch(() => [props.nodes, props.edges, props.groupBy, props.focusKeyword, props.centerTable, props.selectedNodeId, props.showReviewLayer, props.layoutMode, props.aggregateGroups, props.viewMode], () => {
  void renderGraph().catch(() => emit("render-error"));
}, { deep: true });

onBeforeUnmount(() => {
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
.advanced-graph-canvas { width: 100%; min-height: 420px; background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); }
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
