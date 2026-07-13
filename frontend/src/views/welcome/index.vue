<script setup lang="ts">
import ReChart from "@/components/ReChart/index.vue";
import ReDataCard from "@/components/ReDataCard/index.vue";
import ReKpiPanel from "@/components/ReKpiPanel/index.vue";
import ReTrendBadge from "@/components/ReTrendBadge/index.vue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import type { EChartsCoreOption } from "echarts/core";
import {
  getDashboardSummary,
  type DashboardActivity,
  type DashboardSummary
} from "@/api/asset";
import { http } from "@/utils/http";
import DatabaseIcon from "~icons/ri/database-2-line";
import TableIcon from "~icons/ri/table-line";
import FieldIcon from "~icons/ri/list-check-2";
import RelationIcon from "~icons/ri/git-branch-line";
import ShieldIcon from "~icons/ri/shield-check-line";
import AlertIcon from "~icons/ri/error-warning-line";
import RefreshIcon from "~icons/ri/refresh-line";
import UserIcon from "~icons/ri/user-3-line";

interface KpiItem {
  label: string;
  value: string;
  unit?: string;
  helper: string;
  trend: string;
  trendDirection: "up" | "down" | "flat";
  tone: "primary" | "accent" | "info" | "warning" | "danger";
  icon: object;
  href?: string;
}

defineOptions({ name: "Welcome" });

const router = useRouter();
const loading = ref(false);
const loadError = ref("");
const healthOk = ref<boolean | null>(null);
const healthDetail = ref("检测中…");
const dash = ref<DashboardSummary | null>(null);

const now = ref(new Date());
const timer = window.setInterval(() => {
  now.value = new Date();
}, 1000 * 30);
onBeforeUnmount(() => window.clearInterval(timer));

const currentTime = computed(() =>
  now.value.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  })
);

function fmt(n: number | null | undefined): string {
  const v = Number(n || 0);
  if (v >= 10000) return `${(v / 10000).toFixed(v >= 100000 ? 0 : 1)}`;
  return String(v);
}

function fmtUnit(n: number | null | undefined): string | undefined {
  return Number(n || 0) >= 10000 ? "万" : undefined;
}

