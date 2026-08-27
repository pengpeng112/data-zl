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
          <el-input v-model="syncForm.source_system" placeholder="source_code" clearable class="control source" />
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

      <el-table v-loading="loading" :data="items" stripe class="medical-data-table">
        <el-table-column prop="category_code" label="类别" width="130">
          <template #default="{ row }">{{ categoryLabel(row.category_code) }}</template>
        </el-table-column>
        <el-table-column prop="target_system" label="目标系统" width="110" />
        <el-table-column prop="diff_type" label="差异类型" width="150">
          <template #default="{ row }">
            <el-tag :type="diffTypeTag(row.diff_type)" size="small">{{ diffTypeLabel(row.diff_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code_set_code" label="编码集" min-width="190" show-overflow-tooltip />
        <el-table-column prop="item_code" label="编码" width="160" show-overflow-tooltip />
        <el-table-column prop="item_name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重度" width="110">
          <template #default="{ row }">
            <el-tag :type="severityTag(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="syncStatusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
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
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { getMedicalSyncDiffs, runMedicalSync, updateMedicalSyncDiff } from "@/api/dict";
import { usePagedList } from "@/composables/usePagedList";
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
function severityTag(severity: string): "danger" | "warning" | "info" { return severity === "high" ? "danger" : severity === "medium" ? "warning" : "info"; }
function syncStatusTag(status: string): "success" | "warning" | "info" { return status === "resolved" ? "success" : status === "ignored" ? "info" : "warning"; }
function categoryLabel(value: string) { return ({ diagnosis: "诊断", operation: "手术" } as Record<string, string>)[value] || value || "-"; }
function diffTypeLabel(value: string) { return ({ missing_target: "目标缺失", name_mismatch: "名称不一致", extra_target: "目标多余" } as Record<string, string>)[value] || value || "-"; }
function severityLabel(value: string) { return ({ high: "高", medium: "中", low: "低" } as Record<string, string>)[value] || value || "-"; }
function statusLabel(value: string) { return ({ open: "未处理", resolved: "已解决", ignored: "已忽略" } as Record<string, string>)[value] || value || "-"; }

async function doSync() {
  syncLoading.value = true;
  try {
    const payload = { ...syncForm, category_code: syncForm.category_code || undefined };
    const res = await runMedicalSync(payload);
    lastResult.value = res.data;
    ElMessage.success("医学编码同步完成");
    loadData();
  } catch {
    ElMessage.error("医学编码同步失败");
  } finally {
    syncLoading.value = false;
  }
}
async function updateStatus(row: any, status: "open" | "resolved" | "ignored") {
  updatingId.value = row.id;
  try {
    await updateMedicalSyncDiff(row.id, { status, handled_by: "frontend", note: "manual status update" });
    ElMessage.success("状态已更新");
    loadData();
  } catch {
    ElMessage.error("状态更新失败");
  } finally {
    updatingId.value = null;
  }
}

onMounted(loadData);
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

