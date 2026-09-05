<template>
  <el-card shadow="never" class="toolbar-card">
    <div class="mode-row">
      <el-segmented :model-value="filters.view_mode" :options="viewModeOptions" @update:model-value="emit('view-mode-change', String($event))" />
      <div class="mode-controls">
        <span class="graph-mode-note">{{ currentViewMode?.description || "选择任务模式开始" }}</span>
        <el-dropdown trigger="click" @command="changeDisplay">
          <el-button>显示 ▾</el-button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="force" :disabled="filters.view_mode === 'path'">知识图谱</el-dropdown-item>
            <el-dropdown-item command="layered" :disabled="filters.view_mode !== 'path'">分层视图</el-dropdown-item>
            <el-dropdown-item command="radial">中心辐射</el-dropdown-item>
            <el-dropdown-item command="grouped">分组布局</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <el-button @click="advancedVisible = !advancedVisible">高级筛选</el-button>
      </div>
    </div>

    <div class="global-search-row">
      <el-input
        :model-value="locate.table"
        placeholder="搜索表名、中文名、Schema 或五段物理键"
        clearable
        @update:model-value="emit('update:locate', { ...locate, table: String($event ?? '') })"
        @keyup.enter="emit('global-search')"
      />
      <el-button type="primary" :loading="loading" @click="emit('global-search')">搜索并聚焦</el-button>
      <template v-if="filters.view_mode === 'explore'">
      <el-segmented
        :model-value="locate.depth"
        :disabled="!locate.physical_key"
        :options="depthOptions"
        @update:model-value="emit('update:locate', { ...locate, depth: Number($event) as 1 | 2 | 3 })"
        @change="emit('load-chain')"
      />
      <el-segmented
        :model-value="locate.direction"
        :disabled="!locate.physical_key"
        class="direction-segmented"
        :options="directionOptions"
        @update:model-value="emit('update:locate', { ...locate, direction: $event as 'in' | 'out' | 'both' })"
        @change="emit('load-chain')"
      />
      </template>
    </div>

    <el-drawer v-model="advancedVisible" title="高级筛选" size="420px" append-to-body>
    <div class="filter-grid">
      <el-select
        :model-value="filters.system_code"
        placeholder="业务系统"
        clearable
        filterable
        @update:model-value="emit('update:filters', { ...filters, system_code: String($event ?? '') })"
        @change="emit('system-change')"
      >
        <el-option v-for="item in systemOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        :model-value="filters.source_code"
        placeholder="数据连接（可选）"
        clearable
        filterable
        @update:model-value="emit('update:filters', { ...filters, source_code: String($event ?? '') })"
        @change="emit('load-data')"
      >
        <el-option v-for="item in sourceOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        :model-value="filters.schema"
        placeholder="Schema / Owner"
        clearable
        filterable
        @update:model-value="emit('update:filters', { ...filters, schema: String($event ?? '') })"
        @change="emit('load-data')"
      >
        <el-option v-for="item in schemaOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        :model-value="filters.domain"
        placeholder="业务域（正交筛选）"
        clearable
        filterable
        @update:model-value="emit('update:filters', { ...filters, domain: String($event ?? '') })"
        @change="emit('load-data')"
      >
        <el-option v-for="item in domainOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select
        v-if="filters.view_mode === 'review'"
        :model-value="filters.validation_status"
        placeholder="验证状态"
        clearable
        @update:model-value="emit('update:filters', { ...filters, validation_status: String($event ?? '') })"
        @change="emit('load-data')"
      >
        <el-option v-for="item in options.validation_statuses" :key="item" :label="statusLabel(item)" :value="item" />
      </el-select>
      <el-select
        v-if="filters.view_mode === 'review'"
        :model-value="filters.confidence"
        placeholder="置信度"
        clearable
        @update:model-value="emit('update:filters', { ...filters, confidence: String($event ?? '') })"
        @change="emit('load-data')"
      >
        <el-option v-for="item in options.confidences" :key="item" :label="item" :value="item" />
      </el-select>
      <el-input-number
        :model-value="filters.limit"
        :min="20"
        :max="500"
        :step="20"
        controls-position="right"
        @update:model-value="emit('update:filters', { ...filters, limit: Number($event) })"
      />
      <el-button type="primary" :loading="loading" @click="emit('load-data')">应用筛选</el-button>
      <el-button @click="emit('reset')">重置</el-button>
    </div>
    </el-drawer>

    <div v-if="filters.view_mode === 'review'" class="switch-row">
      <el-checkbox
        :model-value="filters.include_candidates"
        @update:model-value="emit('update:filters', { ...filters, include_candidates: Boolean($event) })"
        @change="emit('load-data')"
      >候选关系</el-checkbox>
      <el-checkbox
        :model-value="filters.include_dependencies"
        @update:model-value="emit('update:filters', { ...filters, include_dependencies: Boolean($event) })"
        @change="emit('load-data')"
      >视图依赖</el-checkbox>
      <el-checkbox
        :model-value="filters.show_review_layer"
        :disabled="!currentViewMode?.show_review_layer"
        @update:model-value="emit('update:filters', { ...filters, show_review_layer: Boolean($event) })"
        @change="emit('refresh')"
      >显示 D 类跨系统（虚线灰紫）</el-checkbox>
      <el-button text type="success" @click="emit('sample-pass')">只看通过关系</el-button>
    </div>


    <el-alert
      v-if="filters.show_review_layer"
      class="review-layer-alert"
      type="warning"
      show-icon
      :closable="false"
      title="D 类可进入图谱展示，但必须保留「跨系统待验证」标识，不可当作 A 类正式血缘依据。"
    />

    <div class="stats-block">
      <button type="button" class="stats-toggle" :aria-expanded="statsExpanded" @click="statsExpanded = !statsExpanded">
        {{ statsExpanded ? "收起统计 ▴" : "展开统计 ▾" }}
      </button>
      <div v-show="statsExpanded" class="stats-body">
        <div class="stats-row">
          <el-tag>节点 {{ normalized.nodes.length }}</el-tag>
          <el-tag type="primary">关系 {{ normalized.edges.length }}</el-tag>
          <el-tag type="success">通过 {{ normalized.passCount }}</el-tag>
          <el-tag type="warning">候选 {{ normalized.candidateCount }}</el-tag>
          <el-tag type="info">依赖 {{ normalized.dependencyCount }}</el-tag>
          <el-tag v-if="normalized.reviewHiddenCount" type="danger" effect="plain">已隐藏 D/待分析 {{ normalized.reviewHiddenCount }}</el-tag>
          <el-tag v-if="selectedNodeId" type="success" effect="dark">已聚焦 {{ selectedNodeId }}</el-tag>
        </div>
        <div v-if="meta" class="meta-row" aria-label="图谱响应统计">
          <el-tag type="info" effect="plain">总数 {{ meta.total_relations }}</el-tag>
          <el-tag type="info" effect="plain">命中 {{ meta.matched_relations }}</el-tag>
          <el-tag type="info" effect="plain">返回 {{ meta.returned_relations }}</el-tag>
          <el-tag v-if="meta.truncated" type="danger" effect="plain" size="small">已截断（limit={{ filters.limit }}）</el-tag>
          <el-tag v-else type="success" effect="plain" size="small">未截断</el-tag>
          <el-tag v-if="meta.unresolved_endpoints" type="warning" effect="plain" size="small">端点未解析 {{ meta.unresolved_endpoints }}</el-tag>
          <span v-if="meta.backend_build_id" class="meta-build">build:{{ meta.backend_build_id }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import type { GraphMeta, GraphOptionsData, GraphViewMode } from "@/api/asset";
import type { NormalizedGraph } from "@/views/asset/graph/graphNormalize";
import { isGovernanceUser } from "@/utils/userRoles";

export type GraphEngine = "svg" | "g6";

type LayoutMode = "force" | "layered" | "grouped" | "radial" | "hierarchy";

type GraphGroupBy = "system" | "source" | "schema" | "domain";

interface GraphFilters {
  view_mode: string;
  group_by: GraphGroupBy;
  system_code: string;
  source_code: string;
  schema: string;
  domain: string;
  validation_status: string;
  confidence: string;
  keyword: string;
  limit: number;
  include_candidates: boolean;
  include_dependencies: boolean;
  show_review_layer: boolean;
  layout_mode: LayoutMode;
  aggregate_groups: boolean;
}

interface LocateState {
  table: string;
  physical_key?: string;
  search_results?: unknown[];
  depth: 1 | 2 | 3;
  direction: "in" | "out" | "both";
}

const props = defineProps<{
  filters: GraphFilters;
  locate: LocateState;
  options: GraphOptionsData;
  normalized: NormalizedGraph;
  currentViewMode?: GraphViewMode;
  viewModeOptions: { label: string; value: string }[];
  graphEngine: GraphEngine;
  loading: boolean;
  selectedNodeId: string;
  meta?: GraphMeta | null;
}>();

const systemOptions = computed(() => props.options.system_options?.length ? props.options.system_options : props.options.systems.map(value => ({ value, label: value })));
const sourceOptions = computed(() => props.options.source_options?.length ? props.options.source_options : props.options.sources.map(value => ({ value, label: value })));
const schemaOptions = computed(() => props.options.schema_options?.length ? props.options.schema_options : props.options.schemas.map(value => ({ value, label: value })));
const domainOptions = computed(() => props.options.domain_options?.length ? props.options.domain_options : props.options.domains.map(value => ({ value, label: value })));

// 146 E2（R5）：普通用户默认折叠统计行，治理角色（*_admin/admin）默认展开；可手动切换。
const statsExpanded = ref(isGovernanceUser());
const advancedVisible = ref(false);

const emit = defineEmits<{
  "update:locate": [value: LocateState];
  "update:filters": [value: GraphFilters];
  "view-mode-change": [value: string];
  "engine-change": [value: GraphEngine];
  "load-chain": [];
  "global-search": [];
  "back-global": [];
  "system-change": [];
  "load-data": [];
  "refresh": [];
  "sample-pass": [];
  "reset": [];
}>();

const depthOptions = [{ label: "1 跳", value: 1 }, { label: "2 跳", value: 2 }, { label: "3 跳", value: 3 }];
const directionOptions = [{ label: "全部方向", value: "both" }, { label: "引用它", value: "in" }, { label: "它引用", value: "out" }];

function statusLabel(status: string) {
  const map: Record<string, string> = {
    sample_pass: "样本通过",
    verified: "已验证",
    manual_reviewed: "人工复核",
    bounded: "有边界",
    needs_split: "需拆分",
    not_tested: "未验证",
    rejected: "已拒绝",
    sample_verified: "抽样验证",
    needs_review: "待复核"
  };
  return map[status] || status || "-";
}

function changeDisplay(command: string) {
  emit("update:filters", { ...props.filters, layout_mode: command as LayoutMode });
  emit("refresh");
}
</script>

<style scoped>
.toolbar-card { margin-bottom: 10px; }
.mode-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.mode-controls { display: flex; gap: 8px; align-items: center; }
.group-select { width: 160px; }
.layout-select { width: 130px; }
.graph-mode-note { color: var(--text-secondary, #64748b); font-size: 12px; }
.global-search-row { display: grid; grid-template-columns: minmax(300px, 1fr) auto auto auto; gap: 8px; align-items: center; margin-bottom: 10px; }
.direction-segmented { width: 190px; }
.filter-grid { display: grid; grid-template-columns: 1fr; gap: 10px; align-items: center; }
.switch-row { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; margin-top: 10px; }
.legend-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 18px;
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgb(14 165 233 / 4%);
  border: 1px solid var(--border-light, #f1f5f9);
  font-size: 12px;
  color: var(--text-secondary, #64748b);
}
.legend-item { display: inline-flex; align-items: center; gap: 6px; }
.swatch {
  display: inline-block;
  width: 22px;
  height: 0;
  border-top-width: 3px;
  border-top-style: solid;
}
.swatch.solid-a { border-top-color: #0f3a66; }
.swatch.dashed-bc { border-top-style: dashed; border-top-color: #d97706; }
.swatch.dashed-d { border-top-style: dashed; border-top-color: #7c6aa6; }
.swatch.dashed-cand { border-top-style: dashed; border-top-color: #94a3b8; }
.review-layer-alert { margin-top: 10px; }
.stats-block { margin-top: 10px; }
.stats-toggle {
  padding: 2px 0;
  border: none;
  background: none;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  cursor: pointer;
}
.stats-toggle:hover { color: var(--el-color-primary); }
.stats-body { display: grid; gap: 8px; }
.stats-row { display: flex; flex-wrap: wrap; gap: 8px; }
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-light, #e2e8f0);
  font-size: 12px;
}
.meta-build {
  color: var(--text-secondary, #64748b);
  font-family: monospace;
}
@media (max-width: 1200px) { .filter-grid, .global-search-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .mode-row { align-items: stretch; } .mode-controls { display: grid; grid-template-columns: 1fr; } .group-select, .layout-select, .direction-segmented { width: 100%; } .filter-grid, .global-search-row { grid-template-columns: 1fr; } }
</style>
