<template>
  <div class="asset-overview">
    <el-row :gutter="16" class="stat-cards">
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="数据表" :value="summary.tables" />
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="字段" :value="summary.columns" />
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="关联关系" :value="summary.relations" />
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="业务域" :value="summary.domains" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card
          v-loading="chartsLoading"
          shadow="never"
          style="margin-top: 16px"
        >
          <template #header>业务域分布</template>
          <div ref="domainChartRef" style="width: 100%; height: 340px" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card
          v-loading="chartsLoading"
          shadow="never"
          style="margin-top: 16px"
        >
          <template #header>关系验证状态分布</template>
          <div ref="statusChartRef" style="width: 100%; height: 340px" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card
          v-loading="chartsLoading"
          shadow="never"
          style="margin-top: 16px"
        >
          <template #header>Schema 关系数 Top 10</template>
          <div ref="schemaRelChartRef" style="width: 100%; height: 340px" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card
          v-loading="chartsLoading"
          shadow="never"
          style="margin-top: 16px"
        >
          <template #header>核心表 Top 10（按关联关系数）</template>
          <div ref="coreTableChartRef" style="width: 100%; height: 340px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue";
import * as echarts from "echarts";
import {
  getSummary,
  getGraph,
  getTables,
  type SummaryData,
  type GraphEdge,
  type TableBrief
} from "@/api/asset";

const summary = ref<SummaryData>({
  tables: 0,
  columns: 0,
  relations: 0,
  domains: 0
});
const chartsLoading = ref(true);
const domainChartRef = ref<HTMLElement>();
const statusChartRef = ref<HTMLElement>();
const schemaRelChartRef = ref<HTMLElement>();
const coreTableChartRef = ref<HTMLElement>();

const statusLabels: Record<string, string> = {
  verified: "已验证",
  bounded: "有界",
  needs_split: "需拆分",
  not_tested: "未测试",
  sample_verified: "抽样验证",
  missing_in_8216: "8.216缺失"
};

async function loadSummary() {
  try {
    const res = await getSummary();
    summary.value = res.data;
  } catch {
    /* */
  }
}

async function loadCharts() {
  chartsLoading.value = true;
  try {
    const [graphRes, tablesRes] = await Promise.all([
      getGraph({ limit: 500 }),
      getTables({ page: 1, page_size: 1000 })
    ]);
    const edges: GraphEdge[] = graphRes.data.edges;
    const tables: TableBrief[] = tablesRes.data.items;

    // 1. Domain distribution from tables
    const domainMap: Record<string, number> = {};
    for (const t of tables) {
      const d = t.domain || "未分类";
      domainMap[d] = (domainMap[d] || 0) + 1;
    }
    const sortedDomains = Object.entries(domainMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 15);
    if (domainChartRef.value) {
      const chart = echarts.init(domainChartRef.value);
      chart.setOption({
        tooltip: { trigger: "axis" },
        grid: { left: 140 },
        yAxis: {
          type: "category",
          data: sortedDomains.map(v => v[0]).reverse(),
          axisLabel: { width: 120, overflow: "truncate" }
        },
        xAxis: { type: "value", name: "表数量" },
        series: [
          {
            type: "bar",
            data: sortedDomains.map(v => v[1]).reverse(),
            itemStyle: { color: "#409EFF" }
          }
        ]
      });
    }

    // 2. Status distribution from edges
    const statusMap: Record<string, number> = {};
    for (const e of edges) {
      const s = e.validation_status || "unknown";
      statusMap[s] = (statusMap[s] || 0) + 1;
    }
    if (statusChartRef.value) {
      const chart = echarts.init(statusChartRef.value);
      chart.setOption({
        tooltip: { trigger: "item" },
        legend: { orient: "vertical", right: 10, top: 20 },
        series: [
          {
            type: "pie",
            radius: ["40%", "70%"],
            center: ["35%", "50%"],
            data: Object.entries(statusMap).map(([k, v]) => ({
              name: statusLabels[k] || k,
              value: v
            })),
            label: { show: true, formatter: "{b}: {c}" }
          }
        ]
      });
    }

    // 3. Schema relation TopN from edges
    const schemaMap: Record<string, number> = {};
    for (const e of edges) {
      const sch = e.source?.split(".")[0] || "?";
      schemaMap[sch] = (schemaMap[sch] || 0) + 1;
    }
    const sortedSchemas = Object.entries(schemaMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    if (schemaRelChartRef.value) {
      const chart = echarts.init(schemaRelChartRef.value);
      chart.setOption({
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: sortedSchemas.map(v => v[0]),
          axisLabel: { rotate: 30 }
        },
        yAxis: { type: "value", name: "关系数" },
        series: [
          {
            type: "bar",
            data: sortedSchemas.map(v => v[1]),
            itemStyle: { color: "#409EFF" }
          }
        ]
      });
    }

    // 4. Core table TopN from edges
    const tableRelMap: Record<string, number> = {};
    for (const e of edges) {
      if (e.source) tableRelMap[e.source] = (tableRelMap[e.source] || 0) + 1;
      if (e.target) tableRelMap[e.target] = (tableRelMap[e.target] || 0) + 1;
    }
    const sortedTables = Object.entries(tableRelMap)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    if (coreTableChartRef.value) {
      const chart = echarts.init(coreTableChartRef.value);
      chart.setOption({
        tooltip: { trigger: "axis" },
        grid: { left: 180 },
        yAxis: {
          type: "category",
          data: sortedTables.map(v => v[0]).reverse(),
          axisLabel: { width: 160, overflow: "truncate" }
        },
        xAxis: { type: "value", name: "关系数" },
        series: [
          {
            type: "bar",
            data: sortedTables.map(v => v[1]).reverse(),
            itemStyle: { color: "#67C23A" }
          }
        ]
      });
    }
  } catch {
    /* */
  } finally {
    chartsLoading.value = false;
  }
}

onMounted(async () => {
  await loadSummary();
  await nextTick();
  loadCharts();
});
</script>

<style scoped>
.stat-cards .stat-card {
  text-align: center;
}
</style>
