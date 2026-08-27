<template>
  <div class="metadata-changes">
    <RePageHeader title="元数据变更事件" subtitle="跟踪源端表、字段和结构变更，支持分配、确认和闭环处理。" />

    <section class="change-stat-grid">
      <ReStatCard label="全部变更" :value="summary.total ?? 0" tone="primary" />
      <ReStatCard label="待处理" :value="summary.open ?? 0" tone="danger" />
      <ReStatCard label="已确认" :value="summary.acknowledged ?? 0" tone="warning" />
      <ReStatCard label="已解决" :value="summary.resolved ?? 0" tone="accent" />
    </section>

    <el-card shadow="never" class="event-card">
      <template #header>
        <span>变更事件列表</span>
      </template>

      <div class="filter-bar">
        <el-select
          v-model="filters.system_code"
          placeholder="所属系统"
          clearable
          class="system-select"
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
          class="type-select"
          @change="doSearch"
        >
          <el-option label="新增表" value="table_added" />
          <el-option label="删除表" value="table_removed" />
          <el-option label="新增字段" value="column_added" />
          <el-option label="删除字段" value="column_removed" />
          <el-option label="字段类型变更" value="column_data_type_changed" />
          <el-option label="字段长度变更" value="column_length_changed" />
          <el-option label="非空约束变更" value="column_nullable_changed" />
          <el-option label="字段注释变更" value="column_comment_changed" />
        </el-select>

        <el-select
          v-model="filters.severity"
          placeholder="严重程度"
          clearable
          class="compact-select"
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
          class="compact-select"
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
          class="keyword-input"
          @keyup.enter="doSearch"
        />
      </div>

      <el-alert v-if="loadError" type="error" :closable="false" :title="loadError" show-icon class="load-error">
        <template #default><el-button size="small" @click="loadData">重试</el-button></template>
      </el-alert>

      <div v-if="selectedIds.length" class="batch-bar">
        <span>已选 {{ selectedIds.length }} 条</span>
        <el-button v-perms="'metadata.change.edit'" size="small" type="primary" @click="batchAction('acknowledge')">批量确认</el-button>
        <el-button v-perms="'metadata.change.edit'" size="small" type="warning" @click="batchAction('ignore')">批量忽略</el-button>
        <el-button v-perms="'metadata.change.edit'" size="small" type="success" @click="batchAction('resolve')">批量解决</el-button>
        <el-button v-perms="'metadata.change.edit'" size="small" @click="batchAction('reopen')">批量重开</el-button>
      </div>
      <el-table
        v-loading="loading"
        :data="items"
        stripe
        class="event-table"
        @row-click="showDetail"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="system_code" label="系统" width="90" />
        <el-table-column prop="namespace" label="Schema" width="100" show-overflow-tooltip />
        <el-table-column prop="change_type" label="变更类型" width="120">
          <template #default="{ row }">
            {{ changeTypeLabel(row.change_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="table_name" label="表名" min-width="160" show-overflow-tooltip />
        <el-table-column prop="column_name" label="字段名" min-width="120" show-overflow-tooltip />
        <el-table-column label="变更内容" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.before_value || row.after_value">
              {{ row.before_value || "（无）" }} → {{ row.after_value || "（无）" }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
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
        <el-table-column label="创建时间" width="140">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'open'"
              v-perms="'metadata.change.edit'"
              type="primary"
              size="small"
              link
              @click.stop="acknowledge(row)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status === 'open'"
              v-perms="'metadata.change.edit'"
              type="warning"
              size="small"
              link
              @click.stop="ignore(row)"
            >
              忽略
            </el-button>
            <el-button
              v-if="row.status === 'acknowledged'"
              v-perms="'metadata.change.edit'"
              type="success"
              size="small"
              link
              @click.stop="resolve(row)"
            >
              解决
            </el-button>
            <el-button
              v-perms="'metadata.change.edit'"
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
        class="pager"
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
        <el-descriptions-item label="Schema">{{ currentRow?.namespace || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ currentRow?.source_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTagType(currentRow?.status)" size="small" disable-transitions>
            {{ statusLabel(currentRow?.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="分配人">{{ currentRow?.assigned_to || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatTime(currentRow?.created_at) }}</el-descriptions-item>
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
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import {
  getMetadataChanges,
  updateMetadataChange,
  getChangesSummary
} from "@/api/metadata";
import {
  changeTypeLabel,
  severityColor,
  severityLabel,
  statusLabel,
  statusTagType
} from "../labels";
import { extractErrorDetail } from "@/utils/errorMessage";
import { batchUpdateMetadataChanges } from "@/api/metadata";
import { formatTime } from "@/utils/format";

const loading = ref(false);
const loadError = ref("");
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

const selectedIds = ref<number[]>([]);

function onSelectionChange(rows: any[]) {
  selectedIds.value = rows.map(row => row.id);
}

async function batchAction(action: "acknowledge" | "ignore" | "resolve" | "reopen") {
  if (!selectedIds.value.length) return;
  try {
    const res = await batchUpdateMetadataChanges({ ids: selectedIds.value, action });
    ElMessage.success(`已处理 ${res.data.updated} 条${res.data.missing.length ? `，缺失 ${res.data.missing.length} 条` : ""}`);
    selectedIds.value = [];
    loadData();
    loadSummary();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "批量处理失败"));
  }
}

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
    // 汇总卡片是可降级资源：主列表错误态由 loadData 负责，这里保持上次值。
  }
}

async function loadData() {
  loading.value = true;
  loadError.value = "";
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
  } catch (error) {
    items.value = [];
    pagination.total = 0;
    loadError.value = extractErrorDetail(error, "变更事件加载失败");
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
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "确认失败"));
  }
}

async function ignore(row: any) {
  try {
    await updateMetadataChange(row.id, { status: "ignored" });
    ElMessage.success("已忽略");
    loadData();
    loadSummary();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "忽略失败"));
  }
}

async function resolve(row: any) {
  try {
    await updateMetadataChange(row.id, { status: "resolved" });
    ElMessage.success("已解决");
    loadData();
    loadSummary();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "解决失败"));
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
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "分配失败"));
  } finally {
    assignLoading.value = false;
  }
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
.metadata-changes { padding: 4px; }
.change-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin-bottom: 16px; }
.event-card { border-color: var(--border-light); border-radius: var(--radius-base); box-shadow: var(--shadow-sm); }
@media (max-width: 960px) { .change-stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .change-stat-grid { grid-template-columns: 1fr; } }
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

.system-select { width: 160px; }
.type-select { width: 160px; margin-left: 12px; }
.compact-select { width: 140px; margin-left: 12px; }
.keyword-input { width: 220px; margin-left: 12px; }
.load-error { margin-bottom: 12px; }
.batch-bar { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.event-table { margin-top: 12px; }
.pager { justify-content: flex-end; margin-top: 16px; }
</style>
