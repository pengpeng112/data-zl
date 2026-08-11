<template>
  <div class="asset-tables-page">
    <RePageHeader
      title="资产表目录"
      subtitle="统一层级：业务系统 → 数据连接 → Schema/Owner → 表 → 字段。一级名称来自系统总览，十个业务系统平行展示。"
    >
      <template #icon><TableIcon /></template>
      <template #actions>
        <el-button :icon="RefreshIcon" :loading="treeLoading || loading" @click="reloadAll">刷新目录</el-button>
      </template>
    </RePageHeader>
    <div class="category-bar">
      <el-check-tag
        :checked="!systemFilter"
        @change="() => setSystemFilter('')"
      >全部业务系统</el-check-tag>
      <el-check-tag
        v-for="sys in systemFilterOptions"
        :key="sys.code"
        :checked="systemFilter === sys.code"
        @change="() => setSystemFilter(sys.code)"
      >{{ sys.label }}</el-check-tag>
    </div>
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
          placeholder="搜索系统、连接、Owner、表或字段"
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
          @node-expand="handleTreeExpand"
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
            <el-table-column label="业务系统" width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.system_name_cn || systemLabelOf(row) }}</template>
            </el-table-column>
            <el-table-column label="数据连接" width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.source_system_cn || row.source_code || "-" }}</template>
            </el-table-column>
            <el-table-column prop="schema_name" label="Schema/Owner" width="120" />
            <el-table-column prop="table_name" label="表名" min-width="190" show-overflow-tooltip />
            <el-table-column prop="table_name_cn" label="表中文名" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.table_name_cn || row.comment || '-' }}</template>
            </el-table-column>
            <el-table-column label="名称来源" width="120">
              <template #default="{ row }">
                <el-tag v-if="row.name_cn_source" size="small" :type="row.name_cn_status === 'confirmed' ? 'success' : 'warning'">{{ row.name_cn_source }}</el-tag>
                <span v-else>-</span>
              </template>
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
  getAssetTreeTables,
  getTableColumns,
  getTables,
  listSystems,
  searchAssetTree,
  type AssetTreeNode,
  type AssetTreeTable,
  type ColumnInfo,
  type TableBrief
} from "@/api/asset";
import {
  CANONICAL_SYSTEM_CODES,
  kindLabel,
  kindTagType,
  type TreeKind
} from "./hierarchy";
import RefreshIcon from "~icons/ri/refresh-line";
import TableIcon from "~icons/ri/table-line";

