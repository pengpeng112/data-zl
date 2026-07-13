<template>
  <div class="asset-lineage-page">
    <RePageHeader title="血缘与影响分析" subtitle="按表名查询 ODS 视图引用和正式关系依赖，辅助评估字段或表结构变更影响范围。">
      <template #icon><LineageIcon /></template>
    </RePageHeader>

    <el-card shadow="never" class="lineage-card">
      <ReToolbar title="表影响分析">
        <div class="impact-query">
          <el-input v-model="impactTable" placeholder="例如 HIS.PAT_VISIT" @keyup.enter="runImpact" />
          <el-button type="primary" :loading="impactLoading" @click="runImpact">分析</el-button>
        </div>
      </ReToolbar>

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
          <el-input v-model="depTable" placeholder="被引用表名" clearable @clear="loadDeps" @keyup.enter="loadDeps" />
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
import { ref } from "vue";
import { getImpactAnalysis, getViewDependencies, type ImpactResult, type ViewDependencyItem } from "@/api/asset";
import { ElMessage } from "element-plus";
import LineageIcon from "~icons/ri/node-tree";
import SearchIcon from "~icons/ri/search-line";

const impactTable = ref("");
const impactLoading = ref(false);
const impactResult = ref<ImpactResult | null>(null);
const depsLoading = ref(false);
const depsItems = ref<ViewDependencyItem[]>([]);
const depsTotal = ref(0);
const depPage = ref(1);
const depPageSize = ref(50);
const depView = ref("");
const depTable = ref("");

function runImpact() {
  if (!impactTable.value.trim()) { ElMessage.warning("请输入表名"); return; }
  impactLoading.value = true;
  getImpactAnalysis(impactTable.value.trim()).then(({ data }) => { impactResult.value = data; }).catch(() => { impactResult.value = null; }).finally(() => { impactLoading.value = false; });
}
function loadDeps() {
  depsLoading.value = true;
  getViewDependencies({ page: depPage.value, page_size: depPageSize.value, view: depView.value || undefined, referenced_table: depTable.value || undefined })
    .then(({ data }) => { depsItems.value = data.items; depsTotal.value = data.total; })
    .finally(() => { depsLoading.value = false; });
}
loadDeps();
</script>

<style scoped lang="scss">
.asset-lineage-page { padding: 4px; }
.lineage-card { border: 1px solid var(--border-light); border-radius: var(--radius-base); box-shadow: var(--shadow-sm); }
.deps-card { margin-top: 16px; }
.impact-query, .deps-filter { display: flex; flex-wrap: wrap; gap: 8px; width: 100%; }
.impact-query :deep(.el-input) { width: 300px; }
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
