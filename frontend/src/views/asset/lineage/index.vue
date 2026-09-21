<template>
  <div class="asset-lineage-page">
    <RePageHeader title="血缘与影响分析" subtitle="按表名查询 ODS 视图引用和正式关系依赖，辅助评估字段或表结构变更影响范围。">
      <template #icon><LineageIcon /></template>
    </RePageHeader>

    <el-card shadow="never" class="lineage-card">
      <ReToolbar title="表影响分析">
        <div class="impact-query">
          <el-select
            v-model="systemCode"
            class="system-select"
            placeholder="业务系统"
            clearable
            filterable
            :loading="optionsLoading"
            @change="onSystemChange"
          >
            <el-option v-for="item in systemOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select
            v-model="schemaName"
            class="schema-select"
            placeholder="Schema / 库"
            clearable
            filterable
            :loading="schemaLoading"
            @change="onSchemaChange"
          >
            <el-option v-for="item in schemaOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select
            v-model="impactTable"
            class="table-select"
            placeholder="输入中文名或表名，从资产库选择"
            clearable
            filterable
            remote
            reserve-keyword
            allow-create
            default-first-option
            :remote-method="searchImpactTables"
            :loading="tableSearching"
            @visible-change="onTableSelectVisible"
            @keyup.enter="runImpact"
          >
            <el-option
              v-for="item in tableOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-button type="primary" :loading="impactLoading" @click="runImpact">分析</el-button>
          <el-button :disabled="!impactTable" @click="expandInGraph">在图谱中展开</el-button>
        </div>
      </ReToolbar>
      <p class="impact-hint">先选业务系统和库，表清单会从资产库带出；也可直接输入中文名或表名搜索，不必手敲完整 SCHEMA.TABLE。</p>

      <div v-if="impactError" class="impact-result">
        <ReEmptyState
          variant="error"
          title="影响分析失败"
          :description="impactError"
          retryable
          @retry="runImpact"
        />
      </div>

      <div v-else-if="impactResult" class="impact-result">
        <section class="impact-stats">
          <ReStatCard label="下游受影响对象" :value="impactResult.downstream_nodes?.length || 0" tone="primary" />
          <ReStatCard label="上游来源对象" :value="impactResult.upstream_nodes?.length || 0" tone="accent" />
          <ReStatCard label="血缘边总数" :value="impactResult.total_edges || 0" tone="info" />
        </section>

        <p class="impact-target">
          分析对象：<code>{{ impactTargetLabel }}</code>
        </p>

        <div class="impact-columns">
          <section class="impact-column">
            <h3>
              下游影响范围
              <span class="col-sub">改这张表，谁会受影响</span>
            </h3>
            <template v-if="downstreamGroups.length">
              <div v-for="group in downstreamGroups" :key="group.hop" class="hop-group">
                <p class="hop-title">{{ hopLabel(group.hop) }}</p>
                <div class="hop-nodes">
                  <el-tag
                    v-for="node in group.nodes"
                    :key="node.key"
                    :type="nodeTagType(node.type)"
                    class="node-tag"
                    effect="plain"
                    @click="expandNodeInGraph(node)"
                  >
                    <span class="node-type">{{ nodeTypeLabel(node.type) }}</span>
                    {{ node.name }}
                  </el-tag>
                </div>
              </div>
            </template>
            <p v-else class="hop-empty">未发现下游依赖对象。</p>
          </section>

          <section class="impact-column">
            <h3>
              上游数据来源
              <span class="col-sub">这张表的数据从哪来</span>
            </h3>
            <template v-if="upstreamGroups.length">
              <div v-for="group in upstreamGroups" :key="group.hop" class="hop-group">
                <p class="hop-title">{{ hopLabel(group.hop) }}</p>
                <div class="hop-nodes">
                  <el-tag
                    v-for="node in group.nodes"
                    :key="node.key"
                    :type="nodeTagType(node.type)"
                    class="node-tag"
                    effect="plain"
                    @click="expandNodeInGraph(node)"
                  >
                    <span class="node-type">{{ nodeTypeLabel(node.type) }}</span>
                    {{ node.name }}
                  </el-tag>
                </div>
              </div>
            </template>
            <p v-else class="hop-empty">未发现上游来源对象。</p>
          </section>
        </div>

        <ReEmptyState
          v-if="!impactResult.downstream_nodes?.length && !impactResult.upstream_nodes?.length"
          title="未发现血缘依赖"
          description="该表暂无登记的血缘边，可先在血缘同步或关系审核中补充。"
        />
      </div>
    </el-card>

    <el-card shadow="never" class="lineage-card deps-card">
      <ReToolbar :title="`ODS 视图依赖（${depsTotal}）`">
        <div class="deps-filter">
          <el-input v-model="depView" placeholder="视图名" clearable @clear="loadDeps" @keyup.enter="loadDeps" />
          <el-select
            v-model="depSchema"
            class="dep-schema-select"
            placeholder="被引用 Schema"
            clearable
            filterable
            @change="onDepSchemaChange"
          >
            <el-option v-for="item in depSchemaOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select
            v-model="depTable"
            class="dep-table-select"
            placeholder="被引用表，可搜索资产库"
            clearable
            filterable
            remote
            allow-create
            default-first-option
            :remote-method="searchDepTables"
            :loading="depTableSearching"
            @clear="loadDeps"
            @change="loadDeps"
          >
            <el-option
              v-for="item in depTableOptions"
              :key="item.value"
              :label="item.label"
              :value="item.table || item.value"
            />
          </el-select>
        </div>
        <template #actions><el-button type="primary" :icon="SearchIcon" @click="loadDeps">查询</el-button></template>
      </ReToolbar>

      <p class="deps-hint">同一视图引用的多张表已合并展示；点击"被引用表"查看表详情，或在行内直接发起影响分析。</p>

      <!-- 146 E10（R5）：依赖表加载失败显式错误态 + 重试（不再静默） -->
      <ReEmptyState
        v-if="depsError"
        variant="error"
        title="视图依赖加载失败"
        :description="depsError"
        retryable
        @retry="loadDeps"
      />
      <el-table
        v-else
        v-loading="depsLoading"
        :data="depsItems"
        stripe
        class="medical-data-table"
        :span-method="depSpanMethod"
      >
        <el-table-column label="ODS 视图" min-width="240">
          <template #default="{ row }">
            <div class="view-cell">
              <span class="view-name">{{ row.view_name }}</span>
              <span v-if="row.referenced_schema" class="view-schema">{{ row.referenced_schema }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="被引用表" min-width="240">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" class="table-link" @click="openTableDetail(row)">
              {{ row.referenced_table }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="别名" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.alias" type="info" effect="plain" size="small">{{ row.alias }}</el-tag>
            <span v-else class="cell-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="runImpactForRow(row)">分析影响</el-button>
            <el-button link type="primary" size="small" @click="expandRowInGraph(row)">图谱</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="depPage" class="pager" :page-size="depPageSize" :total="depsTotal" layout="total, prev, pager, next" @current-change="loadDeps" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  getGraphFilterOptions,
  getGraphOptions,
  getImpactAnalysis,
  getTables,
  getViewDependencies,
  searchGraphTables,
  type GraphOptionItem,
  type LineageImpactEdge,
  type LineageImpactResult,
  type ViewDependencyItem
} from "@/api/asset";
import {
  mergeTableOptions,
  optionFromCatalog,
  parseImpactTableQuery,
  type ImpactTableOption
} from "@/views/asset/lineage/lineagePicker";
import { ElMessage } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import LineageIcon from "~icons/ri/node-tree";
import SearchIcon from "~icons/ri/search-line";

const route = useRoute();
const router = useRouter();
const systemCode = ref("");
const schemaName = ref("");
const impactTable = ref("");
const impactLoading = ref(false);
const impactResult = ref<LineageImpactResult | null>(null);
// 146 E10（R5）：影响分析/视图依赖的真实错误态（失败原因 + 重试）
const impactError = ref("");
const depsError = ref("");
const optionsLoading = ref(false);
const schemaLoading = ref(false);
const tableSearching = ref(false);
const systemOptions = ref<GraphOptionItem[]>([]);
const schemaOptions = ref<GraphOptionItem[]>([]);
const allSchemaOptions = ref<GraphOptionItem[]>([]);
const tableOptions = ref<ImpactTableOption[]>([]);
const depsLoading = ref(false);
const depsItems = ref<ViewDependencyItem[]>([]);
const depsTotal = ref(0);
const depPage = ref(1);
const depPageSize = ref(50);
const depView = ref("");
const depSchema = ref("");
const depTable = ref("");
const depTableSearching = ref(false);
const depTableOptions = ref<ImpactTableOption[]>([]);
// 依赖卡 schema 筛选复用图谱 schema 选项全集（后端 /lineage/views 已支持 schema 参数）
const depSchemaOptions = computed(() => allSchemaOptions.value);

// --- 血缘影响结果：typed object_key 解析与按跳分层 ---

interface ImpactNodeDisplay {
  key: string;
  name: string;
  type: string;
}

interface ImpactHopGroup {
  hop: number;
  nodes: ImpactNodeDisplay[];
}

const OBJECT_TYPE_LABELS: Record<string, string> = {
  table: "表",
  view: "视图",
  query: "查询",
  metric: "指标",
  product: "产品"
};

const NODE_TAG_TYPES: Record<string, "primary" | "success" | "warning" | "danger" | "info"> = {
  table: "primary",
  view: "warning",
  query: "success",
  metric: "danger",
  product: "info"
};

function parseObjectKeyName(key: string): { name: string; type: string } {
  const parts = key.split("|");
  if (parts.length === 6) return { name: `${parts[3]}.${parts[4]}`, type: parts[5] };
  return { name: key, type: "table" };
}

function buildHopGroups(nodes: string[], edges: LineageImpactEdge[], side: "down" | "up"): ImpactHopGroup[] {
  const info = new Map<string, { hop: number; type: string }>();
  for (const edge of edges || []) {
    const isDown = side === "down";
    const node = isDown ? edge.to : edge.from;
    const type = isDown ? edge.to_type : edge.from_type;
    const prev = info.get(node);
    if (!prev || edge.hops < prev.hop) info.set(node, { hop: edge.hops, type });
  }
  // nodes 列表兜底（无边记录的节点按 1 跳处理）
  for (const key of nodes || []) {
    if (!info.has(key)) info.set(key, { hop: 1, type: parseObjectKeyName(key).type });
  }
  const grouped = new Map<number, ImpactNodeDisplay[]>();
  for (const [key, meta] of info) {
    const parsed = parseObjectKeyName(key);
    const list = grouped.get(meta.hop) || [];
    list.push({ key, name: parsed.name, type: meta.type });
    grouped.set(meta.hop, list);
  }
  return [...grouped.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([hop, items]) => ({ hop, nodes: items.sort((a, b) => a.name.localeCompare(b.name)) }));
}

const downstreamGroups = computed<ImpactHopGroup[]>(() => {
  if (!impactResult.value) return [];
  return buildHopGroups(impactResult.value.downstream_nodes || [], impactResult.value.downstream_edges || [], "down");
});

const upstreamGroups = computed<ImpactHopGroup[]>(() => {
  if (!impactResult.value) return [];
  return buildHopGroups(impactResult.value.upstream_nodes || [], impactResult.value.upstream_edges || [], "up");
});

const impactTargetLabel = computed(() => {
  const key = impactResult.value?.object_key || "";
  return key ? parseObjectKeyName(key).name : impactTable.value;
});

function hopLabel(hop: number): string {
  return hop <= 1 ? "直接依赖（1 跳）" : `间接依赖（${hop} 跳）`;
}

function nodeTypeLabel(type: string): string {
  return OBJECT_TYPE_LABELS[type] || type;
}

function nodeTagType(type: string): "primary" | "success" | "warning" | "danger" | "info" {
  return NODE_TAG_TYPES[type] || "info";
}

// --- 影响分析 ---

function runImpact() {
  if (!impactTable.value.trim()) { ElMessage.warning("请选择或搜索要分析的表"); return; }
  impactLoading.value = true;
  impactError.value = "";
  getImpactAnalysis(impactTable.value.trim())
    .then(({ data }) => { impactResult.value = data; })
    .catch(error => {
      impactResult.value = null;
      impactError.value = extractErrorDetail(error, "影响分析失败，请稍后重试");
    })
    .finally(() => { impactLoading.value = false; });
}

function scrollToImpact() {
  document.querySelector(".impact-query")?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function runImpactForRow(row: ViewDependencyItem) {
  const schema = String(row.referenced_schema || "").trim();
  const table = String(row.referenced_table || "").trim();
  if (!table) { ElMessage.warning("该行缺少被引用表名"); return; }
  impactTable.value = schema ? `${schema}.${table}` : table;
  runImpact();
  scrollToImpact();
}

function expandInGraph() {
  const selected = tableOptions.value.find(item => item.value === impactTable.value);
  const physicalKey = selected?.value || impactTable.value.trim();
  if (!physicalKey) { ElMessage.warning("请先选择要展开的表"); return; }
  router.push({ path: "/asset/graph", query: { center: physicalKey } });
}

function expandNodeInGraph(node: ImpactNodeDisplay) {
  if (node.type !== "table" && node.type !== "view") {
    ElMessage.info("该对象类型暂不支持图谱定位，可在血缘同步中查看详情");
    return;
  }
  router.push({ path: "/asset/graph", query: { center: node.name } });
}

// --- 视图依赖列表 ---

function loadDeps() {
  depsLoading.value = true;
  depsError.value = "";
  getViewDependencies({
    page: depPage.value,
    page_size: depPageSize.value,
    view: depView.value || undefined,
    referenced_table: depTable.value || undefined,
    schema: depSchema.value || undefined
  })
    .then(({ data }) => { depsItems.value = data.items; depsTotal.value = data.total; })
    .catch(error => {
      depsItems.value = [];
      depsTotal.value = 0;
      depsError.value = extractErrorDetail(error, "视图依赖加载失败，请稍后重试");
    })
    .finally(() => { depsLoading.value = false; });
}

function onDepSchemaChange() {
  depPage.value = 1;
  loadDeps();
}

// 同一视图引用多张表：合并"视图"列单元格，去重复观感
type DepSpanMethod = (params: { row: ViewDependencyItem; rowIndex: number; columnIndex: number }) => [number, number];
const depSpanMethod = computed<DepSpanMethod>(() => {
  const items = depsItems.value;
  const spans = new Array<number>(items.length).fill(0);
  let i = 0;
  while (i < items.length) {
    let j = i;
    while (j + 1 < items.length && items[j + 1].view_name === items[i].view_name) j += 1;
    spans[i] = j - i + 1;
    i = j + 1;
  }
  return ({ rowIndex, columnIndex }) => {
    if (columnIndex !== 0) return [1, 1];
    return [spans[rowIndex] || 1, 1];
  };
});

function openTableDetail(row: ViewDependencyItem) {
  const schema = String(row.referenced_schema || "").trim();
  const table = String(row.referenced_table || "").trim();
  if (!schema || !table) { ElMessage.warning("缺少 SCHEMA.TABLE 信息，无法打开表详情"); return; }
  router.push(`/asset/tables/${encodeURIComponent(schema)}/${encodeURIComponent(table)}`);
}

function expandRowInGraph(row: ViewDependencyItem) {
  const schema = String(row.referenced_schema || "").trim();
  const table = String(row.referenced_table || "").trim();
  if (!schema || !table) { ElMessage.warning("缺少 SCHEMA.TABLE 信息，无法在图谱展开"); return; }
  router.push({ path: "/asset/graph", query: { center: `${schema}.${table}` } });
}

// --- 筛选选项加载（沿用原逻辑） ---

async function loadCatalogOptions() {
  optionsLoading.value = true;
  try {
    const { data } = await getGraphOptions();
    systemOptions.value = data.system_options?.length
      ? data.system_options
      : (data.systems || []).map(value => ({ value, label: value }));
    allSchemaOptions.value = data.schema_options?.length
      ? data.schema_options
      : (data.schemas || []).map(value => ({ value, label: value }));
    if (!systemCode.value) schemaOptions.value = allSchemaOptions.value;
  } catch {
    // 选项属于可选资源：失败降级为手输模式，不阻断主流程（D1 口径）
  } finally {
    optionsLoading.value = false;
  }
}

async function loadSchemas(system?: string) {
  if (!system) {
    schemaOptions.value = allSchemaOptions.value;
    return;
  }
  schemaLoading.value = true;
  try {
    const { data } = await getGraphFilterOptions({ system_code: system, next_level: "schema" });
    schemaOptions.value = data.items?.length ? data.items : allSchemaOptions.value;
  } catch {
    schemaOptions.value = allSchemaOptions.value;
  } finally {
    schemaLoading.value = false;
  }
}

async function loadTablesFromLibrary(keyword = "") {
  tableSearching.value = true;
  try {
    const query = keyword.trim();
    if (query) {
      const { data } = await searchGraphTables({
        q: query,
        system_code: systemCode.value || undefined,
        schema: schemaName.value || undefined,
        limit: 30
      });
      tableOptions.value = mergeTableOptions([], (data.items || []).map(optionFromCatalog).filter((item): item is ImpactTableOption => Boolean(item)));
      return;
    }
    if (!schemaName.value && !systemCode.value) {
      tableOptions.value = [];
      return;
    }
    const { data } = await getTables({
      system_code: systemCode.value || undefined,
      schema_name: schemaName.value || undefined,
      page: 1,
      page_size: 80
    });
    tableOptions.value = mergeTableOptions([], (data.items || []).map(item => optionFromCatalog({
      table_name_cn: item.table_name_cn,
      schema_name: item.schema_name,
      table_name: item.table_name,
      technical_name: item.schema_name && item.table_name ? `${item.schema_name}.${item.table_name}` : item.table_name
    })).filter((item): item is ImpactTableOption => Boolean(item)));
  } catch (error) {
    tableOptions.value = [];
    ElMessage.error(extractErrorDetail(error, "表选项加载失败，请重试"));
  } finally {
    tableSearching.value = false;
  }
}

function searchImpactTables(query: string) {
  void loadTablesFromLibrary(query);
}

function onTableSelectVisible(visible: boolean) {
  if (visible && !tableOptions.value.length) void loadTablesFromLibrary();
}

async function onSystemChange() {
  schemaName.value = "";
  impactTable.value = "";
  tableOptions.value = [];
  await loadSchemas(systemCode.value);
}

async function onSchemaChange() {
  impactTable.value = "";
  await loadTablesFromLibrary();
}

async function searchDepTables(query: string) {
  const keyword = query.trim();
  if (!keyword) {
    depTableOptions.value = [];
    return;
  }
  depTableSearching.value = true;
  try {
    const { data } = await searchGraphTables({ q: keyword, limit: 30 });
    depTableOptions.value = (data.items || []).map(optionFromCatalog).filter((item): item is ImpactTableOption => Boolean(item));
  } catch (error) {
    depTableOptions.value = [];
    ElMessage.error(extractErrorDetail(error, "依赖表搜索失败，请重试"));
  } finally {
    depTableSearching.value = false;
  }
}

onMounted(async () => {
  const parsed = parseImpactTableQuery(route.query as Record<string, unknown>);
  systemCode.value = parsed.systemCode;
  schemaName.value = parsed.schemaName;
  impactTable.value = parsed.table;
  await loadCatalogOptions();
  if (systemCode.value) await loadSchemas(systemCode.value);
  if (schemaName.value || parsed.table) await loadTablesFromLibrary(parsed.table.split(".").pop() || "");
  if (impactTable.value) runImpact();
});
loadDeps();
</script>

<style scoped lang="scss">
.asset-lineage-page { padding: 4px; }
.lineage-card { border: 1px solid var(--border-light); border-radius: var(--radius-base); box-shadow: var(--shadow-sm); }
.deps-card { margin-top: 16px; }
.impact-query, .deps-filter { display: flex; flex-wrap: wrap; gap: 8px; width: 100%; align-items: center; }
.system-select { width: 180px; }
.schema-select { width: 180px; }
.table-select { width: min(420px, 100%); }
.dep-table-select { width: 280px; }
.dep-schema-select { width: 180px; }
.impact-hint, .deps-hint { margin: 8px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.deps-filter :deep(.el-input) { width: 240px; }
.impact-result { display: grid; gap: 14px; margin-top: 14px; }
.impact-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.impact-target { margin: 0; font-size: 13px; color: var(--text-regular); }
.impact-target code { padding: 2px 8px; background: var(--bg-page); border: 1px solid var(--border-light); border-radius: 4px; font-family: "Courier New", monospace; }
.impact-columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.impact-column { padding: 14px; background: var(--bg-page); border: 1px solid var(--border-light); border-radius: var(--radius-base); }
.impact-column h3 { display: flex; align-items: baseline; gap: 8px; margin: 0 0 10px; font-size: 15px; color: var(--text-primary); }
.col-sub { font-size: 12px; font-weight: normal; color: var(--text-secondary); }
.hop-group { margin-bottom: 10px; }
.hop-title { margin: 0 0 6px; font-size: 12px; color: var(--text-secondary); }
.hop-nodes { display: flex; flex-wrap: wrap; gap: 6px; }
.node-tag { cursor: pointer; }
.node-tag:hover { border-color: var(--el-color-primary); }
.node-type { margin-right: 4px; opacity: 0.75; }
.hop-empty { margin: 0; font-size: 13px; color: var(--text-secondary); }
.view-cell { display: flex; flex-direction: column; gap: 2px; }
.view-name { font-family: "Courier New", monospace; font-size: 13px; color: var(--text-primary); }
.view-schema { font-size: 12px; color: var(--text-secondary); }
.table-link { font-family: "Courier New", monospace; font-size: 13px; }
.cell-muted { color: var(--text-secondary); }
.medical-data-table { --el-table-header-bg-color: var(--bg-elevated); --el-table-row-hover-bg-color: rgb(14 165 233 / 6%); --el-table-border-color: var(--border-light); margin-top: 12px; font-size: 13px; }
.pager { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 760px) {
  .impact-stats { grid-template-columns: 1fr; }
  .impact-columns { grid-template-columns: 1fr; }
  .impact-query :deep(.el-input), .deps-filter :deep(.el-input) { width: 100%; }
}
</style>
