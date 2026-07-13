<template>
  <div class="identity-sync-diffs">
    <RePageHeader title="人员同步差异" subtitle="采集 HIS/HRP 等来源人员与科室数据，生成差异并进行人工处理；默认 HIS dry-run 不写入。">
      <template #icon><DiffIcon /></template>
      <template #actions>
        <el-button :loading="hisSyncLoading" type="success" :icon="HisIcon" @click="doHisSync">HIS 预同步</el-button>
        <el-button :loading="collectLoading" :icon="CollectIcon" @click="doCollect">采集来源</el-button>
        <el-button type="primary" :loading="syncLoading" :icon="DiffIcon" @click="doSync">生成差异</el-button>
      </template>
    </RePageHeader>

    <section class="diff-stats">
      <ReStatCard label="当前页差异" :value="items.length" tone="primary" helper="按筛选条件展示">
        <template #icon><DiffIcon /></template>
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
          <el-input v-model="collectForm.source_code" placeholder="source_code" clearable class="control source" />
          <el-select v-model="collectForm.entity_type" class="control entity">
            <el-option label="科室" value="identity_department" />
            <el-option label="人员" value="identity_person" />
            <el-option label="全部" value="identity_all" />
          </el-select>
          <el-input-number v-model="collectForm.max_rows" :min="1" :max="50000" :step="100" class="rows" />
          <el-checkbox v-model="hisSyncForm.dry_run">HIS dry-run</el-checkbox>
        </div>
      </ReToolbar>

      <ReToolbar title="差异筛选" class="diff-toolbar" dense>
        <el-select v-model="params.status" placeholder="处理状态" clearable class="control status" @change="doSearch">
          <el-option label="未处理" value="open" />
          <el-option label="已解决" value="resolved" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
      </ReToolbar>

      <el-alert v-if="lastResult" :type="lastResult.dry_run ? 'warning' : 'success'" :closable="false" class="result-alert">
        <template #title>{{ resultTitle }}</template>
      </el-alert>

      <el-table v-loading="loading" :data="items" stripe class="medical-data-table">
        <el-table-column prop="diff_type" label="差异类型" width="160">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.diff_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_system" label="来源系统" width="140" />
        <el-table-column prop="target_system" label="目标系统" width="120" />
        <el-table-column prop="entity_type" label="实体类型" width="150">
          <template #default="{ row }">{{ entityTypeLabel(row.entity_type) }}</template>
        </el-table-column>
        <el-table-column prop="entity_code" label="实体编码" min-width="150" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重度" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="severityTag(row.severity)">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
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
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
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
import { collectSources, getSyncDiffs, runIdentitySync, syncHisIdentity, updateIdentitySyncDiff } from "@/api/identity";
import CheckIcon from "~icons/ri/checkbox-circle-line";
import CollectIcon from "~icons/ri/download-cloud-2-line";
import DiffIcon from "~icons/ri/git-branch-line";
import HisIcon from "~icons/ri/database-2-line";
import IgnoreIcon from "~icons/ri/forbid-2-line";
import OpenIcon from "~icons/ri/error-warning-line";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const collectLoading = ref(false);
const syncLoading = ref(false);
const hisSyncLoading = ref(false);
const updatingId = ref<number | null>(null);
const lastResult = ref<any>(null);

const params = reactive({ status: "", page: 1, page_size: 20 });
const collectForm = reactive({ source_code: "his_ready_10_10_10_15", source_system: "HIS", entity_type: "identity_all", max_rows: 5000 });
const hisSyncForm = reactive({ dry_run: true });
const openCount = computed(() => items.value.filter(item => item.status === "open").length);
const resolvedCount = computed(() => items.value.filter(item => item.status === "resolved").length);
const ignoredCount = computed(() => items.value.filter(item => item.status === "ignored").length);

