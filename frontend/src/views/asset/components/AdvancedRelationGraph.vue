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
import { computeHierarchyPositions } from "@/views/asset/graph/hierarchyLayout";

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
  // normalizeGraphData 会把节点 label 覆盖为 echarts 风格对象 {show, formatter, ...}，
  // 必须把对象形态的 label 排除/取 formatter，否则 G6 文本布局对非字符串调 .split 抛 TypeError。
  const labelField =
    typeof node.label === "string" ? node.label : (node.label?.formatter ?? "");
  const isField = node.category === "field" || node.object_type === "column";
  const isSystem = !isField && (node.type === "system" || node.category === "system" || node.is_aggregate);
  const count = node.count ?? node.table_count ?? node.child_count;
  // 129号修复：聚合节点（系统/连接/Schema 各层）必须用后端下发的本层名称
  // （display_id/label），不能一律映射成系统中文名——否则下钻后所有子节点都叫"数据中心"。
  let primary = isField
    ? String(node.column_name_cn || node.column_name || labelField || node.display_id || node.id || "")
    : isSystem && !node.table_name
    ? String(node.display_id || labelField || "") || mappedSystem(node)
    : String(node.table_name_cn || node.tableNameCn || labelField || node.table_name || node.display_id || node.id || "");
  // 系统/聚合节点：中文名 + 数量；表节点：中文名 + 技术表名
  if (isSystem && count != null && !String(primary).includes(String(count))) {
    primary = `${primary}（${count}）`;
  }
  const techName = isField ? node.data_type || "" : node.table_name || node.tableName || "";
  const cnName = node.table_name_cn || node.tableNameCn || "";
  if (!isSystem && cnName && techName && cnName !== techName) {
    primary = `${cnName}`;
  }
  const shorten = (value: string, max: number) => value.length > max ? `${value.slice(0, max - 1)}…` : value;
  const meta = isField ? techName : isSystem && !node.table_name
    ? ""
    : (techName && cnName && cnName !== techName ? techName : mappedMeta(node));
  return meta ? `${shorten(String(primary), 23)}\n${shorten(String(meta), 32)}` : shorten(String(primary), 23);
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
  // 分层树状：坐标由 computeHierarchyPositions 预计算（写入节点 style.x/y），
  // 返回 null 表示不启用 G6 布局引擎（G6 v5 数据自带位置时可省略 layout）。
  if (props.layoutMode === "hierarchy") {
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
    linkDistance: (d: any) => 140 + (d?.data?.weight ? d.data.weight * 10 : 0),
    nodeStrength: -120,
    edgeStrength: 0.7,
    collideStrength: 0.8,
    preventOverlap: true,
    nodeSize: 40,
    alpha: 0.3,
    alphaDecay: 0.028,
    alphaMin: 0.01,
    forceSimulation: undefined
  };
}

