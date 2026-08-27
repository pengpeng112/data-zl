<template>
  <div class="relation-rates-page">
    <RePageHeader title="关系命中率" subtitle="正式关系的抽样命中率。检查、检验按门诊/住院单独列出。">
      <template #icon><RateIcon /></template>
    </RePageHeader>

    <section class="scene-grid">
      <button
        v-for="card in sceneCards"
        :key="card.scene"
        type="button"
        class="scene-card"
        :class="{ active: filters.scene === card.scene }"
        @click="toggleScene(card.scene)"
      >
        <div class="scene-card-head">
          <strong>{{ card.label }}</strong>
          <el-tag size="small" :type="card.tone === 'danger' ? 'danger' : card.tone === 'warning' ? 'warning' : 'success'">
            {{ card.rateText }}
          </el-tag>
        </div>
        <p>{{ card.pair }}</p>
        <small>{{ card.hint }}</small>
      </button>
    </section>

    <el-card shadow="never">
      <ReToolbar title="正式关系">
        <div class="filters">
          <el-select v-model="filters.system_code" clearable placeholder="系统" class="sys" @change="reload">
            <el-option label="ODS / 数据中心" value="DATA_CENTER" />
            <el-option label="HISUSER 源端" value="HIS_SOURCE" />
            <el-option label="嘉和 EMR" value="JHEMR_VASTBASE" />
          </el-select>
          <el-select v-model="filters.scene" clearable placeholder="检查/检验场景" class="scene" @change="reload">
            <el-option v-for="opt in sceneOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
          <el-input v-model="filters.keyword" clearable placeholder="表名" class="keyword" @keyup.enter="reload" @clear="reload" />
          <el-select v-model="rateRange" clearable placeholder="命中率区间" class="rate-range" @change="reload">
            <el-option label="低（<50%）" value="low" />
            <el-option label="中（50%-80%）" value="mid" />
            <el-option label="高（≥80%）" value="high" />
          </el-select>
          <el-button type="primary" :loading="loading" @click="reload">查询</el-button>
        </div>
      </ReToolbar>

      <div class="metric-strip">
        <span>关系 <b>{{ total }}</b></span>
        <span>有命中率 <b>{{ stats.with_rate }}</b></span>
        <span>平均命中 <b>{{ formatHitRate(stats.avg_hit_rate) }}</b></span>
        <span class="metric-warn" title="当前页命中率<50%的关系数">低命中 <b>{{ lowRateCount }}</b></span>
        <small v-if="rateRange" class="metric-hint">区间筛选在服务端完成，统计与分页同口径</small>
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        stripe
        size="small"
        row-class-name="rate-row"
        @row-click="openRelation"
      >
        <el-table-column label="系统" width="90">
          <template #default="{ row }">{{ systemShortLabel(row.from_system_code) }}</template>
        </el-table-column>
        <el-table-column label="从" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.from_table }}</div>
            <small class="tech">{{ row.from_columns || "-" }}</small>
          </template>
        </el-table-column>
        <el-table-column label="到" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.to_table }}</div>
            <small class="tech">{{ row.to_columns || "-" }}</small>
          </template>
        </el-table-column>
        <el-table-column label="场景" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.scene_label" size="small" effect="plain">{{ row.scene_label }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="命中率" width="180" sortable :sort-method="sortByHitRate">
          <template #default="{ row }">
            <div class="rate-cell">
              <el-progress
                :percentage="hitRatePercent(row.hit_rate)"
                :stroke-width="10"
                :status="progressStatus(row.tone)"
              />
              <b>{{ formatHitRate(row.hit_rate) }}</b>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="样本/命中/未命中" width="170" sortable :sort-method="sortBySample">
          <template #default="{ row }">
            {{ row.sample_size ?? "-" }} / {{ row.matched ?? "-" }} / {{ row.missed ?? "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="validation_status" label="状态" width="130" />
      </el-table>

      <div class="pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          v-model:page-size="pageSize"
          :page-sizes="pageSizes"
          v-model:current-page="page"
          @current-change="loadData"
          @size-change="changeSize"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { usePagedList } from "@/composables/usePagedList";
import { useRouter } from "vue-router";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import {
  getRelationHitRates,
  type RelationHitRateItem
} from "@/api/asset";
import {
  HIGHLIGHT_SCENES,
  SCENE_OPTIONS,
  formatHitRate,
  hitRatePercent,
  pickHighlight,
  systemShortLabel
} from "./relationHitRates";
import RateIcon from "~icons/ri/pie-chart-2-line";

const router = useRouter();
const pageSizes = [30, 50, 100];
const sceneOptions = SCENE_OPTIONS;
const rateRange = ref(""); // 命中率区间筛选：空=全部 low<50% mid 50-80% high>=80%（146 E10 服务端过滤）
// F6：分页五件套收敛到 usePagedList（含请求序号守卫与 catch 提示，E8/E7 语义）。
const stats = reactive<{ with_rate: number; avg_hit_rate: number | null }>({
  with_rate: 0,
  avg_hit_rate: null
});
const filters = reactive({
  system_code: "",
  scene: "",
  keyword: ""
});
const { items, total, page, pageSize, loading, loadData, doSearch } = usePagedList<
  RelationHitRateItem,
  {
    page: number;
    page_size: number;
    system_code?: string;
    scene?: string;
    keyword?: string;
    hit_rate_min?: number;
    hit_rate_max?: number;
  }
>({
  pageSize: 30,
  errorText: "关系命中率加载失败",
  extraParams: () => ({
    system_code: filters.system_code || undefined,
    scene: filters.scene || undefined,
    keyword: filters.keyword || undefined,
    hit_rate_min:
      rateRange.value === "mid" || rateRange.value === "high"
        ? rateRange.value === "high"
          ? 0.8
          : 0.5
        : undefined,
    hit_rate_max:
      rateRange.value === "mid" || rateRange.value === "low"
        ? rateRange.value === "low"
          ? 0.5
          : 0.8
        : undefined
  }),
  fetcher: async params => {
    const res = await getRelationHitRates(params);
    stats.with_rate = res.data.with_rate ?? 0;
    stats.avg_hit_rate = res.data.avg_hit_rate ?? null;
    if (!filters.scene) buildSceneCards(res.data.highlights || []);
    return { items: res.data.items || [], total: res.data.total || 0 };
  }
});

const sceneCards = ref(
  HIGHLIGHT_SCENES.map(scene => ({
    scene,
    label: SCENE_OPTIONS.find(item => item.value === scene)?.label || scene,
    pair: "暂无拆分关系",
    hint: "住院用 PATIENT_ID+VISIT_ID；门诊用收据号 RCPT_NO",
    rateText: "-",
    tone: "info"
  }))
);

function progressStatus(tone?: string) {
  if (tone === "danger") return "exception";
  if (tone === "success") return "success";
  if (tone === "warning") return "warning";
  return undefined;
}

// 数值排序（null 排最后）
function sortByHitRate(a: RelationHitRateItem, b: RelationHitRateItem): number {
  return (a.hit_rate ?? -1) - (b.hit_rate ?? -1);
}
function sortBySample(a: RelationHitRateItem, b: RelationHitRateItem): number {
  return (a.sample_size ?? -1) - (b.sample_size ?? -1);
}

function toggleScene(scene: string) {
  filters.scene = filters.scene === scene ? "" : scene;
  reload();
}

function buildSceneCards(highlights: RelationHitRateItem[]) {
  sceneCards.value = HIGHLIGHT_SCENES.map(scene => {
    const row = pickHighlight(highlights, scene);
    return {
      scene,
      label: SCENE_OPTIONS.find(item => item.value === scene)?.label || scene,
      pair: row ? `${row.from_table} → ${row.to_table}` : "暂无拆分关系",
      hint: row
        ? `${systemShortLabel(row.from_system_code)} · 样本 ${row.sample_size ?? "-"} · 未命中 ${row.missed ?? "-"}`
        : "住院用 PATIENT_ID+VISIT_ID；门诊用收据号 RCPT_NO",
      rateText: formatHitRate(row?.hit_rate),
      tone: row?.tone || "info"
    };
  });
}

// 命中率区间筛选（前端过滤当前页数据；全量筛选需后端支持）
// 146 E10：区间过滤已由服务端 hit_rate_min/max 在分页/汇总前完成。

// 低命中率（<50%）关系数，用于指标条异常提示
// 低命中率（<50%）关系数（当前页口径；服务端区间过滤后该值反映筛选结果）
const lowRateCount = computed(() =>
  items.value.filter(r => r.hit_rate !== null && r.hit_rate !== undefined && r.hit_rate < 0.5).length
);

// F6：reload/翻页/改页大小全部收敛到 usePagedList。
function reload() {
  doSearch();
}

function changeSize(size: number) {
  pageSize.value = size;
  loadData(1);
}

function openRelation(row: RelationHitRateItem) {
  if (row.from_table && row.to_table) {
    // 146 E1：联动图谱路径模式（/asset/relations 兼容 redirect 会原样带参）
    router.push({
      path: "/asset/graph",
      query: { view_mode: "path", from: row.from_table, to: row.to_table }
    });
  }
}

onMounted(async () => {
  await loadData();
});
</script>

<style scoped>
.scene-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.scene-card {
  text-align: left;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  background: var(--el-bg-color);
  padding: 12px 14px;
  cursor: pointer;
}
.scene-card.active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-7);
}
.scene-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.scene-card p {
  margin: 0 0 6px;
  font-size: 13px;
  word-break: break-all;
}
.scene-card small,
.tech {
  color: var(--el-text-color-secondary);
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.sys,
.scene {
  width: 160px;
}
.keyword {
  width: 220px;
}
.rate-range {
  width: 150px;
}
.metric-strip {
  display: flex;
  gap: 20px;
  margin: 8px 0 12px;
  color: var(--el-text-color-regular);
  align-items: center;
}
.metric-warn b {
  color: var(--el-color-danger);
}
.metric-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
/* 行可点击提示 */
:deep(.rate-row) {
  cursor: pointer;
}
:deep(.rate-row:hover) td {
  background-color: var(--el-color-primary-light-9) !important;
}
.rate-cell {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
@media (max-width: 1100px) {
  .scene-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .scene-grid {
    grid-template-columns: 1fr;
  }
}
</style>
