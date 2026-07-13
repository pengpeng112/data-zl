<template>
  <div class="asset-tables-page">
    <RePageHeader title="资产表目录" subtitle="按系统、数据源、Schema、表、字段五层浏览资产结构，支持表字段联动预览。">
      <template #icon><TableIcon /></template>
      <template #actions>
        <el-button :icon="RefreshIcon" :loading="treeLoading || loading" @click="reloadAll">刷新目录</el-button>
      </template>
    </RePageHeader>
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
          placeholder="搜索系统、库、Schema、表或字段"
          class="tree-search"
        />
        <el-tree
          ref="treeRef"
          v-loading="treeLoading"
          :data="treeData"
          node-key="id"
          :props="treeProps"
          :filter-node-method="filterTreeNode"
          default-expand-all
          highlight-current
          @node-click="handleTreeClick"
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
          <ReToolbar title="表资产筛选" class="table-toolbar">
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
            <el-select v-model="params.page_size" class="page-size-select" @change="loadData">
              <el-option :value="20" label="20 条" />
              <el-option :value="50" label="50 条" />
              <el-option :value="100" label="100 条" />
            </el-select>
          </div>
          </ReToolbar>

          <el-table
            v-loading="loading"
            :data="items"
            stripe
            height="430"
            highlight-current-row
            class="medical-data-table"
            @row-click="selectTable"
            @row-dblclick="goDetail"
          >
            <el-table-column prop="system_code" label="系统" width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ systemDisplayName(row.system_code) }}</template>
            </el-table-column>
            <el-table-column prop="source_code" label="库/数据源" width="170" show-overflow-tooltip />
            <el-table-column prop="schema_name" label="Schema/Owner" width="130" />
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
          <el-table :data="columns" v-loading="columnsLoading" stripe height="260" class="medical-data-table">
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
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import type { ElTree } from "element-plus";
import { useRouter } from "vue-router";
import {
  getAssetTree,
  getTableColumns,
  getTables,
  type AssetTreeNode,
  type AssetTreeTable,
  type ColumnInfo,
  type TableBrief
} from "@/api/asset";
import RefreshIcon from "~icons/ri/refresh-line";
import TableIcon from "~icons/ri/table-line";

type TreeKind = "system" | "source" | "schema" | "table" | "column";
interface TreeItem {
  id: string;
  label: string;
  kind: TreeKind;
  count?: number;
  system_code?: string;
  source_code?: string;
  schema_name?: string;
  table_name?: string;
  table?: TableBrief;
  column?: ColumnInfo;
  children?: TreeItem[];
}

const router = useRouter();
const treeRef = ref<InstanceType<typeof ElTree>>();
const treeKeyword = ref("");
const treeLoading = ref(false);
const loading = ref(false);
const columnsLoading = ref(false);
const rawTree = ref<AssetTreeNode[]>([]);
const columnChildren = ref<Record<string, TreeItem[]>>({});
const items = ref<TableBrief[]>([]);
const columns = ref<ColumnInfo[]>([]);
const total = ref(0);
const selectedTable = ref<TableBrief | null>(null);

const scope = reactive({ system_code: "", source_code: "", schema_name: "" });
const params = reactive({ keyword: "", domain: "", page: 1, page_size: 20 });

const treeProps = { label: "label", children: "children" };

function systemGroupCode(systemCode?: string | null) {
  const code = (systemCode || "").toUpperCase();
  if (code.includes("HIS")) return "HIS_SOURCE";
  return "DATA_CENTER";
}

function systemDisplayName(systemCode?: string | null) {
  return systemGroupCode(systemCode) === "HIS_SOURCE" ? "HIS 系统" : "ODS 数据中心系统";
}

function tableNodeKey(sourceCode: string, schemaName: string, tableName: string) {
  return `${sourceCode}::${schemaName}::${tableName}`;
}

function toTableBrief(source: AssetTreeNode, schemaName: string, table: AssetTreeTable): TableBrief {
  return {
    id: table.id,
    system_code: source.system_code,
    source_code: source.source_code,
    namespace_name: schemaName,
    schema_name: schemaName,
    table_name: table.table_name,
    table_name_cn: table.table_name_cn,
    table_role: null,
    comment: null,
    column_count: table.column_count ?? null,
    domain: table.domain ?? null,
    source: source.source_name_cn
  };
}