function edgeStyle(edge: any, showLabel = false) {
  const visual = graphEdgeStyle(edge);
  const type = edge.lineStyle?.type;
  const stroke = edge.lineStyle?.color || visual.stroke;
  // 129号：知识图谱样式——边上显示关系标签（参考图：科室/产品/检查等关系名），标签随边着色
  const labelText = showLabel
    ? String(edge.label || edge.from_columns || "").slice(0, 14)
    : "";
  return {
    stroke,
    lineWidth: edge.lineStyle?.width || visual.lineWidth,
    lineDash: type === "dotted" ? [2, 5] : type === "dashed" ? [8, 5] : visual.lineDash,
    endArrow: true,
    opacity: edge.lineStyle?.opacity ?? visual.opacity,
    labelText,
    labelFontSize: 10,
    labelFill: stroke,
    labelBackground: Boolean(labelText),
    labelBackgroundFill: "rgba(255,255,255,0.88)",
    labelBackgroundRadius: 3
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
  // 分层树状：预计算节点坐标（包含边定层深，关系边不影响分层）
  const hierarchyPos =
    props.layoutMode === "hierarchy"
      ? computeHierarchyPositions(uniqueNodes, validEdges).positions
      : null;
  // 129号：边标签在边数较少时显示（知识图谱样式），边多时不显示防糊
  const showEdgeLabels = validEdges.length <= 40;
  return {
    nodes: uniqueNodes.map(node => {
      const typeStyle = graphNodeVisualStyle(node);
      const preset = hierarchyPos?.get(String(node.id));
      // 129号：中心节点强调（辐射图参考样式：中心实体更大更醒目）
      const isCenter = Boolean(props.centerTable) && String(node.id) === String(props.centerTable);
      return {
        id: node.id,
        type: typeStyle.shape === "diamond" ? "diamond" : typeStyle.shape === "ellipse" ? "circle" : "rect",
        data: { raw: node },
        style: {
          ...(preset ? { x: preset.x, y: preset.y } : {}),
          size: isCenter ? [176, 64] : node.isAggregate ? [132, 50] : typeStyle.size,
          radius: typeStyle.shape === "roundRect" ? 24 : typeStyle.shape === "rect" ? 8 : 12,
          fill: isCenter ? "#111827" : typeStyle.fill,
          fillOpacity: node.itemStyle?.opacity ?? typeStyle.opacity ?? 1,
          stroke: isCenter ? "#f0b429" : typeStyle.stroke,
          lineWidth: isCenter ? 3.5 : node.itemStyle?.borderWidth || (typeStyle.shape === "diamond" ? 2.6 : 1.5),
          lineDash: typeStyle.lineDash,
          // 127: G6 default labelPlacement is bottom → white text on light canvas is invisible
          labelPlacement: "center",
          labelText: nodeLabel(node),
          labelFill: isCenter ? "#ffffff" : typeStyle.textColor || "#ffffff",
          labelFontSize: isCenter ? 14 : node.is_aggregate || node.isAggregate ? 13 : 12,
          labelFontWeight: isCenter ? 800 : node.id === props.selectedNodeId ? 700 : 600,
          labelWordWrap: true,
          labelMaxWidth: node.isAggregate ? 120 : 200,
          labelTextAlign: "center",
          labelTextBaseline: "middle"
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
  const instance = new Graph({
      container: containerRef.value,
      // 不做自动 autoFit：渲染后手动 fitView + 最小缩放兜底（见 performRender），
      // 兼顾"少节点不散出视口"与"127+ 节点不缩成不可读方块"两种场景。
      autoFit: false,
      animation: false,
      // 分层模式 layout 为 null：不配置布局引擎，使用节点自带坐标
      ...(layout ? { layout } : {}),
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
    // 分层模式不启用布局引擎；若现有实例带着旧布局配置，销毁重建以彻底清除
    if (props.layoutMode === "hierarchy" && graph) {
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
    // 视口适配：先 fitView 让所有节点进入可视区（修复少节点时节点散出视口被裁切）；
    // 若整体缩放过小（节点很多时），锁定最小缩放并居中，保证节点文字可读，用户可再缩放/拖拽。
    await instance.fitView({ padding: 40 } as any, false);
    const MIN_ZOOM = 0.5;
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
.advanced-graph-shell { border: 1px solid #dbe3ef; border-radius: 8px; background: #ffffff; overflow: hidden; }
.advanced-legend { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 9px 12px; border-bottom: 1px solid #e2e8f0; color: #334155; font-size: 12px; background: #ffffff; }
.advanced-legend span { display: inline-flex; align-items: center; gap: 5px; }
.advanced-graph-canvas { width: 100%; min-height: 420px; background: #ffffff; }
.edge-line { display: inline-block; width: 24px; border-top-width: 2px; border-top-style: solid; }
.edge-line.solid { border-top-style: solid; }
.edge-line.dashed { border-top-style: dashed; }
.edge-line.dotted { border-top-style: dotted; }
/* 129号：与 pastel 边色一致的图例 */
.edge-line.primary { border-color: #3f7cac; }
.edge-line.pass { border-color: #58a05c; }
.edge-line.orange { border-color: #dd8b2e; }
.edge-line.review { border-color: #9b7ec8; }
.edge-line.muted { border-color: #94a3b8; }
</style>
