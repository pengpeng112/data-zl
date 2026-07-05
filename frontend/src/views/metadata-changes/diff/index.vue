<template>
  <div class="metadata-diff">
    <el-card shadow="never">
      <template #header>
        <span>快照对比</span>
      </template>

      <div class="diff-form">
        <el-select
          v-model="fromId"
          placeholder="源快照"
          clearable
          style="width: 260px"
          filterable
        >
          <el-option
            v-for="sn in snapshots"
            :key="sn.id"
            :label="`#${sn.id} ${sn.label || ''} (${sn.snapshot_time || ''})`"
            :value="sn.id"
          />
        </el-select>
        <span style="margin: 0 12px; font-size: 16px; color: #409eff">→</span>
        <el-select
          v-model="toId"
          placeholder="目标快照"
          clearable
          style="width: 260px"
          filterable
        >
          <el-option
            v-for="sn in snapshots"
            :key="sn.id"
            :label="`#${sn.id} ${sn.label || ''} (${sn.snapshot_time || ''})`"
            :value="sn.id"
          />
        </el-select>
        <el-button
          type="primary"
          :loading="diffRunning"
          :disabled="!fromId || !toId || fromId === toId"
          style="margin-left: 12px"
          @click="runDiff"
        >
          执行对比
        </el-button>
      </div>

      <div class="snapshot-selector-hint">
        <span style="font-size: 12px; color: #909399">提示：</span>
        <el-select
          v-model="sourceCode"
          placeholder="先选择数据源，加载快照列表"
          clearable
          style="width: 220px; margin-left: 8px"
          @change="loadSnapshots"
        >
          <el-option label="HIS (8.216)" value="his_8216" />
          <el-option label="EMR (JHEMR)" value="jhemr" />
          <el-option label="LIS" value="lis" />
          <el-option label="PACS" value="pacs" />
          <el-option label="YDHL" value="ydhl" />
          <el-option label="ODS" value="ods" />
        </el-select>
      </div>
    </el-card>

    <template v-if="diffResult">
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <el-card shadow="never">
            <el-statistic title="变更事件数" :value="diffResult.total_changes ?? 0" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <el-statistic title="关联质量问题数" :value="diffResult.linked_to_quality_findings ?? 0" />
          </el-card>
        </el-col>
      </el-row>

      <el-card v-if="diffResult.changes && diffResult.changes.length > 0" shadow="never" style="margin-top: 16px">
        <template #header>
          <span>对比结果 — 变更事件</span>
        </template>
        <el-table :data="diffResult.changes" stripe>
          <el-table-column prop="id" label="ID" width="80" align="center" />
          <el-table-column prop="system_code" label="系统" width="90" />
          <el-table-column prop="change_type" label="变更类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" disable-transitions>{{ changeTypeLabel(row.change_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="table_name" label="表名" min-width="180" show-overflow-tooltip />
          <el-table-column prop="column_name" label="字段名" min-width="140" show-overflow-tooltip />
          <el-table-column prop="severity" label="严重程度" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="severityColor(row.severity)" size="small" disable-transitions>
                {{ severityLabel(row.severity) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" disable-transitions>
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="160" />
        </el-table>
      </el-card>

      <el-empty
        v-else-if="diffResult && (!diffResult.changes || diffResult.changes.length === 0)"
        description="两个快照之间未检测到变更"
        style="margin-top: 16px"
      />
    </template>

    <el-empty
      v-if="!diffResult"
      description="选择两个快照并执行对比"
      style="margin-top: 16px"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { ElMessage } from "element-plus";
import {
  getSourceSnapshots,
  runMetadataDiff
} from "@/api/metadata";

const sourceCode = ref("");
const snapshots = ref<any[]>([]);
const fromId = ref<number | null>(null);
const toId = ref<number | null>(null);
const diffRunning = ref(false);
const diffResult = ref<any>(null);

async function loadSnapshots() {
  if (!sourceCode.value) {
    snapshots.value = [];
    fromId.value = null;
    toId.value = null;
    diffResult.value = null;
    return;
  }
  try {
    const res = await getSourceSnapshots(sourceCode.value);
    snapshots.value = res.data ?? [];
  } catch {
    snapshots.value = [];
  }
}

async function runDiff() {
  if (fromId.value == null || toId.value == null) return;
  diffRunning.value = true;
  try {
    const res = await runMetadataDiff({
      from_id: fromId.value,
      to_id: toId.value
    });
    diffResult.value = res.data;
    ElMessage.success("对比完成");
  } catch {
    diffResult.value = null;
  } finally {
    diffRunning.value = false;
  }
}

function changeTypeLabel(type: string): string {
  const map: Record<string, string> = {
    table_added: "新增表",
    table_removed: "删除表",
    column_added: "新增字段",
    column_removed: "删除字段",
    column_type_changed: "字段类型变更",
    column_renamed: "字段重命名"
  };
  return map[type] ?? type;
}

function severityLabel(sev: string): string {
  const map: Record<string, string> = {
    info: "提示",
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重"
  };
  return map[sev] ?? sev;
}

function severityColor(sev: string): any {
  const map: Record<string, string> = {
    info: "info",
    low: "success",
    medium: "warning",
    high: "danger",
    critical: "danger"
  };
  return map[sev] ?? "info";
}

function statusLabel(s: string): string {
  const map: Record<string, string> = {
    open: "待处理",
    acknowledged: "已确认",
    ignored: "已忽略",
    resolved: "已解决"
  };
  return map[s] ?? s;
}

function statusTagType(s: string): any {
  const map: Record<string, string> = {
    open: "danger",
    acknowledged: "warning",
    ignored: "info",
    resolved: "success"
  };
  return map[s] ?? "info";
}
</script>

<style scoped>
.diff-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}
.snapshot-selector-hint {
  margin-top: 12px;
  display: flex;
  align-items: center;
}
</style>
