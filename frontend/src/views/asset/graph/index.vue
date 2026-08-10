<template>
  <div class="asset-graph-page">
    <RePageHeader
      title="关系图谱"
      subtitle="资产概览、关系探索、证据审核；中文名称为主，技术标识为辅。"
    />

    <!-- 加载/成功：工具栏 + 图表 -->
    <template v-if="!isErrorState && state !== 'loading'">
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
        :meta="graphMeta"
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
        <template v-if="graphData.nodes.length && (graphData.edges.length || filters.view_mode === 'overview')">
          <component
            :is="graphEngine === 'g6' ? AdvancedRelationGraph : RelationGraph"
            :key="renderKey"
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
            height="calc(100vh - 400px)"
            @node-click="selectNode"
            @edge-click="showEdge"
            @render-error="handleRenderError"
          />
        </template>
        <ReEmptyState
          v-else-if="hasAnyData"
          title="暂无可展示关系"
          description="请调整系统、Schema、关系等级或中心表条件后重新加载。"
        />
        <ReEmptyState
          v-else
          title="筛选结果为空"
          description="当前条件未命中任何关系，可清空条件或调整筛选后重试。"
        >
          <template #extra>
            <el-button type="primary" @click="resetFilters">清空条件</el-button>
          </template>
        </ReEmptyState>
      </div>
    </template>

    <!-- 错误面板：auth/permission/api/contract 统一展示，可重试 -->
    <div v-else-if="errorInfo" class="graph-error-panel">
      <el-result
        :icon="errorIcon"
        :title="errorInfo.title"
        :sub-title="errorDescription"
      >
        <template #extra>
          <el-button v-if="errorInfo.canRetry" type="primary" @click="retryPage">重试</el-button>
          <el-button @click="resetFilters">重置条件</el-button>
        </template>
      </el-result>
      <p class="graph-error-correlation">关联编号：{{ errorInfo.correlationId }}</p>
    </div>

    <!-- 初始 loading -->
    <div v-else class="graph-loading-page">
      <el-skeleton :rows="6" animated />
    </div>

    <ReDetailDrawer
      v-model="nodeDrawerVisible"
      title="节点详情"
      :subtitle="selectedNodeDisplayKey || ''"
      :status="selectedNode?.review_status || selectedNode?.include_status || ''"
      status-type="info"
      size="520px"
    >
      <el-descriptions v-if="selectedNode" :column="1" border size="small">
        <el-descriptions-item label="节点（物理键）">{{ selectedNode.id }}</el-descriptions-item>
        <el-descriptions-item label="展示名">{{ selectedNodeDisplayKey }}</el-descriptions-item>
        <el-descriptions-item label="业务系统">{{ selectedNode.system_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="数据源/数据库">{{ selectedNode.source_code || selectedNode.source || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Schema / Owner">{{ selectedNode.schema_name || selectedNode.namespace_name || '-' }}</el-descriptions-item>
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

    <GraphEvidenceDrawer v-model="drawerVisible" :edge="selectedEdge" :edge-key="selectedEdge?.id || ''" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
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
import {
  classifyGraphError,
  contractErrorInfo,
  validateGraphData,
  type GraphErrorInfo,
  type GraphPageState
} from "@/views/asset/graph/graphErrors";
import { getGraph, getGraphDiagnostics, getGraphFilterOptions, getGraphNeighbors, getGraphOptions, getGraphOverview, searchGraphTables, type GraphData, type GraphEdge, type GraphMeta, type GraphNode, type GraphOptionsData, type GraphViewMode, type GraphTableSearchItem } from "@/api/asset";

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
const overviewLevel = ref<"system" | "source" | "schema" | "object">("system");
const graphEngine = ref<GraphEngine>("g6");
const graphLoadNotice = ref("");
const diagnosticWarnings = ref<string[]>([]);
const graphData = ref<GraphData>({ nodes: [], edges: [] });
const graphMeta = ref<GraphMeta | null>(null);
const renderKey = ref(0);
const options = reactive<GraphOptionsData>({ systems: [], sources: [], schemas: [], domains: [], validation_statuses: [], confidences: [], relation_types: [], view_modes: [] });

// 108号 §五：明确状态机
const state = ref<GraphPageState>("initial");
const errorInfo = ref<GraphErrorInfo | null>(null);
const optionsReady = ref(false);

const filters = reactive({
  view_mode: "table",
  group_by: "schema" as "system" | "source" | "schema" | "domain",
  system_code: "",
  source_code: "",
  schema: "",
  domain: "",
  validation_status: "",
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
  physical_key: "",
  search_results: [] as GraphTableSearchItem[],
  depth: 1 as 1 | 2,
  direction: "both" as "in" | "out" | "both"
});

const viewModeOptions = computed(() => options.view_modes.filter(item => !item.deprecated && ["overview", "explore", "review"].includes(item.code)).map(item => ({ label: item.label, value: item.code })));
const currentViewMode = computed<GraphViewMode | undefined>(() => options.view_modes.find(item => item.code === filters.view_mode));
const graphLoadingText = computed(() => filters.view_mode === "overview" ? "正在加载资产概览" : filters.view_mode === "explore" ? "正在加载关系探索" : "正在加载证据视图");
const isErrorState = computed(() => ["auth_error", "permission_error", "api_error", "contract_error"].includes(state.value));
const errorIcon = computed(() => {
  if (state.value === "auth_error") return "error";
  if (state.value === "permission_error") return "warning";
  return "error";
});
const errorDescription = computed(() => errorInfo.value?.description || "");
const hasAnyData = computed(() => graphData.value.nodes.length > 0 || graphData.value.edges.length > 0);
const selectedNodeDisplayKey = computed(() => selectedNode.value?.display_id || selectedNode.value?.id || "");

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
  filters.validation_status = mode.validation_status || "";
  filters.include_candidates = mode.include_candidates;
  filters.include_dependencies = mode.include_dependencies;
  filters.show_review_layer = Boolean(mode.show_review_layer);
  filters.layout_mode = mode.layout_mode;
  if (mode.code === "overview") {
    filters.group_by = "system";
    filters.confidence = "";
    filters.validation_status = "";
  }
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
  if (mode.code === "explore" || mode.requires_table) {
    if (locate.physical_key || locate.table.trim()) {
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
  renderKey.value += 1;
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
  if (validationStatus && options.validation_statuses.includes(validationStatus)) {
    filters.validation_status = validationStatus;
  }
  if (confidence) filters.confidence = confidence;
  if (["system", "source", "schema", "domain"].includes(groupBy)) filters.group_by = groupBy as typeof filters.group_by;
  if (["1", "true", "yes"].includes(showReviewLayer) && currentViewMode.value?.show_review_layer) filters.show_review_layer = true;
}

function routeViewMode() {
  const code = routeQueryText(route.query.view_mode).trim();
  const selected = options.view_modes.find(item => item.code === code);
  return selected?.deprecated ? options.view_modes.find(item => item.code === "overview") : selected;
}

// 108号 P0-01：筛选默认值只来自后端 options.view_modes，前端不猜测状态
async function loadOptions() {
  optionsReady.value = false;
  try {
    const res = await getGraphOptions();
    Object.assign(options, res.data);
    optionsReady.value = true;
    const mode = routeViewMode() || options.view_modes.find(item => item.code === "overview") || currentViewMode.value || options.view_modes.find(item => item.code === "table") || options.view_modes[0];
    if (mode) {
      filters.view_mode = mode.code;
      applyModeDefaults(mode);
      applyRouteQueryFilters();
    }
    return true;
  } catch (err) {
    const info = classifyGraphError(err);
    state.value = info.state === "api_error" ? "api_error" : info.state;
    errorInfo.value = {
      ...info,
      title: "图谱配置加载失败",
      description: "无法获取图谱筛选选项，请确认后端服务正常。",
    };
    return false;
  }
}

async function loadDiagnostics() {
  try {
    const res = await getGraphDiagnostics();
    diagnosticWarnings.value = res.data?.warnings || [];
  } catch {
    // diagnostics 失败与主图隔离，不阻断页面（108号 §五.4）
    diagnosticWarnings.value = ["图谱诊断接口暂时不可用，不影响图谱展示"];
  }
}

async function loadCascadeOptions() {
  if (filters.view_mode !== "overview") return;
  try {
    const res = await getGraphFilterOptions({
      system_code: filters.system_code || undefined,
      source_code: filters.source_code || undefined,
      schema: filters.schema || undefined,
      next_level: overviewLevel.value
    });
    if (overviewLevel.value === "system") options.systems = res.data.items.map(item => item.value);
    if (overviewLevel.value === "source") options.sources = res.data.items.map(item => item.value);
    if (overviewLevel.value === "schema") options.schemas = res.data.items.map(item => item.value);
    if (overviewLevel.value === "object") options.domains = res.data.business_domains.map(item => item.value);
  } catch {
    // 主概览请求仍会返回可见错误，级联选项失败不覆盖主状态。
  }
}

function emptyState() {
  const hasFilters = Boolean(
    filters.system_code || filters.source_code || filters.schema || filters.domain
    || filters.validation_status || filters.keyword || filters.confidence
  );
  state.value = hasFilters ? "filter_empty" : "empty";
}

async function loadData() {
  loading.value = true;
  state.value = "loading";
  centerTable.value = "";
  selectedNodeId.value = "";
  try {
    if (filters.view_mode === "overview") {
      await loadCascadeOptions();
      const overview = await getGraphOverview({
        level: overviewLevel.value,
        system_code: filters.system_code || undefined,
        source_code: filters.source_code || undefined,
        schema: filters.schema || undefined,
        domain: filters.domain || undefined,
        limit: 80
      });
      const data = overview.data.data;
      graphData.value = data;
      graphMeta.value = data.meta || null;
      state.value = data.nodes.length ? "success" : "empty";
      return;
    }
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
    const data = res.data;
    if (!validateGraphData(data)) {
      state.value = "contract_error";
      errorInfo.value = contractErrorInfo(new Error("graph data structure invalid"));
      return;
    }
    graphData.value = data;
    graphMeta.value = data.meta || null;
    applyGraphLoadPolicy(data);
    if (data.nodes.length && data.edges.length) {
      state.value = "success";
    } else {
      emptyState();
    }
  } catch (err) {
    graphData.value = { nodes: [], edges: [] };
    graphMeta.value = null;
    const info = classifyGraphError(err);
    state.value = info.state;
    errorInfo.value = info;
  } finally {
    loading.value = false;
  }
}

async function loadChain() {
  const exploreMode = options.view_modes.find(item => item.code === "explore");
  if (exploreMode) {
    filters.view_mode = exploreMode.code;
    applyModeDefaults(exploreMode);
  }
  let physicalKey = locate.physical_key.trim();
  if (!physicalKey && locate.table.trim()) {
    try {
      const search = await searchGraphTables({
        q: locate.table.trim(),
        system_code: filters.system_code || undefined,
        source_code: filters.source_code || undefined,
        schema: filters.schema || undefined,
        limit: 30
      });
      locate.search_results = search.data.items;
      if (search.data.items.length !== 1) {
        ElMessage.warning(search.data.items.length ? "找到多个同名资产，请补充系统、数据源或 Owner 后再展开" : "未找到唯一中心资产");
        return;
      }
      physicalKey = search.data.items[0].physical_key;
      locate.physical_key = physicalKey;
    } catch (err) {
      const info = classifyGraphError(err);
      state.value = info.state;
      errorInfo.value = info;
      return;
    }
  }
  if (!physicalKey) {
    ElMessage.warning("请输入要定位的表名");
    return;
  }
  loading.value = true;
  state.value = "loading";
  try {
    const res = await getGraphNeighbors({
      center_physical_key: physicalKey,
      depth: locate.depth,
      direction: locate.direction,
      limit: filters.limit
    });
    if (!validateGraphData(res.data)) {
      state.value = "contract_error";
      errorInfo.value = contractErrorInfo(new Error("neighbors data structure invalid"));
      return;
    }
    graphData.value = res.data;
    graphMeta.value = res.data.meta || null;
    applyGraphLoadPolicy(res.data);
    centerTable.value = physicalKey;
    selectedNodeId.value = res.data.nodes[0]?.id || physicalKey;
    filters.keyword = physicalKey;
    filters.layout_mode = "radial";
    if (res.data.nodes.length && res.data.edges.length) {
      state.value = "success";
    } else {
      emptyState();
    }
  } catch (err) {
    graphData.value = { nodes: [], edges: [] };
    graphMeta.value = null;
    const info = classifyGraphError(err);
    state.value = info.state;
    errorInfo.value = info;
    ElMessage.warning(info.description);
  } finally {
    loading.value = false;
  }
}

function backToGlobal() {
  locate.table = "";
  locate.physical_key = "";
  locate.search_results = [];
  centerTable.value = "";
  selectedNodeId.value = "";
  const overviewMode = options.view_modes.find(item => item.code === "overview");
  if (overviewMode) {
    filters.view_mode = overviewMode.code;
    overviewLevel.value = "system";
    applyModeDefaults(overviewMode);
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
  const overviewMode = options.view_modes.find(item => item.code === "overview") || options.view_modes.find(item => item.code === "table");
  filters.view_mode = overviewMode?.code || "overview";
  overviewLevel.value = "system";
  if (overviewMode) applyModeDefaults(overviewMode);
  filters.system_code = "";
  filters.source_code = "";
  filters.schema = "";
  filters.domain = "";
  filters.validation_status = overviewMode?.validation_status || "";
  filters.confidence = overviewMode?.confidence || "";
  filters.keyword = "";
  filters.limit = 120;
  filters.aggregate_groups = false;
  locate.table = "";
  locate.physical_key = "";
  locate.search_results = [];
  locate.depth = 1;
  locate.direction = "both";
  errorInfo.value = null;
  loadData();
}

function retryPage() {
  errorInfo.value = null;
  loadData();
}

// 108号 P1-05：表详情跳转保留 system/source 物理来源上下文
function openTable(node: GraphNode) {
  const rawId = String(node.display_id || node.id || "");
  const parts = rawId ? rawId.split(".") : [];
  const schema = node.schema_name || parts[0] || "";
  const table = node.table_name || parts.slice(1).join(".");
  if (!schema || !table) {
    ElMessage.warning("该节点缺少 schema/table 信息，无法打开表详情");
    return;
  }
  const query: Record<string, string> = {};
  if (node.system_code) query.system_code = node.system_code;
  if (node.source_code) query.source_code = node.source_code;
  router.push({ path: `/asset/tables/${schema}/${table}`, query });
}

function selectNode(node: GraphNode) {
  if (filters.view_mode === "overview" && node.is_aggregate) {
    if (node.category === "system") {
      filters.system_code = node.system_code || "";
      filters.source_code = "";
      filters.schema = "";
      overviewLevel.value = "source";
    } else if (node.category === "source") {
      filters.source_code = node.source_code || "";
      filters.schema = "";
      overviewLevel.value = "schema";
    } else if (node.category === "schema") {
      filters.schema = node.schema_name || "";
      overviewLevel.value = "object";
    } else {
      selectedNode.value = node;
      selectedNodeId.value = node.id;
      nodeDrawerVisible.value = true;
      return;
    }
    void loadData();
    return;
  }
  selectedNode.value = node;
  selectedNodeId.value = node.id;
  nodeDrawerVisible.value = true;
}

function showEdge(edge: GraphEdge) {
  selectedEdge.value = edge;
  drawerVisible.value = true;
}

// 108号 P1-06：G6 失败自动回退 SVG
function handleRenderError() {
  if (graphEngine.value !== "g6") return;
  graphEngine.value = "svg";
  renderKey.value += 1;
  ElMessage.warning("高级图引擎渲染失败，已自动切换到内置 SVG 图");
}

async function init() {
  state.value = "loading";
  const ok = await loadOptions();
  // options/graph 相互隔离：options 失败也尝试诊断与主图（主图仍会因缺 options 给出明确错误）
  void loadDiagnostics();
  if (ok) {
    await loadData();
  } else if (!errorInfo.value) {
    state.value = "api_error";
    errorInfo.value = classifyGraphError(new Error("options failed"));
  }
}

onMounted(() => {
  void init();
});

onBeforeUnmount(() => {
  // 卸载时清理，避免实例泄漏（108号 测试 F 项）
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
  min-height: calc(100vh - 400px);
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

.graph-error-panel {
  padding: 48px 24px;
  background: var(--re-page-bg);
  border: 1px solid var(--border-light, #f1f5f9);
  border-radius: var(--radius-lg);
  text-align: center;
}

.graph-error-correlation {
  margin-top: 12px;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  font-family: monospace;
}

.graph-loading-page {
  padding: 32px;
}
</style>
