<template>
  <div class="metadata-diff">
    <RePageHeader title="快照对比" subtitle="选择同一数据连接的两个元数据快照，只读预览字段级差异；需要留痕时再显式生成变更事件。" />

    <el-card shadow="never" class="diff-card">
      <template #header>
        <span>快照对比</span>
      </template>

      <div class="diff-form">
        <el-select
          v-model="sourceCode"
          placeholder="先选择数据连接"
          clearable
          filterable
          class="source-select"
          :loading="sourcesLoading"
          @change="onSourceChange"
        >
          <el-option
            v-for="source in sources"
            :key="source.source_code"
            :label="`${source.source_name_cn || source.source_code} (${source.source_code})`"
            :value="source.source_code"
          />
        </el-select>
        <el-select
          v-model="fromId"
          placeholder="源快照"
          clearable
          class="snapshot-select"
          filterable
          :disabled="!sourceCode"
          @change="onSnapshotSelectionChange"
        >
          <el-option
            v-for="sn in snapshots"
            :key="sn.id"
            :label="`#${sn.id} ${sn.label || ''} (${sn.snapshot_time || ''})`"
            :value="sn.id"
          />
        </el-select>
        <span class="diff-arrow">→</span>
        <el-select
          v-model="toId"
          placeholder="目标快照"
          clearable
          class="snapshot-select"
          filterable
          :disabled="!sourceCode"
          @change="onSnapshotSelectionChange"
        >
          <el-option
            v-for="sn in snapshots"
            :key="sn.id"
            :label="`#${sn.id} ${sn.label || ''} (${sn.snapshot_time || ''})`"
            :value="sn.id"
          />
        </el-select>
        <el-button :disabled="!fromId || !toId" @click="swapSnapshots">交换</el-button>
        <el-button
          type="primary"
          :loading="diffRunning"
          :disabled="Boolean(orderError)"
          class="run-button"
          @click="runPreview"
        >
          执行对比
        </el-button>
        <el-button
          v-perms="'metadata.snapshot.collect'"
          :disabled="!fromId || !toId || Boolean(orderError)"
          :loading="generating"
          @click="generateEvents"
        >
          生成变更事件
        </el-button>
      </div>
      <el-alert v-if="sourcesError" type="error" :closable="false" :title="sourcesError" show-icon class="mt-12">
        <template #default><el-button size="small" @click="loadSources">重试来源</el-button></template>
      </el-alert>
      <el-alert v-else-if="snapshotsError" type="error" :closable="false" :title="snapshotsError" show-icon class="mt-12">
        <template #default><el-button size="small" @click="loadSnapshots">重试快照</el-button></template>
      </el-alert>
      <el-alert v-else-if="orderError && fromId && toId" type="warning" :closable="false" :title="orderError" class="mt-12" />
    </el-card>

    <template v-if="preview">
      <section class="diff-stat-grid">
        <ReStatCard label="差异条目" :value="preview.summary.total" tone="primary" />
        <ReStatCard label="受影响表" :value="preview.summary.tables_affected" tone="info" />
        <ReStatCard label="高严重度" :value="preview.summary.by_severity.high || 0" tone="danger" />
        <ReStatCard label="中严重度" :value="preview.summary.by_severity.medium || 0" tone="warning" />
      </section>

      <el-card shadow="never" class="result-card">
        <template #header>
          <div class="result-header">
            <span>字段级差异（只读预览，不落库）</span>
            <el-radio-group v-model="viewMode" size="small">
              <el-radio-button value="inline">单列</el-radio-button>
              <el-radio-button value="side">并排</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <div class="filter-bar">
          <el-select v-model="filters.type" placeholder="变更类型" clearable size="small" class="type-select" @change="doFilter">
            <el-option v-for="(count, type) in preview.summary.by_type" :key="type" :label="`${changeTypeLabel(type)} (${count})`" :value="type" />
          </el-select>
          <el-select v-model="filters.severity" placeholder="严重度" clearable size="small" class="sev-select" @change="doFilter">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
          <el-input
            v-model="filters.keyword"
            placeholder="搜索表/字段/Schema"
            clearable
            size="small"
            class="kw-input"
            @keyup.enter="doFilter"
            @clear="doFilter"
          />
          <el-button type="primary" size="small" @click="doFilter">筛选</el-button>
        </div>
        <el-table v-loading="diffRunning" :data="preview.items" stripe size="small">
          <el-table-column prop="namespace" label="Schema" width="110" show-overflow-tooltip />
          <el-table-column label="表" min-width="170" show-overflow-tooltip>
            <template #default="{ row }">{{ row.table_name }}</template>
          </el-table-column>
          <el-table-column label="对象" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.object_type === 'table' ? 'warning' : 'info'" size="small" disable-transitions>
                {{ row.object_type === "table" ? "表" : "字段" }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="字段/字段属性" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ row.object_type === "column" ? row.object_name : "-" }}</template>
          </el-table-column>
          <el-table-column label="变更类型" width="120" align="center">
            <template #default="{ row }">
              <el-tag :type="changeTypeColor(row.change_type)" size="small" disable-transitions>
                {{ changeTypeLabel(row.change_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="严重度" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="severityColor(row.severity)" size="small" disable-transitions>{{ severityLabel(row.severity) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="viewMode === 'inline'" label="变更内容 (before → after)" min-width="240">
            <template #default="{ row }">
              <span class="value-before">{{ row.before_value ?? "（无）" }}</span>
              <span class="diff-arrow-small">→</span>
              <span class="value-after">{{ row.after_value ?? "（无）" }}</span>
            </template>
          </el-table-column>
          <el-table-column v-else label="Before" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.before_value ?? "（无）" }}</template>
          </el-table-column>
          <el-table-column v-if="viewMode !== 'inline'" label="After" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.after_value ?? "（无）" }}</template>
          </el-table-column>
          <el-table-column label="质量影响" width="150" align="center">
            <template #default="{ row }">
              <el-tooltip v-if="row.quality_impact" :content="row.quality_impact" placement="top">
                <el-tag type="danger" size="small" disable-transitions>联动质量 finding</el-tag>
              </el-tooltip>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-if="!diffRunning && !preview.items.length"
          description="当前筛选下没有差异条目"
          class="empty-block"
        />
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="preview.total"
          layout="total, prev, pager, next"
          size="small"
          class="pager"
          @current-change="runPreview"
        />
      </el-card>
    </template>

    <el-empty v-else-if="!sourcesError && !snapshotsError" description="选择两个快照并执行对比" class="empty-block" />
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { listSources, type AssetSourceItem } from "@/api/asset";
import {
  diffMetadataPreview,
  getSourceSnapshots,
  runMetadataDiff,
  type DiffPreviewData
} from "@/api/metadata";
import { changeTypeColor, changeTypeLabel, severityColor, severityLabel } from "../labels";
import { snapshotOrderError, type SnapshotOption } from "./contracts";

const route = useRoute();
const sourceCode = ref("");
const sources = ref<AssetSourceItem[]>([]);
const snapshots = ref<SnapshotOption[]>([]);
const fromId = ref<number | null>(null);
const toId = ref<number | null>(null);
const diffRunning = ref(false);
const generating = ref(false);
const preview = ref<DiffPreviewData | null>(null);
const sourcesLoading = ref(false);
const sourcesError = ref("");
const snapshotsError = ref("");
const viewMode = ref<"inline" | "side">("inline");
const page = ref(1);
const pageSize = 20;
const filters = reactive({ type: "", severity: "", keyword: "" });
const orderError = computed(() => snapshotOrderError(fromId.value, toId.value, snapshots.value));

function detailMessage(error: any, fallback: string) {
  return String(error?.response?.data?.detail || fallback).slice(0, 300);
}

function clearSelectionAndResult() {
  fromId.value = null;
  toId.value = null;
  preview.value = null;
}

async function loadSources() {
  sourcesLoading.value = true;
  sourcesError.value = "";
  try {
    const res = await listSources();
    sources.value = res.data || [];
  } catch (error: any) {
    sources.value = [];
    sourcesError.value = detailMessage(error, "数据连接加载失败");
  } finally {
    sourcesLoading.value = false;
  }
}

async function onSourceChange() {
  clearSelectionAndResult();
  snapshots.value = [];
  await loadSnapshots();
}

function onSnapshotSelectionChange() {
  preview.value = null;
}

function swapSnapshots() {
  const previous = fromId.value;
  fromId.value = toId.value;
  toId.value = previous;
  preview.value = null;
}

async function loadSnapshots() {
  snapshotsError.value = "";
  if (!sourceCode.value) {
    snapshots.value = [];
    fromId.value = null;
    toId.value = null;
    preview.value = null;
    return;
  }
  try {
    const res = await getSourceSnapshots(sourceCode.value);
    snapshots.value = res.data ?? [];
  } catch (error: any) {
    snapshots.value = [];
    snapshotsError.value = detailMessage(error, "快照列表加载失败");
  }
}

function doFilter() {
  page.value = 1;
  runPreview();
}

async function runPreview() {
  if (!fromId.value || !toId.value) return;
  if (orderError.value) {
    ElMessage.warning(orderError.value);
    return;
  }
  diffRunning.value = true;
  try {
    const res = await diffMetadataPreview({
      source: sourceCode.value,
      from: fromId.value,
      to: toId.value,
      type: filters.type || undefined,
      severity: filters.severity || undefined,
      keyword: filters.keyword || undefined,
      page: page.value,
      page_size: pageSize
    });
    preview.value = res.data;
  } catch (error: any) {
    preview.value = null;
    ElMessage.error(detailMessage(error, "快照对比失败"));
  } finally {
    diffRunning.value = false;
  }
}

async function generateEvents() {
  if (!fromId.value || !toId.value) return;
  generating.value = true;
  try {
    const res = await runMetadataDiff({
      snapshot_id_from: fromId.value,
      snapshot_id_to: toId.value,
      source_code: sourceCode.value || undefined
    });
    ElMessage.success(
      `已生成变更事件：新增 ${res.data.total_changes} 条，幂等跳过 ${res.data.skipped_existing} 条，联动质量 finding ${res.data.linked_to_quality_findings} 条`
    );
  } catch (error: any) {
    ElMessage.error(detailMessage(error, "生成变更事件失败"));
  } finally {
    generating.value = false;
  }
}

onMounted(async () => {
  await loadSources();
  // 146 E9：对比入口预选 source/from/to（如快照列表"对比"按钮带入）
  const qSource = String(route.query.source || "").trim();
  const qFrom = Number(route.query.from || 0);
  const qTo = Number(route.query.to || 0);
  if (qSource) {
    sourceCode.value = qSource;
    await loadSnapshots();
    if (qFrom && qTo) {
      fromId.value = qFrom;
      toId.value = qTo;
      if (!orderError.value) await runPreview();
    }
  }
});
</script>

<style scoped>
.metadata-diff { padding: 4px; }
.diff-card, .result-card { border-color: var(--border-light); border-radius: var(--radius-base); box-shadow: var(--shadow-sm); }
.diff-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
.diff-arrow { margin: 0 12px; font-size: 16px; color: var(--primary-500); font-weight: 700; }
.diff-arrow-small { margin: 0 6px; color: var(--text-secondary); }
.mt-12 { margin-top: 12px; }
@media (max-width: 760px) { .diff-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.diff-form { display: flex; align-items: center; flex-wrap: wrap; }
.snapshot-select { width: 260px; }
.source-select { width: 240px; margin-right: 12px; }
.run-button { margin-left: 12px; }
.empty-block { margin-top: 16px; }
.result-header { display: flex; align-items: center; justify-content: space-between; }
.filter-bar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.type-select { width: 200px; }
.sev-select { width: 110px; }
.kw-input { width: 220px; }
.pager { justify-content: flex-end; margin-top: 12px; }
.value-before { color: var(--el-color-danger); word-break: break-all; }
.value-after { color: var(--el-color-success); word-break: break-all; }
</style>
