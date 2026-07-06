<template>
  <div class="asset-graph-page">
    <el-card shadow="never" class="toolbar-card">
      <div class="filter-grid">
        <el-select v-model="filters.schema" placeholder="表空间" clearable filterable @change="loadData">
          <el-option v-for="item in options.schemas" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.domain" placeholder="业务域" clearable filterable @change="loadData">
          <el-option v-for="item in options.domains" :key="item" :label="item" :value="item" />
        </el-select>
        <el-select v-model="filters.validation_status" placeholder="验证状态" clearable @change="loadData">
          <el-option v-for="item in options.validation_statuses" :key="item" :label="statusLabel(item)" :value="item" />
        </el-select>
        <el-select v-model="filters.confidence" placeholder="关系级别" clearable @change="loadData">
          <el-option v-for="item in options.confidences" :key="item" :label="item" :value="item" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索表名或关系端点" clearable @keyup.enter="loadData" />
        <el-input-number v-model="filters.limit" :min="20" :max="500" :step="20" controls-position="right" />
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
      <div class="switch-row">
        <el-checkbox v-model="filters.include_candidates" @change="loadData">候选关系</el-checkbox>
        <el-checkbox v-model="filters.include_dependencies" @change="loadData">视图依赖</el-checkbox>
        <el-button text type="success" @click="showSamplePass">只看通过关系</el-button>
      </div>
      <div class="stats-row">
        <el-tag>节点 {{ graphData.nodes.length }}</el-tag>
        <el-tag type="primary">关系 {{ graphData.edges.length }}</el-tag>
        <el-tag type="success">通过 {{ passCount }}</el-tag>
        <el-tag type="warning">候选 {{ candidateCount }}</el-tag>
        <el-tag type="info">依赖 {{ dependencyCount }}</el-tag>
      </div>
    </el-card>

    <div v-loading="loading" class="graph-wrap">
      <RelationGraph
        v-if="graphData.nodes.length"
        :nodes="graphData.nodes"
        :edges="graphData.edges"
        height="calc(100vh - 280px)"
        @node-click="goTable"
        @edge-click="showEdge"
      />
      <el-empty v-else description="暂无可展示关系" />
    </div>

    <el-drawer v-model="drawerVisible" title="关系详情" size="560px">
      <el-descriptions v-if="selectedEdge" :column="1" border size="small">
        <el-descriptions-item label="来源表">{{ selectedEdge.source }}</el-descriptions-item>
        <el-descriptions-item label="来源字段">{{ selectedEdge.from_columns || '-' }}</el-descriptions-item>
        <el-descriptions-item label="目标表">{{ selectedEdge.target }}</el-descriptions-item>
        <el-descriptions-item label="目标字段">{{ selectedEdge.to_columns || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关系类型">{{ selectedEdge.relation_type || 'formal' }}</el-descriptions-item>
        <el-descriptions-item label="关系级别">{{ selectedEdge.confidence || '-' }}</el-descriptions-item>
        <el-descriptions-item label="验证状态">
          <el-tag size="small" :type="statusTagType(selectedEdge.validation_status)">{{ statusLabel(selectedEdge.validation_status || '') }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="验证级别">{{ selectedEdge.validation_level || '-' }}</el-descriptions-item>
        <el-descriptions-item label="关联条件">{{ selectedEdge.join_condition || '-' }}</el-descriptions-item>
        <el-descriptions-item label="验证指标">{{ selectedEdge.validation_metrics || '-' }}</el-descriptions-item>
        <el-descriptions-item label="依据/备注">{{ selectedEdge.note || '-' }}</el-descriptions-item>
        <el-descriptions-item label="风险说明">{{ selectedEdge.validation_note || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import { getGraph, getGraphOptions, type GraphData, type GraphEdge, type GraphNode, type GraphOptionsData } from "@/api/asset";

const router = useRouter();
const loading = ref(false);
const drawerVisible = ref(false);
const selectedEdge = ref<GraphEdge | null>(null);
const graphData = ref<GraphData>({ nodes: [], edges: [] });
const options = reactive<GraphOptionsData>({ schemas: [], domains: [], validation_statuses: [], confidences: [], relation_types: [] });

const filters = reactive({
  schema: "",
  domain: "",
  validation_status: "",
  confidence: "A",
  keyword: "",
  limit: 120,
  include_candidates: false,
  include_dependencies: false
});

const passCount = computed(() => graphData.value.edges.filter(edge => ["sample_pass", "verified"].includes(edge.validation_status || "")).length);
const candidateCount = computed(() => graphData.value.edges.filter(edge => edge.relation_type === "candidate").length);
const dependencyCount = computed(() => graphData.value.edges.filter(edge => edge.relation_type === "dependency").length);

function statusLabel(status: string) {
  const map: Record<string, string> = {
    sample_pass: "样本通过",
    verified: "已审核",
    manual_reviewed: "人工复核",
    bounded: "有边界",
    needs_split: "需拆分",
    not_tested: "未验证",
    rejected: "已拒绝"
  };
  return map[status] || status || "-";
}

function statusTagType(status?: string | null) {
  if (["sample_pass", "verified"].includes(status || "")) return "success";
  if (["bounded", "manual_reviewed"].includes(status || "")) return "warning";
  if (["needs_split", "rejected"].includes(status || "")) return "danger";
  return "info";
}

async function loadOptions() {
  const res = await getGraphOptions();
  Object.assign(options, res.data);
}

async function loadData() {
  loading.value = true;
  try {
    const res = await getGraph({
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
  } finally {
    loading.value = false;
  }
}

function showSamplePass() {
  filters.validation_status = "sample_pass";
  filters.confidence = "A";
  loadData();
}

function resetFilters() {
  filters.schema = "";
  filters.domain = "";
  filters.validation_status = "";
  filters.confidence = "A";
  filters.keyword = "";
  filters.limit = 120;
  filters.include_candidates = false;
  filters.include_dependencies = false;
  loadData();
}

function goTable(node: GraphNode) {
  const parts = node.id.split(".");
  if (parts.length >= 2) router.push(`/asset/tables/${parts[0]}/${parts.slice(1).join(".")}`);
}

function showEdge(edge: GraphEdge) {
  selectedEdge.value = edge;
  drawerVisible.value = true;
}

onMounted(async () => {
  await loadOptions();
  await loadData();
});
</script>

<style scoped>
.asset-graph-page { min-height: calc(100vh - 120px); }
.toolbar-card { margin-bottom: 10px; }
.filter-grid { display: grid; grid-template-columns: 130px 150px 140px 110px minmax(180px, 1fr) 110px 76px 76px; gap: 8px; align-items: center; }
.switch-row { display: flex; align-items: center; gap: 14px; margin-top: 10px; }
.stats-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.graph-wrap { min-height: calc(100vh - 280px); }
@media (max-width: 1200px) { .filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>