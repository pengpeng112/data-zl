<template>
  <div class="metadata-changes">
    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="全部变更" :value="summary.total ?? 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="待处理" :value="summary.open ?? 0">
            <template #suffix>
              <el-tag type="danger" size="small">NEW</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="已确认" :value="summary.acknowledged ?? 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="已解决" :value="summary.resolved ?? 0" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <span>变更事件列表</span>
      </template>

      <div class="filter-bar">
        <el-select
          v-model="filters.system_code"
          placeholder="所属系统"
          clearable
          style="width: 160px"
          @change="doSearch"
        >
          <el-option label="HIS" value="HIS" />
          <el-option label="EMR" value="EMR" />
          <el-option label="LIS" value="LIS" />
          <el-option label="PACS" value="PACS" />
          <el-option label="YDHL" value="YDHL" />
          <el-option label="SM" value="SM" />
          <el-option label="ODS" value="ODS" />
        </el-select>

        <el-select
          v-model="filters.change_type"
          placeholder="变更类型"
          clearable
          style="width: 160px; margin-left: 12px"
          @change="doSearch"
        >
          <el-option label="新增表" value="table_added" />
          <el-option label="删除表" value="table_removed" />
          <el-option label="新增字段" value="column_added" />
          <el-option label="删除字段" value="column_removed" />
          <el-option label="字段类型变更" value="column_type_changed" />
          <el-option label="字段重命名" value="column_renamed" />
        </el-select>

        <el-select
          v-model="filters.severity"
          placeholder="严重程度"
          clearable
          style="width: 140px; margin-left: 12px"
          @change="doSearch"
        >
          <el-option label="提示" value="info" />
          <el-option label="低" value="low" />
          <el-option label="中" value="medium" />
          <el-option label="高" value="high" />
          <el-option label="严重" value="critical" />
        </el-select>

        <el-select
          v-model="filters.status"
          placeholder="状态"
          clearable
          style="width: 140px; margin-left: 12px"
          @change="doSearch"
        >
          <el-option label="待处理" value="open" />
          <el-option label="已确认" value="acknowledged" />
          <el-option label="已忽略" value="ignored" />
          <el-option label="已解决" value="resolved" />
        </el-select>

        <el-input
          v-model="filters.keyword"
          placeholder="搜索表名/字段名"
          clearable
          style="width: 220px; margin-left: 12px"
          @keyup.enter="doSearch"
        />
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        stripe
        style="margin-top: 12px"
        @row-click="showDetail"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="system_code" label="系统" width="90" />
        <el-table-column prop="change_type" label="变更类型" width="120">
          <template #default="{ row }">
            {{ changeTypeLabel(row.change_type) }}
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
            <el-tag
              :type="statusTagType(row.status)"
              size="small"
              disable-transitions
            >
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assigned_to" label="分配人" width="100" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'open'"
              type="primary"
              size="small"
              link
              @click.stop="acknowledge(row)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status === 'open'"
              type="warning"
              size="small"
              link
              @click.stop="ignore(row)"
            >
              忽略
            </el-button>
            <el-button
              v-if="row.status === 'acknowledged'"
              type="success"
              size="small"
              link
              @click.stop="resolve(row)"
            >
              解决
            </el-button>
            <el-button
              type="info"
              size="small"
              link
              @click.stop="openAssignDialog(row)"
            >
              分配
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        style="margin-top: 16px; justify-content: flex-end"
        @change="loadData"
      />
    </el-card>

    <el-dialog v-model="detailVisible" title="变更详情" width="700px">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="ID">{{ currentRow?.id }}</el-descriptions-item>
        <el-descriptions-item label="系统">{{ currentRow?.system_code }}</el-descriptions-item>
        <el-descriptions-item label="变更类型">
          {{ changeTypeLabel(currentRow?.change_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="severityColor(currentRow?.severity)" size="small" disable-transitions>
            {{ severityLabel(currentRow?.severity) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="表名">{{ currentRow?.table_name }}</el-descriptions-item>
        <el-descriptions-item label="字段名">{{ currentRow?.column_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(currentRow?.status)" size="small" disable-transitions>
            {{ statusLabel(currentRow?.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="分配人">{{ currentRow?.assigned_to || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ currentRow?.created_at }}</el-descriptions-item>
        <el-descriptions-item label="变更前值" :span="2">
          <pre v-if="currentRow?.before_value" class="json-block">{{ formatJson(currentRow.before_value) }}</pre>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="变更后值" :span="2">
          <pre v-if="currentRow?.after_value" class="json-block">{{ formatJson(currentRow.after_value) }}</pre>
          <span v-else>-</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog v-model="assignVisible" title="分配处理人" width="450px">
      <el-form :model="assignForm" label-width="80px">
        <el-form-item label="处理人">
          <el-input v-model="assignForm.assigned_to" placeholder="请输入处理人" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assignLoading" @click="doAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import {
  getMetadataChanges,
  updateMetadataChange,
  getChangesSummary
} from "@/api/metadata";

const loading = ref(false);
const items = ref<any[]>([]);
const summary = reactive({
  total: 0,
  open: 0,
  acknowledged: 0,
  resolved: 0
});

const filters = reactive({
  system_code: "",
  change_type: "",
  severity: "",
  status: "",
  keyword: ""
});

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
});

const detailVisible = ref(false);
const currentRow = ref<any>(null);

const assignVisible = ref(false);
const assignLoading = ref(false);
const assignForm = reactive({
  assigned_to: ""
});
let assignTargetId: number | null = null;

async function loadSummary() {
  try {
    const res = await getChangesSummary();
    Object.assign(summary, res.data);
  } catch {
    // ignore
  }
}

async function loadData() {
  loading.value = true;
  try {
    const res = await getMetadataChanges({
      system_code: filters.system_code || undefined,
      change_type: filters.change_type || undefined,
      severity: filters.severity || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
      page: pagination.page,
      page_size: pagination.page_size
    });
    items.value = res.data.items ?? [];
    pagination.total = res.data.total ?? 0;
  } catch {
    items.value = [];
    pagination.total = 0;
  } finally {
    loading.value = false;
  }
}

function doSearch() {
  pagination.page = 1;
  loadData();
}

function showDetail(row: any) {
  currentRow.value = row;
  detailVisible.value = true;
}

async function acknowledge(row: any) {
  try {
    await updateMetadataChange(row.id, { status: "acknowledged" });
    ElMessage.success("已确认");
    loadData();
    loadSummary();
  } catch {
    // handled
  }
}

async function ignore(row: any) {
  try {
    await updateMetadataChange(row.id, { status: "ignored" });
    ElMessage.success("已忽略");
    loadData();
    loadSummary();
  } catch {
    // handled
  }
}

async function resolve(row: any) {
  try {
    await updateMetadataChange(row.id, { status: "resolved" });
    ElMessage.success("已解决");
    loadData();
    loadSummary();
  } catch {
    // handled
  }
}

function openAssignDialog(row: any) {
  assignTargetId = row.id;
  assignForm.assigned_to = row.assigned_to || "";
  assignVisible.value = true;
}

async function doAssign() {
  if (!assignTargetId) return;
  assignLoading.value = true;
  try {
    await updateMetadataChange(assignTargetId, {
      assigned_to: assignForm.assigned_to
    });
    ElMessage.success("已分配");
    assignVisible.value = false;
    loadData();
  } catch {
    // handled
  } finally {
    assignLoading.value = false;
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

function formatJson(val: any): string {
  if (typeof val === "string") {
    try {
      return JSON.stringify(JSON.parse(val), null, 2);
    } catch {
      return val;
    }
  }
  return JSON.stringify(val, null, 2);
}

onMounted(() => {
  loadSummary();
  loadData();
});
</script>

<style scoped>
.summary-row .el-card {
  text-align: center;
}
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.json-block {
  margin: 0;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
