<template>
  <div ref="chartEl" :style="{ width: '100%', height: height }" />
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from "vue";
import * as echarts from "echarts";
import type { GraphNode, GraphEdge } from "@/api/asset";

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
  HIS: "#409EFF",
  LIS: "#67C23A",
  PACS: "#9B59B6",
  YDHL: "#E6A23C",
  SM: "#F56C6C",
  MTL: "#909399",
  JHEMR: "#01A6A0",
  ODS: "#B8860B"
};

const STATUS_COLORS: Record<string, string> = {
  verified: "#67C23A",
  bounded: "#E6A23C",
  needs_split: "#F56C6C",
  not_tested: "#909399",
  sample_verified: "#67C23A",
  missing_in_8216: "#909399"
};

const RELATION_TYPE_STYLE: Record<
  string,
  { color: string; lineWidth: number; type: string }
> = {
  candidate: { color: "#E6A23C", lineWidth: 1.2, type: "dashed" },
  dependency: { color: "#909399", lineWidth: 1, type: "dotted" },
  formal: { color: "#409EFF", lineWidth: 1.2, type: "solid" }
};

function getSchemaColor(schemaName?: string | null): string {
  return SCHEMA_COLORS[schemaName ?? ""] || "#909399";
}

function getStatusColor(status?: string | null): string {
  return STATUS_COLORS[status ?? ""] || "#909399";
}

function buildOption() {
  const schemas = Array.from(
    new Set(props.nodes.map(n => n.category ?? n.schema_name ?? "?"))
  );
  const categories = schemas.map(s => ({
    name: s,
    itemStyle: { color: getSchemaColor(s) }
  }));

  const chartNodes = props.nodes.map(n => {
    const isCenter = props.centerTable && n.id === props.centerTable;
    return {
      id: n.id,
      name: n.label || n.table_name || n.id,
      category: n.category ?? n.schema_name ?? "?",
      symbolSize: isCenter ? 52 : 36,
      itemStyle: isCenter ? { borderColor: "#E6A23C", borderWidth: 3 } : {},
      ...n,
      tooltip: {
        formatter: `${n.id}<br/>域：${n.domain || "-"}<br/>字段：${n.column_count || "-"}`
      }
    };
  });

  const chartEdges = props.edges.map(e => {
    const rt = e.relation_type || "formal";
    const style = RELATION_TYPE_STYLE[rt] || RELATION_TYPE_STYLE.formal;
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      label: { show: false },
      lineStyle: {
        color:
          rt === "formal" ? getStatusColor(e.validation_status) : style.color,
        curveness: 0.2,
        opacity: rt === "formal" ? 0.75 : 0.5,
        width:
          rt === "formal" && e.validation_status === "verified"
            ? 2
            : style.lineWidth,
        type: style.type
      },
      ...e
    };
  });

  return {
    tooltip: {
      formatter(params: any) {
        if (params.dataType === "node") {
          const d = params.data;
          return `<b>${d.id}</b><br/>域：${d.domain || "-"}<br/>字段数：${d.column_count || "-"}`;
        }
        const e = params.data;
        const typeLabel =
          e.relation_type === "candidate"
            ? "候选"
            : e.relation_type === "dependency"
              ? "视图依赖"
              : "正式";
        return `<b>${e.source} → ${e.target}</b><br/>类型：${typeLabel}<br/>${e.join_condition || ""}<br/>状态：${e.validation_status || "-"}<br/>指标：${e.validation_metrics || "-"}`;
      }
    },
    legend: [
      {
        data: categories.map(c => c.name),
        bottom: 0,
        textStyle: { fontSize: 11 }
      }
    ],
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        categories,
        data: chartNodes,
        links: chartEdges,
        force: {
          repulsion: 280,
          edgeLength: [80, 200],
          gravity: 0.08
        },
        label: {
          show: true,
          position: "right",
          fontSize: 11,
          formatter: "{b}"
        },
        lineStyle: {
          curveness: 0.2,
          opacity: 0.7
        },
        emphasis: {
          focus: "adjacency",
          itemStyle: { borderWidth: 2, borderColor: "#333" },
          lineStyle: { width: 4 }
        }
      }
    ]
  };
}

function renderChart() {
  if (!chartEl.value) return;
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }
  chart.setOption(buildOption(), true);
}

function handleClick(params: any) {
  if (params.dataType === "node") {
    emit("node-click", params.data as GraphNode);
  } else if (params.dataType === "edge") {
    emit("edge-click", params.data as GraphEdge);
  }
}

watch(() => [props.nodes, props.edges], renderChart, { deep: true });

onMounted(() => {
  renderChart();
  chart?.on("click", handleClick);
  window.addEventListener("resize", () => chart?.resize());
});

onBeforeUnmount(() => {
  chart?.off("click", handleClick);
  chart?.dispose();
  window.removeEventListener("resize", () => chart?.resize());
});
</script>