interface TreeItem {
  id: string;
  label: string;
  kind: TreeKind | "category";
  count?: number;
  system_category?: string;
  system_code?: string;
  system_name_cn?: string;
  source_system?: string;
  source_code?: string;
  schema_name?: string;
  name_cn_source?: string;
  name_cn_status?: string;
  table_name?: string;
  /** schema 表是否已懒加载 */
  tablesLoaded?: boolean;
  tablesLoading?: boolean;
  table?: TableBrief & {
    system_category_cn?: string;
    system_name_cn?: string;
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
/** schemaId -> 已加载的表节点 */
const schemaTableChildren = ref<Record<string, TreeItem[]>>({});
const schemaTablesLoading = ref<Record<string, boolean>>({});
const columnChildren = ref<Record<string, TreeItem[]>>({});
const searchHits = ref<TreeItem[]>([]);
const items = ref<
  (TableBrief & { system_category_cn?: string; system_name_cn?: string; source_system_cn?: string })[]
>([]);
const columns = ref<ColumnInfo[]>([]);
const total = ref(0);
const selectedTable = ref<
  (TableBrief & { system_category_cn?: string; system_name_cn?: string; source_system_cn?: string }) | null
>(null);
/** plan 90: filter by first-level system_code, not legacy category */
const systemFilter = ref("");
const systemNameMap = ref<Record<string, string>>({});

const scope = reactive({
  system_category: "",
  system_code: "",
  source_code: "",
  schema_name: ""
});
const params = reactive({ keyword: "", domain: "", page: 1, page_size: 20 });

const treeProps = { label: "label", children: "children" };
const systemFilterOptions = computed(() =>
  (CANONICAL_SYSTEM_CODES as readonly string[]).map(code => ({
    code,
    label: systemNameMap.value[code] || code
  }))
);

function tableNodeKey(sourceCode: string, schemaName: string, tableName: string) {
  return `${sourceCode}::${schemaName}::${tableName}`;
}

function toTableBrief(
  source: AssetTreeNode,
  schemaName: string,
  table: AssetTreeTable
): TableBrief & { system_category_cn?: string; system_name_cn?: string; source_system_cn?: string } {
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
    system_name_cn: source.system_name_cn || systemNameMap.value[source.system_code] || undefined,
    system_category_cn: source.system_name_cn || undefined,
    source_system_cn: source.source_system_cn || undefined
  };
}

function systemLabelOf(row: { system_code?: string | null; system_name_cn?: string | null }) {
  const code = (row.system_code || "").toUpperCase();
  return row.system_name_cn || systemNameMap.value[code] || code || "-";
}

const treeData = computed<TreeItem[]>(() => {
  /** system_code → 业务系统节点（十系统平行，无「其他业务系统」大类） */
  const systemMap = new Map<string, TreeItem>();

  for (const source of rawTree.value) {
    const sysCode = (source.system_code || "UNKNOWN").toUpperCase();
    if (systemFilter.value && sysCode !== systemFilter.value) continue;

    if (!systemMap.has(sysCode)) {
      systemMap.set(sysCode, {
        id: `system:${sysCode}`,
        label:
          source.system_name_cn ||
          systemNameMap.value[sysCode] ||
          sysCode,
        kind: "system",
        system_code: sysCode,
        system_name_cn: source.system_name_cn || systemNameMap.value[sysCode],
        count: 0,
        children: []
      });
    }
    const sysNode = systemMap.get(sysCode)!;

    const physical = source.physical_source_code || source.source_code;
    const connKey = `${sysCode}::${physical}`;
    let connNode = sysNode.children!.find(c => c.id === `connection:${connKey}`);
    if (!connNode) {
      connNode = {
        id: `connection:${connKey}`,
        label:
          source.source_system_cn ||
          source.connection_endpoint ||
          source.source_name_cn ||
          source.source_code,
        kind: "connection",
        system_code: sysCode,
        system_name_cn: sysNode.system_name_cn,
        source_system: source.source_system || undefined,
        source_code: source.source_code,
        count: 0,
        children: []
      };
      sysNode.children!.push(connNode);
    }

    const addCount = source.table_count || 0;
    sysNode.count = (sysNode.count || 0) + addCount;
    connNode.count = (connNode.count || 0) + addCount;

    if (!source.schemas?.length && addCount === 0) {
      if (!connNode.children!.some(c => c.id.startsWith("empty:"))) {
        connNode.children!.push({
          id: `empty:${connKey}`,
          label: "当前未发现非空对象",
          kind: "schema",
          system_code: sysCode,
          source_code: source.source_code
        });
      }
    }

    for (const schema of source.schemas) {
      const schemaSourceCode = schema.source_code || source.source_code;
      const schemaId = `schema:${schemaSourceCode}:${schema.namespace}`;
      let schemaNode = connNode.children!.find(c => c.id === schemaId);
      if (!schemaNode) {
        schemaNode = {
          id: schemaId,
          label: schema.namespace_name_cn
            ? `${schema.namespace_name_cn}（${schema.namespace}）`
            : schema.namespace || "默认 Owner",
          kind: "schema",
          system_code: sysCode,
          system_name_cn: sysNode.system_name_cn,
          source_system: source.source_system || undefined,
          source_code: schemaSourceCode,
          schema_name: schema.namespace,
          name_cn_source: schema.name_cn_source || undefined,
          name_cn_status: schema.name_cn_status || undefined,
          count: schema.table_count,
          children: []
        };
        connNode.children!.push(schemaNode);
      } else {
        schemaNode.count = (schemaNode.count || 0) + schema.table_count;
      }

      const lazyTables = schemaTableChildren.value[schemaId];
      if (lazyTables?.length) {
        schemaNode.children = lazyTables.map(t => ({
          ...t,
          children: t.table
            ? columnChildren.value[
                tableNodeKey(t.source_code || "", t.schema_name || "", t.table_name || "")
              ]
            : undefined
        }));
        schemaNode.tablesLoaded = true;
      } else if (schema.tables_loaded || (schema.tables && schema.tables.length)) {
        for (const table of schema.tables || []) {
          const key = tableNodeKey(source.source_code, schema.namespace, table.table_name);
          schemaNode.children!.push({
            id: `table:${key}`,
            label: table.table_name_cn
              ? `${table.table_name} · ${table.table_name_cn}`
              : table.table_name,
            kind: "table",
            system_code: sysCode,
            system_name_cn: sysNode.system_name_cn,
            source_system: source.source_system || undefined,
            source_code: source.source_code,
            schema_name: schema.namespace,
            table_name: table.table_name,
            table: toTableBrief(source, schema.namespace, table),
            count: table.column_count ?? undefined,
            children: columnChildren.value[key]
          });
        }
        schemaNode.tablesLoaded = true;
      } else {
        schemaNode.tablesLoaded = false;
        if ((schema.table_count || 0) > 0) {
          schemaNode.children = [
            {
              id: `placeholder:${schemaId}`,
              label: schemaTablesLoading.value[schemaId]
                ? "加载中…"
                : `共 ${schema.table_count} 张表（展开/点击加载）`,
              kind: "table",
              system_code: sysCode,
              source_code: source.source_code,
              schema_name: schema.namespace
            }
          ];
        }
      }
    }
  }

  const order = new Map(
    (CANONICAL_SYSTEM_CODES as readonly string[]).map((c, i) => [c, i])
  );
  const base = Array.from(systemMap.values()).sort(
    (a, b) =>
      (order.get(a.system_code || "") ?? 999) - (order.get(b.system_code || "") ?? 999)
  );

  if (searchHits.value.length && treeKeyword.value.trim()) {
    return [
      {
        id: "search-hits",
        label: `搜索结果（${searchHits.value.length}）`,
        kind: "category",
        count: searchHits.value.length,
        children: searchHits.value
      },
      ...base
    ];
  }
  return base;
});

const defaultExpandedKeys = computed(() =>
  treeData.value.flatMap(sys => [sys.id, ...(sys.children || []).map(s => s.id)])
);

const selectedScopeText = computed(() => {
  const parts = [
    scope.system_code
      ? systemNameMap.value[scope.system_code] || scope.system_code
      : "",
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

let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(treeKeyword, value => {
  treeRef.value?.filter(value);
  if (searchTimer) clearTimeout(searchTimer);
  const kw = (value || "").trim();
  if (!kw) {
    searchHits.value = [];
    return;
  }
  // 服务端表名搜索（骨架树不含表节点时本地 filter 不够）
  searchTimer = setTimeout(() => runTreeSearch(kw), 300);
});

function filterTreeNode(value: string, data: TreeItem): boolean {
  if (!value) return true;
  // 搜索结果分区始终展示
  if (data.id === "search-hits") return true;
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

function setSystemFilter(code: string) {
  systemFilter.value = code;
  scope.system_category = "";
  scope.system_code = code;
  scope.source_code = "";
  scope.schema_name = "";
  params.page = 1;
  loadData();
}

async function loadSystemNames() {
  try {
    const res = await listSystems();
    const map: Record<string, string> = {};
    for (const s of res.data || []) {
      if (s.system_code) map[s.system_code] = s.system_name_cn || s.system_code;
    }
    systemNameMap.value = map;
  } catch {
    systemNameMap.value = {};
  }
}

async function loadTree() {
  treeLoading.value = true;
  try {
    await loadSystemNames();
    // 默认不内嵌表，显著减小首包
    const res = await getAssetTree({ include_tables: false });
    rawTree.value = res.data || [];
    schemaTableChildren.value = {};
  } finally {
    treeLoading.value = false;
  }
}

async function loadSchemaTables(node: TreeItem) {
  if (node.kind !== "schema" || !node.source_code) return;
  const sid = node.id;
  if (schemaTableChildren.value[sid]?.length || schemaTablesLoading.value[sid]) return;
  schemaTablesLoading.value = { ...schemaTablesLoading.value, [sid]: true };
  try {
    const res = await getAssetTreeTables({
      source_code: node.source_code,
      schema_name: node.schema_name || "",
      page: 1,
      page_size: 500
    });
    const sourceStub: AssetTreeNode = {
      source_code: node.source_code,
      source_name_cn: node.source_code,
      system_code: node.system_code || "",
      system_name_cn: node.system_name_cn,
      system_category: node.system_category,
      source_system: node.source_system,
      table_count: res.data.total,
      schemas: []
    };
    schemaTableChildren.value = {
      ...schemaTableChildren.value,
      [sid]: (res.data.items || []).map(table => {
        const key = tableNodeKey(node.source_code || "", node.schema_name || "", table.table_name);
        return {
          id: `table:${key}`,
          label: table.table_name_cn
            ? `${table.table_name} · ${table.table_name_cn}`
            : table.table_name,
          kind: "table" as const,
          system_code: node.system_code,
          system_name_cn: node.system_name_cn,
          source_system: node.source_system,
          source_code: node.source_code,
          schema_name: node.schema_name,
          table_name: table.table_name,
          table: toTableBrief(sourceStub, node.schema_name || "", table),
          count: table.column_count ?? undefined
        };
      })
    };
  } finally {
    schemaTablesLoading.value = { ...schemaTablesLoading.value, [sid]: false };
  }
}

async function handleTreeExpand(node: TreeItem) {
  if (node.kind === "schema") {
    await loadSchemaTables(node);
  }
}

async function runTreeSearch(keyword: string) {
  try {
    const res = await searchAssetTree({
      keyword,
      system_category: systemFilter.value || undefined,
      limit: 40
    });
    searchHits.value = (res.data.items || []).map(table => {
      const schema = (table as any).schema_name || "";
      const sourceCode = (table as any).source_code || "";
      const key = tableNodeKey(sourceCode, schema, table.table_name);
      const path = (table as any).path as string | undefined;
      const stub: AssetTreeNode = {
        source_code: sourceCode,
        source_name_cn: (table as any).source_name_cn || sourceCode,
        system_code: (table as any).system_code || "",
        system_name_cn: (table as any).system_name_cn,
        system_category: (table as any).system_category,
        source_system: (table as any).source_system,
        table_count: 1,
        schemas: []
      };
      return {
        id: `search-table:${key}`,
        label:
          path ||
          (table.table_name_cn
            ? `${schema}.${table.table_name} · ${table.table_name_cn}`
            : `${schema}.${table.table_name}`),
        kind: "table" as const,
        system_code: (table as any).system_code,
        system_name_cn: (table as any).system_name_cn,
        source_system: (table as any).source_system,
        source_code: sourceCode,
        schema_name: schema,
        table_name: table.table_name,
        table: toTableBrief(stub, schema, table),
        count: table.column_count ?? undefined
      };
    });
  } catch {
    searchHits.value = [];
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
  if (node.id === "search-hits") return;
  // 占位节点：触发 schema 加载
  if (node.id.startsWith("placeholder:")) {
    const schemaLike: TreeItem = {
      ...node,
      id: node.id.replace(/^placeholder:/, ""),
      kind: "schema"
    };
    await loadSchemaTables(schemaLike);
    return;
  }
  scope.system_category = "";
  // 列表过滤：业务系统 → 连接 → schema
  scope.system_code =
    node.kind === "category" || node.id === "search-hits" ? "" : node.system_code || "";
  scope.source_code = ["connection", "schema", "table", "column"].includes(node.kind)
    ? node.source_code || ""
    : "";
  scope.schema_name = ["schema", "table", "column"].includes(node.kind)
    ? node.schema_name || ""
    : "";
  if (node.kind === "schema") {
    await loadSchemaTables(node);
  }
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
    items.value = (res.data.items || []).map(row => ({
      ...row,
      system_name_cn: systemLabelOf(row),
      system_category_cn: systemLabelOf(row),
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
