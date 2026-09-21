<script setup lang="ts">
import { onMounted, ref } from "vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { listDatasets, type DatasetListItem } from "@/api/datasets";

defineOptions({ name: "DatasetCatalog" });

const loading = ref(false);
const items = ref<DatasetListItem[]>([]);
const errorMsg = ref("");
const batchRunId = ref("");
const batch = ref<Record<string, unknown> | null>(null);

async function load() {
  loading.value = true;
  errorMsg.value = "";
  try {
    const res = await listDatasets();
    items.value = res.data || [];
  } catch (e: unknown) {
    errorMsg.value = (e as { response?: { data?: { message?: string } } })?.response?.data?.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadBatch() {
  if (!batchRunId.value.trim()) return;
  const { getDatasetBatch } = await import("@/api/datasets");
  try {
    const res = await getDatasetBatch(batchRunId.value.trim());
    batch.value = res.data as unknown as Record<string, unknown>;
  } catch {
    batch.value = null;
    errorMsg.value = "批次不存在或无权限";
  }
}

onMounted(load);
</script>

<template>
  <div class="dataset-catalog-page">
    <RePageHeader title="数据集目录" subtitle="193 患者纵向高质量数据集：分类分级、版本状态与批次（真实平台 API）" />
    <el-card shadow="never">
      <el-alert v-if="errorMsg" type="error" :title="errorMsg" :closable="false" class="mb-2" />
      <el-table v-loading="loading" :data="items" stripe>
        <el-table-column prop="dataset_code" label="编码" min-width="160" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="purpose_code" label="用途" width="140" />
        <el-table-column prop="grain" label="粒度" width="90" />
        <el-table-column label="最新版本" width="80" align="right">
          <template #default="{ row }">{{ row.version ?? "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'published' ? 'success' : row.status === 'revoked' ? 'danger' : 'info'">
              {{ row.status || "draft" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="访问" width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="row.readable ? 'success' : 'warning'">
              {{ row.readable ? "已授权" : row.decision || "受限" }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="mt-3">
      <template #header>批次检查点查询（B07 幂等与断点恢复）</template>
      <div class="batch-bar">
        <el-input v-model="batchRunId" placeholder="输入 run_id，如 RUN-193-A" clearable class="w-64" @keyup.enter="loadBatch" />
        <el-button type="primary" @click="loadBatch">查询批次</el-button>
      </div>
      <pre v-if="batch" class="batch-json">{{ JSON.stringify(batch, null, 2) }}</pre>
      <el-empty v-else description="输入批次号查看计数与检查点" :image-size="60" />
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.dataset-catalog-page {
  padding: 4px;
}

.batch-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;

  .w-64 {
    width: 280px;
  }
}

.batch-json {
  padding: 8px;
  overflow: auto;
  font-size: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
</style>
