<template>
  <div class="dict-sync-diffs">
    <el-card shadow="never">
      <template #header>
        <span>字典同步差异</span>
      </template>

      <div class="filter-bar">
        <el-select
          v-model="statusFilter"
          placeholder="差异状态"
          clearable
          style="width: 160px"
          @change="doSearch"
        >
          <el-option label="待处理" value="open" />
          <el-option label="已确认" value="acknowledged" />
          <el-option label="已解决" value="resolved" />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="搜索编码/名称"
          clearable
          style="width: 240px; margin-left: 8px"
          @keyup.enter="doSearch"
        />
        <el-button type="primary" style="margin-left: 8px" @click="doSearch">搜索</el-button>
      </div>

      <el-table v-loading="loading" :data="items" stripe style="margin-top: 12px">
        <el-table-column prop="category_code" label="类别" width="140" />
        <el-table-column prop="target_system" label="目标系统" width="100" align="center" />
        <el-table-column label="差异类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="diffTypeTag(row.diff_type)" size="small">
              {{ row.diff_type === 'missing_source' ? '缺少来源' : row.diff_type === 'mismatch' ? '不匹配' : row.diff_type === 'extra_source' ? '多余来源' : row.diff_type || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code_set" label="编码体系" width="140" />
        <el-table-column prop="item_code" label="编码" width="160" />
        <el-table-column prop="item_name_cn" label="名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="严重程度" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="severityTag(row.severity)" size="small">
              {{ row.severity === 'critical' ? '严重' : row.severity === 'major' ? '重要' : row.severity === 'minor' ? '一般' : '提示' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="syncStatusTag(row.status)" size="small">
              {{ row.status === 'open' ? '待处理' : row.status === 'acknowledged' ? '已确认' : '已解决' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="found_at" label="发现时间" width="170" />
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        style="margin-top: 16px; justify-content: flex-end"
        @change="loadData"
      />
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="header-row">
          <span>字典版本记录</span>
          <el-button size="small" @click="loadVersions">刷新</el-button>
        </div>
      </template>
      <el-table v-loading="verLoading" :data="versions" stripe size="small">
        <el-table-column prop="category_code" label="类别" width="140" />
        <el-table-column prop="target_system" label="目标系统" width="100" align="center" />
        <el-table-column prop="version" label="版本号" width="160" />
        <el-table-column prop="item_count" label="条目数" width="100" align="center" />
        <el-table-column prop="sync_at" label="同步时间" width="170" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'success' ? 'success' : 'warning'"
              size="small"
            >
              {{ row.status === 'success' ? '成功' : row.status || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="diff_count" label="差异数" width="80" align="center" />
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
      </el-table>
      <el-pagination
        v-if="verTotal > 0"
        v-model:current-page="verPage"
        v-model:page-size="verPageSize"
        :total="verTotal"
        layout="total, prev, pager, next"
        size="small"
        style="margin-top: 8px; justify-content: flex-end"
        @change="loadVersions"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getMedicalSyncDiffs, getDictVersions } from "@/api/dict";

// --- 同步差异 ---
const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const statusFilter = ref("");
const keyword = ref("");

function doSearch() {
  page.value = 1;
  loadData();
}

function diffTypeTag(diffType: string): any {
  const map: Record<string, string> = { missing_source: "danger", mismatch: "warning" }
  return map[diffType] || "info"
}

function severityTag(sev: string): any {
  const map: Record<string, string> = { critical: "danger", major: "warning", minor: "info" }
  return map[sev] || ""
}

function syncStatusTag(status: string): any {
  const map: Record<string, string> = { open: "danger", acknowledged: "warning", resolved: "success" }
  return map[status] || "info"
}

async function loadData() {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value
    };
    if (statusFilter.value) params.status = statusFilter.value;
    if (keyword.value) params.keyword = keyword.value;
    const res = await getMedicalSyncDiffs(params);
    items.value = (res as any).data.items;
    total.value = (res as any).data.total;
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

// --- 版本记录 ---
const versions = ref<any[]>([]);
const verLoading = ref(false);
const verTotal = ref(0);
const verPage = ref(1);
const verPageSize = ref(20);

async function loadVersions() {
  verLoading.value = true;
  try {
    const res = await getDictVersions({
      page: verPage.value,
      page_size: verPageSize.value
    });
    const data = (res as any).data;
    if (Array.isArray(data)) {
      versions.value = data;
      verTotal.value = data.length;
    } else if (data && data.items) {
      versions.value = data.items;
      verTotal.value = data.total;
    }
  } catch {
    // handled
  } finally {
    verLoading.value = false;
  }
}

onMounted(() => {
  loadData();
  loadVersions();
});
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