const kpis = computed<KpiItem[]>(() => {
  const d = dash.value;
  if (!d) {
    return [
      {
        label: "系统与数据源",
        value: "—",
        helper: "加载中…",
        trend: "…",
        trendDirection: "flat",
        tone: "primary",
        icon: DatabaseIcon
      },
      {
        label: "资产表",
        value: "—",
        helper: "加载中…",
        trend: "…",
        trendDirection: "flat",
        tone: "accent",
        icon: TableIcon
      },
      {
        label: "字段资产",
        value: "—",
        helper: "加载中…",
        trend: "…",
        trendDirection: "flat",
        tone: "info",
        icon: FieldIcon
      },
      {
        label: "正式关系",
        value: "—",
        helper: "加载中…",
        trend: "…",
        trendDirection: "flat",
        tone: "primary",
        icon: RelationIcon
      },
      {
        label: "人员主档",
        value: "—",
        helper: "加载中…",
        trend: "…",
        trendDirection: "flat",
        tone: "accent",
        icon: UserIcon
      },
      {
        label: "待人工复核",
        value: "—",
        helper: "加载中…",
        trend: "…",
        trendDirection: "flat",
        tone: "danger",
        icon: AlertIcon
      }
    ];
  }

  const last = d.quality_last_run;
  const lastHint = last
    ? `最近 run #${last.id} · findings ${last.total_findings ?? 0}`
    : "尚无质量跑批记录";

  return [
    {
      label: "系统与数据源",
      value: String(d.systems),
      helper: `启用数据源 ${d.sources_enabled}/${d.sources_total}`,
      trend: "登记",
      trendDirection: "flat" as const,
      tone: "primary" as const,
      icon: DatabaseIcon,
      href: "/asset/sources"
    },
    {
      label: "资产表",
      value: fmt(d.assets.tables),
      unit: fmtUnit(d.assets.tables),
      helper: `业务域 ${d.assets.domains} · 快照 ${d.metadata_snapshots}`,
      trend: "目录",
      trendDirection: "flat" as const,
      tone: "accent" as const,
      icon: TableIcon,
      href: "/asset/tables"
    },
    {
      label: "字段资产",
      value: fmt(d.assets.columns),
      unit: fmtUnit(d.assets.columns),
      helper: "asset_columns 实计",
      trend: "结构",
      trendDirection: "flat" as const,
      tone: "info" as const,
      icon: FieldIcon,
      href: "/asset/tables"
    },
    {
      label: "正式关系",
      value: String(d.assets.relations),
      helper: d.relation_by_confidence
        .slice(0, 3)
        .map(x => `${x.name}:${x.count}`)
        .join(" · ") || "暂无分级统计",
      trend: "图谱",
      trendDirection: "flat" as const,
      tone: "primary" as const,
      icon: RelationIcon,
      href: "/asset/graph"
    },
    {
      label: "人员主档",
      value: String(d.persons),
      helper: `科室 ${d.departments} · 规则 ${d.quality_rules}`,
      trend: last ? `质量open ${d.quality_findings_open}` : "HIS",
      trendDirection: "flat" as const,
      tone: "accent" as const,
      icon: UserIcon,
      href: "/identity/persons"
    },
    {
      label: "待人工复核",
      value: String(d.identity_diffs_open),
      helper: lastHint,
      trend: d.identity_diffs_open > 0 ? "待处理" : "清空",
      trendDirection: d.identity_diffs_open > 0 ? ("up" as const) : ("flat" as const),
      tone: "danger" as const,
      icon: AlertIcon,
      href: "/identity/sync-diffs"
    }
  ];
});

const healthTrendOption = computed<EChartsCoreOption>(() => {
  const trend = dash.value?.quality_run_trend || [];
  if (!trend.length) {
    return {
      title: {
        text: "暂无质量跑批趋势",
        left: "center",
        top: "middle",
        textStyle: { color: "#94a3b8", fontSize: 13 }
      }
    };
  }
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["findings", "pass_rate%"] },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: trend.map(t => t.label)
    },
    yAxis: [{ type: "value", name: "findings" }, { type: "value", name: "%", max: 100 }],
    series: [
      {
        name: "findings",
        type: "line",
        smooth: true,
        symbolSize: 6,
        areaStyle: { opacity: 0.16 },
        data: trend.map(t => t.findings)
      },
      {
        name: "pass_rate%",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        symbolSize: 6,
        data: trend.map(t => t.pass_rate)
      }
    ]
  };
});

const domainOption = computed<EChartsCoreOption>(() => {
  const rows = dash.value?.domain_top || [];
  if (!rows.length) {
    return {
      title: {
        text: "暂无业务域分布（表目录可能未导入）",
        left: "center",
        top: "middle",
        textStyle: { color: "#94a3b8", fontSize: 13 }
      }
    };
  }
  return {
    tooltip: { trigger: "item" },
    legend: { bottom: 0 },
    series: [
      {
        name: "业务域",
        type: "pie",
        radius: ["52%", "76%"],
        center: ["50%", "44%"],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 8, borderColor: "#0B1120", borderWidth: 2 },
        label: { color: "#CBD5E1" },
        data: rows.map(r => ({ value: r.count, name: r.name }))
      }
    ]
  };
});

