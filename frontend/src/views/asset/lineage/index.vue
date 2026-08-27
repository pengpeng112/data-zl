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

      <div v-if="impactResult" class="impact-result">
        <section class="impact-stats">
          <ReStatCard label="引用视图数" :value="impactResult.total_views" tone="primary" />
          <ReStatCard label="关联关系数" :value="impactResult.total_relations" tone="accent" />
          <ReStatCard label="分析表" :value="impactResult.table" tone="info" />
        </section>

        <div v-if="impactResult.referencing_views.length > 0" class="result-section">
          <h3>被以下 ODS 视图引用</h3>
          <el-tag v-for="viewName in impactResult.referencing_views" :key="viewName" class="tag-item" type="info">{{ viewName }}</el-tag>
        </div>

        <div v-if="impactResult.dependent_relations.length > 0" class="result-section">
          <h3>关联的正式关系</h3>
          <div v-for="relation in impactResult.dependent_relations" :key="relation" class="relation-line">{{ relation }}</div>
        </div>

        <ReEmptyState v-if="impactResult.total_views === 0 && impactResult.total_relations === 0" title="未发现影响" description="未找到该表相关的视图或关系。" />
      </div>
    </el-card>

    <el-card shadow="never" class="lineage-card deps-card">
      <ReToolbar :title="`ODS 视图依赖（${depsTotal}）`">
        <div class="deps-filter">
          <el-input v-model="depView" placeholder="视图名" clearable @clear="loadDeps" @keyup.enter="loadDeps" />
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

      <el-table v-loading="depsLoading" :data="depsItems" stripe class="medical-data-table">
        <el-table-column prop="view_name" label="ODS 视图" min-width="220" show-overflow-tooltip />
        <el-table-column prop="referenced_schema" label="被引用 Schema" width="140" />
        <el-table-column prop="referenced_table" label="被引用表" min-width="220" show-overflow-tooltip />
        <el-table-column prop="alias" label="别名" width="100" />
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
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  getGraphFilterOptions,
  getGraphOptions,
  getImpactAnalysis,
  getTables,
  getViewDependencies,
  searchGraphTables,
  type GraphOptionItem,
  type ImpactResult,
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
const impactResult = ref<ImpactResult | null>(null);
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
const depTable = ref("");
const depTableSearching = ref(false);
const depTableOptions = ref<ImpactTableOption[]>([]);

function runImpact() {
  if (!impactTable.value.trim()) { ElMessage.warning("请选择或搜索要分析的表"); return; }
  impactLoading.value = true;
  getImpactAnalysis(impactTable.value.trim()).then(({ data }) => { impactResult.value = data; }).catch(() => { impactResult.value = null; }).finally(() => { impactLoading.value = false; });
}

function expandInGraph() {
  const selected = tableOptions.value.find(item => item.value === impactTable.value);
  const physicalKey = selected?.value || impactTable.value.trim();
  if (!physicalKey) { ElMessage.warning("请先选择要展开的表"); return; }
  router.push({ path: "/asset/graph", query: { center: physicalKey } });
}

function loadDeps() {
  depsLoading.value = true;
  getViewDependencies({ page: depPage.value, page_size: depPageSize.value, view: depView.value || undefined, referenced_table: depTable.value || undefined })
    .then(({ data }) => { depsItems.value = data.items; depsTotal.value = data.total; })
    .finally(() => { depsLoading.value = false; });
}

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
.impact-hint { margin: 8px 0 0; color: var(--text-secondary); font-size: 12px; line-height: 1.5; }
.deps-filter :deep(.el-input) { width: 240px; }
.impact-result { display: grid; gap: 14px; margin-top: 14px; }
.impact-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.result-section { padding: 14px; background: var(--bg-page); border: 1px solid var(--border-light); border-radius: var(--radius-base); }
.result-section h3 { margin: 0 0 10px; font-size: 15px; color: var(--text-primary); }
.tag-item { margin: 0 6px 6px 0; }
.relation-line { padding: 5px 0; font-family: "Courier New", monospace; font-size: 13px; color: var(--text-regular); }
.medical-data-table { --el-table-header-bg-color: var(--bg-elevated); --el-table-row-hover-bg-color: rgb(14 165 233 / 6%); --el-table-border-color: var(--border-light); margin-top: 12px; font-size: 13px; }
.pager { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 760px) { .impact-stats { grid-template-columns: 1fr; } .impact-query :deep(.el-input), .deps-filter :deep(.el-input) { width: 100%; } }
</style>
