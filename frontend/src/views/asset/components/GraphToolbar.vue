<template>
  <el-card shadow="never" class="toolbar-card">
    <div class="mode-row">
      <el-segmented :model-value="filters.view_mode" :options="viewModeOptions" @update:model-value="emit('view-mode-change', String($event))" />
      <div class="mode-controls">
        <el-segmented :model-value="graphEngine" :options="engineOptions" @update:model-value="emit('engine-change', $event as GraphEngine)" />
        <el-select v-model="filters.group_by" class="group-select" @change="emit('refresh')">
          <el-option label="按系统大类分组" value="system" />
          <el-option label="按数据源分组" value="source" />
          <el-option label="按表空间分组" value="schema" />
          <el-option label="按业务域分组" value="domain" />
        </el-select>
        <el-select v-model="filters.layout_mode" class="layout-select" @change="emit('refresh')">
          <el-option label="分层布局" value="layered" />
          <el-option label="泳道分组" value="grouped" />
          <el-option label="链路环形" value="radial" />
        </el-select>
      </div>
    </div>

    <div class="locate-row">
      <el-input v-model="locate.table" placeholder="输入表名定位，如 MEDREC.PAT_VISIT" clearable @keyup.enter="emit('load-chain')" />
      <el-segmented v-model="locate.depth" :options="depthOptions" @change="emit('load-chain')" />
      <el-segmented v-model="locate.direction" class="direction-segmented" :options="directionOptions" @change="emit('load-chain')" />
      <el-button type="primary" :loading="loading" @click="emit('load-chain')">定位链路</el-button>
      <el-button @click="emit('back-global')">返回全局</el-button>
    </div>

    <div class="filter-grid">
      <el-select v-model="filters.system_code" placeholder="系统大类" clearable filterable @change="emit('load-data')">
        <el-option v-for="item in options.systems" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.source_code" placeholder="系统库/数据源" clearable filterable @change="emit('load-data')">
        <el-option v-for="item in options.sources" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.schema" placeholder="表空间" clearable filterable @change="emit('load-data')">
        <el-option v-for="item in options.schemas" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.domain" placeholder="业务域" clearable filterable @change="emit('load-data')">
        <el-option v-for="item in options.domains" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.validation_status" placeholder="验证状态" clearable @change="emit('load-data')">
        <el-option v-for="item in options.validation_statuses" :key="item" :label="statusLabel(item)" :value="item" />
      </el-select>
      <el-select v-model="filters.confidence" placeholder="关系等级" clearable @change="emit('load-data')">
        <el-option v-for="item in options.confidences" :key="item" :label="item" :value="item" />
      </el-select>
      <el-input v-model="filters.keyword" placeholder="搜索表名、中文名或关系端点" clearable @keyup.enter="emit('load-data')" @clear="emit('load-data')" />
      <el-input-number v-model="filters.limit" :min="20" :max="500" :step="20" controls-position="right" />
      <el-button type="primary" :loading="loading" @click="emit('load-data')">查询</el-button>
      <el-button @click="emit('reset')">重置</el-button>
    </div>

    <div class="switch-row">
      <el-checkbox v-model="filters.include_candidates" @change="emit('load-data')">候选关系</el-checkbox>
      <el-checkbox v-model="filters.include_dependencies" @change="emit('load-data')">视图依赖</el-checkbox>
      <el-checkbox v-model="filters.aggregate_groups" @change="emit('refresh')">节点聚合</el-checkbox>
      <el-checkbox
        v-model="filters.show_review_layer"
        :disabled="!currentViewMode?.show_review_layer"
        @change="emit('refresh')"
      >显示 D 类跨系统（虚线灰紫）</el-checkbox>
      <el-button text type="success" @click="emit('sample-pass')">只看通过关系</el-button>
    </div>

    <div class="legend-row" aria-label="关系图例">
      <span class="legend-item"><i class="swatch solid-a" />A 类高置信（实线）</span>
      <span class="legend-item"><i class="swatch dashed-bc" />B/C 类（虚线琥珀）</span>
      <span class="legend-item"><i class="swatch dashed-d" />D 类跨系统待验证（虚线灰紫）</span>
      <span class="legend-item"><i class="swatch dashed-cand" />候选关系</span>
    </div>

    <el-alert
      v-if="filters.show_review_layer"
      class="review-layer-alert"
      type="warning"
      show-icon
      :closable="false"
      title="D 类可进入图谱展示，但必须保留「跨系统待验证」标识，不可当作 A 类正式血缘依据。"
    />

    <div class="stats-row">
      <el-tag>节点 {{ normalized.nodes.length }}</el-tag>
      <el-tag type="primary">关系 {{ normalized.edges.length }}</el-tag>
      <el-tag type="success">通过 {{ normalized.passCount }}</el-tag>
      <el-tag type="warning">候选 {{ normalized.candidateCount }}</el-tag>
      <el-tag type="info">依赖 {{ normalized.dependencyCount }}</el-tag>
      <el-tag v-if="normalized.reviewHiddenCount" type="danger" effect="plain">已隐藏 D/待分析 {{ normalized.reviewHiddenCount }}</el-tag>
      <el-tag v-if="selectedNodeId" type="success" effect="dark">已聚焦 {{ selectedNodeId }}</el-tag>
      <el-tag v-for="item in normalized.topGroups" :key="item.name" effect="plain">{{ item.name }} {{ item.count }}</el-tag>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { GraphOptionsData, GraphViewMode } from "@/api/asset";
