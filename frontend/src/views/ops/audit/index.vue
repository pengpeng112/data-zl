<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, ref } from "vue";
import { http } from "@/utils/http";
import { ElMessage } from "element-plus";
import AuditIcon from "~icons/ri/file-list-3-line";
import ErrorIcon from "~icons/ri/error-warning-line";
import RefreshIcon from "~icons/ri/refresh-line";
import ShieldIcon from "~icons/ri/shield-check-line";
import TimeIcon from "~icons/ri/time-line";

interface AuditLog {
  id: number;
  module: string;
  entity_type: string;
  entity_ref: string;
  action: string;
  operator: string;
  created_at: string;
}

defineOptions({ name: "OpsAudit" });

const tableData = ref<AuditLog[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const failedCount = computed(() => tableData.value.filter(item => ["failed", "reject"].includes(item.action)).length);
const successCount = computed(() => tableData.value.filter(item => ["success", "approve"].includes(item.action)).length);
const executeCount = computed(() => tableData.value.filter(item => item.action === "execute").length);
const latestTime = computed(() => tableData.value[0]?.created_at || "-");

function actionTagType(action: string): "primary" | "success" | "warning" | "danger" | "info" {
  const map: Record<string, "primary" | "success" | "warning" | "danger" | "info"> = {
    create: "primary",
    approve: "success",
    reject: "danger",
    execute: "warning",
    success: "success",
    failed: "danger"
  };
  return map[action] || "info";
}

function actionLabel(action: string) {
  const map: Record<string, string> = {
    create: "创建",
    approve: "审批通过",
    reject: "审批拒绝",
    execute: "执行",
    success: "成功",
    failed: "失败"
  };
  return map[action] || action || "-";
}

async function fetchData() {
  loading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/govern/audit-logs", {
      params: { module: "ops", page: page.value, page_size: pageSize.value }
    });
    tableData.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch {
    ElMessage.error("获取审计日志失败");
  } finally {
    loading.value = false;
  }
}

function handlePageChange(p: number) {
  page.value = p;
  fetchData();
}

function handleSizeChange(s: number) {
  pageSize.value = s;
  page.value = 1;
  fetchData();
}

onMounted(fetchData);
</script>

<template>
  <div class="ops-audit-page">
    <RePageHeader
      title="运维审计日志"
      subtitle="记录运维工具、审批、执行和失败事件，保留操作人、对象和时间证据。"
    >
      <template #icon><AuditIcon /></template>
      <template #actions>
        <el-button type="primary" :icon="RefreshIcon" :loading="loading" @click="fetchData">
          刷新
        </el-button>
      </template>
    </RePageHeader>

    <section class="audit-stats">
      <ReStatCard label="当前页日志" :value="tableData.length" tone="primary" helper="按最近时间排序">
        <template #icon><AuditIcon /></template>
      </ReStatCard>
      <ReStatCard label="成功/通过" :value="successCount" tone="accent" helper="当前页统计">
        <template #icon><ShieldIcon /></template>
      </ReStatCard>
      <ReStatCard label="执行动作" :value="executeCount" tone="warning" helper="当前页统计">
        <template #icon><TimeIcon /></template>
      </ReStatCard>
      <ReStatCard label="失败/拒绝" :value="failedCount" tone="danger" :helper="`最近：${latestTime}`">
        <template #icon><ErrorIcon /></template>
      </ReStatCard>
    </section>

    <el-card class="audit-card" shadow="never">
      <ReToolbar title="审计明细">
        <el-tag type="info" effect="plain">模块：ops</el-tag>
        <el-tag type="primary" effect="plain">总数 {{ total }}</el-tag>
        <template #actions>
          <el-button :icon="RefreshIcon" :loading="loading" @click="fetchData">重新加载</el-button>
        </template>
      </ReToolbar>

      <el-table v-loading="loading" :data="tableData" class="medical-data-table" size="small" stripe>
        <el-table-column prop="id" label="日志ID" width="90" fixed="left" />
        <el-table-column prop="entity_type" label="实体类型" width="130" show-overflow-tooltip />
        <el-table-column prop="entity_ref" label="实体引用" min-width="180" show-overflow-tooltip />
        <el-table-column prop="action" label="操作" width="120">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">
              {{ actionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作人" width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="190" />
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.ops-audit-page {
  padding: 4px;
}

.audit-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.audit-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);

  :deep(.el-card__body) {
    display: grid;
    gap: 14px;
  }
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);

  font-size: 13px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1180px) {
  .audit-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .audit-stats {
    grid-template-columns: 1fr;
  }

  .pagination-wrap {
    justify-content: flex-start;
    overflow-x: auto;
  }
}
</style>
