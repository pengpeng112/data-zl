<template>
  <div class="asset-graph-page">
    <el-card shadow="never">
      <div class="filter-bar">
        <el-select
          v-model="filters.schema"
          placeholder="Schema"
          clearable
          style="width: 110px"
          @change="loadData"
        >
          <el-option
            v-for="s in options.schemas"
            :key="s"
            :label="s"
            :value="s"
          />
        </el-select>
        <el-select
          v-model="filters.domain"
          placeholder="业务域"
          clearable
          style="width: 130px; margin-left: 8px"
          @change="loadData"
        >
          <el-option
            v-for="d in options.domains"
            :key="d"
            :label="d"
            :value="d"
          />
        </el-select>
        <el-select
          v-model="filters.validation_status"
          placeholder="验证状态"
          clearable
          style="width: 110px; margin-left: 8px"
          @change="loadData"
        >
          <el-option
            v-for="s in options.validation_statuses"
            :key="s"
            :label="statusLabel(s)"
            :value="s"
          />
        </el-select>
        <el-select
          v-model="filters.confidence"
          placeholder="置信度"
          clearable
          style="width: 90px; margin-left: 8px"
          @change="loadData"
        >
          <el-option
            v-for="c in options.confidences"
            :key="c"
            :label="c"
            :value="c"
          />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="输入表名，如 PAT_VISIT"
          clearable
          style="width: 200px; margin-left: 8px"
          @keyup.enter="loadData"
        />
        <el-button
          type="primary"
          :loading="loading"
          style="margin-left: 8px"
          @click="loadData"
          >查询</el-button
        >
        <el-button style="margin-left: 4px" @click="setVerified"
          >只看已验证</el-button
        >
        <el-button style="margin-left: 4px" @click="resetFilters"
          >重置</el-button
        >
        <el-checkbox
          v-model="filters.include_candidates"
          style="margin-left: 12px"
          @change="loadData"
        >
          候选关系
        </el-checkbox>
        <el-checkbox
          v-model="filters.include_dependencies"
          style="margin-left: 8px"
          @change="loadData"
        >
          视图依赖
        </el-checkbox>
      </div>
      <div v-if="!loading && graphData.edges.length > 0" class="stats-bar">
        <el-tag>节点 {{ graphData.nodes.length }}</el-tag>
        <el-tag type="primary">边 {{ graphData.edges.length }}</el-tag>
        <el-tag type="success">已验证 {{ verifiedCount }}</el-tag>
        <el-tag v-if="candidateCount > 0" type="warning"
          >候选 {{ candidateCount }}</el-tag
        >
        <el-tag v-if="depCount > 0" type="info">依赖 {{ depCount }}</el-tag>
        <el-tag v-if="needsSplitCount > 0" type="danger"
          >需拆分 {{ needsSplitCount }}</el-tag
        >
      </div>
    </el-card>

    <div v-loading="loading" style="margin-top: 8px">
      <RelationGraph
        v-if="graphData.nodes.length > 0"
        :nodes="graphData.nodes"
        :edges="graphData.edges"
        height="calc(100vh - 290px)"
        @node-click="goTable"
        @edge-click="showEdge"
      />
      <el-empty v-else description="无匹配关系" />
    </div>

    <el-drawer v-model="drawerVisible" title="关系详情" size="500px">
      <el-descriptions v-if="selectedEdge" :column="1" border size="small">
        <el-descriptions-item label="rel_id">{{
          selectedEdge.rel_id
        }}</el-descriptions-item>
        <el-descriptions-item label="来源表">{{
          selectedEdge.source
        }}</el-descriptions-item>
        <el-descriptions-item label="目标表">{{
          selectedEdge.target
        }}</el-descriptions-item>
        <el-descriptions-item label="关联条件">{{
          selectedEdge.join_condition || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="来源字段">{{
          selectedEdge.from_columns || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="目标字段">{{
          selectedEdge.to_columns || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="基数">{{
          selectedEdge.cardinality || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="置信度">{{
          selectedEdge.confidence || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="验证等级">{{
          selectedEdge.validation_level || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="指标">{{
          selectedEdge.validation_metrics || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{
          selectedEdge.note || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="验证备注">{{
          selectedEdge.validation_note || "-"
        }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import {
  getGraph,
  getGraphOptions,
  type GraphData,
  type GraphEdge,
  type GraphNode,
  type GraphOptionsData
} from "@/api/asset";

const router = useRouter();
const loading = ref(false);
const drawerVisible = ref(false);
const selectedEdge = ref<GraphEdge | null>(null);
const graphData = ref<GraphData>({ nodes: [], edges: [] });
const options = reactive<GraphOptionsData>({
  schemas: [],
  domains: [],
  validation_statuses: [],
  confidences: [],
  relation_types: []
});

const filters = reactive({
  schema: "",
  domain: "",
  validation_status: "",
  confidence: "",
  keyword: "",
  limit: 80,
  include_candidates: false,
  include_dependencies: false
});

const verifiedCount = computed(
  () =>
    graphData.value.edges.filter(e => e.validation_status === "verified").length
);
const needsSplitCount = computed(
  () =>
    graphData.value.edges.filter(e => e.validation_status === "needs_split")
      .length
);
const candidateCount = computed(
  () =>
    graphData.value.edges.filter(e => e.relation_type === "candidate").length
);
const depCount = computed(
  () =>
    graphData.value.edges.filter(e => e.relation_type === "dependency").length
);

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    verified: "已验证",
    bounded: "有界",
    needs_split: "需拆分",
    not_tested: "未测试"
  };
  return map[s] || s;
}

async function loadOptions() {
  try {
    const res = await getGraphOptions();
    Object.assign(options, res.data);
  } catch {
    /* */
  }
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
  } catch {
    graphData.value = { nodes: [], edges: [] };
  } finally {
    loading.value = false;
  }
}

function setVerified() {
  filters.validation_status = "verified";
  loadData();
}

function resetFilters() {
  filters.schema = "";
  filters.domain = "";
  filters.validation_status = "";
  filters.confidence = "";
  filters.keyword = "";
  filters.limit = 80;
  loadData();
}

function goTable(node: GraphNode) {
  const parts = node.id.split(".");
  if (parts.length >= 2)
    router.push(`/asset/tables/${parts[0]}/${parts.slice(1).join(".")}`);
}

function showEdge(edge: GraphEdge) {
  selectedEdge.value = edge;
  drawerVisible.value = true;
}

onMounted(async () => {
  await loadOptions();
  loadData();
});
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.stats-bar {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