const treeData = computed<TreeItem[]>(() => {
  const systemMap = new Map<string, TreeItem>();
  for (const source of rawTree.value) {
    const sysCode = systemGroupCode(source.system_code);
    if (!systemMap.has(sysCode)) {
      systemMap.set(sysCode, {
        id: `system:${sysCode}`,
        label: systemDisplayName(sysCode),
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
      label: source.source_name_cn ? `${source.source_name_cn} (${source.source_code})` : source.source_code,
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
        count: schema.table_count,
        children: schema.tables.map(table => {
          const key = tableNodeKey(source.source_code, schema.namespace, table.table_name);
          return {
            id: `table:${key}`,
            label: table.table_name_cn ? `${table.table_name} - ${table.table_name_cn}` : table.table_name,
            kind: "table",
            system_code: sysCode,
            source_code: source.source_code,
            schema_name: schema.namespace,
            table_name: table.table_name,
            table: toTableBrief(source, schema.namespace, table),
            count: table.column_count ?? undefined,
            children: columnChildren.value[key]
          };
        })
      }))
    });
  }
  return ["DATA_CENTER", "HIS_SOURCE"]
    .map(code => systemMap.get(code))
    .filter(Boolean) as TreeItem[];
});

const selectedScopeText = computed(() => {
  const parts = [scope.system_code ? systemDisplayName(scope.system_code) : "", scope.source_code, scope.schema_name].filter(Boolean);
  return parts.length ? ` / ${parts.join(" / ")}` : " / 全部资产";
});
const selectedTableName = computed(() => selectedTable.value ? `${selectedTable.value.schema_name}.${selectedTable.value.table_name}` : "");

watch(treeKeyword, value => treeRef.value?.filter(value));

function filterTreeNode(value: string, data: TreeItem) {
  if (!value) return true;
  const keyword = value.toLowerCase();
  return [data.label, data.id, data.system_code, data.source_code, data.schema_name, data.table_name, data.column?.column_name]
    .filter(Boolean)
    .some(item => String(item).toLowerCase().includes(keyword));
}

function kindLabel(kind: TreeKind) {
  const labels: Record<TreeKind, string> = {
    system: "系统",
    source: "库",
    schema: "Schema",
    table: "表",
    column: "字段"
  };
  return labels[kind];
}

function kindTagType(kind: TreeKind) {
  const types: Record<TreeKind, "primary" | "success" | "info" | "warning" | "danger"> = {
    system: "primary",
    source: "success",
    schema: "info",
    table: "warning",
    column: "danger"
  };
  return types[kind];
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

async function hydrateColumnChildren(table: TableBrief) {
  const key = tableNodeKey(table.source_code || "", table.schema_name, table.table_name);
  if (columnChildren.value[key]) return;
  const list = columns.value.length && selectedTable.value?.schema_name === table.schema_name && selectedTable.value?.table_name === table.table_name
    ? columns.value
    : (await getTableColumns(table.schema_name, table.table_name)).data || [];
  columnChildren.value = {
    ...columnChildren.value,
    [key]: list.map(col => ({
      id: `column:${key}:${col.column_name || col.column_id}`,
      label: col.column_name_cn ? `${col.column_name} - ${col.column_name_cn}` : col.column_name || `字段 ${col.column_id}`,
      kind: "column",
      system_code: table.system_code || undefined,
      source_code: table.source_code || undefined,
      schema_name: table.schema_name,
      table_name: table.table_name,
      table,
      column: col
    }))
  };
}

async function handleTreeClick(node: TreeItem) {
  scope.system_code = node.system_code || "";
  scope.source_code = ["source", "schema", "table", "column"].includes(node.kind) ? node.source_code || "" : "";
  scope.schema_name = ["schema", "table", "column"].includes(node.kind) ? node.schema_name || "" : "";
  if (node.kind === "table" && node.table) {
    await selectTable(node.table);
    await hydrateColumnChildren(node.table);
    return;
  }
  if (node.kind === "column" && node.schema_name && node.table_name) {
    const table = selectedTable.value?.schema_name === node.schema_name && selectedTable.value?.table_name === node.table_name
      ? selectedTable.value
      : node.table;
    if (table) await selectTable(table);
    return;
  }
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

function reloadAll() {
  loadTree();
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

<style scoped lang="scss">
.asset-tables-page {
  min-height: calc(100vh - 120px);
  padding: 4px;
}

.layout-grid {
  display: grid;
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.tree-panel,
.content-panel :deep(.el-card) {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
}

.tree-panel {
  min-height: calc(100vh - 210px);
}

.content-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.panel-header {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.header-subtitle {
  margin-left: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.tree-search {
  margin-bottom: 12px;
}

.tree-node {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  min-width: 0;
  max-width: 330px;
}

.tree-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-count {
  font-size: 12px;
  color: var(--text-secondary);
}

.table-toolbar {
  margin-bottom: 12px;
}

.filter-bar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) 180px 110px;
  gap: 8px;
  width: 100%;
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  font-size: 13px;
}

.pager {
  justify-content: flex-end;
  margin-top: 12px;
}

.field-panel {
  min-height: 320px;
}

@media (max-width: 1100px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }

  .tree-panel {
    min-height: auto;
  }
}

@media (max-width: 760px) {
  .filter-bar {
    grid-template-columns: 1fr;
  }
}

.page-size-select { width: 110px; }
</style>
