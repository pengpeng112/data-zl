<template>
  <div class="dict-sync-diffs">
    <RePageHeader title="医学编码同步差异" subtitle="对诊断、手术等医学编码做来源同步比对，生成差异并支持人工处理。">
      <template #icon><CodeIcon /></template>
      <template #actions>
        <el-button v-perms="'dict.medical.execute'" type="primary" :icon="SyncIcon" :loading="syncLoading" @click="doSync">执行同步</el-button>
      </template>
    </RePageHeader>

    <section class="diff-stats">
      <ReStatCard label="当前页差异" :value="items.length" tone="primary" helper="按筛选条件展示">
        <template #icon><CodeIcon /></template>
      </ReStatCard>
      <ReStatCard label="未处理" :value="openCount" tone="warning" helper="当前页统计">
        <template #icon><OpenIcon /></template>
      </ReStatCard>
      <ReStatCard label="已解决" :value="resolvedCount" tone="accent" helper="当前页统计">
        <template #icon><CheckIcon /></template>
      </ReStatCard>
      <ReStatCard label="忽略" :value="ignoredCount" tone="info" helper="当前页统计">
        <template #icon><IgnoreIcon /></template>
      </ReStatCard>
    </section>

    <el-card shadow="never" class="diff-card">
      <ReToolbar title="同步参数" class="diff-toolbar">
        <div class="action-bar">
          <!-- 146 E8（R5）：来源改动态加载（数据连接接口驱动） -->
          <el-select
            v-model="syncForm.source_system"
            filterable
            placeholder="选择来源数据连接"
            :loading="sourceOptionsLoading"
            class="control source"
          >
            <el-option
              v-for="item in sourceOptions"
              :key="item.source_code"
              :label="item.source_name_cn ? `${item.source_name_cn}（${item.source_code}）` : item.source_code"
              :value="item.source_code"
            />
          </el-select>
          <el-select v-model="syncForm.category_code" placeholder="编码类别" clearable class="control category">
            <el-option label="全部" value="" />
            <el-option label="诊断" value="diagnosis" />
            <el-option label="手术" value="operation" />
          </el-select>
          <el-input-number v-model="syncForm.max_rows" :min="1" :max="50000" :step="100" class="rows" />
        </div>
      </ReToolbar>

      <ReToolbar title="差异筛选" class="diff-toolbar" dense>
        <div class="filter-bar">
          <el-select v-model="statusFilter" placeholder="处理状态" clearable class="control status" @change="doSearch">
            <el-option label="未处理" value="open" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="ignored" />
          </el-select>
          <el-input v-model="keyword" placeholder="编码或名称" clearable class="control keyword" @keyup.enter="doSearch" />
        </div>
        <template #actions>
          <el-button type="primary" :icon="SearchIcon" @click="doSearch">查询</el-button>
        </template>
      </ReToolbar>

      <el-alert v-if="lastResult" type="success" :closable="false" class="result-alert">
        <template #title>
          {{ lastResult.status }}：扫描 {{ lastResult.scanned ?? 0 }}，生成差异 {{ lastResult.diffs_created ?? 0 }}
        </template>
      </el-alert>

      <!-- 146 E8（R5）：全量 summary（服务端 total，按状态统计；-1 表示未知） -->
      <el-alert
        v-if="totalsLoaded"
        type="info"
        :closable="false"
        class="result-alert"
        :title="`全量统计：未处理 ${formatTotal(totals.open)} · 已解决 ${formatTotal(totals.resolved)} · 已忽略 ${formatTotal(totals.ignored)}（服务端 total，不受当前页筛选影响）`"
      />

      <div class="batch-bar">
        <span class="batch-hint">已选 {{ selectedDiffs.length }} 条</span>
        <el-button size="small" type="success" :disabled="!selectedDiffs.length" :loading="batchLoading" @click="batchSetStatus('resolved')">
          批量解决
        </el-button>
        <el-button size="small" type="info" :disabled="!selectedDiffs.length" :loading="batchLoading" @click="batchSetStatus('ignored')">
          批量忽略
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        stripe
        class="medical-data-table"
        row-key="id"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="48" reserve-selection />
        <el-table-column prop="category_code" label="类别" width="110">
          <template #default="{ row }">{{ categoryLabel(row.category_code) }}</template>
        </el-table-column>
        <el-table-column prop="target_system" label="目标系统" width="110" />
        <el-table-column prop="diff_type" label="差异类型" width="140">
          <template #default="{ row }">
            <el-tag :type="diffTypeTag(row.diff_type)" size="small">{{ diffTypeLabel(row.diff_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code_set_code" label="编码集" min-width="170" show-overflow-tooltip />
        <el-table-column prop="item_code" label="编码" width="150" show-overflow-tooltip />
        <el-table-column prop="item_name" label="名称" min-width="170" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重度" width="90">
          <template #default="{ row }">
            <el-tag :type="syncSeverityTag(row.severity)" size="small">{{ syncSeverityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="syncDiffStatusTag(row.status)" size="small">{{ syncDiffStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="row.status !== 'resolved'" link type="success" :loading="updatingId === row.id" @click="updateStatus(row, 'resolved')">解决</el-button>
            <el-button v-if="row.status !== 'ignored'" link type="info" :loading="updatingId === row.id" @click="updateStatus(row, 'ignored')">忽略</el-button>
            <el-button v-if="row.status !== 'open'" link type="warning" :loading="updatingId === row.id" @click="updateStatus(row, 'open')">重开</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        class="pager"
        @change="loadData"
      />
    </el-card>

    <!-- 146 E8（R5）：差异详情抽屉 -->
    <el-drawer v-model="detailVisible" title="编码同步差异详情" size="420px">
      <template v-if="detailRow">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="类别">{{ categoryLabel(detailRow.category_code) }}</el-descriptions-item>
          <el-descriptions-item label="编码集">{{ detailRow.code_set_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="编码">{{ detailRow.item_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detailRow.item_name || "-" }}</el-descriptions-item>
          <el-descriptions-item label="差异类型">{{ diffTypeLabel(detailRow.diff_type) }}</el-descriptions-item>
          <el-descriptions-item label="严重度">{{ syncSeverityLabel(detailRow.severity) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ syncDiffStatusLabel(detailRow.status) }}</el-descriptions-item>
          <el-descriptions-item label="目标系统">{{ detailRow.target_system || "-" }}</el-descriptions-item>
          <el-descriptions-item label="来源系统">{{ detailRow.source_system || "-" }}</el-descriptions-item>
          <el-descriptions-item label="处理意见">{{ detailRow.note || detailRow.review_note || "—" }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ detailRow.handled_by || "—" }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getMedicalSyncDiffs, runMedicalSync, updateMedicalSyncDiff } from "@/api/dict";
import { listSources } from "@/api/asset";
import { usePagedList } from "@/composables/usePagedList";
import {
  loadSyncDiffTotals,
  runSerialBatch,
  syncSeverityLabel,
  syncSeverityTag,
  syncDiffStatusLabel,
  syncDiffStatusTag,
  type SyncDiffTotals
} from "@/composables/useSyncDiffPanel";
import { extractErrorDetail } from "@/utils/errorMessage";
import CheckIcon from "~icons/ri/checkbox-circle-line";
import CodeIcon from "~icons/ri/code-box-line";
import IgnoreIcon from "~icons/ri/forbid-2-line";
import OpenIcon from "~icons/ri/error-warning-line";
import SearchIcon from "~icons/ri/search-line";
import SyncIcon from "~icons/ri/git-branch-line";

const syncLoading = ref(false);
const updatingId = ref<number | null>(null);
const statusFilter = ref("");
const keyword = ref("");
const lastResult = ref<any>(null);
const detailVisible = ref(false);
const detailRow = ref<any>(null);
const selectedDiffs = ref<any[]>([]);
const batchLoading = ref(false);
// 146 E8（R5）：全量 summary 状态（-1 = 该状态统计未知）
const totals = ref<SyncDiffTotals>({ open: -1, resolved: -1, ignored: -1 });
const totalsLoaded = ref(false);

function formatTotal(value: number | undefined) {
  return value == null || value < 0 ? "未知" : String(value);
}

async function loadTotals() {
  totals.value = await loadSyncDiffTotals(async params => {
    const res = await getMedicalSyncDiffs(params);
    return { total: res.data.total ?? 0 };
  });
  totalsLoaded.value = true;
}

// 146 E8（R5）：来源选项动态加载（与 identity 版一致，走数据连接接口）
const sourceOptions = ref<Array<{ source_code: string; source_name_cn?: string | null }>>([]);
const sourceOptionsLoading = ref(false);
async function loadSourceOptions() {
  sourceOptionsLoading.value = true;
  try {
    const res = await listSources();
    sourceOptions.value = (res.data || []).map(item => ({
      source_code: item.source_code,
      source_name_cn: item.source_name_cn
    }));
    if (sourceOptions.value.length && !sourceOptions.value.some(item => item.source_code === syncForm.source_system)) {
      syncForm.source_system = sourceOptions.value[0].source_code;
    }
  } catch {
    sourceOptions.value = [];
  } finally {
    sourceOptionsLoading.value = false;
  }
}

const syncForm = reactive({ source_system: "his_ready_10_10_10_15", target_system: "asset", category_code: "", max_rows: 5000 });
// F6：分页五件套收敛到 usePagedList（含请求序号守卫与 catch 提示，E8/E7 语义）。
const { items, total, page, pageSize, loading, loadData, doSearch } = usePagedList<
  any,
  { page: number; page_size: number; status?: string; keyword?: string }
>({
  pageSize: 20,
  errorText: "字典同步差异加载失败",
  extraParams: () => ({
    status: statusFilter.value || undefined,
    keyword: keyword.value || undefined
  }),
  fetcher: async params => {
    const res = await getMedicalSyncDiffs(params);
    return { items: res.data.items ?? [], total: res.data.total ?? 0 };
  }
});
const openCount = computed(() => items.value.filter(item => item.status === "open").length);
const resolvedCount = computed(() => items.value.filter(item => item.status === "resolved").length);
const ignoredCount = computed(() => items.value.filter(item => item.status === "ignored").length);
function diffTypeTag(diffType: string): "danger" | "warning" | "info" { return diffType === "missing_target" ? "danger" : diffType === "name_mismatch" ? "warning" : "info"; }
function categoryLabel(value: string) { return ({ diagnosis: "诊断", operation: "手术" } as Record<string, string>)[value] || value || "-"; }
function diffTypeLabel(value: string) { return ({ missing_target: "目标缺失", name_mismatch: "名称不一致", extra_target: "目标多余" } as Record<string, string>)[value] || value || "-"; }

async function doSync() {
  syncLoading.value = true;
  try {
    const payload = { ...syncForm, category_code: syncForm.category_code || undefined };
    const res = await runMedicalSync(payload);
    lastResult.value = res.data;
    ElMessage.success("医学编码同步完成");
    loadData();
    void loadTotals();
  } catch (error) {
    // 161 P2-2（round-2 P11）：动作 catch 与列表加载对称，走 extractErrorDetail。
    ElMessage.error(extractErrorDetail(error, "医学编码同步失败"));
  } finally {
    syncLoading.value = false;
  }
}

function openDetail(row: any) {
  detailRow.value = row;
  detailVisible.value = true;
}

function onSelectionChange(rows: any[]) {
  selectedDiffs.value = rows;
}

/** 146 E8（R5）：处理意见（可选输入，取消即放弃操作）。 */
async function promptNote(title: string): Promise<string | null> {
  try {
    const { value } = await ElMessageBox.prompt("处理意见（可留空）", title, {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      inputPlaceholder: "如：与临床核对后确认映射"
    });
    return value || "";
  } catch {
    return null;
  }
}

async function updateStatus(row: any, status: "open" | "resolved" | "ignored") {
  const note = status === "open" ? "" : await promptNote(status === "resolved" ? "解决差异" : "忽略差异");
  if (note === null) return;
  updatingId.value = row.id;
  try {
    await updateMedicalSyncDiff(row.id, { status, handled_by: "frontend", note: note || "manual status update" });
    ElMessage.success("状态已更新");
    loadData();
    void loadTotals();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "状态更新失败"));
  } finally {
    updatingId.value = null;
  }
}

/** 146 E8（R5）：批量处理——后端无批量接口，前端明确串行并汇总部分失败。 */
async function batchSetStatus(status: "resolved" | "ignored") {
  const targets = selectedDiffs.value.filter(row => row.status !== status).slice(0, 50);
  if (!targets.length) {
    ElMessage.warning("请勾选需要处理且状态不同的差异（最多 50）");
    return;
  }
  const note = await promptNote(status === "resolved" ? "批量解决" : "批量忽略");
  if (note === null) return;
  batchLoading.value = true;
  try {
    const result = await runSerialBatch(targets, async row => {
      await updateMedicalSyncDiff(row.id, { status, handled_by: "frontend", note: note || "batch status update" });
    });
    if (result.failed) {
      ElMessage.warning(`批量${status === "resolved" ? "解决" : "忽略"}：成功 ${result.done} 条，失败 ${result.failed} 条（${result.lastError}）`);
    } else {
      ElMessage.success(`批量${status === "resolved" ? "解决" : "忽略"}完成：共 ${result.done} 条`);
    }
    await loadData();
    void loadTotals();
  } finally {
    batchLoading.value = false;
  }
}

onMounted(() => {
  void loadSourceOptions();
  void loadTotals();
  loadData();
});
</script>

<style scoped lang="scss">
.dict-sync-diffs {
  padding: 4px;
}

.diff-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.diff-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);

  :deep(.el-card__body) {
    display: grid;
    gap: 12px;
  }
}

.batch-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.batch-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-right: 4px;
}

.action-bar,
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.control.source {
  width: 260px;
}

.control.category,
.control.status {
  width: 150px;
}

.control.keyword {
  width: 220px;
}

.rows {
  width: 150px;
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  font-size: 13px;
}

.pager {
  justify-content: flex-end;
  margin-top: 4px;
}

@media (max-width: 1180px) {
  .diff-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .diff-stats {
    grid-template-columns: 1fr;
  }

  .control.source,
  .control.category,
  .control.status,
  .control.keyword,
  .rows {
    width: 100%;
  }
}
</style>

