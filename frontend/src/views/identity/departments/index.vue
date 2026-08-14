<template>
  <div class="identity-departments">
    <div class="page-head">
      <strong>科室基线</strong>
      <span>HIS 科室字典：编码、名称、上级、门诊/住院类型和启停状态。</span>
    </div>

    <section class="dept-stat-grid">
      <ReStatCard label="科室总数" :value="totalCount" tone="primary" />
      <ReStatCard label="启用科室" :value="activeDeptCount" tone="accent" />
      <ReStatCard label="停用/待确认" :value="inactiveDeptCount" tone="warning" />
    </section>

    <el-card shadow="never">
      <template #header>
        <div class="list-head">
          <strong>科室列表（{{ filteredItems.length }}）</strong>
          <div class="filters">
            <el-input v-model="keyword" clearable placeholder="编码/名称" class="filter-md" @keyup.enter="applyFilter" @clear="applyFilter" />
            <el-select v-model="typeFilter" clearable placeholder="科室类型" class="filter-sm" @change="applyFilter">
              <el-option v-for="opt in typeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
            </el-select>
            <el-select v-model="statusFilter" clearable placeholder="状态" class="filter-sm" @change="applyFilter">
              <el-option label="启用" value="active" />
              <el-option label="停用" value="inactive" />
            </el-select>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="pagedItems" stripe size="small" class="dept-table" @row-click="showDetail">
        <el-table-column prop="dept_code" label="科室编码" width="110" />
        <el-table-column prop="dept_name_cn" label="科室名称" width="180" show-overflow-tooltip />
        <el-table-column label="上级科室" width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.parent_dept_name || row.parent_dept_code || "-" }}</template>
        </el-table-column>
        <el-table-column label="科室类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.dept_type)">{{ row.dept_type_name || deptTypeLabel(row.dept_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="人员数" width="80" align="center">
          <template #default="{ row }">{{ row.person_count ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">{{ row.source_system || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'warning'">
              {{ row.status_name || deptStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="复核" width="90">
          <template #default="{ row }">{{ row.review_status_name || deptReviewLabel(row.review_status) }}</template>
        </el-table-column>
        <el-table-column label="最近同步" min-width="160">
          <template #default="{ row }">{{ formatSyncTime(row.last_source_sync_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        class="pager"
        :page-size="pageSize"
        :total="filteredItems.length"
        layout="total, prev, pager, next"
        @current-change="onPageChange"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" title="科室详情" width="680px" destroy-on-close>
      <div v-if="detailLoading" class="detail-loading">加载中…</div>
      <el-descriptions v-else-if="detail" :column="2" border size="small">
        <el-descriptions-item label="科室编码">{{ detail.dept_code }}</el-descriptions-item>
        <el-descriptions-item label="科室名称">{{ detail.dept_name_cn }}</el-descriptions-item>
        <el-descriptions-item label="科室类型">{{ detail.dept_type_name || deptTypeLabel(detail.dept_type) }}</el-descriptions-item>
        <el-descriptions-item label="上级科室">{{ detail.parent_dept_name || detail.parent_dept_code || "-" }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detail.status_name || deptStatusLabel(detail.status) }}</el-descriptions-item>
        <el-descriptions-item label="复核">{{ detail.review_status_name || deptReviewLabel(detail.review_status) }}</el-descriptions-item>
        <el-descriptions-item label="来源系统">{{ detail.source_system || "-" }}</el-descriptions-item>
        <el-descriptions-item label="来源表">{{ detail.source_table || "-" }}</el-descriptions-item>
        <el-descriptions-item label="最近同步" :span="2">{{ formatSyncTime(detail.last_source_sync_at) }}</el-descriptions-item>
      </el-descriptions>
      <el-table v-if="detail?.persons?.length" :data="detail.persons" size="small" class="detail-table">
        <el-table-column prop="person_name_cn" label="人员" min-width="120" />
        <el-table-column prop="person_code" label="工号" width="120" />
        <el-table-column prop="person_type" label="类型" width="100" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { getDepartmentDetail, getDepartments } from "@/api/identity";
import {
  DEPT_TYPE_OPTIONS,
  deptReviewLabel,
  deptStatusLabel,
  deptTypeLabel,
  formatSyncTime
} from "@/views/identity/departments/deptLabels";

interface DeptItem {
  dept_code: string;
  dept_name_cn: string;
  dept_type?: string;
  dept_type_name?: string;
  parent_dept_code?: string;
  parent_dept_name?: string;
  source_system?: string;
  source_table?: string;
  status?: string;
  status_name?: string;
  review_status?: string;
  review_status_name?: string;
  person_count?: number;
  last_source_sync_at?: string;
}

const items = ref<DeptItem[]>([]);
const loading = ref(false);
const keyword = ref("");
const typeFilter = ref("");
const statusFilter = ref("");
const page = ref(1);
const pageSize = 30;
const typeOptions = DEPT_TYPE_OPTIONS;

const filteredItems = computed(() => {
  const key = keyword.value.trim().toLowerCase();
  return items.value.filter(item => {
    if (typeFilter.value && String(item.dept_type) !== typeFilter.value) return false;
    if (statusFilter.value && item.status !== statusFilter.value) return false;
    if (!key) return true;
    return [item.dept_code, item.dept_name_cn, item.parent_dept_name, item.parent_dept_code]
      .some(value => String(value || "").toLowerCase().includes(key));
  });
});
const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize;
  return filteredItems.value.slice(start, start + pageSize);
});
const totalCount = computed(() => items.value.length);
const activeDeptCount = computed(() => items.value.filter(item => item.status === "active").length);
const inactiveDeptCount = computed(() => items.value.length - activeDeptCount.value);

const dialogVisible = ref(false);
const detailLoading = ref(false);
const detail = ref<any>(null);

function typeTag(value?: string) {
  if (value === "0") return "success";
  if (value === "1") return "warning";
  if (value === "2") return "primary";
  return "info";
}

function applyFilter() {
  page.value = 1;
}

function onPageChange() {
  /* pagination handled by computed slice */
}

async function loadData() {
  loading.value = true;
  try {
    const res = await getDepartments();
    items.value = res.data ?? [];
  } catch {
    ElMessage.error("加载科室列表失败");
  } finally {
    loading.value = false;
  }
}

async function showDetail(row: DeptItem) {
  dialogVisible.value = true;
  detailLoading.value = true;
  detail.value = null;
  try {
    const res = await getDepartmentDetail(row.dept_code);
    detail.value = res.data;
  } catch {
    ElMessage.error("加载科室详情失败");
  } finally {
    detailLoading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.identity-departments { padding: 4px; }
.page-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}
.page-head span { color: var(--text-secondary, #64748b); font-size: 12px; }
.dept-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.filters { display: flex; gap: 8px; }
.filter-md { width: 180px; }
.filter-sm { width: 120px; }
.dept-table { width: 100%; }
.pager { justify-content: flex-end; margin-top: 12px; }
.detail-loading { padding: 24px; text-align: center; }
.detail-table { margin-top: 12px; }
@media (max-width: 760px) {
  .dept-stat-grid { grid-template-columns: 1fr; }
  .list-head { flex-direction: column; align-items: stretch; }
}
</style>
