<template>
  <div class="metadata-snapshots">
    <RePageHeader
      title="元数据快照管理"
      subtitle="管理资产缓存与真实源库只读采集快照；live_source 采集建议限定 schema_filter。"
    >
      <template #icon><SnapshotIcon /></template>
      <template #actions>
        <el-button
          type="primary"
          :icon="CollectIcon"
          :loading="collecting"
          :disabled="!sourceCode"
          @click="doCollect"
        >
          采集元数据
        </el-button>
      </template>
    </RePageHeader>

    <section class="snapshot-stats">
      <ReStatCard label="快照数" :value="snapshots.length" tone="primary" helper="当前数据源">
        <template #icon><SnapshotIcon /></template>
      </ReStatCard>
      <ReStatCard label="表数量" :value="latestSnapshot?.table_count ?? '-'" tone="accent" helper="最近快照">
        <template #icon><TableIcon /></template>
      </ReStatCard>
      <ReStatCard label="字段数量" :value="latestSnapshot?.column_count ?? '-'" tone="info" helper="最近快照">
        <template #icon><FieldIcon /></template>
      </ReStatCard>
      <ReStatCard label="采集模式" :value="collectForm.mode" tone="warning" helper="当前选择">
        <template #icon><ModeIcon /></template>
      </ReStatCard>
    </section>

    <el-card shadow="never" class="snapshot-card">
      <ReToolbar title="采集参数" class="snapshot-toolbar">
        <div class="collect-panel">
          <el-select
            v-model="sourceCode"
            placeholder="选择数据源"
            filterable
            clearable
            class="source-select"
            @change="loadSnapshots"
          >
            <el-option
              v-for="item in sources"
              :key="item.source_code"
              :label="`${item.source_name_cn || item.source_code} (${item.source_code})`"
              :value="item.source_code"
            />
          </el-select>
          <el-input
            v-model="manualSourceCode"
            placeholder="或手动输入 source_code"
            clearable
            class="source-input"
            @keyup.enter="applyManualSource"
          />
          <el-button @click="applyManualSource">使用</el-button>
          <el-segmented v-model="collectForm.mode" :options="modeOptions" />
          <el-input v-model="collectForm.label" placeholder="快照标签，可选" clearable class="label-input" />
          <el-input
            v-model="schemaFilterText"
            :disabled="collectForm.mode !== 'live_source'"
            placeholder="schema_filter，逗号分隔，如 COMM,MEDREC"
            clearable
            class="schema-input"
          />
        </div>
      </ReToolbar>

      <el-alert v-if="collectForm.mode === 'live_source'" type="warning" :closable="false" show-icon class="hint-alert">
        <template #title>live_source 会真实连接源库，只读采集 schema/table/column；建议填写 schema_filter，避免全库扫描。</template>
      </el-alert>

      <el-alert v-if="lastResult" type="success" :closable="false" show-icon class="result-alert">
        <template #title>
          采集完成：快照 #{{ lastResult.snapshot_id }}，{{ lastResult.mode }}，{{ lastResult.table_count }} 表，{{ lastResult.column_count }} 字段
        </template>
      </el-alert>

      <el-table v-loading="loading" :data="snapshots" stripe class="medical-data-table">
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="label" label="标签" min-width="180" show-overflow-tooltip />
        <el-table-column prop="mode" label="模式" width="120">
          <template #default="{ row }">
            <el-tag :type="row.mode === 'live_source' ? 'warning' : 'info'" size="small">
              {{ row.mode || 'asset_cache' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Schema Filter" min-width="170" show-overflow-tooltip>
          <template #default="{ row }">{{ (row.schema_filter || []).join(', ') || '-' }}</template>
        </el-table-column>
        <el-table-column prop="snapshot_time" label="快照时间" width="180" />
        <el-table-column prop="table_count" label="表数量" width="100" align="center" />
        <el-table-column prop="column_count" label="字段数量" width="100" align="center" />
      </el-table>

      <ReEmptyState
        v-if="!loading && snapshots.length === 0"
        title="暂无快照"
        description="请选择数据源或先采集快照。"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { http } from "@/utils/http";
import { collectMetadata, getSourceSnapshots } from "@/api/metadata";
import CollectIcon from "~icons/ri/download-cloud-2-line";
import FieldIcon from "~icons/ri/list-check-2";
import ModeIcon from "~icons/ri/git-branch-line";
import SnapshotIcon from "~icons/ri/camera-lens-line";
import TableIcon from "~icons/ri/table-line";

interface DataSourceOption {
  source_code: string;
  source_name_cn?: string | null;
}

const modeOptions = [
  { label: "资产缓存", value: "asset_cache" },
  { label: "真实源库", value: "live_source" }
];

const sourceCode = ref("");
const manualSourceCode = ref("");
const schemaFilterText = ref("");
const sources = ref<DataSourceOption[]>([]);
const snapshots = ref<any[]>([]);
const loading = ref(false);
const collecting = ref(false);
const lastResult = ref<any>(null);
const collectForm = ref({ label: "", mode: "asset_cache" as "asset_cache" | "live_source" });
const latestSnapshot = computed(() => snapshots.value[0]);

function schemaFilter() {
  return schemaFilterText.value
    .split(/[，,\s]+/)
    .map(item => item.trim())
    .filter(Boolean);
}

async function loadSources() {
  try {
    const res = await http.request<any>("get", "/api/v1/sources");
    sources.value = res.data ?? [];
    if (!sourceCode.value && sources.value.length > 0) {
      sourceCode.value = sources.value[0].source_code;
      await loadSnapshots();
    }
  } catch {
    sources.value = [];
  }
}

function applyManualSource() {
  const value = manualSourceCode.value.trim();
  if (!value) return;
  sourceCode.value = value;
  loadSnapshots();
}

async function loadSnapshots() {
  lastResult.value = null;
  if (!sourceCode.value) {
    snapshots.value = [];
    return;
  }
  loading.value = true;
  try {
    const res = await getSourceSnapshots(sourceCode.value);
    snapshots.value = res.data ?? [];
  } catch (e: any) {
    snapshots.value = [];
    ElMessage.error(e?.response?.data?.detail || "获取快照失败");
  } finally {
    loading.value = false;
  }
}

async function doCollect() {
  if (!sourceCode.value) return;
  if (collectForm.value.mode === "live_source" && schemaFilter().length === 0) {
    ElMessage.warning("live_source 建议填写 schema_filter 后再采集");
    return;
  }
  collecting.value = true;
  try {
    const payload = {
      label: collectForm.value.label || undefined,
      mode: collectForm.value.mode,
      schema_filter: collectForm.value.mode === "live_source" ? schemaFilter() : undefined
    };
    const res = await collectMetadata(sourceCode.value, payload);
    lastResult.value = res.data;
    ElMessage.success(`采集完成：快照ID ${res.data?.snapshot_id}`);
    await loadSnapshots();
    lastResult.value = res.data;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "采集失败");
  } finally {
    collecting.value = false;
  }
}

onMounted(loadSources);
</script>

<style scoped lang="scss">
.metadata-snapshots {
  padding: 4px;
}

.snapshot-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.snapshot-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);

  :deep(.el-card__body) {
    display: grid;
    gap: 12px;
  }
}

.collect-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.source-select {
  width: 300px;
}

.source-input,
.label-input {
  width: 220px;
}

.schema-input {
  width: 300px;
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  font-size: 13px;
}

@media (max-width: 1180px) {
  .snapshot-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .snapshot-stats {
    grid-template-columns: 1fr;
  }

  .source-select,
  .source-input,
  .label-input,
  .schema-input {
    width: 100%;
  }
}
</style>