const relationRankOption = computed<EChartsCoreOption>(() => {
  const rows = [...(dash.value?.schema_top || [])].reverse();
  if (!rows.length) {
    return {
      title: {
        text: "暂无 Schema 表量统计",
        left: "center",
        top: "middle",
        textStyle: { color: "#94a3b8", fontSize: 13 }
      }
    };
  }
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 96, right: 20, top: 20, bottom: 24 },
    xAxis: { type: "value" },
    yAxis: {
      type: "category",
      data: rows.map(r => r.name)
    },
    series: [
      {
        name: "表数量",
        type: "bar",
        barWidth: 12,
        itemStyle: { borderRadius: [0, 8, 8, 0] },
        data: rows.map(r => r.count)
      }
    ]
  };
});

const activities = computed<DashboardActivity[]>(() => {
  const list = dash.value?.activities || [];
  if (list.length) return list;
  return [
    {
      title: "等待指标加载",
      desc: loadError.value || "请点击右上角刷新，或确认已登录且后端可用",
      status: loadError.value ? "异常" : "空",
      tone: "info"
    }
  ];
});

const healthText = computed(() => {
  if (healthOk.value === null) return "检测中…";
  return healthOk.value ? "运行正常" : healthDetail.value || "异常";
});

async function checkHealth() {
  try {
    // 经 Nginx 只能走 /api/*；后端同时提供 /health 与 /api/v1/health
    const res = await http.request<any>("get", "/api/v1/health");
    // 兼容 ApiResponse 或裸对象
    const data = res?.data ?? res;
    const db = data?.database ?? data?.db ?? data?.status;
    const ok =
      data?.status === "ok" ||
      db === "connected" ||
      data?.status === "alive" ||
      res?.code === 0;
    healthOk.value = ok !== false;
    healthDetail.value =
      typeof db === "string" ? `DB: ${db}` : data?.message || "API 可达";
  } catch (e: any) {
    healthOk.value = false;
    healthDetail.value = e?.response?.status
      ? `HTTP ${e.response.status}`
      : "健康检查失败";
  }
}

async function loadDashboard() {
  loading.value = true;
  loadError.value = "";
  // 健康检查失败不阻塞 KPI；summary 失败才算首页失败
  const healthPromise = checkHealth().catch(() => undefined);
  try {
    const sumRes = await getDashboardSummary();
    dash.value = sumRes.data;
    await healthPromise;
  } catch (e: any) {
    loadError.value =
      e?.response?.data?.message ||
      e?.response?.data?.detail ||
      e?.message ||
      "加载失败";
    dash.value = null;
    await healthPromise;
  } finally {
    loading.value = false;
  }
}

function go(href?: string) {
  if (href) router.push(href);
}

onMounted(loadDashboard);
</script>

<template>
  <main v-loading="loading" class="welcome-dashboard asset-shell-dark">
    <section class="dashboard-hero">
      <div>
        <p class="dashboard-eyebrow">Data Asset Command Center</p>
        <h1>数据资产指挥中心</h1>
        <p class="dashboard-subtitle">
          指标来自平台库实时聚合（系统/表/关系/人员/质量/复核），点击卡片可跳转对应工作台。
        </p>
        <p v-if="dash?.generated_at" class="generated-at">
          数据时间 {{ new Date(dash.generated_at).toLocaleString("zh-CN") }}
        </p>
        <p v-if="loadError" class="load-error">{{ loadError }}</p>
      </div>
      <div class="status-panel">
        <div>
          <span>当前时间</span>
          <strong>{{ currentTime }}</strong>
        </div>
        <div>
          <span>系统健康</span>
          <strong :class="{ 'is-ok': healthOk === true, 'is-bad': healthOk === false }">
            {{ healthText }}
          </strong>
        </div>
        <el-button
          type="primary"
          :icon="RefreshIcon"
          plain
          :loading="loading"
          @click="loadDashboard"
        >
          刷新视图
        </el-button>
      </div>
    </section>

    <section class="kpi-grid">
      <div
        v-for="item in kpis"
        :key="item.label"
        class="kpi-click"
        :class="{ clickable: !!item.href }"
        @click="go(item.href)"
      >
        <ReKpiPanel
          :label="item.label"
          :value="item.value"
          :unit="item.unit"
          :helper="item.helper"
          :trend="item.trend"
          :trend-direction="item.trendDirection"
          :tone="item.tone"
        >
          <template #icon><component :is="item.icon" /></template>
        </ReKpiPanel>
      </div>
    </section>

    <section class="dashboard-grid">
      <ReDataCard title="质量跑批趋势" subtitle="最近质量检查 run（findings / pass_rate）" glow>
        <ReChart :option="healthTrendOption" height="320px" />
      </ReDataCard>
      <ReDataCard title="业务域分布" subtitle="按 asset_tables.domain 实计" glow>
        <ReChart :option="domainOption" height="320px" />
      </ReDataCard>
      <ReDataCard title="Schema/Owner 表量 Top" subtitle="按 namespace/schema 聚合" glow>
        <ReChart :option="relationRankOption" height="310px" />
      </ReDataCard>
      <ReDataCard title="最近工作台" subtitle="根据当前库状态生成的关注项" glow>
        <div class="activity-list">
          <article
            v-for="item in activities"
            :key="item.title"
            class="activity-item"
            :class="{ clickable: !!item.href }"
            @click="go(item.href)"
          >
            <div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </div>
            <ReTrendBadge :value="item.status" direction="flat" />
          </article>
        </div>
      </ReDataCard>
    </section>
  </main>
