<template>
  <div class="asset-overview">
    <RePageHeader
      title="资产总览"
      subtitle="按业务域、关系状态、数据库分区与核心表热度汇总当前治理资产。"
    >
      <template #icon><DashboardIcon /></template>
      <template #actions>
        <el-button :icon="RefreshIcon" :loading="chartsLoading" @click="reloadAll">
          刷新
        </el-button>
      </template>
    </RePageHeader>

    <el-alert
      v-if="summaryError"
      class="mb20"
      type="error"
      :closable="false"
      :title="`汇总指标加载失败：${summaryError}`"
      show-icon
    >
      <template #default>
        <el-button size="small" type="primary" plain @click="loadSummary">重试汇总</el-button>
      </template>
    </el-alert>

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
      <el-card v-loading="domainLoading" shadow="never" class="overview-card">
        <template #header>
          业务域分布
          <small v-if="domainHint" class="chart-hint">{{ domainHint }}</small>
        </template>
        <ReChart :option="domainChartOption" :empty="!domainRows.length && !domainError" height="340px" :dark="false" />
        <el-alert v-if="domainError" type="error" :closable="false" :title="domainError" class="mt8" show-icon>
          <template #default><el-button size="small" @click="reloadAll">重试</el-button></template>
        </el-alert>
      </el-card>
      <el-card v-loading="statusLoading" shadow="never" class="overview-card">
        <template #header>关系验证状态分布</template>
        <ReChart :option="statusChartOption" :empty="!statusRows.length && !statusError" height="340px" :dark="false" />
        <el-alert v-if="statusError" type="error" :closable="false" :title="statusError" class="mt8" show-icon>
          <template #default><el-button size="small" @click="reloadAll">重试</el-button></template>
        </el-alert>
      </el-card>
      <el-card v-loading="partitionLoading" shadow="never" class="overview-card">
        <template #header>
          数据库分区关系数 Top 10
          <small class="chart-hint">Oracle 对应 Owner，其他库对应数据库/架构或命名空间</small>
        </template>
        <ReChart :option="schemaRelChartOption" :empty="!schemaRows.length && !partitionError" height="340px" :dark="false" />
        <el-alert v-if="partitionError" type="error" :closable="false" :title="partitionError" class="mt8" show-icon>
          <template #default><el-button size="small" @click="reloadAll">重试</el-button></template>
        </el-alert>
      </el-card>
      <el-card v-loading="coreLoading" shadow="never" class="overview-card">
        <template #header>
          核心表 Top 10
          <small class="chart-hint">按已治理关系数量排序，不等同于业务重要性认定</small>
        </template>
        <ReChart :option="coreTableChartOption" :empty="!coreTableRows.length && !coreError" height="340px" :dark="false" />
        <el-alert v-if="coreError" type="error" :closable="false" :title="coreError" class="mt8" show-icon>
          <template #default><el-button size="small" @click="reloadAll">重试</el-button></template>
        </el-alert>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import ReChart from "@/components/ReChart/index.vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { computed, onMounted, ref } from "vue";
import { getOverviewCharts, getSummary, type SummaryData } from "@/api/asset";
import { extractErrorDetail } from "@/utils/errorMessage";
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
const domainLoading = ref(false);
const statusLoading = ref(false);
const partitionLoading = ref(false);
const coreLoading = ref(false);
const domainRows = ref<[string, number][]>([]);
const statusRows = ref<[string, number][]>([]);
const schemaRows = ref<[string, number][]>([]);
const coreTableRows = ref<[string, number][]>([]);
const domainHint = ref("");
const domainError = ref("");
const statusError = ref("");
const partitionError = ref("");
const coreError = ref("");
// 146 E10（R5）：汇总指标失败态
const summaryError = ref("");

const statusLabels: Record<string, string> = {
  verified: "已验证",
  bounded: "有界",
  needs_split: "需拆分",
  not_tested: "未测试",
  sample_verified: "抽样验证",
  sample_pass: "抽样通过",
  missing_in_8216: "8.216缺失",
  candidate: "候选",
  approved: "已批准",
  rejected: "已拒绝"
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
  summaryError.value = "";
  try {
    const res = await getSummary();
    summary.value = res.data;
  } catch (error) {
    // 146 E10（R4→R5）：总览汇总失败不再静默——显式错误 + 重试
    summaryError.value = extractErrorDetail(error, "汇总接口加载失败");
  }
}

async function loadCharts() {
  chartsLoading.value = true;
  domainLoading.value = true;
  statusLoading.value = true;
  partitionLoading.value = true;
  coreLoading.value = true;
  domainError.value = "";
  statusError.value = "";
  partitionError.value = "";
  coreError.value = "";
  try {
    const res = await getOverviewCharts();
    const data = res.data || {};
    const domains = data.domains || { items: [] };
    domainRows.value = (domains.items || []).map((x: any) => [x.name, x.count]);
    if (domains.unclassified != null) {
      domainHint.value = `未分业务域 ${domains.unclassified} / 表总数 ${domains.total_tables ?? "-"}`;
    }
    statusRows.value = (data.validation_status?.items || []).map((x: any) => [
      statusLabels[x.name] || x.name,
      x.count
    ]);
    schemaRows.value = (data.partitions?.items || []).map((x: any) => [x.name, x.count]);
    coreTableRows.value = (data.core_tables?.items || []).map((x: any) => [
      x.label || x.table,
      x.count
    ]);
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || "聚合接口加载失败";
    domainError.value = msg;
    statusError.value = msg;
    partitionError.value = msg;
    coreError.value = msg;
    domainRows.value = [];
    statusRows.value = [];
    schemaRows.value = [];
    coreTableRows.value = [];
  } finally {
    domainLoading.value = false;
    statusLoading.value = false;
    partitionLoading.value = false;
    coreLoading.value = false;
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

.chart-hint {
  display: block;
  margin-top: 4px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.mt8 {
  margin-top: 8px;
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
