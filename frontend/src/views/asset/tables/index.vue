<template>
  <div class="asset-tables-page">
    <RePageHeader
      title="资产表目录"
      subtitle="五层导航：系统大类 → 系统/库 → Schema/Owner → 表 → 字段。ODS 下按抽取来源分区，HIS 源端独立大类。"
    >
      <template #icon><TableIcon /></template>
      <template #actions>
        <el-button :icon="RefreshIcon" :loading="treeLoading || loading" @click="reloadAll">刷新目录</el-button>
      </template>
    </RePageHeader>
    <div class="category-bar">
      <el-check-tag
        :checked="!categoryFilter"
        @change="() => setCategoryFilter('')"
      >全部大类</el-check-tag>
      <el-check-tag
        v-for="cat in categoryOptions"
        :key="cat.code"
        :checked="categoryFilter === cat.code"
        @change="() => setCategoryFilter(cat.code)"
      >{{ cat.label }}</el-check-tag>
    </div>
    <div class="layout-grid">
      <el-card class="tree-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>资产目录（五层）</span>
            <el-button text type="primary" @click="loadTree">刷新</el-button>
          </div>
        </template>
        <el-input
          v-model="treeKeyword"
          clearable
          placeholder="搜索大类、系统、Owner、表或字段"
          class="tree-search"
        />
        <el-tree
          ref="treeRef"
          v-loading="treeLoading"
          :data="treeData"
          node-key="id"
          :props="treeProps"
          :filter-node-method="filterTreeNode"
          :default-expanded-keys="defaultExpandedKeys"
          highlight-current
          @node-click="handleTreeClick"
        >
          <template #default="{ data }">
            <span class="tree-node">
              <el-tag v-if="data.kind" size="small" :type="kindTagType(data.kind)">{{ kindLabel(data.kind) }}</el-tag>
              <span class="tree-label" :title="data.label">{{ data.label }}</span>
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
            <el-table-column label="系统大类" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.system_category_cn || categoryLabelOf(row) }}</template>
            </el-table-column>
            <el-table-column label="系统/库" width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.source_system_cn || row.source_code || "-" }}</template>
            </el-table-column>
            <el-table-column prop="schema_name" label="Schema/Owner" width="120" />
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
            @current-change="loadData"
            @size-change="onPageSizeChange"
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
import {
  CATEGORY_LABEL,
  CATEGORY_ORDER,
  kindLabel,
  kindTagType,
  type TreeKind
} from "./hierarchy";
import RefreshIcon from "~icons/ri/refresh-line";
import TableIcon from "~icons/ri/table-line";

interface TreeItem {
  id: string;
  label: string;
  kind: TreeKind;
  count?: number;
  system_category?: string;
  system_code?: string;
  source_system?: string;
  source_code?: string;
  schema_name?: string;
  table_name?: string;
  table?: TableBrief & {
    system_category_cn?: string;
    source_system_cn?: string;
  };
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
const items = ref<(TableBrief & { system_category_cn?: string; source_system_cn?: string })[]>([]);
const columns = ref<ColumnInfo[]>([]);
const total = ref(0);
const selectedTable = ref<(TableBrief & { system_category_cn?: string; source_system_cn?: string }) | null>(null);
const categoryFilter = ref("");

const scope = reactive({
  system_category: "",
  system_code: "",
  source_code: "",
  schema_name: ""
});
const params = reactive({ keyword: "", domain: "", page: 1, page_size: 20 });

const treeProps = { label: "label", children: "children" };
const categoryOptions = CATEGORY_ORDER.map(code => ({
  code,
  label: CATEGORY_LABEL[code]
}));

function tableNodeKey(sourceCode: string, schemaName: string, tableName: string) {
  return `${sourceCode}::${schemaName}::${tableName}`;
}

function toTableBrief(
  source: AssetTreeNode,
  schemaName: string,
  table: AssetTreeTable
): TableBrief & { system_category_cn?: string; source_system_cn?: string } {
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
    source: source.source_name_cn,
    system_category_cn: source.system_category_cn || undefined,
    source_system_cn: source.source_system_cn || undefined
  };
}

function categoryLabelOf(row: { system_code?: string | null; source_code?: string | null }) {
  const sc = (row.system_code || "").toUpperCase();
  if (sc.includes("HIS")) return CATEGORY_LABEL.his_source;
  if (sc === "HRP") return CATEGORY_LABEL.hrp_source;
  if (["LIS", "PACS", "EMR", "MOBILE_NURSING", "SM"].includes(sc)) {
    return CATEGORY_LABEL.external_business;
  }
  return CATEGORY_LABEL.ods_center;
}

