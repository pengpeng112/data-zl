<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { formatTime } from "@/utils/format";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  getSchedulerOpsBoard,
  type SchedulerOpsBoard
} from "@/api/ops";
import RefreshIcon from "~icons/ep/refresh";
import PulseIcon from "~icons/ri/pulse-line";
import JobIcon from "~icons/ri/calendar-check-line";
import ShieldIcon from "~icons/ri/shield-check-line";
import WarnIcon from "~icons/ri/alarm-warning-line";

defineOptions({ name: "OpsSchedulerBoard" });

const board = ref<SchedulerOpsBoard | null>(null);
const loading = ref(false);
let timer: ReturnType<typeof setInterval> | null = null;
const AUTO_REFRESH_MS = 30_000;

async function fetchBoard(silent = false) {
  loading.value = true;
  try {
    const resp = await getSchedulerOpsBoard();
    board.value = resp.data;
  } catch (err) {
    if (!silent) ElMessage.error("看板加载失败");
  } finally {
    loading.value = false;
  }
}

function onMountedStart() {
  fetchBoard();
  timer = setInterval(() => fetchBoard(true), AUTO_REFRESH_MS);
}

onMounted(onMountedStart);
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

const switchEntries = computed(() => {
  const s = board.value?.scheduler_switches;
  if (!s) return [];
  return [
    { key: "identity_nightly_enabled", label: "身份夜间同步", on: s.identity_nightly_enabled },
    { key: "dict_medical_push_enabled", label: "字典外发推送", on: s.dict_medical_push_enabled },
    { key: "query_schedule_enabled", label: "查询调度", on: s.query_schedule_enabled },
    { key: "quality_execution_scheduler_enabled", label: "质量执行调度", on: s.quality_execution_scheduler_enabled },
    { key: "ai_context_cache_cleanup_enabled", label: "AI上下文过期清理", on: s.ai_context_cache_cleanup_enabled }
  ];
});

const enabledSwitchCount = computed(() => switchEntries.value.filter(s => s.on).length);
const qualityWorkers = computed(() => board.value?.worker_heartbeats.quality_runs ?? []);
const activeWorkers = computed(() => qualityWorkers.value.filter(w => w.lease_active).length);
const staleWorkers = computed(() => qualityWorkers.value.filter(w => !w.lease_active).length);

