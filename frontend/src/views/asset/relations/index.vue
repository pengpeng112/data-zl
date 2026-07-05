<template>
  <div class="asset-relations">
    <el-card shadow="never">
      <template #header>关系路径查询</template>
      <div class="filter-bar">
        <el-input
          v-model="fromTable"
          placeholder="来源表 (如 HIS.PAT_VISIT)"
          clearable
          style="width: 280px"
        />
        <span style="margin: 0 12px">→</span>
        <el-input
          v-model="toTable"
          placeholder="目标表 (如 HIS.PAT_MASTER_INDEX)"
          clearable
          style="width: 280px"
        />
        <el-button
          type="primary"
          :loading="loading"
          style="margin-left: 12px"
          @click="doQuery"
        >
          查询路径
        </el-button>
      </div>
      <div style="margin-top: 8px">
        <span style="font-size: 12px; color: #909399">快捷示例：</span>
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

    <el-card v-if="result" shadow="never" style="margin-top: 16px">
      <template #header>
        结果：{{ result.from }} → {{ result.to }}
        <el-tag v-if="result.path" style="margin-left: 12px">
          {{ result.hops.length }} 跳
        </el-tag>
        <el-tag v-else type="danger">未找到路径</el-tag>
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

      <div v-if="result.path" class="path-display" style="margin-top: 12px">
        <div v-for="(hop, idx) in result.hops" :key="idx" class="hop-card">
          <div class="hop-header">
            第 {{ idx + 1 }} 跳：{{ hop.from }} → {{ hop.to }}
          </div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="关联条件">{{
              hop.join_condition || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="基数">{{
              hop.cardinality || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="置信度">{{
              hop.confidence || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="验证等级">{{
              hop.validation_level || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="验证状态">
              <el-tag
                :type="
                  hop.validation_status === 'verified'
                    ? 'success'
                    : hop.validation_status === 'bounded'
                      ? 'warning'
                      : 'info'
                "
                size="small"
              >
                {{ hop.validation_status || "-" }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="指标">{{
              hop.validation_metrics || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="来源字段">{{
              hop.from_columns || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="目标字段">{{
              hop.to_columns || "-"
            }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="2">{{
              hop.note || "-"
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <el-empty v-else description="两张表之间未找到关联路径" />
    </el-card>

    <el-drawer v-model="drawerVisible" title="关系详情" size="500px">
      <el-descriptions v-if="selectedEdge" :column="1" border size="small">
        <el-descriptions-item label="来源">{{
          selectedEdge.source
        }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{
          selectedEdge.target
        }}</el-descriptions-item>
        <el-descriptions-item label="关联条件">{{
          selectedEdge.join_condition || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{
          selectedEdge.validation_status || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="指标">{{
          selectedEdge.validation_metrics || "-"
        }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import {
  getRelationPath,
  type PathResult,
  type GraphData,
  type GraphNode,
  type GraphEdge
} from "@/api/asset";

const router = useRouter();
const fromTable = ref("");
const toTable = ref("");
const loading = ref(false);
const result = ref<PathResult | null>(null);
const drawerVisible = ref(false);
const selectedEdge = ref<GraphEdge | null>(null);

const examples = [
  {
    label: "PAT_VISIT → PAT_MASTER_INDEX",
    from: "HIS.PAT_VISIT",
    to: "HIS.PAT_MASTER_INDEX"
  },
  {
    label: "PAT_VISIT → LAB_TEST_MASTER",
    from: "HIS.PAT_VISIT",
    to: "HIS.LAB_TEST_MASTER"
  },
  {
    label: "PAT_VISIT → EXAM_MASTER",
    from: "HIS.PAT_VISIT",
    to: "HIS.EXAM_MASTER"
  }
];

const pathGraph = computed<GraphData>(() => {
  if (!result.value?.path || result.value.path.length < 2) {
    return { nodes: [], edges: [] };
  }
  const path = result.value.path;
  const hops = result.value.hops;
  const nodeSet = new Set<string>();
  const nodes: GraphNode[] = [];
  for (const tableName of path) {
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
  const edges: GraphEdge[] = hops.map((h, i) => ({
    id: `${h.from}->${h.to}#${i}`,
    source: h.from,
    target: h.to,
    label: h.join_condition,
    join_condition: h.join_condition,
    validation_status: h.validation_status,
    validation_metrics: h.validation_metrics
  }));
  return { nodes, edges };
});

function setExample(ex: { from: string; to: string }) {
  fromTable.value = ex.from;
  toTable.value = ex.to;
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
  if (parts.length >= 2) {
    router.push(`/asset/tables/${parts[0]}/${parts.slice(1).join(".")}`);
  }
}

function showEdge(edge: GraphEdge) {
  selectedEdge.value = edge;
  drawerVisible.value = true;
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
.hop-card {
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.hop-header {
  font-weight: 600;
  margin-bottom: 8px;
  color: #409eff;
}
</style>
