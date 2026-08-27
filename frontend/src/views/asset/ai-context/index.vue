<template>
  <div class="asset-ai-context">
    <RePageHeader
      title="AI 上下文导出"
      subtitle="选择表，导出脱敏的元数据（表名、字段、关系），提供给外网 AI 做 SQL/视图生成参考。"
    />

    <el-card class="context-card" shadow="never">
      <el-alert
        title="导出内容不含患者数据"
        type="info"
        :closable="false"
        show-icon
      />

      <div class="filter-bar">
        <el-input
          v-model="keyword"
          placeholder="搜索表名加入列表"
          clearable
          class="search-input"
          @keyup.enter="searchTables"
        />
        <el-button
          type="primary"
          class="search-button"
          @click="searchTables"
        >
          搜索
        </el-button>
      </div>

      <el-table
        v-loading="searching"
        :data="searchResults"
        stripe
        class="result-table"
        max-height="300"
        @selection-change="onSelect"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column prop="schema_name" label="Schema" width="80" />
        <el-table-column
          prop="table_name"
          label="表名"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column
          prop="comment"
          label="注释"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column
          prop="column_count"
          label="字段"
          width="60"
          align="center"
        />
        <el-table-column prop="domain" label="业务域" width="100" />
      </el-table>
    </el-card>

    <el-card class="context-card" shadow="never">
      <template #header>按系统导出摘要</template>
      <div class="filter-bar">
        <el-select
          v-model="systemCode"
          placeholder="选择业务系统"
          clearable
          filterable
          class="system-select"
          :loading="systemsLoading"
        >
          <el-option
            v-for="sys in systemOptions"
            :key="sys.system_code"
            :label="`${sys.system_name_cn || sys.system_code} (${sys.system_code})`"
            :value="sys.system_code"
          />
        </el-select>
        <el-button type="success" :loading="systemExporting" :disabled="!systemCode" @click="doSystemExport">
          生成系统摘要
        </el-button>
        <el-button v-if="systemSummary" type="info" @click="copySystemSummary">复制摘要 JSON</el-button>
      </div>
      <el-alert
        v-if="systemSummary"
        class="action-row"
        type="success"
        :closable="false"
        show-icon
        :title="`已生成 ${systemSummary.system_name_cn || systemSummary.system_code || systemCode} 摘要`"
      >
        <template #default>
          覆盖表 {{ formatNumber(systemSummary.table_count ?? systemSummary.tables?.length ?? 0) }} 张、关系
          {{ formatNumber(systemSummary.relations?.length ?? 0) }} 条（脱敏，可直接给外网 AI 作系统背景）。
        </template>
      </el-alert>
      <el-alert v-if="systemError" class="action-row" type="error" :closable="false" :title="systemError" show-icon />
    </el-card>

    <el-card class="context-card selected-card" shadow="never">
      <template #header> 已选表 ({{ selectedTables.length }}) </template>
      <el-tag
        v-for="t in selectedTables"
        :key="`${t.schema_name}.${t.table_name}`"
        closable
        class="selected-tag"
        @close="removeTable(t)"
      >
        {{ t.schema_name }}.{{ t.table_name }}
      </el-tag>
      <el-empty
        v-if="selectedTables.length === 0"
        description="从上方表格勾选需要导出的表"
        :image-size="80"
      />

      <div v-if="selectedTables.length > 0" class="action-row">
        <el-button type="success" :loading="exporting" @click="doExport">
          导出上下文
        </el-button>
        <el-button
          v-if="exported"
          type="primary"
          class="secondary-action"
          @click="copyJson"
        >
          复制 JSON
        </el-button>
        <el-button
          v-if="exported"
          type="info"
          class="secondary-action"
          @click="downloadJson"
        >
          下载 JSON
        </el-button>
      </div>

      <div v-if="exported" class="action-row">
        <el-alert title="导出成功" type="success" :closable="false" show-icon>
          <template #default>
            已导出 {{ formatNumber(exportedTables) }} 张表、{{ formatNumber(exportedColumns) }} 个字段、{{
              formatNumber(exportedRelations)
            }}
            条关系的脱敏元数据。 <br />该数据可安全粘贴给外网 AI 使用。
          </template>
        </el-alert>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import { formatNumber } from "@/utils/format";
