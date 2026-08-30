<template>
  <!--
    146 E10（R5）：质检 run（检查批次/执行记录）共享表格。
    「质控任务」与「执行记录」两个 Tab 的表格此前重复维护；本组件合并为一份，
    通过 props 控制差异列，业务加载逻辑仍由父页面负责。
  -->
  <div>
    <el-table v-loading="loading" :data="runs" stripe size="small" :class="{ 'clickable-row': clickable }" @row-click="onRowClick">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="started_at" label="开始时间" width="170" />
      <el-table-column v-if="showTaskId" prop="task_id" label="任务ID" width="80" />
      <el-table-column v-if="showTriggeredBy" prop="triggered_by" label="触发方式" width="80" />
      <el-table-column v-if="showSystem" label="业务系统" width="180">
        <template #default="{ row }">
          {{ row.system_name_cn || systemNameMap[row.system_code] || row.system_code || '-' }}
          <small class="system-code-inline">{{ row.system_code }}</small>
        </template>
      </el-table-column>
      <el-table-column prop="total_rules" label="规则数" width="80" align="center" />
      <el-table-column prop="total_findings" label="发现问题" width="100" align="center" />
      <el-table-column prop="total_records" label="扫描记录" width="100" align="center" />
      <el-table-column prop="error_records" label="异常记录" width="100" align="center" />
      <el-table-column label="通过率" width="100" align="center">
        <template #default="{ row }">
          <span v-if="row.pass_rate != null" :class="passRateClass(row.pass_rate)">
            {{ formatPercent(row.pass_rate) }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag
            :type="row.status === 'success' ? 'success' : row.status === 'running' ? 'warning' : 'danger'"
            size="small"
          >
            {{ runStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="showFailedReason" prop="failed_reason" label="失败原因" min-width="150" show-overflow-tooltip />
    </el-table>
    <el-pagination
      :current-page="page"
      class="mt15"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="(value: number) => emit('page-change', value)"
    />
  </div>
</template>

<script setup lang="ts">
import { passRateClass, formatPercent, runStatusLabel, type CheckRunItem } from "@/views/asset/quality/qualityContracts";

withDefaults(
  defineProps<{
    runs: CheckRunItem[];
    loading?: boolean;
    clickable?: boolean;
    showTaskId?: boolean;
    showTriggeredBy?: boolean;
    showSystem?: boolean;
    showFailedReason?: boolean;
    systemNameMap?: Record<string, string>;
    page?: number;
    pageSize?: number;
    total?: number;
  }>(),
  {
    loading: false,
    clickable: false,
    showTaskId: false,
    showTriggeredBy: false,
    showSystem: false,
    showFailedReason: false,
    systemNameMap: () => ({}),
    page: 1,
    pageSize: 20,
    total: 0
  }
);

const emit = defineEmits<{
  "row-click": [row: CheckRunItem];
  "page-change": [page: number];
}>();

function onRowClick(row: CheckRunItem) {
  if (row) emit("row-click", row);
}
</script>

<style scoped>
.clickable-row { cursor: pointer; }
.system-code-inline { display: block; color: var(--text-secondary); font-size: 11px; }
.mt15 { margin-top: 15px; }
</style>
