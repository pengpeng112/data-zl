<template>
  <div class="system-map">
    <RePageHeader
      title="数据资产系统图"
      subtitle="高质量专题数据集 · 持续治理链路全景（可信 · 可解释 · 可追溯 · 可复用）"
    >
      <template #actions>
        <el-button :loading="loading" @click="reloadAll">刷新</el-button>
      </template>
    </RePageHeader>

    <el-alert
      v-if="loadError"
      class="mt12"
      type="error"
      :closable="false"
      :title="loadError"
      show-icon
    >
      <template #default>
        <el-button size="small" type="primary" plain @click="reloadAll">重试</el-button>
      </template>
    </el-alert>

    <!-- 治理规模 KPI（真实接口数据） -->
    <section class="kpi-grid">
      <ReStatCard label="接入业务系统" :value="kpi.systems" tone="primary" helper="HIS/LIS/PACS/EMR/手麻 等" />
      <ReStatCard label="治理资产表" :value="kpi.tables" tone="accent" helper="全景视图 · 资产可知" />
      <ReStatCard label="数据字段" :value="kpi.columns" tone="info" helper="结构与语义覆盖" />
      <ReStatCard label="数据关系" :value="kpi.relations" tone="warning" helper="跨系统关联 · 置信度分级" />
      <ReStatCard label="质量规则" :value="kpi.qualityRules" tone="accent" helper="自动化质控基线" />
      <ReStatCard label="确认值域" :value="kpi.confirmedDomains" tone="primary" helper="AI 取数口径来源" />
    </section>

    <!-- 六步持续治理链路 -->
    <el-card shadow="never" class="chain-card">
      <template #header>
        <div class="chain-head">
          <span class="chain-title">六步持续治理链路</span>
          <span class="chain-sub">每一步由平台真实模块支撑，从临时导数走向持续治理的高质量专题数据集</span>
        </div>
      </template>

      <div class="chain-grid">
        <template v-for="(step, idx) in steps" :key="step.key">
          <div class="step" :class="{ active: step.key === 'relations' }" @click="go(step)">
            <div class="step-no">{{ idx + 1 }}</div>
            <div class="step-name">{{ step.name }}</div>
            <div class="step-desc">{{ step.desc }}</div>
            <div class="step-data">
              <div v-for="row in step.rows()" :key="row.label" class="data-row">
                <span class="data-label">{{ row.label }}</span>
                <span class="data-value">{{ row.value }}</span>
              </div>
            </div>
            <el-button class="step-btn" size="small" text type="primary">
              进入{{ step.module }} →
            </el-button>
          </div>
          <div v-if="idx < steps.length - 1" class="chain-arrow">➤</div>
        </template>
      </div>
    </el-card>

    <!-- 底部横幅 -->
    <div class="slogan">
      <span class="slogan-main">可信 · 可解释 · 可追溯 · 可复用</span>
      <span class="slogan-sub">全链路治理闭环：规范标准 · 应用友好化 · 口径稳定 · 生成可靠 · 场景赋能 · 互信共赢</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { getDashboardSummary, listValueDomains, type SummaryData } from "@/api/asset";
import { getAuditLogsSummary } from "@/api/ops";
import { extractErrorDetail } from "@/utils/errorMessage";

defineOptions({ name: "AssetSystemMap" });

const router = useRouter();
const loading = ref(false);
const loadError = ref("");
const summary = ref<SummaryData>({ tables: 0, columns: 0, relations: 0, domains: 0 });
const extra = reactive({
  systems: 0,
  qualityRules: 0,
  qualityFindingsOpen: 0,
  metadataSnapshots: 0,
  relationA: 0,
  confirmedDomains: 0,
  auditTotal: 0
});

const kpi = computed(() => ({
  systems: extra.systems,
  tables: summary.value.tables,
  columns: summary.value.columns,
  relations: summary.value.relations,
  qualityRules: extra.qualityRules,
  confirmedDomains: extra.confirmedDomains
}));

const fmt = (n: number) => (n == null ? "-" : Number(n).toLocaleString("en-US"));

interface StepRow {
  label: string;
  value: string;
}

interface StepDef {
  key: string;
  name: string;
  desc: string;
  module: string;
  path: string;
  rows: () => StepRow[];
}