const treeData = computed<TreeItem[]>(() => {
  const categoryMap = new Map<string, TreeItem>();

  for (const source of rawTree.value) {
    const cat = source.system_category || "ods_center";
    if (categoryFilter.value && cat !== categoryFilter.value) continue;

    if (!categoryMap.has(cat)) {
      categoryMap.set(cat, {
        id: `category:${cat}`,
        label: source.system_category_cn || CATEGORY_LABEL[cat] || cat,
        kind: "category",
        system_category: cat,
        count: 0,
        children: []
      });
    }
    const catNode = categoryMap.get(cat)!;

    const sysKey = `${cat}::${source.source_system || source.source_code}`;
    let sysNode = catNode.children!.find(c => c.id === `system:${sysKey}`);
    if (!sysNode) {
      sysNode = {
        id: `system:${sysKey}`,
        label:
          source.source_system_cn ||
          source.source_name_cn ||
          source.source_code,
        kind: "system",
        system_category: cat,
        system_code: source.system_code,
        source_system: source.source_system || undefined,
        source_code: source.source_code,
        count: 0,
        children: []
      };
      catNode.children!.push(sysNode);
    }

    const addCount = source.table_count || 0;
    catNode.count = (catNode.count || 0) + addCount;
    sysNode.count = (sysNode.count || 0) + addCount;

    for (const schema of source.schemas) {
      const schemaId = `schema:${source.source_code}:${source.source_system || ""}:${schema.namespace}`;
      let schemaNode = sysNode.children!.find(c => c.id === schemaId);
      if (!schemaNode) {
        schemaNode = {
          id: schemaId,
          label: schema.namespace || "默认 Owner",
          kind: "schema",
          system_category: cat,
          system_code: source.system_code,
          source_system: source.source_system || undefined,
          source_code: source.source_code,
          schema_name: schema.namespace,
          count: schema.table_count,
          children: []
        };
        sysNode.children!.push(schemaNode);
      } else {
        schemaNode.count = (schemaNode.count || 0) + schema.table_count;
      }

      for (const table of schema.tables) {
        const key = tableNodeKey(source.source_code, schema.namespace, table.table_name);
        schemaNode.children!.push({
          id: `table:${key}`,
          label: table.table_name_cn
            ? `${table.table_name} · ${table.table_name_cn}`
            : table.table_name,
          kind: "table",
          system_category: cat,
          system_code: source.system_code,
          source_system: source.source_system || undefined,
          source_code: source.source_code,
          schema_name: schema.namespace,
          table_name: table.table_name,
          table: toTableBrief(source, schema.namespace, table),
          count: table.column_count ?? undefined,
          children: columnChildren.value[key]
        });
      }
    }
  }

  return CATEGORY_ORDER.map(code => categoryMap.get(code)).filter(Boolean) as TreeItem[];
});

const defaultExpandedKeys = computed(() =>
  treeData.value.flatMap(cat => [cat.id, ...(cat.children || []).map(s => s.id)])
);

const selectedScopeText = computed(() => {
  const parts = [
    scope.system_category ? CATEGORY_LABEL[scope.system_category] || scope.system_category : "",
    scope.source_code,
    scope.schema_name
  ].filter(Boolean);
  return parts.length ? ` / ${parts.join(" / ")}` : " / 全部资产";
});
const selectedTableName = computed(() =>
  selectedTable.value
    ? `${selectedTable.value.schema_name}.${selectedTable.value.table_name}`
    : ""
);

watch(treeKeyword, value => treeRef.value?.filter(value));

function filterTreeNode(value: string, data: TreeItem): boolean {
  if (!value) return true;
  const keyword = value.toLowerCase();
  const selfMatch = [
    data.label,
    data.id,
    data.system_category,
    data.system_code,
    data.source_code,
    data.schema_name,
    data.table_name,
    data.column?.column_name
  ]
    .filter(Boolean)
    .some(item => String(item).toLowerCase().includes(keyword));
  if (selfMatch) return true;
  // 子节点命中时父节点必须返回 true，否则搜索表名时整支树被裁掉
  return (data.children || []).some(child => filterTreeNode(value, child));
}

function setCategoryFilter(code: string) {
  categoryFilter.value = code;
  scope.system_category = code;
  scope.system_code = "";
  scope.source_code = "";
  scope.schema_name = "";
  params.page = 1;
  loadData();
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
  scope.system_category = node.system_category || "";
  // 列表过滤用真实 system_code / source_code，不用大类伪编码
  scope.system_code =
    node.kind === "category" ? "" : node.system_code || "";
  scope.source_code = ["system", "schema", "table", "column"].includes(node.kind)
    ? node.source_code || ""
    : "";
  scope.schema_name = ["schema", "table", "column"].includes(node.kind)
    ? node.schema_name || ""
    : "";
  if (node.kind === "table" && node.table) {
    await selectTable(node.table);
    await hydrateColumnChildren(node.table);
    return;
  }
  if (node.kind === "column" && node.schema_name && node.table_name) {
    const table =
      selectedTable.value?.schema_name === node.schema_name &&
      selectedTable.value?.table_name === node.table_name
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
    // 附带大类展示字段（前端派生，兼容后端未回填）
    items.value = (res.data.items || []).map(row => ({
      ...row,
      system_category_cn: categoryLabelOf(row),
      source_system_cn: row.source || row.source_code || undefined
    }));
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

function onPageSizeChange() {
  params.page = 1;
  loadData();
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

.category-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 12px;
}

.layout-grid {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

@media (max-width: 1100px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }

  .tree-panel {
    min-height: 320px;
    max-height: 420px;
    overflow: auto;
  }

  .filter-bar {
    grid-template-columns: 1fr;
  }
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
