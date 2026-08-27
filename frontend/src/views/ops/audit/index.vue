<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { listOpsEvents } from "@/api/ops";
import { getMedicalImportRuns } from "@/api/dict";
import { exportAuditLogs, getAuditLogsSummary, getGovernAuditLogs } from "@/api/ops";
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

const activeTab = ref("audit");
const tableData = ref<AuditLog[]>([]);
const eventData = ref<any[]>([]);
const dictImportData = ref<any[]>([]);
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
    if (activeTab.value === "events") {
      const res = await listOpsEvents({ page: page.value, page_size: pageSize.value });
      eventData.value = res.data?.items || [];
      total.value = res.data?.total || 0;
    } else if (activeTab.value === "dict") {
      const res = await getMedicalImportRuns({ page: page.value, page_size: pageSize.value });
      dictImportData.value = res.data?.items || [];
      total.value = res.data?.total || 0;
    } else {
      const res = await getGovernAuditLogs({
        module: "ops",
        operator: auditFilters.operator || undefined,
        action: auditFilters.action || undefined,
        entity_ref: auditFilters.entity_ref || undefined,
        created_from: auditFilters.created_from || undefined,
        created_to: auditFilters.created_to || undefined,
        page: page.value,
        page_size: pageSize.value
      });
      tableData.value = res.data?.items || [];
      total.value = res.data?.total || 0;
    }
  } catch (error) {
    tableData.value = [];
    eventData.value = [];
    dictImportData.value = [];
    total.value = 0;
    ElMessage.error(String((error as any)?.response?.data?.detail || "获取日志失败"));
  } finally {
    loading.value = false;
  }
}

function handlePageChange(p: number) {
  page.value = p;
  fetchData();
}

function onTabChange() {
  page.value = 1;
  fetchData();
}

function handleSizeChange(s: number) {
  pageSize.value = s;
  page.value = 1;
  fetchData();
}

const summaryText = ref("");

const auditFilters = reactive({ operator: "", action: "", entity_ref: "", created_from: "", created_to: "" });

function doFilter() {
  page.value = 1;
  fetchData();
}

async function loadSummary() {
  try {
    const res = await getAuditLogsSummary({ module: "ops" });
    summaryText.value = `共 ${res.data.total} 条；按动作：${Object.entries(res.data.by_action).slice(0, 6).map(([k, v]) => `${k} ${v}`).join("、")}`;
  } catch {
    summaryText.value = "";
    ElMessage.error("统计加载失败");
  }
}

async function doExport() {
  try {
    const res = await exportAuditLogs({ module: "ops" });
    const blob = new Blob([res as unknown as BlobPart], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "audit-logs.csv";
    link.click();
    URL.revokeObjectURL(url);
  } catch {
    ElMessage.error("导出失败");
  }
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
      <div v-if="activeTab === 'audit'" class="audit-filters">
        <el-input v-model="auditFilters.operator" placeholder="操作人" clearable size="small" class="f-op" @keyup.enter="doFilter" @clear="doFilter" />
        <el-input v-model="auditFilters.action" placeholder="动作，如 approve" clearable size="small" class="f-act" @keyup.enter="doFilter" @clear="doFilter" />
        <el-input v-model="auditFilters.entity_ref" placeholder="实体引用包含" clearable size="small" class="f-ent" @keyup.enter="doFilter" @clear="doFilter" />
        <el-date-picker v-model="auditFilters.created_from" type="datetime" placeholder="开始时间" size="small" class="f-time" value-format="YYYY-MM-DDTHH:mm:ss" @change="doFilter" />
        <el-date-picker v-model="auditFilters.created_to" type="datetime" placeholder="结束时间" size="small" class="f-time" value-format="YYYY-MM-DDTHH:mm:ss" @change="doFilter" />
        <el-button size="small" type="primary" @click="doFilter">筛选</el-button>
      </div>
      <div class="audit-actions">
        <el-button size="small" @click="loadSummary">全量统计</el-button>
        <el-button size="small" type="primary" @click="doExport">导出 CSV</el-button>
      </div>
      <el-alert v-if="summaryText" type="info" :closable="false" :title="summaryText" show-icon class="summary-alert" />
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="治理审计" name="audit" />
        <el-tab-pane label="执行日志" name="events" />
        <el-tab-pane label="字典同步日志" name="dict" />
      </el-tabs>

      <ReToolbar :title="activeTab === 'dict' ? '字典导入批次' : activeTab === 'events' ? '统一执行事件' : '审计明细'">
        <el-tag type="info" effect="plain">脱敏展示</el-tag>
        <el-tag type="primary" effect="plain">总数 {{ total }}</el-tag>
        <template #actions>
          <el-button :icon="RefreshIcon" :loading="loading" @click="fetchData">重新加载</el-button>
        </template>
      </ReToolbar>

      <el-table
        v-if="activeTab === 'audit'"
        v-loading="loading"
        :data="tableData"
        class="medical-data-table"
        size="small"
        stripe
      >
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

      <el-table
        v-else-if="activeTab === 'events'"
        v-loading="loading"
        :data="eventData"
        class="medical-data-table"
        size="small"
        stripe
      >
        <el-table-column prop="event_id" label="事件ID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="module" label="模块" width="100" />
        <el-table-column prop="action" label="动作" width="140" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="target_source_code" label="目标" width="140" />
        <el-table-column prop="affected_count" label="影响行" width="90" />
        <el-table-column prop="summary_masked" label="摘要" min-width="180" show-overflow-tooltip />
        <el-table-column prop="operator" label="操作人" width="120" />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>

      <el-table
        v-else
        v-loading="loading"
        :data="dictImportData"
        class="medical-data-table"
        size="small"
        stripe
      >
        <el-table-column prop="batch_code" label="批次" min-width="160" show-overflow-tooltip />
        <el-table-column prop="mode" label="模式" width="90" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="operator" label="操作人" width="140" />
        <el-table-column prop="diagnosis_file_name" label="诊断文件" min-width="160" show-overflow-tooltip />
        <el-table-column prop="operation_file_name" label="手术文件" min-width="160" show-overflow-tooltip />
        <el-table-column prop="error_summary" label="错误" min-width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="180" />
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
.audit-actions { display: flex; gap: 8px; margin-bottom: 8px; }
.summary-alert { margin-bottom: 8px; }
.audit-filters { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
.f-op, .f-act { width: 140px; }
.f-ent { width: 180px; }
.f-time { width: 200px; }
</style>