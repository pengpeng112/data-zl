<template>
  <div class="asset-relations">
    <RePageHeader title="关系路径查询" subtitle="查询两张表之间的可达关系路径，查看每一跳的关联条件、验证等级和指标证据。">
      <template #icon><RelationIcon /></template>
    </RePageHeader>

    <el-card shadow="never" class="query-card">
      <ReToolbar title="查询条件">
        <div class="filter-bar">
          <el-input v-model="fromTable" placeholder="来源表 (如 HIS.PAT_VISIT)" clearable />
          <span class="arrow-text">→</span>
          <el-input v-model="toTable" placeholder="目标表 (如 HIS.PAT_MASTER_INDEX)" clearable />
          <el-button type="primary" :loading="loading" @click="doQuery">查询路径</el-button>
        </div>
      </ReToolbar>
      <div class="quick-examples">
        <span>快捷示例：</span>
        <el-button
          v-for="ex in examples"
          :key="ex.label"
          size="small"
          text
          type="primary"
          @click="setExample(ex)"
        >
          {{ ex.label }}
        </el-button>
      </div>
    </el-card>

    <el-card v-if="result" shadow="never" class="result-card">
      <template #header>
        结果：{{ result.from }} → {{ result.to }}
        <el-tag v-if="result.path" class="result-tag">{{ result.hops.length }} 跳</el-tag>
        <el-tag v-else type="danger" class="result-tag">未找到路径</el-tag>
      </template>

      <div v-if="result.path && pathGraph.nodes.length > 0">
        <RelationGraph
          :nodes="pathGraph.nodes"
          :edges="pathGraph.edges"
          height="420px"
          @node-click="goTable"
          @edge-click="showEdge"
        />
      </div>

      <div v-if="result.path" class="path-display">
        <div v-for="(hop, idx) in result.hops" :key="idx" class="hop-card">
          <div class="hop-header">第 {{ idx + 1 }} 跳：{{ hop.from }} → {{ hop.to }}</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="关联条件">{{ hop.join_condition || "-" }}</el-descriptions-item>
            <el-descriptions-item label="基数">{{ hop.cardinality || "-" }}</el-descriptions-item>
            <el-descriptions-item label="置信度">{{ hop.confidence || "-" }}</el-descriptions-item>
            <el-descriptions-item label="验证等级">{{ hop.validation_level || "-" }}</el-descriptions-item>
            <el-descriptions-item label="验证状态">
              <el-tag :type="relationStatusTag(hop.validation_status)" size="small">
                {{ hop.validation_status || "-" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="指标">{{ hop.validation_metrics || "-" }}</el-descriptions-item>
            <el-descriptions-item label="来源字段">{{ hop.from_columns || "-" }}</el-descriptions-item>
            <el-descriptions-item label="目标字段">{{ hop.to_columns || "-" }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{ hop.note || "-" }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <ReEmptyState v-else title="未找到关联路径" description="当前关系包中没有发现这两张表之间的可达路径。" />
    </el-card>

    <ReDetailDrawer
      v-model="drawerVisible"
      title="关系详情"
      :subtitle="selectedEdge ? `${selectedEdge.source} → ${selectedEdge.target}` : ''"
      size="560px"
    >
      <el-descriptions v-if="selectedEdge" :column="1" border size="small">
        <el-descriptions-item label="来源">{{ selectedEdge.source }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{ selectedEdge.target }}</el-descriptions-item>
        <el-descriptions-item label="关联条件">{{ selectedEdge.join_condition || "-" }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ selectedEdge.validation_status || "-" }}</el-descriptions-item>
        <el-descriptions-item label="指标">{{ selectedEdge.validation_metrics || "-" }}</el-descriptions-item>
      </el-descriptions>
    </ReDetailDrawer>
  </div>
</template>

<script setup lang="ts">
import ReDetailDrawer from "@/components/ReDetailDrawer/index.vue";
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import {
  getRelationPath,
  type GraphData,
  type GraphEdge,
  type GraphNode,
  type PathResult
} from "@/api/asset";
import RelationIcon from "~icons/ri/git-branch-line";

const router = useRouter();
const route = useRoute();
const fromTable = ref("");
const toTable = ref("");
const loading = ref(false);
const result = ref<PathResult | null>(null);
const drawerVisible = ref(false);
const selectedEdge = ref<GraphEdge | null>(null);

const examples = [
  { label: "PAT_VISIT → PAT_MASTER_INDEX", from: "HIS.PAT_VISIT", to: "HIS.PAT_MASTER_INDEX" },
  { label: "PAT_VISIT → LAB_TEST_MASTER", from: "HIS.PAT_VISIT", to: "HIS.LAB_TEST_MASTER" },
  { label: "PAT_VISIT → EXAM_MASTER", from: "HIS.PAT_VISIT", to: "HIS.EXAM_MASTER" }
];

const pathGraph = computed<GraphData>(() => {
  if (!result.value?.path || result.value.path.length < 2) return { nodes: [], edges: [] };
  const nodeSet = new Set<string>();
  const nodes: GraphNode[] = [];
  for (const tableName of result.value.path) {
    if (!nodeSet.has(tableName)) {
      nodeSet.add(tableName);
      const parts = tableName.split(".");
      nodes.push({
        id: tableName,
        label: parts.length > 1 ? parts[1] : tableName,
        schema_name: parts.length > 1 ? parts[0] : "?",
        table_name: parts.length > 1 ? parts[1] : tableName,
        category: parts.length > 1 ? parts[0] : "?"
      });
    }
  }
  const edges: GraphEdge[] = result.value.hops.map((hop, index) => ({
    id: `${hop.from}->${hop.to}#${index}`,
    source: hop.from,
    target: hop.to,
    label: hop.join_condition,
    join_condition: hop.join_condition,
    validation_status: hop.validation_status,
    validation_metrics: hop.validation_metrics
  }));
  return { nodes, edges };
});

function relationStatusTag(status?: string | null): "success" | "warning" | "info" {
  if (status === "verified") return "success";
  if (status === "bounded") return "warning";
  return "info";
}

function setExample(example: { from: string; to: string }) {
  fromTable.value = example.from;
  toTable.value = example.to;
  doQuery();
}

async function doQuery() {
  if (!fromTable.value || !toTable.value) return;
  loading.value = true;
  try {
    const res = await getRelationPath(fromTable.value, toTable.value);
    result.value = res.data;
  } catch {
    result.value = null;
  } finally {
    loading.value = false;
  }
}

function goTable(node: GraphNode) {
  const parts = node.id.split(".");
  if (parts.length >= 2) router.push(`/asset/tables/${parts[0]}/${parts.slice(1).join(".")}`);
}

function showEdge(edge: GraphEdge) {
  selectedEdge.value = edge;
  drawerVisible.value = true;
}

onMounted(() => {
  const from = String(route.query.from || "").trim();
  const to = String(route.query.to || "").trim();
  if (from && to) {
    fromTable.value = from;
    toTable.value = to;
    void doQuery();
  }
});
</script>

<style scoped lang="scss">
.asset-relations {
  padding: 4px;
}

.query-card,
.result-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
}

.result-card {
  margin-top: 16px;
}

.result-tag {
  margin-left: 12px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  width: 100%;
}

.filter-bar :deep(.el-input) {
  width: 280px;
}

.arrow-text {
  color: var(--text-secondary);
}

.quick-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 10px;

  span {
    font-size: 12px;
    color: var(--text-secondary);
  }
}

.path-display {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.hop-card {
  padding: 14px;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
}

.hop-header {
  margin-bottom: 10px;
  font-weight: 700;
  color: var(--primary-600);
}

@media (max-width: 760px) {
  .filter-bar :deep(.el-input) {
    width: 100%;
  }
}
</style>