import { getTables, exportContext, getAiSystemContext, listSystems, type AiSystemContext, type AssetSystemItem, type TableBrief } from "@/api/asset";

const keyword = ref("");
const searching = ref(false);
const searchResults = ref<TableBrief[]>([]);
const selectedTables = ref<TableBrief[]>([]);
const exporting = ref(false);
const exported = ref(false);

// 146 E1：吸收系统上下文摘要入口
const systemCode = ref("");
const systemOptions = ref<AssetSystemItem[]>([]);
const systemsLoading = ref(false);
const systemExporting = ref(false);
const systemSummary = ref<AiSystemContext | null>(null);
const systemError = ref("");

async function loadSystems() {
  systemsLoading.value = true;
  systemError.value = "";
  try {
    const res = await listSystems();
    systemOptions.value = res.data || [];
  } catch (error) {
    systemOptions.value = [];
    systemError.value = extractErrorDetail(error, "系统选项加载失败");
  } finally {
    systemsLoading.value = false;
  }
}

async function doSystemExport() {
  if (!systemCode.value) return;
  systemExporting.value = true;
  systemError.value = "";
  try {
    const res = await getAiSystemContext(systemCode.value);
    systemSummary.value = res.data;
  } catch (error) {
    systemSummary.value = null;
    systemError.value = extractErrorDetail(error, "系统摘要生成失败");
  } finally {
    systemExporting.value = false;
  }
}

async function copySystemSummary() {
  if (!systemSummary.value) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(systemSummary.value, null, 2));
    ElMessage.success("已复制");
  } catch {
    ElMessage.warning("剪贴板不可用，请手动复制");
  }
}
const exportedJson = ref<any>(null);
const exportedTables = ref(0);
const exportedColumns = ref(0);
const exportedRelations = ref(0);

async function searchTables() {
  searching.value = true;
  try {
    const res = await getTables({
      keyword: keyword.value || undefined,
      page: 1,
      page_size: 50
    });
    searchResults.value = res.data.items;
  } catch (error) {
    searchResults.value = [];
    ElMessage.error(extractErrorDetail(error, "表搜索失败，请重试"));
  } finally {
    searching.value = false;
  }
}

function onSelect(rows: TableBrief[]) {
  selectedTables.value = rows;
}

function removeTable(t: TableBrief) {
  selectedTables.value = selectedTables.value.filter(
    r => !(r.schema_name === t.schema_name && r.table_name === t.table_name)
  );
}

async function doExport() {
  exporting.value = true;
  try {
    const names = selectedTables.value.map(
      t => `${t.schema_name}.${t.table_name}`
    );
    const res = await exportContext({
      tables: names,
      include_relations: true,
      include_columns: true
    });
    exportedJson.value = res.data;
    exportedTables.value = res.data.tables.length;
    exportedColumns.value = res.data.columns.length;
    exportedRelations.value = res.data.relations.length;
    exported.value = true;
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "导出失败"));
  } finally {
    exporting.value = false;
  }
}

function copyJson() {
  navigator.clipboard.writeText(JSON.stringify(exportedJson.value, null, 2));
  ElMessage.success("已复制到剪贴板");
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(exportedJson.value, null, 2)], {
    type: "application/json"
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "asset-context.json";
  a.click();
  URL.revokeObjectURL(url);
}
onMounted(() => {
  void searchTables();
  void loadSystems();
});
</script>

<style scoped>
.asset-ai-context {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}

.context-card {
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-md);
  box-shadow: var(--re-shadow-sm);
}

.selected-card {
  margin-top: 16px;
}

.filter-bar {
  display: flex;
  align-items: center;
  margin-top: 14px;
}

.action-row {
  margin-top: 16px;
}

.system-select { width: 280px; }
.search-input {
  width: 320px;
}

.search-button {
  margin-left: 12px;
}

.result-table {
  margin-top: 12px;
}

.selected-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.secondary-action {
  margin-left: 8px;
}
</style>
