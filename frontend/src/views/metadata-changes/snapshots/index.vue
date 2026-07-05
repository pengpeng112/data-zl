<template>
  <div class="metadata-snapshots">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>快照管理</span>
          <div class="header-actions">
            <el-select
              v-model="sourceCode"
              placeholder="选择数据源"
              style="width: 200px"
              @change="loadSnapshots"
            >
              <el-option label="HIS (8.216)" value="his_8216" />
              <el-option label="EMR (JHEMR)" value="jhemr" />
              <el-option label="LIS" value="lis" />
              <el-option label="PACS" value="pacs" />
              <el-option label="YDHL" value="ydhl" />
              <el-option label="ODS" value="ods" />
            </el-select>
            <el-button
              type="primary"
              :loading="collecting"
              :disabled="!sourceCode"
              style="margin-left: 12px"
              @click="doCollect"
            >
              采集元数据
            </el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="snapshots" stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="label" label="标签" min-width="180" show-overflow-tooltip />
        <el-table-column prop="snapshot_time" label="快照时间" width="180" />
        <el-table-column prop="table_count" label="表数量" width="100" align="center" />
        <el-table-column prop="column_count" label="字段数量" width="100" align="center" />
      </el-table>

      <el-empty v-if="!loading && snapshots.length === 0" description="请先选择数据源" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import {
  collectMetadata,
  getSourceSnapshots
} from "@/api/metadata";

const sourceCode = ref("");
const snapshots = ref<any[]>([]);
const loading = ref(false);
const collecting = ref(false);

async function loadSnapshots() {
  if (!sourceCode.value) {
    snapshots.value = [];
    return;
  }
  loading.value = true;
  try {
    const res = await getSourceSnapshots(sourceCode.value);
    snapshots.value = res.data ?? [];
  } catch {
    snapshots.value = [];
  } finally {
    loading.value = false;
  }
}

async function doCollect() {
  collecting.value = true;
  try {
    await collectMetadata(sourceCode.value);
    ElMessage.success("采集任务已触发，请稍后刷新查看");
    setTimeout(() => loadSnapshots(), 2000);
  } catch {
    // handled
  } finally {
    collecting.value = false;
  }
}

onMounted(() => {
  if (sourceCode.value) {
    loadSnapshots();
  }
});
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  align-items: center;
}
</style>