function heartbeatAge(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "无心跳";
  if (seconds < 90) return `${Math.round(seconds)} 秒前`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} 分钟前`;
  return `${(seconds / 3600).toFixed(1)} 小时前`;
}

function leaseTone(on: boolean): "success" | "danger" {
  return on ? "success" : "danger";
}
</script>

<template>
  <div class="scheduler-board">
    <RePageHeader
      title="调度与Worker心跳看板"
      :subtitle="`只读视图（${formatTime(board?.generated_at)}）——任务启停请走既有端点，本页不做任何写操作`"
    >
      <template #actions>
        <el-button type="primary" :icon="RefreshIcon" :loading="loading" @click="fetchBoard()">
          刷新
        </el-button>
      </template>
    </RePageHeader>

    <section class="board-stats">
      <ReStatCard label="启用调度开关" :value="`${enabledSwitchCount}/5`" tone="primary" helper="运行时配置，只读呈现">
        <template #icon><JobIcon /></template>
      </ReStatCard>
      <ReStatCard label="表驱动常驻任务" :value="board?.scheduled_jobs.length ?? 0" tone="accent" helper="asset_scheduler_jobs（scheduled）">
        <template #icon><PulseIcon /></template>
      </ReStatCard>
      <ReStatCard label="租约活跃Worker" :value="activeWorkers" tone="info" helper="质量执行运行中且租约未过期">
        <template #icon><ShieldIcon /></template>
      </ReStatCard>
      <ReStatCard label="心跳过期Worker" :value="staleWorkers" :tone="staleWorkers > 0 ? 'danger' : 'warning'" helper="租约已过期，需人工排查">
        <template #icon><WarnIcon /></template>
      </ReStatCard>
    </section>

    <el-card shadow="never" class="board-card">
      <template #header>
        <div class="card-head">
          <span>调度开关状态</span>
          <el-tag type="info" effect="plain">时区 {{ board?.scheduler_switches.scheduler_timezone ?? "-" }}</el-tag>
        </div>
      </template>
      <div class="switch-row">
        <div v-for="s in switchEntries" :key="s.key" class="switch-item">
          <span class="switch-label">{{ s.label }}</span>
          <el-tag :type="s.on ? 'success' : 'info'" effect="plain">{{ s.on ? "启用" : "关闭" }}</el-tag>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="board-card">
      <template #header>
        <div class="card-head">
          <span>常驻调度任务（最近 50 条 scheduled）</span>
          <el-tag type="info" effect="plain">合计 {{ board?.jobs_summary.total ?? 0 }} 条任务记录</el-tag>
        </div>
      </template>
      <el-table :data="board?.scheduled_jobs ?? []" size="small" border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="job_type" label="类型" width="140" />
        <el-table-column prop="source_code" label="源" width="120" />
        <el-table-column prop="schedule_cron" label="cron" width="130" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'primary' : 'info'" effect="plain">
              {{ row.status ?? "-" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近开始" width="150">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="最近结束" width="150">
          <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
        </el-table-column>
        <el-table-column prop="total_processed" label="处理数" width="90" />
        <el-table-column prop="error_message" label="错误" min-width="160" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card shadow="never" class="board-card">
      <template #header>
        <div class="card-head">
          <span>质量执行 Worker 心跳</span>
          <el-tag type="info" effect="plain">heartbeat_at / lease_owner</el-tag>
        </div>
      </template>
      <el-table :data="qualityWorkers" size="small" border>
        <el-table-column prop="run_code" label="运行单" min-width="140" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="detector_kind" label="检测器" width="110" />
        <el-table-column prop="lease_owner" label="租约持有者" width="140" />
        <el-table-column label="心跳时间" width="150">
          <template #default="{ row }">{{ formatTime(row.heartbeat_at) }}</template>
        </el-table-column>
        <el-table-column label="心跳距今" width="120">
          <template #default="{ row }">{{ heartbeatAge(row.heartbeat_age_seconds) }}</template>
        </el-table-column>
        <el-table-column label="租约" width="110">
          <template #default="{ row }">
            <el-tag :type="leaseTone(row.lease_active)" effect="plain">{{ row.lease_active ? "活跃" : "过期" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="租约到期" width="150">
          <template #default="{ row }">{{ formatTime(row.lease_expires_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="board-card">
      <template #header>
        <div class="card-head">
          <span>身份夜间同步心跳</span>
          <el-tag type="info" effect="plain">provider_heartbeat_at</el-tag>
        </div>
      </template>
      <el-table :data="board?.worker_heartbeats.identity_nightly ?? []" size="small" border>
        <el-table-column prop="run_id" label="运行ID" min-width="150" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="lock_holder" label="锁持有者" width="140" />
        <el-table-column prop="provider_code" label="Provider" width="110" />
        <el-table-column label="Provider 心跳" width="150">
          <template #default="{ row }">{{ formatTime(row.provider_heartbeat_at) }}</template>
        </el-table-column>
        <el-table-column label="心跳距今" width="130">
          <template #default="{ row }">{{ heartbeatAge(row.provider_heartbeat_age_seconds) }}</template>
        </el-table-column>
        <el-table-column label="开始" width="150">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="结束" width="150">
          <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="board-card">
      <template #header>
        <div class="card-head">
          <span>调度任务启停/创建审计（最近 20 条）</span>
          <el-tag type="info" effect="plain">启停人 / 对象 / 时间</el-tag>
        </div>
      </template>
      <el-table :data="board?.scheduler_job_audit_trail ?? []" size="small" border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="action" label="动作" width="110" />
        <el-table-column prop="operator" label="操作人" width="140" />
        <el-table-column label="对象" min-width="180">
          <template #default="{ row }">{{ row.entity_type }} #{{ row.entity_ref }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.scheduler-board {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.board-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.switch-row {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
}

.switch-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.switch-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
