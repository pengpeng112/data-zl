<script setup lang="ts">
import ReChart from "@/components/ReChart/index.vue";
import ReDataCard from "@/components/ReDataCard/index.vue";
import ReKpiPanel from "@/components/ReKpiPanel/index.vue";
import ReTrendBadge from "@/components/ReTrendBadge/index.vue";
import { computed, onBeforeUnmount, ref } from "vue";
import type { EChartsCoreOption } from "echarts/core";
import DatabaseIcon from "~icons/ri/database-2-line";
import TableIcon from "~icons/ri/table-line";
import FieldIcon from "~icons/ri/list-check-2";
import RelationIcon from "~icons/ri/git-branch-line";
import ShieldIcon from "~icons/ri/shield-check-line";
import AlertIcon from "~icons/ri/error-warning-line";
import RefreshIcon from "~icons/ri/refresh-line";

interface KpiItem {
  label: string;
  value: string;
  unit?: string;
  helper: string;
  trend: string;
  trendDirection: "up" | "down" | "flat";
  tone: "primary" | "accent" | "info" | "warning" | "danger";
  icon: object;
}

const now = ref(new Date());
const timer = window.setInterval(() => {
  now.value = new Date();
}, 1000 * 30);

onBeforeUnmount(() => window.clearInterval(timer));

defineOptions({
  name: "Welcome"
});

const currentTime = computed(() => {
  return now.value.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
});

const kpis: KpiItem[] = [
  {
    label: "系统与数据源",
    value: "12",
    helper: "ODS / HIS / HRP 已纳入治理视图",
    trend: "+2",
    trendDirection: "up",
    tone: "primary",
    icon: DatabaseIcon
  },
  {
    label: "资产表",
    value: "8.6",
    unit: "万",
    helper: "含 HRP 首版资产包与 HIS_READY",
    trend: "+76057",
    trendDirection: "up",
    tone: "accent",
    icon: TableIcon
  },
  {
    label: "字段资产",
    value: "502",
    unit: "万",
    helper: "HRP 字段仍需夜间分段补采",
    trend: "待复核",
    trendDirection: "flat",
    tone: "info",
    icon: FieldIcon
  },
  {
    label: "正式关系",
    value: "47",
    helper: "A/B/C 当前可用，D 类独立标识",
    trend: "稳定",
    trendDirection: "flat",
    tone: "primary",
    icon: RelationIcon
  },
  {
    label: "质量执行",
    value: "10",
    helper: "核心表质量规则已跑通",
    trend: "3 findings",
    trendDirection: "down",
    tone: "warning",
    icon: ShieldIcon
  },
  {
    label: "待人工确认",
    value: "4",
    helper: "人员唯一键、科室编码等需确认",
    trend: "人工复核",
    trendDirection: "flat",
    tone: "danger",
    icon: AlertIcon
  }
];

const healthTrendOption: EChartsCoreOption = {
  tooltip: { trigger: "axis" },
  legend: { data: ["元数据", "关系", "质量"] },
  xAxis: {
    type: "category",
    boundaryGap: false,
    data: ["07-02", "07-03", "07-04", "07-05", "07-06", "07-07", "07-08"]
  },
  yAxis: { type: "value" },
  series: [
    {
      name: "元数据",
      type: "line",
      smooth: true,
      symbolSize: 6,
      areaStyle: { opacity: 0.16 },
      data: [62, 68, 75, 81, 88, 91, 94]
    },
    {
      name: "关系",
      type: "line",
      smooth: true,
      symbolSize: 6,
      areaStyle: { opacity: 0.12 },
      data: [42, 48, 56, 64, 72, 78, 82]
    },
    {
      name: "质量",
      type: "line",
      smooth: true,
      symbolSize: 6,
      areaStyle: { opacity: 0.1 },
      data: [28, 34, 43, 52, 61, 68, 73]
    }
  ]
};

const domainOption: EChartsCoreOption = {
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
      data: [
        { value: 31, name: "临床主线" },
        { value: 22, name: "运营财务" },
        { value: 18, name: "人员组织" },
        { value: 14, name: "物资供应" },
        { value: 15, name: "字典编码" }
      ]
    }
  ]
};

const relationRankOption: EChartsCoreOption = {
  tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
  grid: { left: 96, right: 20, top: 20, bottom: 24 },
  xAxis: { type: "value" },
  yAxis: {
    type: "category",
    data: ["MEDREC", "COMM", "ORDADM", "LAB", "EXAM", "HRP", "ODS"].reverse()
  },
  series: [
    {
      name: "关系数",
      type: "bar",
      barWidth: 12,
      itemStyle: { borderRadius: [0, 8, 8, 0] },
      data: [47, 35, 28, 24, 22, 18, 16].reverse()
    }
  ]
};

const activities = [
  { title: "HRP 源端资产包已生成", desc: "表/字段/索引/约束资产已输出，字段需分段补采", status: "待复核", tone: "warning" },
  { title: "HIS_READY 待确认表清零", desc: "按 40 号治理口径完成核心/排除/保留收敛", status: "已完成", tone: "success" },
  { title: "图谱高级交互已落地", desc: "支持分层、泳道、环形布局与边证据详情", status: "稳定", tone: "primary" },
  { title: "D 类跨系统关系延后验证", desc: "等待更多系统源端元数据后再纳入正式验证", status: "待启动", tone: "info" }
];
</script>

<template>
  <main class="welcome-dashboard asset-shell-dark">
    <section class="dashboard-hero">
      <div>
        <p class="dashboard-eyebrow">Data Asset Command Center</p>
        <h1>数据资产指挥中心</h1>
        <p class="dashboard-subtitle">
          聚合源库探查、资产治理、关系验证与质量执行状态，优先暴露风险与下一步复核入口。
        </p>
      </div>
      <div class="status-panel">
        <div>
          <span>当前时间</span>
          <strong>{{ currentTime }}</strong>
        </div>
        <div>
          <span>系统健康</span>
          <strong class="is-ok">运行正常</strong>
        </div>
        <el-button type="primary" :icon="RefreshIcon" plain>刷新视图</el-button>
      </div>
    </section>

    <section class="kpi-grid">
      <ReKpiPanel
        v-for="item in kpis"
        :key="item.label"
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
    </section>

    <section class="dashboard-grid">
      <ReDataCard title="资产健康趋势" subtitle="近 7 日治理覆盖与质量执行进度" glow>
        <ReChart :option="healthTrendOption" height="320px" />
      </ReDataCard>
      <ReDataCard title="业务域分布" subtitle="按资产主题粗分布" glow>
        <ReChart :option="domainOption" height="320px" />
      </ReDataCard>
      <ReDataCard title="Schema 关系热度" subtitle="按已验证与候选关系汇总" glow>
        <ReChart :option="relationRankOption" height="310px" />
      </ReDataCard>
      <ReDataCard title="最近工作台" subtitle="需要关注的资产与治理动作" glow>
        <div class="activity-list">
          <article v-for="item in activities" :key="item.title" class="activity-item">
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

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(160px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
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
