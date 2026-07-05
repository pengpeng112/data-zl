<template>
  <div class="identity-sync-diffs">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>同步差异清单</span>
          <el-button type="primary" :loading="collectLoading" @click="doCollect" :icon="'ep-refresh'">
            手动采集
          </el-button>
        </div>
      </template>
      <div class="filter-bar">
        <el-select
          v-model="params.status"
          placeholder="状态筛选"
          clearable
          style="width: 160px"
          @change="doSearch"
        >
          <el-option label="待处理" value="pending" />
          <el-option label="已处理" value="resolved" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
      </div>
      <el-table v-loading="loading" :data="items" stripe style="margin-top: 12px">
        <el-table-column prop="diff_type" label="差异类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.diff_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_system" label="源系统" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.source_system }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_system" label="目标系统" width="110">
          <template #default="{ row }">
            <el-tag size="small" type="warning">{{ row.target_system }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="entity_type" label="实体类型" width="120" />
        <el-table-column prop="severity" label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.severity === 'high' ? 'danger' : row.severity === 'medium' ? 'warning' : 'info'"
            >
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'resolved' ? 'success' : row.status === 'ignored' ? 'info' : 'warning'"
            >
              {{ row.status === 'resolved' ? '已处理' : row.status === 'ignored' ? '已忽略' : '待处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="差异描述" min-width="180" show-overflow-tooltip />
        <el-table-column prop="detected_at" label="检测时间" width="160" />
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
import { ElMessage } from "element-plus";
import { getSyncDiffs, collectSources } from "@/api/identity";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const collectLoading = ref(false);

const params = reactive({
  status: "",
  page: 1,
  page_size: 20
});

async function loadData() {
  loading.value = true;
  try {
    const res = await getSyncDiffs({
      status: params.status || undefined,
      page: params.page,
      page_size: params.page_size
    });
    items.value = res.data.items ?? [];
    total.value = res.data.total ?? 0;
  } catch {
    ElMessage.error("加载差异列表失败");
  } finally {
    loading.value = false;
  }
}

function doSearch() {
  params.page = 1;
  loadData();
}

async function doCollect() {
  collectLoading.value = true;
  try {
    await collectSources();
    ElMessage.success("采集触发成功");
    loadData();
  } catch {
    ElMessage.error("采集失败");
  } finally {
    collectLoading.value = false;
  }
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
