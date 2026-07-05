<template>
  <div class="asset-tables">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>表资产浏览</span>
        </div>
      </template>
      <div class="filter-bar">
        <el-input
          v-model="params.keyword"
          placeholder="搜索 schema/表名/注释"
          clearable
          style="width: 320px"
          @keyup.enter="doSearch"
        />
        <el-input
          v-model="params.domain"
          placeholder="业务域"
          clearable
          style="width: 200px; margin-left: 12px"
          @keyup.enter="doSearch"
        />
        <el-button type="primary" style="margin-left: 12px" @click="doSearch">
          搜索
        </el-button>
      </div>
      <el-table
        v-loading="loading"
        :data="items"
        stripe
        style="margin-top: 12px"
        @row-click="goDetail"
      >
        <el-table-column prop="schema_name" label="Schema" width="120" />
        <el-table-column
          prop="table_name"
          label="表名"
          min-width="200"
          show-overflow-tooltip
        />
        <el-table-column
          prop="comment"
          label="注释"
          min-width="200"
          show-overflow-tooltip
        />
        <el-table-column
          prop="column_count"
          label="字段数"
          width="90"
          align="center"
        />
        <el-table-column prop="domain" label="业务域" width="120" />
        <el-table-column prop="source" label="来源" width="90" />
      </el-table>
      <el-pagination
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        style="margin-top: 16px; justify-content: flex-end"
        @change="loadData"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
import { getTables, type TableBrief } from "@/api/asset";

const router = useRouter();
const items = ref<TableBrief[]>([]);
const total = ref(0);
const loading = ref(false);

const params = reactive({
  keyword: "",
  domain: "",
  page: 1,
  page_size: 20
});

async function loadData() {
  loading.value = true;
  try {
    const res = await getTables({
      keyword: params.keyword || undefined,
      domain: params.domain || undefined,
      page: params.page,
      page_size: params.page_size
    });
    items.value = res.data.items;
    total.value = res.data.total;
  } catch {
    // handled
  } finally {
    loading.value = false;
  }
}

function doSearch() {
  params.page = 1;
  loadData();
}

function goDetail(row: TableBrief) {
  router.push(`/asset/tables/${row.schema_name}/${row.table_name}`);
}

onMounted(loadData);
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