</template>

<style scoped lang="scss">
.welcome-dashboard {
  min-height: calc(100vh - 88px);
  padding: 28px;
  overflow: hidden;
  background:
    radial-gradient(circle at 80% 8%, rgb(14 165 233 / 16%), transparent 30%),
    radial-gradient(circle at 12% 42%, rgb(13 148 136 / 15%), transparent 26%),
    var(--gradient-hero);
}

.dashboard-hero {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
}

.dashboard-eyebrow {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 800;
  color: var(--accent-400);
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(28px, 3.4vw, 44px);
  font-weight: 850;
  line-height: 1.15;
  color: #fff;
}

.dashboard-subtitle {
  max-width: 720px;
  margin: 14px 0 0;
  font-size: 15px;
  line-height: 1.7;
  color: var(--dark-text-regular);
}

.generated-at {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--dark-text-secondary);
}

.load-error {
  margin: 8px 0 0;
  font-size: 13px;
  color: #fb7185;
}

.status-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: flex-end;
  min-width: 360px;
  padding: 14px;
  background: rgb(15 23 42 / 58%);
  border: 1px solid rgb(148 163 184 / 16%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-inset);
  backdrop-filter: blur(18px);
}

.status-panel div {
  min-width: 98px;
}

.status-panel span,
.status-panel strong {
  display: block;
}

.status-panel span {
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--dark-text-secondary);
}

.status-panel strong {
  font-size: 14px;
  color: #fff;
}

.status-panel .is-ok {
  color: var(--accent-400);
}

.status-panel .is-bad {
  color: #fb7185;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(160px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.kpi-click.clickable {
  cursor: pointer;
}

.kpi-click.clickable:hover {
  filter: brightness(1.05);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: 16px;
}

.activity-list {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 12px;
}

.activity-item {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  justify-content: space-between;
  padding: 14px;
  background: rgb(15 23 42 / 48%);
  border: 1px solid rgb(148 163 184 / 12%);
  border-radius: var(--radius-base);
}

.activity-item.clickable {
  cursor: pointer;
}

.activity-item.clickable:hover {
  border-color: rgb(14 165 233 / 35%);
}

.activity-item h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--dark-text-primary);
}

.activity-item p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--dark-text-secondary);
}

@media (max-width: 1480px) {
  .kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1080px) {
  .dashboard-hero,
  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-hero {
    flex-direction: column;
  }

  .status-panel {
    justify-content: flex-start;
    min-width: 0;
    width: 100%;
  }
}

@media (max-width: 760px) {
  .welcome-dashboard {
    padding: 18px;
  }

  .kpi-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
