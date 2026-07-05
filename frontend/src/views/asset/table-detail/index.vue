<template>
  <div v-loading="loading" class="asset-table-detail">
    <el-card v-if="detail" shadow="never">
      <template #header>
        <el-page-header
          :content="`${detail.schema_name}.${detail.table_name}`"
          @back="goBack"
        />
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="Schema">{{
          detail.schema_name
        }}</el-descriptions-item>
        <el-descriptions-item label="表名">{{
          detail.table_name
        }}</el-descriptions-item>
        <el-descriptions-item label="业务域">{{
          detail.domain || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="注释" :span="2">{{
          detail.comment || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="字段数">{{
          detail.column_count_actual ?? detail.column_count
        }}</el-descriptions-item>
        <el-descriptions-item label="关联关系">{{
          detail.relation_count ?? 0
        }}</el-descriptions-item>
        <el-descriptions-item label="行数">{{
          detail.row_count_stats || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="置信度">{{
          detail.confidence || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="主键">{{
          detail.pk || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{
          detail.source || "-"
        }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 12px">
        <el-button type="primary" @click="openAnnotDialog">编辑注释</el-button>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>当前表关系图</template>
      <RelationGraph
        v-if="neighborGraph.nodes.length > 0 && !neighborLoading"
        :nodes="neighborGraph.nodes"
        :edges="neighborGraph.edges"
        height="420px"
        :center-table="`${schema}.${table}`"
        @node-click="goNode"
        @edge-click="showEdge"
      />
      <el-empty
        v-if="neighborGraph.nodes.length === 0 && !neighborLoading"
        description="暂无直接关联"
        :image-size="80"
      />
      <div v-if="neighborLoading" style="text-align: center; padding: 40px">
        加载中...
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        字段列表 ({{ filteredColumns.length }})
        <span
          v-if="filteredColumns.length !== columns.length"
          style="color: #909399; font-size: 12px"
        >
          / 共 {{ columns.length }}
        </span>
      </template>
      <div style="margin-bottom: 8px; display: flex; gap: 8px">
        <el-input
          v-model="colFilter.keyword"
          placeholder="搜索字段名或注释"
          clearable
          style="width: 240px"
        />
        <el-select
          v-model="colFilter.nullable"
          placeholder="可空"
          clearable
          style="width: 90px"
        >
          <el-option label="是" value="Y" />
          <el-option label="否" value="N" />
        </el-select>
      </div>
      <el-table :data="filteredColumns" stripe max-height="400">
        <el-table-column prop="column_id" label="#" width="60" align="center" />
        <el-table-column
          prop="column_name"
          label="字段名"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column prop="data_type" label="类型" width="120" />
        <el-table-column prop="length" label="长度" width="80" align="center" />
        <el-table-column prop="nullable" label="可空" width="70" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.nullable === 'Y' ? 'success' : 'info'"
              size="small"
            >
              {{ row.nullable === "Y" ? "是" : "否" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="comment"
          label="注释"
          min-width="200"
          show-overflow-tooltip
        />
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>关联关系 ({{ relations.length }})</template>
      <el-table :data="relations" stripe>
        <el-table-column
          prop="from_table"
          label="来源表"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column
          prop="to_table"
          label="目标表"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column
          prop="join_condition"
          label="关联条件"
          min-width="280"
          show-overflow-tooltip
        />
        <el-table-column
          prop="cardinality"
          label="基数"
          width="100"
          align="center"
        />
        <el-table-column
          prop="confidence"
          label="置信度"
          width="80"
          align="center"
        />
        <el-table-column
          prop="validation_status"
          label="验证状态"
          width="100"
          align="center"
        >
          <template #default="{ row }">
            <el-tag
              :type="
                row.validation_status === 'verified'
                  ? 'success'
                  : row.validation_status === 'bounded'
                    ? 'warning'
                    : 'info'
              "
              size="small"
            >
              {{ row.validation_status || "-" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="validation_metrics"
          label="指标"
          width="150"
          show-overflow-tooltip
        />
      </el-table>
    </el-card>

    <el-drawer v-model="edgeDrawerVisible" title="关系详情" size="500px">
      <el-descriptions
        v-if="selectedEdgeDetail"
        :column="1"
        border
        size="small"
      >
        <el-descriptions-item label="来源">{{
          selectedEdgeDetail.source
        }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{
          selectedEdgeDetail.target
        }}</el-descriptions-item>
        <el-descriptions-item label="关联条件">{{
          selectedEdgeDetail.join_condition || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="基数">{{
          selectedEdgeDetail.cardinality || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="置信度">{{
          selectedEdgeDetail.confidence || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="验证等级">{{
          selectedEdgeDetail.validation_level || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="验证状态">
          <el-tag size="small">{{
            selectedEdgeDetail.validation_status || "-"
          }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="指标">{{
          selectedEdgeDetail.validation_metrics || "-"
        }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{
          selectedEdgeDetail.note || "-"
        }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>

    <el-dialog v-model="annotDialogVisible" title="编辑注释" width="750px">
      <el-form label-width="100px" size="small">
        <el-form-item label="中文表名">
          <el-input v-model="annotForm.table_name_cn" />
        </el-form-item>
        <el-form-item label="业务描述">
          <el-input
            v-model="annotForm.business_desc_cn"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item label="表角色">
          <el-input v-model="annotForm.table_role" />
        </el-form-item>
      </el-form>
      <div style="text-align: right; margin-bottom: 12px">
        <el-button type="primary" @click="saveTableAnnot">保存表注释</el-button>
      </div>
      <el-divider />
      <div
        v-for="col in columns"
        :key="col.column_id"
        style="margin-bottom: 10px; padding: 8px; border: 1px solid #ebeef5; border-radius: 4px"
      >
        <div style="font-weight: 600; margin-bottom: 6px">
          {{ col.column_name }}
        </div>
        <el-row :gutter="8">
          <el-col :span="8">
            <el-input
              v-model="columnAnnotForm[col.column_id].column_name_cn"
              placeholder="中文名"
              size="small"
            />
          </el-col>
          <el-col :span="8">
            <el-input
              v-model="columnAnnotForm[col.column_id].business_desc_cn"
              placeholder="业务描述"
              size="small"
            />
          </el-col>
          <el-col :span="8">
            <el-input
              v-model="columnAnnotForm[col.column_id].value_desc_cn"
              placeholder="值域描述"
              size="small"
            />
          </el-col>
        </el-row>
        <div style="text-align: right; margin-top: 6px">
          <el-button
            size="small"
            type="primary"
            @click="saveColumnAnnot(col.column_id)"
          >
            保存
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import { http } from "@/utils/http";
import {
  getTableDetail,
  getTableColumns,
  getTableRelations,
  getGraphNeighbors,
  type TableDetail,
  type ColumnInfo,
  type RelationInfo,
  type GraphData,
  type GraphNode,
  type GraphEdge
} from "@/api/asset";

const route = useRoute();
const router = useRouter();
const schema = route.params.schema as string;
const table = route.params.table as string;
const loading = ref(true);

const detail = ref<TableDetail | null>(null);
const columns = ref<ColumnInfo[]>([]);
const relations = ref<RelationInfo[]>([]);
const neighborGraph = ref<GraphData>({ nodes: [], edges: [] });
const neighborLoading = ref(true);
const edgeDrawerVisible = ref(false);
const selectedEdgeDetail = ref<GraphEdge | null>(null);

const colFilter = reactive({ keyword: "", nullable: "" });

const annotDialogVisible = ref(false);
const annotForm = reactive({
  table_name_cn: "",
  business_desc_cn: "",
  table_role: ""
});
const columnAnnotForm = ref<Record<number, { column_name_cn: string; business_desc_cn: string; value_desc_cn: string }>>({});

const filteredColumns = computed(() => {
  let list = columns.value;
  if (colFilter.keyword) {
    const kw = colFilter.keyword.toLowerCase();
    list = list.filter(
      c =>
        (c.column_name || "").toLowerCase().includes(kw) ||
        (c.comment || "").toLowerCase().includes(kw)
    );
  }
  if (colFilter.nullable) {
    list = list.filter(c => c.nullable === colFilter.nullable);
  }
  return list;
});

async function loadAll() {
  loading.value = true;
  neighborLoading.value = true;
  try {
    const [dRes, cRes, rRes] = await Promise.all([
      getTableDetail(schema, table),
      getTableColumns(schema, table),
      getTableRelations(schema, table)
    ]);
    detail.value = dRes.data;
    columns.value = cRes.data;
    relations.value = rRes.data;
  } catch {
    /* */
  }

  try {
    const nRes = await getGraphNeighbors({
      table: `${schema}.${table}`,
      depth: 1,
      direction: "both"
    });
    neighborGraph.value = nRes.data;
  } catch {
    neighborGraph.value = { nodes: [], edges: [] };
  } finally {
    neighborLoading.value = false;
    loading.value = false;
  }
}

function goNode(node: GraphNode) {
  const parts = node.id.split(".");
  if (parts.length >= 2) {
    router.replace(`/asset/tables/${parts[0]}/${parts.slice(1).join(".")}`);
    loadAll();
  }
}

function showEdge(edge: GraphEdge) {
  selectedEdgeDetail.value = edge;
  edgeDrawerVisible.value = true;
}

function goBack() {
  router.push("/asset/tables");
}

function openAnnotDialog() {
  annotForm.table_name_cn = (detail.value as any)?.table_name_cn || "";
  annotForm.business_desc_cn = (detail.value as any)?.business_desc_cn || "";
  annotForm.table_role = (detail.value as any)?.table_role || "";

  const map: Record<number, { column_name_cn: string; business_desc_cn: string; value_desc_cn: string }> = {};
  for (const col of columns.value) {
    map[col.column_id] = {
      column_name_cn: (col as any).column_name_cn || "",
      business_desc_cn: (col as any).business_desc_cn || "",
      value_desc_cn: (col as any).value_desc_cn || ""
    };
  }
  columnAnnotForm.value = map;
  annotDialogVisible.value = true;
}

function saveTableAnnot() {
  http
    .request("patch", `/api/v1/tables/${(detail.value as any)?.id}/annotation`, {
      data: annotForm
    })
    .then(() => {
      ElMessage.success("表注释已保存");
      annotDialogVisible.value = false;
      loadAll();
    })
    .catch(() => {});
}

function saveColumnAnnot(colId: number) {
  const form = columnAnnotForm.value[colId];
  if (!form) return;
  http
    .request("patch", `/api/v1/columns/${colId}/annotation`, {
      data: form
    })
    .then(() => {
      ElMessage.success("字段注释已保存");
    })
    .catch(() => {});
}

onMounted(loadAll);
</script>
