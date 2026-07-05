<template>
  <div class="asset-ai-context">
    <el-card shadow="never">
      <template #header>AI 上下文导出</template>
      <p style="color: #909399; margin-bottom: 16px">
        选择表，导出脱敏的元数据（表名、字段、关系），提供给外网 AI 做
        SQL/视图生成参考。
        <strong>导出内容不含患者数据。</strong>
      </p>

      <div class="filter-bar">
        <el-input
          v-model="keyword"
          placeholder="搜索表名加入列表"
          clearable
          style="width: 320px"
          @keyup.enter="searchTables"
        />
        <el-button
          type="primary"
          style="margin-left: 12px"
          @click="searchTables"
        >
          搜索
        </el-button>
      </div>

      <el-table
        v-loading="searching"
        :data="searchResults"
        stripe
        style="margin-top: 12px"
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

    <el-card shadow="never" style="margin-top: 16px">
      <template #header> 已选表 ({{ selectedTables.length }}) </template>
      <el-tag
        v-for="t in selectedTables"
        :key="`${t.schema_name}.${t.table_name}`"
        closable
        style="margin-right: 8px; margin-bottom: 8px"
        @close="removeTable(t)"
      >
        {{ t.schema_name }}.{{ t.table_name }}
      </el-tag>
      <el-empty
        v-if="selectedTables.length === 0"
        description="从上方表格勾选需要导出的表"
        :image-size="80"
      />

      <div v-if="selectedTables.length > 0" style="margin-top: 16px">
        <el-button type="success" :loading="exporting" @click="doExport">
          导出上下文
        </el-button>
        <el-button
          v-if="exported"
          type="primary"
          style="margin-left: 8px"
          @click="copyJson"
        >
          复制 JSON
        </el-button>
        <el-button
          v-if="exported"
          type="info"
          style="margin-left: 8px"
          @click="downloadJson"
        >
          下载 JSON
        </el-button>
      </div>

      <div v-if="exported" style="margin-top: 16px">
        <el-alert title="导出成功" type="success" :closable="false" show-icon>
          <template #default>
            已导出 {{ exportedTables }} 张表、{{ exportedColumns }} 个字段、{{
              exportedRelations
            }}
            条关系的脱敏元数据。 <br />该数据可安全粘贴给外网 AI 使用。
          </template>
        </el-alert>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { getTables, exportContext, type TableBrief } from "@/api/asset";

const keyword = ref("");
const searching = ref(false);
const searchResults = ref<TableBrief[]>([]);
const selectedTables = ref<TableBrief[]>([]);
const exporting = ref(false);
const exported = ref(false);
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
  } catch {
    searchResults.value = [];
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
  } catch {
    ElMessage.error("导出失败");
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
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
}
</style>