const resultTitle = computed(() => {
  if (Array.isArray(lastResult.value?.runs)) {
    const scanned = lastResult.value.runs.reduce((sum: number, item: any) => sum + (item.scanned ?? 0), 0);
    const diffs = lastResult.value.runs.reduce((sum: number, item: any) => sum + (item.diffs_created ?? 0), 0);
    return `采集完成：扫描 ${scanned}，生成差异 ${diffs}`;
  }
  if (lastResult.value?.prepared) {
    const prepared = lastResult.value.prepared;
    const bridge = lastResult.value.bridge || {};
    return `${lastResult.value.mode}: 人员 ${prepared.persons ?? 0}，科室 ${prepared.departments ?? 0}，桥接 ${bridge.bridge_hits ?? 0}/${bridge.sys_employee_rows ?? 0}`;
  }
  return `${lastResult.value.status}: 扫描 ${lastResult.value.scanned ?? 0}，变更 ${lastResult.value.diffs_created ?? lastResult.value.inserted ?? 0}`;
});

function severityTag(severity: string): "danger" | "warning" | "info" {
  return severity === "high" ? "danger" : severity === "medium" ? "warning" : "info";
}
function statusTag(status: string): "success" | "warning" | "info" {
  return status === "resolved" ? "success" : status === "ignored" ? "info" : "warning";
}
function severityLabel(value: string) {
  const map: Record<string, string> = { high: "高", medium: "中", low: "低" };
  return map[value] || value || "-";
}
function statusLabel(value: string) {
  const map: Record<string, string> = { open: "未处理", resolved: "已解决", ignored: "已忽略" };
  return map[value] || value || "-";
}
function entityTypeLabel(value: string) {
  const map: Record<string, string> = { identity_department: "科室", identity_person: "人员", identity_all: "全部" };
  return map[value] || value || "-";
}

async function loadData() {
  loading.value = true;
  try {
    const res = await getSyncDiffs({ status: params.status || undefined, page: params.page, page_size: params.page_size });
    items.value = res.data.items ?? [];
    total.value = res.data.total ?? 0;
  } finally {
    loading.value = false;
  }
}
function doSearch() {
  params.page = 1;
  loadData();
}
async function doCollect() {
  collectLoading.value = true;
  try {
    const res = await collectSources({ ...collectForm });
    lastResult.value = res.data;
    ElMessage.success("来源采集完成");
    loadData();
  } catch {
    ElMessage.error("来源采集失败");
  } finally {
    collectLoading.value = false;
  }
}
async function doSync() {
  syncLoading.value = true;
  try {
    const entityTypes = collectForm.entity_type === "identity_all" ? ["identity_department", "identity_person"] : [collectForm.entity_type];
    const runs = [];
    for (const entityType of entityTypes) {
      const res = await runIdentitySync({ source_system: collectForm.source_system, target_system: "asset", entity_type: entityType });
      runs.push(res.data);
    }
    lastResult.value = runs.length === 1 ? runs[0] : { runs };
    ElMessage.success("差异生成完成");
    loadData();
  } catch {
    ElMessage.error("差异生成失败");
  } finally {
    syncLoading.value = false;
  }
}
async function doHisSync() {
  hisSyncLoading.value = true;
  try {
    const res = await syncHisIdentity({ dry_run: hisSyncForm.dry_run, max_rows: collectForm.max_rows, operator: "frontend" });
    lastResult.value = res.data;
    ElMessage.success(hisSyncForm.dry_run ? "HIS dry-run 完成" : "HIS 同步完成");
    if (!hisSyncForm.dry_run) loadData();
  } catch {
    ElMessage.error("HIS 同步失败");
  } finally {
    hisSyncLoading.value = false;
  }
}
async function updateStatus(row: any, status: "open" | "resolved" | "ignored") {
  updatingId.value = row.id;
  try {
    await updateIdentitySyncDiff(row.id, { status, handled_by: "frontend", note: "manual status update" });
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
.identity-sync-diffs {
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

.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.control.source {
  width: 260px;
}

.control.entity {
  width: 180px;
}

.control.status {
  width: 160px;
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
  .control.entity,
  .control.status,
  .rows {
    width: 100%;
  }
}
</style>