const steps: StepDef[] = [
  {
    key: "assets",
    name: "资产可知",
    desc: "梳理全域数据全景视图，系统/表/字段三级目录一览无余",
    module: "表资产",
    path: "/asset/tables",
    rows: () => [
      { label: "治理资产表", value: fmt(summary.value.tables) },
      { label: "数据字段", value: fmt(summary.value.columns) },
      { label: "接入系统", value: fmt(extra.systems) }
    ]
  },
  {
    key: "relations",
    name: "关系可信",
    desc: "构建跨系统关联关系，置信度分级、复核确认、责任到人",
    module: "关系图谱",
    path: "/asset/graph",
    rows: () => [
      { label: "数据关系", value: fmt(summary.value.relations) },
      { label: "A 级（已复核）", value: fmt(extra.relationA) },
      { label: "关系图谱可视化", value: "force 直观视图" }
    ]
  },
  {
    key: "standards",
    name: "标准统一",
    desc: "值域知识库与字典中心统一数据标准与口径语义",
    module: "值域知识库",
    path: "/value-domains",
    rows: () => [
      { label: "确认值域", value: fmt(extra.confirmedDomains) },
      { label: "业务域覆盖", value: fmt(summary.value.domains) },
      { label: "AI 取数注入", value: "自动生效" }
    ]
  },
  {
    key: "quality",
    name: "质控可检",
    desc: "规则统一 + AI 自动化探查质控，及时发现并跟踪问题",
    module: "数据质量",
    path: "/asset/quality",
    rows: () => [
      { label: "质量规则", value: fmt(extra.qualityRules) },
      { label: "待处理发现", value: fmt(extra.qualityFindingsOpen) },
      { label: "AI 夜间探查", value: "常态化执行" }
    ]
  },
  {
    key: "trace",
    name: "过程可溯",
    desc: "全链路日志留痕，质量轨迹可追溯、可审计",
    module: "审计日志",
    path: "/asset/admin",
    rows: () => [
      { label: "审计留痕", value: fmt(extra.auditTotal) },
      { label: "元数据快照", value: fmt(extra.metadataSnapshots) },
      { label: "操作可回放", value: "全程覆盖" }
    ]
  },
  {
    key: "reuse",
    name: "结果可复用",
    desc: "基于确认数据与口径，多场景业务可复用",
    module: "查询与指标中心",
    path: "/asset/queries",
    rows: () => [
      { label: "查询资产", value: "受控治理" },
      { label: "指标计算", value: "口径稳定" },
      { label: "数据产品", value: "发布复用" }
    ]
  }
];

function go(step: StepDef) {
  router.push(step.path);
}

async function loadSummary() {
  // /dashboard/summary 单接口聚合：assets{tables/columns/relations/domains} + 系统/质控/置信度分布
  const res = await getDashboardSummary();
  const data: any = res.data || {};
  summary.value = { ...(data.assets || {}) };
  extra.systems = data.systems || 0;
  extra.qualityRules = data.quality_rules || 0;
  extra.qualityFindingsOpen = data.quality_findings_open || 0;
  extra.metadataSnapshots = data.metadata_snapshots || 0;
  const conf = (data.relation_by_confidence || []) as { name: string; count: number }[];
  extra.relationA = conf.filter(c => (c.name || "").toUpperCase().startsWith("A")).reduce((acc, c) => acc + (c.count || 0), 0);
}

async function loadConfirmedDomains() {
  const res = await listValueDomains({ status: "confirmed", page: 1, page_size: 1 } as any);
  extra.confirmedDomains = res.data.total;
}

async function loadAudit() {
  const res = await getAuditLogsSummary();
  extra.auditTotal = res.data.total || 0;
}

async function reloadAll() {
  loading.value = true;
  loadError.value = "";
  const results = await Promise.allSettled([loadSummary(), loadConfirmedDomains(), loadAudit()]);
  loading.value = false;
  const failed = results.filter(r => r.status === "rejected");
  if (failed.length === results.length) {
    loadError.value = "治理指标加载失败，请确认平台服务可用";
  }
  for (const f of failed) {
    console.warn("[system-map]", extractErrorDetail((f as PromiseRejectedResult).reason, "部分指标加载失败"));
  }
}

onMounted(reloadAll);
</script>

<style scoped>
.system-map {
  padding: 4px;
}

.mt12 {
  margin-top: 12px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.chain-card {
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-md);
}

.chain-head {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
}

.chain-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--re-text-primary);
}

.chain-sub {
  color: var(--re-text-secondary);
  font-size: 12.5px;
}

.chain-grid {
  display: grid;
  grid-template-columns: 1fr 22px 1fr 22px 1fr 22px 1fr 22px 1fr 22px 1fr;
  align-items: stretch;
  gap: 8px;
}

.step {
  padding: 16px 14px;
  text-align: center;
  cursor: pointer;
  background: linear-gradient(180deg, #ffffff, #f5f8ff);
  border: 1px solid #dfe8f8;
  border-radius: 12px;
  transition: all 0.2s ease;
}

.step:hover {
  border-color: #9dbcf5;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.12);
  transform: translateY(-2px);
}

.step.active {
  border-color: #2563eb;
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.16);
}

.step-no {
  width: 38px;
  height: 38px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border-radius: 50%;
}

.step-name {
  margin-top: 10px;
  color: var(--re-text-primary);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 1px;
}

.step-desc {
  min-height: 60px;
  margin-top: 8px;
  color: var(--re-text-secondary);
  font-size: 12.5px;
  line-height: 1.65;
}

.step-data {
  padding: 8px 6px;
  margin-top: 6px;
  text-align: left;
  background: #fff;
  border: 1px solid #eef2fa;
  border-radius: 8px;
}

.data-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 3px 2px;
  font-size: 12.5px;
}

.data-label {
  color: var(--re-text-secondary);
}

.data-value {
  color: #1d4ed8;
  font-weight: 700;
}

.step-btn {
  margin-top: 6px;
}

.chain-arrow {
  align-self: center;
  color: #93b4f5;
  font-size: 20px;
  font-weight: 700;
  text-align: center;
}

.slogan {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 18px 30px;
  margin-top: 16px;
  color: #fff;
  background: linear-gradient(120deg, #0b3b8f, #1d5fd4);
  border-radius: var(--re-radius-md);
}

.slogan-main {
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 5px;
}

.slogan-sub {
  margin-left: auto;
  font-size: 13.5px;
  opacity: 0.92;
}
</style>
