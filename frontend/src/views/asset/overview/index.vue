<template>
  <div class="asset-overview">
    <RePageHeader
      title="资产总览"
      subtitle="按业务域、关系状态、Schema 与核心表热度汇总当前治理资产。"
    >
      <template #icon><DashboardIcon /></template>
      <template #actions>
        <el-button :icon="RefreshIcon" :loading="chartsLoading" @click="reloadAll">
          刷新
        </el-button>
      </template>
    </RePageHeader>

    <section class="stat-grid">
      <ReStatCard label="数据表" :value="summary.tables" tone="primary" helper="纳入资产目录">
        <template #icon><TableIcon /></template>
      </ReStatCard>
      <ReStatCard label="字段" :value="summary.columns" tone="accent" helper="结构与语义字段">
        <template #icon><ListIcon /></template>
      </ReStatCard>
      <ReStatCard label="关联关系" :value="summary.relations" tone="info" helper="正式与候选关系">
        <template #icon><RelationIcon /></template>
      </ReStatCard>
      <ReStatCard label="业务域" :value="summary.domains" tone="warning" helper="主题分类覆盖">
        <template #icon><PieIcon /></template>
      </ReStatCard>
    </section>

    <section class="chart-grid">
      <el-card v-loading="chartsLoading" shadow="never" class="overview-card">
        <template #header>业务域分布</template>
        <ReChart :option="domainChartOption" :empty="!domainRows.length" height="340px" :dark="false" />
      </el-card>
      <el-card v-loading="chartsLoading" shadow="never" class="overview-card">
        <template #header>关系验证状态分布</template>
        <ReChart :option="statusChartOption" :empty="!statusRows.length" height="340px" :dark="false" />
      </el-card>
      <el-card v-loading="chartsLoading" shadow="never" class="overview-card">
        <template #header>Schema 关系数 Top 10</template>
        <ReChart :option="schemaRelChartOption" :empty="!schemaRows.length" height="340px" :dark="false" />
      </el-card>
      <el-card v-loading="chartsLoading" shadow="never" class="overview-card">
        <template #header>核心表 Top 10（按关联关系数）</template>
        <ReChart :option="coreTableChartOption" :empty="!coreTableRows.length" height="340px" :dark="false" />
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import ReChart from "@/components/ReChart/index.vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { computed, onMounted, ref } from "vue";
import {
  getGraph,
  getSummary,
  getTables,
  type GraphEdge,
  type SummaryData,
  type TableBrief
} from "@/api/asset";
import type { EChartsCoreOption } from "echarts/core";
import DashboardIcon from "~icons/ri/dashboard-3-line";
import ListIcon from "~icons/ri/list-check-2";
import PieIcon from "~icons/ri/pie-chart-2-line";
import RefreshIcon from "~icons/ri/refresh-line";
import RelationIcon from "~icons/ri/git-branch-line";
import TableIcon from "~icons/ri/table-line";

defineOptions({ name: "AssetOverview" });

const summary = ref<SummaryData>({
  tables: 0,
  columns: 0,
  relations: 0,
  domains: 0
});
const chartsLoading = ref(true);
const domainRows = ref<[string, number][]>([]);
const statusRows = ref<[string, number][]>([]);
const schemaRows = ref<[string, number][]>([]);
const coreTableRows = ref<[string, number][]>([]);

const statusLabels: Record<string, string> = {
  verified: "已验证",
  bounded: "有界",
  needs_split: "需拆分",
  not_tested: "未测试",
  sample_verified: "抽样验证",
  sample_pass: "抽样通过",
  missing_in_8216: "8.216缺失"
};

const barItemStyle = { borderRadius: [0, 8, 8, 0] };

const domainChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  grid: { left: 132, right: 20, top: 24, bottom: 24 },
  yAxis: {
    type: "category",
    data: domainRows.value.map(v => v[0]).reverse(),
    axisLabel: { width: 116, overflow: "truncate" }
  },
  xAxis: { type: "value", name: "表数量" },
  series: [{ type: "bar", data: domainRows.value.map(v => v[1]).reverse(), itemStyle: barItemStyle }]
}));

const statusChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: "item" },
  legend: { orient: "vertical", right: 12, top: 20 },
  series: [
    {
      type: "pie",
      radius: ["46%", "72%"],
      center: ["36%", "52%"],
      itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 2 },
      data: statusRows.value.map(([name, value]) => ({ name, value })),
      label: { show: true, formatter: "{b}: {c}" }
    }
  ]
}));

const schemaRelChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  xAxis: { type: "category", data: schemaRows.value.map(v => v[0]), axisLabel: { rotate: 30 } },
  yAxis: { type: "value", name: "关系数" },
  series: [{ type: "bar", data: schemaRows.value.map(v => v[1]), itemStyle: { borderRadius: [8, 8, 0, 0] } }]
}));

const coreTableChartOption = computed<EChartsCoreOption>(() => ({
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  grid: { left: 178, right: 20, top: 24, bottom: 24 },
  yAxis: {
    type: "category",
    data: coreTableRows.value.map(v => v[0]).reverse(),
    axisLabel: { width: 158, overflow: "truncate" }
  },
  xAxis: { type: "value", name: "关系数" },
  series: [{ type: "bar", data: coreTableRows.value.map(v => v[1]).reverse(), itemStyle: barItemStyle }]
}));

async function loadSummary() {
  try {
    const res = await getSummary();
    summary.value = res.data;
  } catch {
    /* keep default summary */
  }
}

function topEntries(map: Record<string, number>, limit: number) {
  return Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, limit);
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

    const domainMap: Record<string, number> = {};
    for (const table of tables) {
      const domain = table.domain || "未分类";
      domainMap[domain] = (domainMap[domain] || 0) + 1;
    }
    domainRows.value = topEntries(domainMap, 15);

    const statusMap: Record<string, number> = {};
    const schemaMap: Record<string, number> = {};
    const tableRelMap: Record<string, number> = {};
    for (const edge of edges) {
      const status = edge.validation_status || "unknown";
      statusMap[statusLabels[status] || status] = (statusMap[statusLabels[status] || status] || 0) + 1;
      const schema = edge.source?.split(".")[0] || "?";
      schemaMap[schema] = (schemaMap[schema] || 0) + 1;
      if (edge.source) tableRelMap[edge.source] = (tableRelMap[edge.source] || 0) + 1;
      if (edge.target) tableRelMap[edge.target] = (tableRelMap[edge.target] || 0) + 1;
    }
    statusRows.value = topEntries(statusMap, 12);
    schemaRows.value = topEntries(schemaMap, 10);
    coreTableRows.value = topEntries(tableRelMap, 10);
  } catch {
    domainRows.value = [];
    statusRows.value = [];
    schemaRows.value = [];
    coreTableRows.value = [];
  } finally {
    chartsLoading.value = false;
  }
}

function reloadAll() {
  loadSummary();
  loadCharts();
}

onMounted(reloadAll);
</script>

<style scoped lang="scss">
.asset-overview {
  padding: 4px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.overview-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);

  :deep(.el-card__header) {
    padding: 14px 16px;
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    background: var(--bg-elevated);
    border-bottom-color: var(--border-light);
  }
}

@media (max-width: 1200px) {
  .stat-grid,
  .chart-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .stat-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
