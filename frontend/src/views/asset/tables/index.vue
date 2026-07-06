<template>
  <div class="asset-tables-page">
    <div class="layout-grid">
      <el-card class="tree-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>资产目录</span>
            <el-button text type="primary" @click="loadTree">刷新</el-button>
          </div>
        </template>
        <el-input
          v-model="treeKeyword"
          clearable
          placeholder="搜索系统、库名、Schema"
          class="tree-search"
        />
        <el-tree
          v-loading="treeLoading"
          :data="treeData"
          node-key="id"
          :props="treeProps"
          :filter-node-method="filterTreeNode"
          default-expand-all
          highlight-current
          @node-click="handleTreeClick"
          ref="treeRef"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-tag v-if="data.kind" size="small" :type="kindTagType(data.kind)">{{ kindLabel(data.kind) }}</el-tag>
              <span class="tree-label">{{ data.label }}</span>
              <span v-if="data.count !== undefined" class="tree-count">{{ data.count }}</span>
            </span>
          </template>
        </el-tree>
      </el-card>

      <div class="content-panel">
        <el-card shadow="never">
          <template #header>
            <div class="panel-header">
              <div>
                <span>数据表</span>
                <span class="header-subtitle">{{ selectedScopeText }}</span>
              </div>
              <el-button type="primary" @click="doSearch">查询</el-button>
            </div>
          </template>
          <div class="filter-bar">
            <el-input
              v-model="params.keyword"
              placeholder="搜索库名、表名、中文名或备注"
              clearable
              @keyup.enter="doSearch"
            />
            <el-input
              v-model="params.domain"
              placeholder="业务域"
              clearable
              @keyup.enter="doSearch"
            />
            <el-select v-model="params.page_size" style="width: 110px" @change="loadData">
              <el-option :value="20" label="20 条" />
              <el-option :value="50" label="50 条" />
              <el-option :value="100" label="100 条" />
            </el-select>
          </div>

          <el-table
            v-loading="loading"
            :data="items"
            stripe
            height="430"
            highlight-current-row
            @row-click="selectTable"
            @row-dblclick="goDetail"
          >
            <el-table-column prop="system_code" label="系统" width="110" show-overflow-tooltip />
            <el-table-column prop="source_code" label="库名/数据源" width="170" show-overflow-tooltip />
            <el-table-column prop="schema_name" label="表空间" width="110" />
            <el-table-column prop="table_name" label="表名" min-width="190" show-overflow-tooltip />
            <el-table-column prop="table_name_cn" label="表中文名" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.table_name_cn || row.comment || '-' }}</template>
            </el-table-column>
            <el-table-column prop="domain" label="业务域" width="110" show-overflow-tooltip />
            <el-table-column prop="table_role" label="表类型" width="120" show-overflow-tooltip />
            <el-table-column prop="column_count" label="字段" width="80" align="right" />
          </el-table>

          <el-pagination
            v-model:current-page="params.page"
            v-model:page-size="params.page_size"
            :total="total"
            layout="total, prev, pager, next, sizes"
            :page-sizes="[20, 50, 100]"
            class="pager"
            @change="loadData"
          />
        </el-card>

        <el-card shadow="never" class="field-panel">
          <template #header>
            <div class="panel-header">
              <span>字段预览</span>
              <span class="header-subtitle">{{ selectedTableName || '请选择一张表' }}</span>
            </div>
          </template>
          <el-table :data="columns" v-loading="columnsLoading" stripe height="260">
            <el-table-column prop="column_id" label="#" width="60" align="right" />
            <el-table-column prop="column_name" label="字段名" min-width="180" show-overflow-tooltip />
            <el-table-column prop="column_name_cn" label="字段中文名" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.column_name_cn || row.comment || '-' }}</template>
            </el-table-column>
            <el-table-column prop="data_type" label="类型" width="120" />
            <el-table-column prop="length" label="长度" width="80" align="right" />
            <el-table-column prop="nullable" label="可空" width="80" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.nullable === 'Y' || row.nullable === 'true' ? 'success' : 'info'">
                  {{ row.nullable === 'Y' || row.nullable === 'true' ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="comment" label="备注" min-width="220" show-overflow-tooltip />
          </el-table>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import type { ElTree } from "element-plus";
import { useRouter } from "vue-router";
import {
  getAssetTree,
  getTableColumns,
  getTables,
  type AssetTreeNode,
  type ColumnInfo,
  type TableBrief
} from "@/api/asset";

type TreeKind = "system" | "source" | "schema";
interface TreeItem {
  id: string;
  label: string;
  kind: TreeKind;
  count?: number;
  system_code?: string;
  source_code?: string;
  schema_name?: string;
  children?: TreeItem[];
}

const router = useRouter();
const treeRef = ref<InstanceType<typeof ElTree>>();
const treeKeyword = ref("");
const treeLoading = ref(false);
const loading = ref(false);
const columnsLoading = ref(false);
const rawTree = ref<AssetTreeNode[]>([]);
const items = ref<TableBrief[]>([]);
const columns = ref<ColumnInfo[]>([]);
const total = ref(0);
const selectedTable = ref<TableBrief | null>(null);

const scope = reactive({ system_code: "", source_code: "", schema_name: "" });
const params = reactive({ keyword: "", domain: "", page: 1, page_size: 20 });

const treeProps = { label: "label", children: "children" };

const treeData = computed<TreeItem[]>(() => {
  const systemMap = new Map<string, TreeItem>();
  for (const source of rawTree.value) {
    const sysCode = source.system_code || "未分组系统";
    if (!systemMap.has(sysCode)) {
      systemMap.set(sysCode, {
        id: `system:${sysCode}`,
        label: sysCode,
        kind: "system",
        system_code: sysCode,
        count: 0,
        children: []
      });
    }
    const systemNode = systemMap.get(sysCode)!;
    systemNode.count = (systemNode.count || 0) + (source.table_count || 0);
    systemNode.children!.push({
      id: `source:${source.source_code}`,
      label: `${source.source_name_cn || source.source_code}（${source.source_code}）`,
      kind: "source",
      system_code: sysCode,
      source_code: source.source_code,
      count: source.table_count,
      children: source.schemas.map(schema => ({
        id: `schema:${source.source_code}:${schema.namespace}`,
        label: schema.namespace || "默认 Schema",
        kind: "schema",
        system_code: sysCode,
        source_code: source.source_code,
        schema_name: schema.namespace,
        count: schema.table_count
      }))
    });
  }
  return Array.from(systemMap.values());
});

const selectedScopeText = computed(() => {
  const parts = [scope.system_code, scope.source_code, scope.schema_name].filter(Boolean);
  return parts.length ? ` / ${parts.join(" / ")}` : " / 全部资产";
});
const selectedTableName = computed(() => selectedTable.value ? `${selectedTable.value.schema_name}.${selectedTable.value.table_name}` : "");

watch(treeKeyword, value => treeRef.value?.filter(value));

function filterTreeNode(value: string, data: TreeItem) {
  if (!value) return true;
  return data.label.toLowerCase().includes(value.toLowerCase()) || data.id.toLowerCase().includes(value.toLowerCase());
}

function kindLabel(kind: TreeKind) {
  return kind === "system" ? "系统" : kind === "source" ? "库" : "表空间";
}

function kindTagType(kind: TreeKind) {
  return kind === "system" ? "primary" : kind === "source" ? "success" : "info";
}

async function loadTree() {
  treeLoading.value = true;
  try {
    const res = await getAssetTree();
    rawTree.value = res.data || [];
  } finally {
    treeLoading.value = false;
  }
}

function handleTreeClick(node: TreeItem) {
  scope.system_code = node.system_code || "";
  scope.source_code = node.kind === "source" || node.kind === "schema" ? node.source_code || "" : "";
  scope.schema_name = node.kind === "schema" ? node.schema_name || "" : "";
  params.page = 1;
  loadData();
}

async function loadData() {
  loading.value = true;
  try {
    const res = await getTables({
      keyword: params.keyword || undefined,
      domain: params.domain || undefined,
      system_code: scope.system_code || undefined,
      source_code: scope.source_code || undefined,
      schema_name: scope.schema_name || undefined,
      page: params.page,
      page_size: params.page_size
    });
    items.value = res.data.items;
    total.value = res.data.total;
    if (!selectedTable.value && items.value.length) {
      await selectTable(items.value[0]);
    }
  } finally {
    loading.value = false;
  }
}

async function selectTable(row: TableBrief) {
  selectedTable.value = row;
  columnsLoading.value = true;
  try {
    const res = await getTableColumns(row.schema_name, row.table_name);
    columns.value = res.data || [];
  } finally {
    columnsLoading.value = false;
  }
}

function doSearch() {
  params.page = 1;
  selectedTable.value = null;
  columns.value = [];
  loadData();
}

function goDetail(row: TableBrief) {
  router.push(`/asset/tables/${row.schema_name}/${row.table_name}`);
}

onMounted(async () => {
  await loadTree();
  await nextTick();
  loadData();
});
</script>

<style scoped>
.asset-tables-page { min-height: calc(100vh - 120px); }
.layout-grid { display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 12px; align-items: start; }
.tree-panel { min-height: calc(100vh - 150px); }
.content-panel { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.panel-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.header-subtitle { color: #909399; font-size: 12px; margin-left: 8px; }
.tree-search { margin-bottom: 10px; }
.tree-node { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
.tree-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tree-count { color: #909399; font-size: 12px; }
.filter-bar { display: grid; grid-template-columns: minmax(240px, 1fr) 180px 110px; gap: 8px; margin-bottom: 10px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.field-panel { min-height: 320px; }
@media (max-width: 1100px) { .layout-grid { grid-template-columns: 1fr; } .tree-panel { min-height: auto; } }
</style>