import type { NormalizedGraph } from "@/views/asset/graph/graphNormalize";

export type GraphEngine = "svg" | "g6";

type LayoutMode = "layered" | "grouped" | "radial";

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
  depth: 1 | 2;
  direction: "in" | "out" | "both";
}

defineProps<{
  filters: GraphFilters;
  locate: LocateState;
  options: GraphOptionsData;
  normalized: NormalizedGraph;
  currentViewMode?: GraphViewMode;
  viewModeOptions: { label: string; value: string }[];
  graphEngine: GraphEngine;
  loading: boolean;
  selectedNodeId: string;
}>();

const emit = defineEmits<{
  "view-mode-change": [value: string];
  "engine-change": [value: GraphEngine];
  "load-chain": [];
  "back-global": [];
  "load-data": [];
  "refresh": [];
  "sample-pass": [];
  "reset": [];
}>();

const engineOptions = [
  { label: "内置 SVG", value: "svg" },
  { label: "AntV G6", value: "g6" }
];
const depthOptions = [{ label: "直接上下游", value: 1 }, { label: "两跳链路", value: 2 }];
const directionOptions = [{ label: "双向", value: "both" }, { label: "上游", value: "in" }, { label: "下游", value: "out" }];

function statusLabel(status: string) {
  const map: Record<string, string> = {
    sample_pass: "样本通过",
    verified: "已验证",
    manual_reviewed: "人工复核",
    bounded: "有边界",
    needs_split: "需拆分",
    not_tested: "未验证",
    rejected: "已拒绝"
  };
  return map[status] || status || "-";
}
</script>

<style scoped>
.toolbar-card { margin-bottom: 10px; }
.mode-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.mode-controls { display: flex; gap: 8px; align-items: center; }
.group-select { width: 160px; }
.layout-select { width: 130px; }
.locate-row { display: grid; grid-template-columns: minmax(240px, 1fr) 210px 190px 90px 90px; gap: 8px; align-items: center; margin-bottom: 10px; }
.direction-segmented { width: 190px; }
.filter-grid { display: grid; grid-template-columns: 130px 150px 130px 150px 140px 110px minmax(220px, 1fr) 110px 76px 76px; gap: 8px; align-items: center; }
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
.stats-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
@media (max-width: 1200px) { .filter-grid, .locate-row { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .mode-row { align-items: stretch; } .mode-controls { display: grid; grid-template-columns: 1fr; } .group-select, .layout-select, .direction-segmented { width: 100%; } .filter-grid, .locate-row { grid-template-columns: 1fr; } }
</style>
