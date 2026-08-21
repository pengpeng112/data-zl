<template>
  <div class="sync-logs-page">
    <div class="page-head">
      <strong>同步日志</strong>
      <span>夜间定时把人员同步到合理用药、嘉和电子病历；动作记录显示工号、脱敏姓名、科室和结果，便于按人排查。</span>
    </div>

    <section class="stat-grid">
      <ReStatCard label="最近一次" :value="overview.last_run?.status_name || '-'" :tone="statusTone(overview.last_run?.status)" />
      <ReStatCard label="成功 / 失败" :value="`${overview.last_run?.success_count ?? 0} / ${overview.last_run?.failed_count ?? 0}`" tone="accent" />
      <ReStatCard label="合理用药熔断" :value="breakerText(overview.circuit_breakers?.cdms)" :tone="overview.circuit_breakers?.cdms?.is_open ? 'danger' : 'info'" />
      <ReStatCard label="嘉和熔断" :value="breakerText(overview.circuit_breakers?.jhemr)" :tone="overview.circuit_breakers?.jhemr?.is_open ? 'danger' : 'info'" />
      <ReStatCard label="未关闭告警" :value="overview.open_alerts || 0" :tone="overview.open_alerts ? 'warning' : 'info'" />
    </section>

    <div v-if="latestSubtasks.length" class="subtask-row">
      <article v-for="item in latestSubtasks" :key="item.subtask_code" class="subtask-card">
        <div class="subtask-card__head">
          <strong>{{ item.subtask_name }}</strong>
          <el-tag size="small" :type="syncStatusTag(item.status)">{{ item.status_name }}</el-tag>
        </div>
        <p>{{ item.target_system_name || "多系统" }}</p>
        <p>成功 {{ item.succeeded_count }} · 跳过 {{ item.skipped_count }} · 失败 {{ item.failed_count }}</p>
      </article>
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="list-head">
          <strong>历史运行（{{ total }}）</strong>
          <div class="list-filters">
            <el-input
              v-model="empNoFilter"
              clearable
              placeholder="按工号查询"
              class="emp-filter"
              @keyup.enter="loadRuns(1)"
              @clear="loadRuns(1)"
            />
            <el-select v-model="statusFilter" clearable placeholder="全部状态" class="status-filter" @change="loadRuns(1)">
              <el-option label="成功" value="success" />
              <el-option label="部分成功" value="partial_success" />
              <el-option label="失败" value="failed" />
              <el-option label="已跳过" value="skipped" />
            </el-select>
          </div>
        </div>
      </template>
      <el-table v-loading="loading" :data="runs" size="small" stripe @row-click="openRun">
        <el-table-column label="开始时间" min-width="160">
          <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="触发方式" width="140">
          <template #default="{ row }">{{ row.triggered_by_name }}</template>
        </el-table-column>
        <el-table-column label="结果" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="syncStatusTag(row.status)">{{ row.status_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="候选" width="70" align="center" prop="candidates_total" />
        <el-table-column label="成功" width="70" align="center" prop="success_count" />
        <el-table-column label="失败" width="70" align="center" prop="failed_count" />
        <el-table-column label="耗时" width="110">
          <template #default="{ row }">{{ formatDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column label="各系统" min-width="220">
          <template #default="{ row }">
            <span v-for="item in row.subtasks" :key="item.subtask_code" class="subtask-pill">
              {{ item.subtask_name }} {{ item.status_name }}
            </span>
            <span v-if="!row.subtasks?.length">-</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        class="pager"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadRuns"
      />
    </el-card>

    <el-drawer v-model="drawerVisible" size="640px" title="运行详情">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="运行编号">{{ detail.run_id }}</el-descriptions-item>
          <el-descriptions-item label="触发方式">{{ detail.triggered_by_name }}</el-descriptions-item>
          <el-descriptions-item label="结果">{{ detail.status_name }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ formatDuration(detail.duration_ms) }}</el-descriptions-item>
          <el-descriptions-item label="开始">{{ formatDateTime(detail.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束">{{ formatDateTime(detail.finished_at) }}</el-descriptions-item>
        </el-descriptions>

        <h4>各系统子任务</h4>
        <el-table :data="detail.subtasks || []" size="small">
          <el-table-column prop="subtask_name" label="子任务" min-width="140" />
          <el-table-column prop="target_system_name" label="目标系统" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="syncStatusTag(row.status)">{{ row.status_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="succeeded_count" label="成功" width="70" />
          <el-table-column prop="skipped_count" label="跳过" width="70" />
          <el-table-column prop="failed_count" label="失败" width="70" />
        </el-table>

        <h4>批次结果</h4>
        <el-table :data="detail.batches || []" size="small">
          <el-table-column prop="batch_type" label="类型" width="110" />
          <el-table-column prop="status_name" label="总状态" width="100" />
          <el-table-column prop="cdms_status_name" label="合理用药" width="100" />
          <el-table-column prop="jhemr_status_name" label="嘉和" width="100" />
          <el-table-column label="开始" min-width="150">
            <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
          </el-table-column>
        </el-table>

        <h4>动作记录</h4>
        <el-table :data="detail.actions || []" size="small">
          <el-table-column prop="emp_no" label="工号" width="110" />
          <el-table-column prop="person_name_masked" label="姓名" width="90" />
          <el-table-column prop="dept_name" label="科室" min-width="120" />
          <el-table-column prop="target_system_name" label="系统" width="110" />
          <el-table-column prop="subtask_name" label="子任务" min-width="120" />
          <el-table-column prop="status_name" label="结果" width="90" />
          <el-table-column label="原因" min-width="140">
            <template #default="{ row }">{{ row.reason_name || row.error_class || "-" }}</template>
          </el-table-column>
          <el-table-column prop="account_fingerprint" label="账号指纹" width="120" />
        </el-table>

        <h4 v-if="detail.alerts?.length">告警</h4>
        <el-table v-if="detail.alerts?.length" :data="detail.alerts" size="small">
          <el-table-column prop="alert_type" label="类型" min-width="140" />
          <el-table-column prop="severity" label="级别" width="80" />
          <el-table-column prop="error_class" label="错误类型" min-width="140" />
          <el-table-column prop="occurrence_count" label="次数" width="70" />
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { http } from "@/utils/http";
import { formatDateTime, formatDuration, syncStatusTag } from "@/views/identity/sync-logs/syncLogLabels";

interface SubtaskItem {
  subtask_code: string;
  subtask_name: string;
  target_system_name?: string;
  status: string;
  status_name: string;
  succeeded_count: number;
  skipped_count: number;
  failed_count: number;
}

interface RunItem {
  run_id: string;
  triggered_by_name: string;
  status: string;
  status_name: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  candidates_total: number;
  success_count: number;
  failed_count: number;
  subtasks: SubtaskItem[];
}

const loading = ref(false);
const runs = ref<RunItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const statusFilter = ref("");
const empNoFilter = ref("");
const overview = ref<any>({ open_alerts: 0, circuit_breakers: {} });
const drawerVisible = ref(false);
const detail = ref<any>(null);

const latestSubtasks = computed(() => overview.value.last_run?.subtasks || []);

function statusTone(status?: string) {
  if (status === "success") return "accent";
  if (status === "partial_success" || status === "running") return "warning";
  if (status === "failed" || status === "overdue" || status === "misconfigured") return "danger";
  return "info";
}

function breakerText(row?: { is_open?: boolean; consecutive_failures?: number }) {
  if (!row) return "正常";
  return row.is_open ? `已熔断（连续失败 ${row.consecutive_failures || 0}）` : "正常";
}

async function loadRuns(nextPage?: number) {
  if (nextPage) page.value = nextPage;
  loading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/identity-sync/runs", {
      params: {
        page: page.value,
        page_size: pageSize,
        status: statusFilter.value || undefined,
        emp_no: empNoFilter.value.trim() || undefined
      }
    });
    const payload = res.data || {};
    runs.value = payload.items || [];
    total.value = payload.total || 0;
    overview.value = payload.overview || { open_alerts: 0, circuit_breakers: {} };
  } catch (error: any) {
    runs.value = [];
    ElMessage.error(error?.response?.data?.detail || "同步日志加载失败");
  } finally {
    loading.value = false;
  }
}

async function openRun(row: RunItem) {
  try {
    const res = await http.request<any>("get", `/api/v1/identity-sync/runs/${row.run_id}`);
    detail.value = res.data;
    drawerVisible.value = true;
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || "运行详情加载失败");
  }
}

onMounted(() => {
  loadRuns(1);
});
</script>

<style scoped>
.sync-logs-page { padding: 4px; }
.page-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}
.page-head span { color: var(--text-secondary, #64748b); font-size: 12px; }
.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.subtask-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.subtask-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--el-bg-color);
}
.subtask-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.subtask-card p { margin: 0; color: var(--text-secondary, #64748b); font-size: 12px; }
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.list-filters { display: flex; gap: 8px; }
.emp-filter { width: 160px; }
.status-filter { width: 140px; }
.pager { justify-content: flex-end; margin-top: 12px; }
.subtask-pill {
  display: inline-block;
  margin-right: 8px;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
}
h4 { margin: 16px 0 8px; font-size: 14px; }
</style>
