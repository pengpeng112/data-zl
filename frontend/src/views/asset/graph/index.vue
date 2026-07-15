<template>
  <div class="asset-graph-page">
    <RePageHeader
      title="关系图谱"
      subtitle="按系统大类 / 数据源 / Schema / 业务域浏览；A 类实线，D 类跨系统虚线灰紫并单独图例。"
    />
    <GraphToolbar
      :filters="filters"
      :locate="locate"
      :options="options"
      :normalized="normalized"
      :current-view-mode="currentViewMode"
      :view-mode-options="viewModeOptions"
      :graph-engine="graphEngine"
      :loading="loading"
      :selected-node-id="selectedNodeId"
      @view-mode-change="changeViewMode"
      @engine-change="changeEngine"
      @load-chain="loadChain"
      @back-global="backToGlobal"
      @load-data="loadData"
      @refresh="refreshGraphOnly"
      @sample-pass="showSamplePass"
      @reset="resetFilters"
    />

    <el-alert
      v-if="graphLoadNotice"
      class="graph-load-alert"
      type="warning"
      show-icon
      :closable="false"
      :title="graphLoadNotice"
    />
    <el-alert v-if="diagnosticWarnings.length" class="graph-load-alert" type="warning" show-icon :closable="false" :title="diagnosticWarnings.join('；')" />
    <div v-loading="loading" :element-loading-text="graphLoadingText" class="graph-wrap">
      <component
        :is="graphEngine === 'g6' ? AdvancedRelationGraph : RelationGraph"
        v-if="graphData.nodes.length"
        :nodes="graphData.nodes"
        :edges="graphData.edges"
        :focus-keyword="filters.keyword"
        :group-by="filters.group_by"
        :center-table="centerTable"
        :selected-node-id="selectedNodeId"
        :show-review-layer="filters.show_review_layer && Boolean(currentViewMode?.show_review_layer)"
        :layout-mode="filters.layout_mode"
        :aggregate-groups="filters.aggregate_groups"
        :aggregation-threshold="8"
        :view-mode="filters.view_mode"
        height="calc(100vh - 370px)"
        @node-click="selectNode"
        @edge-click="showEdge"
      />
      <ReEmptyState v-else title="暂无可展示关系" description="请调整系统、Schema、关系等级或中心表条件后重新加载。" />
    </div>

    <ReDetailDrawer
      v-model="nodeDrawerVisible"
      title="节点详情"
      :subtitle="selectedNode?.id || ''"
      :status="selectedNode?.review_status || selectedNode?.include_status || ''"
      status-type="info"
      size="520px"
    >
      <el-descriptions v-if="selectedNode" :column="1" border size="small">
        <el-descriptions-item label="节点">{{ selectedNode.id }}</el-descriptions-item>
        <el-descriptions-item label="系统大类">{{ selectedNode.system_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="系统库/数据源">{{ selectedNode.source_code || selectedNode.source || '-' }}</el-descriptions-item>
        <el-descriptions-item label="表空间">{{ selectedNode.schema_name || selectedNode.namespace_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="表名">{{ selectedNode.table_name || selectedNode.label }}</el-descriptions-item>
        <el-descriptions-item label="中文名">{{ selectedNode.table_name_cn || '-' }}</el-descriptions-item>
        <el-descriptions-item label="表角色">{{ selectedNode.table_role || '-' }}</el-descriptions-item>
        <el-descriptions-item label="业务域">{{ selectedNode.business_domain || selectedNode.domain || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源说明">{{ selectedNode.source || '-' }}</el-descriptions-item>
        <el-descriptions-item label="字段数">{{ selectedNode.column_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="行数统计">{{ selectedNode.row_count_stats || '-' }}</el-descriptions-item>
        <el-descriptions-item label="粒度">{{ selectedNode.grain || '-' }}</el-descriptions-item>
        <el-descriptions-item label="主键">{{ selectedNode.pk || '-' }}</el-descriptions-item>
        <el-descriptions-item label="纳入状态">{{ selectedNode.include_status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="复核状态">{{ selectedNode.review_status || '-' }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button v-if="selectedNode" type="primary" @click="openTable(selectedNode)">打开表详情</el-button>
        <el-button @click="selectedNodeId = ''">取消高亮</el-button>
      </template>
    </ReDetailDrawer>

    <GraphEvidenceDrawer v-model="drawerVisible" :edge="selectedEdge" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import ReDetailDrawer from "@/components/ReDetailDrawer/index.vue";
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import AdvancedRelationGraph from "@/views/asset/components/AdvancedRelationGraph.vue";
import GraphEvidenceDrawer from "@/views/asset/components/GraphEvidenceDrawer.vue";
import GraphToolbar, { type GraphEngine } from "@/views/asset/components/GraphToolbar.vue";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import { normalizeGraphData } from "@/views/asset/graph/graphNormalize";
import { decideGraphLoadPolicy } from "@/views/asset/graph/graphLoadPolicy";
import { getGraph, getGraphDiagnostics, getGraphNeighbors, getGraphOptions, type GraphData, type GraphEdge, type GraphNode, type GraphOptionsData, type GraphViewMode } from "@/api/asset";

type LayoutMode = "layered" | "grouped" | "radial";

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const drawerVisible = ref(false);
const nodeDrawerVisible = ref(false);
const selectedEdge = ref<GraphEdge | null>(null);
const selectedNode = ref<GraphNode | null>(null);
const selectedNodeId = ref("");
const centerTable = ref("");
const graphEngine = ref<GraphEngine>("svg");
const graphLoadNotice = ref("");
const diagnosticWarnings = ref<string[]>([]);
const graphData = ref<GraphData>({ nodes: [], edges: [] });
const options = reactive<GraphOptionsData>({ systems: [], sources: [], schemas: [], domains: [], validation_statuses: [], confidences: [], relation_types: [], view_modes: [] });

const filters = reactive({
  view_mode: "table",
  group_by: "schema" as "system" | "source" | "schema" | "domain",
  system_code: "",
  source_code: "",
  schema: "",
  domain: "",
  validation_status: "A_rechecked",
  confidence: "A",
  keyword: "",
  limit: 120,
  include_candidates: false,
  include_dependencies: false,
  show_review_layer: false,
  layout_mode: "layered" as LayoutMode,
  aggregate_groups: false
});

const locate = reactive({
  table: "",
  depth: 1 as 1 | 2,
  direction: "both" as "in" | "out" | "both"
});

const viewModeOptions = computed(() => options.view_modes.map(item => ({ label: item.label, value: item.code })));
const currentViewMode = computed<GraphViewMode | undefined>(() => options.view_modes.find(item => item.code === filters.view_mode));
const graphLoadingText = computed(() => filters.view_mode === "lineage" ? "Loading lineage graph" : "Loading relation graph");
const normalized = computed(() => normalizeGraphData(graphData.value.nodes, graphData.value.edges, {
  groupBy: filters.group_by,
  focusKeyword: filters.keyword,
  centerTable: centerTable.value,
  selectedNodeId: selectedNodeId.value,
  showReviewLayer: filters.show_review_layer && Boolean(currentViewMode.value?.show_review_layer)
}));

function applyModeDefaults(mode: GraphViewMode) {
  filters.group_by = mode.group_by;
  filters.confidence = mode.confidence || "";
  filters.validation_status = mode.validation_status ?? (mode.confidence === "A" ? "A_rechecked" : "");
  filters.include_candidates = mode.include_candidates;
  filters.include_dependencies = mode.include_dependencies;
  filters.show_review_layer = Boolean(mode.show_review_layer);
  filters.layout_mode = mode.layout_mode;
}

function changeViewMode(value: string) {
  filters.view_mode = value;
  applyViewMode();
}

function changeEngine(value: GraphEngine) {
  graphEngine.value = value;
  refreshGraphOnly();
}

function applyViewMode() {
  selectedNodeId.value = "";
  const mode = currentViewMode.value;
  if (!mode) return;
  applyModeDefaults(mode);
  if (mode.requires_table) {
    if (locate.table.trim()) {
      loadChain();
    } else {
      refreshGraphOnly();
      ElMessage.warning("请输入中心表后查看上下游链路");
    }
    return;
  }
  loadData();
}

function refreshGraphOnly() {
  graphData.value = { ...graphData.value };
}
function applyGraphLoadPolicy(data: GraphData) {
  const policy = decideGraphLoadPolicy({
    nodeCount: data.nodes.length,
    edgeCount: data.edges.length,
    viewMode: filters.view_mode,
    graphEngine: graphEngine.value,
    aggregateGroups: filters.aggregate_groups
  });
  graphLoadNotice.value = policy.notice;
  if (policy.shouldAggregate) filters.aggregate_groups = true;
  if (policy.shouldUseSvg) graphEngine.value = "svg";
  if (policy.shouldAggregate || policy.shouldUseSvg) ElMessage.warning(policy.notice);
}


function routeQueryText(value: unknown) {
  return Array.isArray(value) ? String(value[0] || "") : String(value || "");
}

function applyRouteQueryFilters() {
  const keyword = routeQueryText(route.query.keyword).trim();
  const validationStatus = routeQueryText(route.query.validation_status).trim();
  const confidence = routeQueryText(route.query.confidence).trim();
  const groupBy = routeQueryText(route.query.group_by).trim();
  const showReviewLayer = routeQueryText(route.query.show_review_layer).trim().toLowerCase();
  if (keyword) filters.keyword = keyword;
  if (validationStatus) filters.validation_status = validationStatus;
  if (confidence) filters.confidence = confidence;
  if (["system", "source", "schema", "domain"].includes(groupBy)) filters.group_by = groupBy as typeof filters.group_by;
  if (["1", "true", "yes"].includes(showReviewLayer) && currentViewMode.value?.show_review_layer) filters.show_review_layer = true;
}

function routeViewMode() {
  const code = routeQueryText(route.query.view_mode).trim();
  return options.view_modes.find(item => item.code === code);
}

async function loadOptions() {
  const res = await getGraphOptions();
  Object.assign(options, res.data);
  const mode = routeViewMode() || currentViewMode.value || options.view_modes[0];
  if (mode) {
    filters.view_mode = mode.code;
    applyModeDefaults(mode);
    applyRouteQueryFilters();
  }
}

async function loadDiagnostics() {
  try {
    const res = await getGraphDiagnostics();
    diagnosticWarnings.value = res.data?.warnings || [];
  } catch {
    diagnosticWarnings.value = ["图谱诊断接口暂时不可用"];
  }
}

async function loadData() {
  loading.value = true;
  centerTable.value = "";
  selectedNodeId.value = "";
  try {
    const res = await getGraph({
      system_code: filters.system_code || undefined,
      source_code: filters.source_code || undefined,
      schema: filters.schema || undefined,
      domain: filters.domain || undefined,
      validation_status: filters.validation_status || undefined,
      confidence: filters.confidence || undefined,
      keyword: filters.keyword || undefined,
      limit: filters.limit,
      include_candidates: filters.include_candidates,
      include_dependencies: filters.include_dependencies
    });
    graphData.value = res.data;
    applyGraphLoadPolicy(res.data);
  } finally {
    loading.value = false;
  }
}

async function loadChain() {
  const lineageMode = options.view_modes.find(item => item.code === "lineage");
  if (lineageMode) {
    filters.view_mode = lineageMode.code;
    applyModeDefaults(lineageMode);
  }
  const table = locate.table.trim();
  if (!table) {
    ElMessage.warning("请输入要定位的表名");
    return;
  }
  loading.value = true;
  try {
    const res = await getGraphNeighbors({ table, depth: locate.depth, direction: locate.direction, limit: filters.limit });
    graphData.value = res.data;
    applyGraphLoadPolicy(res.data);
    centerTable.value = table;
    selectedNodeId.value = table;
    filters.keyword = table;
    filters.layout_mode = "radial";
    if (!res.data.nodes.length) ElMessage.warning("未找到该表的上下游链路");
  } finally {
    loading.value = false;
  }
}

function backToGlobal() {
  locate.table = "";
  centerTable.value = "";
  selectedNodeId.value = "";
  const tableMode = options.view_modes.find(item => item.code === "table");
  if (tableMode) {
    filters.view_mode = tableMode.code;
    applyModeDefaults(tableMode);
  }
  loadData();
}

function showSamplePass() {
  filters.validation_status = "sample_pass";
  filters.confidence = "A";
  filters.include_candidates = false;
  filters.include_dependencies = false;
  filters.show_review_layer = false;
  loadData();
}

function resetFilters() {
  const tableMode = options.view_modes.find(item => item.code === "table");
  filters.view_mode = tableMode?.code || "table";
  if (tableMode) applyModeDefaults(tableMode);
  filters.system_code = "";
  filters.source_code = "";
  filters.schema = "";
  filters.domain = "";
  filters.validation_status = tableMode?.validation_status || "A_rechecked";
  filters.keyword = "";
  filters.limit = 120;
  filters.aggregate_groups = false;
  locate.table = "";
  locate.depth = 1;
  locate.direction = "both";
  loadData();
}

function openTable(node: GraphNode) {
  const parts = node.id.split(".");
  if (parts.length >= 2) router.push(`/asset/tables/${parts[0]}/${parts.slice(1).join(".")}`);
}

function selectNode(node: GraphNode) {
  selectedNode.value = node;
  selectedNodeId.value = node.id;
  nodeDrawerVisible.value = true;
}

function showEdge(edge: GraphEdge) {
  selectedEdge.value = edge;
  drawerVisible.value = true;
}

onMounted(async () => {
  await loadOptions();
  await loadDiagnostics();
  await loadData();
});
</script>

<style scoped lang="scss">
.asset-graph-page {
  min-height: calc(100vh - 120px);
  padding: 20px;
  background: var(--re-page-bg);
}

.graph-load-alert {
  margin-bottom: 12px;
  border-radius: var(--radius-base);
}

.graph-wrap {
  min-height: calc(100vh - 370px);
  padding: 14px;
  overflow: hidden;
  background:
    radial-gradient(circle at 82% 10%, rgb(14 165 233 / 12%), transparent 28%),
    linear-gradient(135deg, #0b1120 0%, #0f172a 52%, #111827 100%);
  border: 1px solid rgb(148 163 184 / 16%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-inset), 0 18px 45px rgb(2 6 23 / 22%);
}

.graph-wrap :deep(.el-loading-mask) {
  background: rgb(15 23 42 / 72%);
  backdrop-filter: blur(8px);
}

.graph-wrap :deep(.re-empty-state h3) {
  color: var(--dark-text-primary);
}

.graph-wrap :deep(.re-empty-state p) {
  color: var(--dark-text-secondary);
}

.drawer-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
</style>
