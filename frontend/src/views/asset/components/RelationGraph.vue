<template>
  <div class="graph-shell">
    <div ref="chartEl" class="graph-canvas" :style="{ height }" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import type { GraphEdge, GraphNode } from "@/api/asset";

const props = withDefaults(
  defineProps<{
    nodes: GraphNode[];
    edges: GraphEdge[];
    height?: string;
    centerTable?: string;
  }>(),
  { height: "620px" }
);

const emit = defineEmits<{
  "node-click": [node: GraphNode];
  "edge-click": [edge: GraphEdge];
}>();

const chartEl = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;

const SCHEMA_COLORS: Record<string, string> = {
  MEDREC: "#2f7de1",
  ORDADM: "#19a974",
  LAB: "#8b5cf6",
  EXAM: "#f59e0b",
  OUTPBILL: "#ef4444",
  INPBILL: "#06b6d4",
  COMM: "#64748b",
  DRUG_USER: "#10b981",
  PHARMACY: "#ec4899",
  HIS: "#2f7de1",
  DATA_CENTER: "#334155",
  ODS: "#475569",
  LIS: "#8b5cf6",
  PACS: "#f59e0b",
  SM: "#dc2626",
  YDHL: "#0f766e"
};

const STATUS_COLORS: Record<string, string> = {
  verified: "#16a34a",
  sample_pass: "#16a34a",
  manual_reviewed: "#2563eb",
  bounded: "#d97706",
  needs_split: "#dc2626",
  rejected: "#991b1b",
  not_tested: "#94a3b8"
};

function schemaOf(node: GraphNode) {
  return node.category || node.schema_name || node.id.split(".")[0] || "UNKNOWN";
}

function colorOfSchema(schema?: string | null) {
  return SCHEMA_COLORS[schema || ""] || "#64748b";
}

function colorOfStatus(status?: string | null) {
  return STATUS_COLORS[status || ""] || "#94a3b8";
}

function edgeWidth(edge: GraphEdge) {
  if (edge.validation_status === "sample_pass" || edge.validation_status === "verified") return 2.8;
  if (edge.confidence === "A") return 2.2;
  return 1.4;
}

function edgeType(edge: GraphEdge) {
  if (edge.relation_type === "candidate") return "dashed";
  if (edge.relation_type === "dependency") return "dotted";
  return "solid";
}

function buildOption() {
  const schemas = Array.from(new Set(props.nodes.map(schemaOf))).sort();
  const categories = schemas.map(name => ({
    name,
    itemStyle: { color: colorOfSchema(name) }
  }));

  const chartNodes = props.nodes.map(node => {
    const schema = schemaOf(node);
    const isCenter = props.centerTable && node.id === props.centerTable;
    const degree = props.edges.filter(edge => edge.source === node.id || edge.target === node.id).length;
    return {
      ...node,
      id: node.id,
      name: node.table_name || node.label || node.id,
      category: schema,
      symbol: isCenter ? "diamond" : "roundRect",
      symbolSize: isCenter ? 62 : Math.min(54, 32 + degree * 3),
      itemStyle: {
        color: colorOfSchema(schema),
        borderColor: isCenter ? "#111827" : "#ffffff",
        borderWidth: isCenter ? 3 : 1.5,
        shadowBlur: isCenter ? 18 : 8,
        shadowColor: "rgba(15, 23, 42, 0.18)"
      },
      label: {
        show: true,
        formatter: node.table_name || node.label || node.id,
        color: "#1f2937",
        fontSize: isCenter ? 12 : 11,
        fontWeight: isCenter ? 700 : 500
      }
    };
  });

  const chartEdges = props.edges.map(edge => ({
    ...edge,
    id: edge.id,
    source: edge.source,
    target: edge.target,
    lineStyle: {
      color: edge.relation_type === "formal" ? colorOfStatus(edge.validation_status) : "#94a3b8",
      width: edgeWidth(edge),
      type: edgeType(edge),
      opacity: edge.relation_type === "dependency" ? 0.45 : 0.78,
      curveness: 0.18
    },
    label: { show: false },
    emphasis: {
      lineStyle: { width: edgeWidth(edge) + 2, opacity: 1 }
    }
  }));

  return {
    backgroundColor: "#f8fafc",
    animationDuration: 900,
    animationEasingUpdate: "quinticInOut",
    tooltip: {
      confine: true,
      borderWidth: 0,
      backgroundColor: "rgba(15, 23, 42, 0.92)",
      textStyle: { color: "#fff" },
      formatter(params: any) {
        if (params.dataType === "node") {
          const node = params.data as GraphNode;
          return [
            `<strong>${node.id}</strong>`,
            `业务域：${node.domain || "-"}`,
            `字段数：${node.column_count ?? "-"}`,
            `来源：${node.source || "-"}`
          ].join("<br/>");
        }
        const edge = params.data as GraphEdge;
        return [
          `<strong>${edge.source} -> ${edge.target}</strong>`,
          `字段：${edge.from_columns || "-"} -> ${edge.to_columns || "-"}`,
          `状态：${edge.validation_status || "-"}`,
          `级别：${edge.confidence || "-"}`,
          edge.join_condition || ""
        ].filter(Boolean).join("<br/>");
      }
    },
    legend: {
      type: "scroll",
      bottom: 8,
      left: 16,
      right: 16,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { color: "#475569", fontSize: 12 },
      data: categories.map(item => item.name)
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        categories,
        data: chartNodes,
        links: chartEdges,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 8,
        force: {
          repulsion: 420,
          edgeLength: [110, 230],
          gravity: 0.045,
          friction: 0.38
        },
        label: { position: "right", distance: 8 },
        emphasis: {
          focus: "adjacency",
          blurScope: "coordinateSystem",
          itemStyle: { shadowBlur: 24, shadowColor: "rgba(37, 99, 235, 0.35)" }
        }
      }
    ]
  };
}

function renderChart() {
  if (!chartEl.value) return;
  if (!chart) {
    chart = echarts.init(chartEl.value, undefined, { renderer: "canvas" });
    chart.on("click", params => {
      if (params.dataType === "node") emit("node-click", params.data as GraphNode);
      if (params.dataType === "edge") emit("edge-click", params.data as GraphEdge);
    });
  }
  chart.setOption(buildOption() as any, true);
}

function resizeChart() {
  chart?.resize();
}

watch(() => [props.nodes, props.edges, props.centerTable], renderChart, { deep: true });

onMounted(() => {
  renderChart();
  window.addEventListener("resize", resizeChart);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
  chart = null;
});
</script>

<style scoped>
.graph-shell { border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; background: #f8fafc; }
.graph-canvas { width: 100%; min-height: 360px; }
</style>