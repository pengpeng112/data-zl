<template>
  <div class="ops-runs-page">
    <RePageHeader title="运维执行申请" subtitle="提交申请、审批、dry-run 预览、执行和审计查询；正式执行必须先完成二次确认。">
      <template #icon><RunIcon /></template>
      <template #actions>
        <el-button type="primary" :icon="AddIcon" @click="handleCreate">创建申请</el-button>
      </template>
    </RePageHeader>

    <ReWorkflow :steps="pipelineSteps" class="runs-workflow" />

    <ReToolbar title="申请筛选" class="runs-toolbar">
      <el-select v-model="filterStatus" clearable placeholder="状态" class="status-filter" @change="fetchData">
        <el-option label="draft" value="draft" />
        <el-option label="ready_for_preview" value="ready_for_preview" />
        <el-option label="submitted" value="submitted" />
        <el-option label="pending" value="pending" />
        <el-option label="approved" value="approved" />
        <el-option label="rejected" value="rejected" />
        <el-option label="executing" value="executing" />
        <el-option label="succeeded" value="succeeded" />
        <el-option label="executed" value="executed" />
        <el-option label="failed" value="failed" />
      </el-select>
      <template #actions>
        <el-button @click="resetFilter">重置</el-button>
      </template>
    </ReToolbar>

    <el-table v-loading="loading" :data="tableData" border stripe class="medical-data-table">
      <el-table-column prop="id" label="编号" width="80" />
      <el-table-column prop="tool_code" label="工具编码" min-width="180" />
      <el-table-column prop="requested_by" label="申请人" width="120" />
      <el-table-column prop="approved_by" label="审批人" width="120" />
      <el-table-column prop="approval_status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.approval_status)" effect="dark">
            {{ opsRunStatusLabel(row.approval_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="affected_count" label="影响行数" width="100" />
      <el-table-column label="创建时间" min-width="150">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="310" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.approval_status === 'draft'"
            type="primary"
            link
            size="small"
            @click="handleSubmitRun(row)"
          >提交</el-button>
          <el-button
            v-if="['submitted', 'pending'].includes(row.approval_status)"
            type="success"
            link
            size="small"
            @click="handleApprove(row)"
          >审批</el-button>
          <el-button
            v-if="['submitted', 'pending'].includes(row.approval_status)"
            type="danger"
            link
            size="small"
            @click="handleReject(row)"
          >驳回</el-button>
          <el-button
            v-if="['approved', 'ready_for_preview'].includes(row.approval_status)"
            type="warning"
            link
            size="small"
            @click="handleDryRun(row)"
          >Dry-run</el-button>
          <el-button
            v-if="row.approval_status === 'approved'"
            type="primary"
            link
            size="small"
            @click="handleExecute(row)"
          >执行</el-button>
          <el-button type="info" link size="small" @click="handleAudit(row)">审计</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="创建运维申请" width="620px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="工具编码" prop="tool_code">
          <el-input v-model="form.tool_code" placeholder="已启用的工具编码" />
        </el-form-item>
        <el-form-item label="申请人" prop="requested_by">
          <el-input v-model="form.requested_by" placeholder="申请人账号" />
        </el-form-item>
        <el-form-item label="输入参数">
          <el-input
            v-model="form.input_params"
            type="textarea"
            :rows="8"
            placeholder='{"target_tool_code":"demo","description":"new value"}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dryRunVisible" title="Dry-run 预览" width="760px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="预览可用">{{ dryRunResult?.preview_available ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="预计行数">{{ dryRunResult?.estimated_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="SQL 校验" :span="2">
          <el-tag :type="dryRunResult?.risk_scan?.valid ? 'success' : 'danger'">
            {{ dryRunResult?.risk_scan?.valid ? '通过' : '拒绝' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <pre class="json-preview">{{ formatJson(dryRunResult) }}</pre>
    </el-dialog>

    <ReDetailDrawer v-model="auditVisible" title="执行审计" subtitle="按时间线展示申请、审批、执行和数据变更证据。" size="56vw">
      <el-timeline>
        <el-timeline-item v-for="item in auditLogs" :key="item.id" :timestamp="item.created_at || ''">
          <div class="audit-title">{{ item.action }} / {{ item.operator || '-' }}</div>
          <div v-if="item.reason" class="audit-reason">{{ item.reason }}</div>
          <pre class="json-preview">{{ formatJson({ before_data: item.before_data, after_data: item.after_data }) }}</pre>
        </el-timeline-item>
      </el-timeline>
      <ReEmptyState v-if="!auditLogs.length" title="暂无审计记录" description="该执行申请尚未产生审计事件。" />
    </ReDetailDrawer>
  </div>
</template>

<script setup lang="ts">
import ReDetailDrawer from "@/components/ReDetailDrawer/index.vue";
import ReEmptyState from "@/components/ReEmptyState/index.vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import ReWorkflow from "@/components/ReWorkflow/index.vue";
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  approveOpsRun,
  createOpsRun,
  dryRunOpsRun,
  executeOpsRun,
  getOpsRunAudit,
  getOpsRuns,
  rejectOpsRun,
  submitOpsRun,
  type OpsRun
} from "@/api/ops";
import AddIcon from "~icons/ri/add-line";
import RunIcon from "~icons/ri/play-list-add-line";
import { opsRunStatusLabel } from "@/constants/labels";
import { formatTime } from "@/utils/format";

const tableData = ref<OpsRun[]>([]);
const loading = ref(false);
const filterStatus = ref("");
const dialogVisible = ref(false);
const dryRunVisible = ref(false);
const auditVisible = ref(false);
const submitting = ref(false);
const formRef = ref();
const dryRunResult = ref<Record<string, any> | null>(null);
const auditLogs = ref<any[]>([]);

const pipelineSteps = [
  { title: "申请", desc: "填写工具与参数" },
  { title: "审批", desc: "人工确认范围" },
  { title: "Dry-run", desc: "预览影响行数" },
  { title: "执行", desc: "二次确认后执行" },
  { title: "审计", desc: "留存前后证据" }
];

const form = reactive({
  tool_code: "",
  requested_by: "",
  input_params: "{}"
});

const formRules = {
  tool_code: [{ required: true, message: "请输入工具编码", trigger: "blur" }],
  requested_by: [{ required: true, message: "请输入申请人", trigger: "blur" }]
};

type ElTagType = "primary" | "success" | "warning" | "danger" | "info";

function statusTagType(status: string): ElTagType {
  const map: Record<string, ElTagType> = {
    draft: "warning",
    pending: "warning",
    submitted: "warning",
    executing: "warning",
    succeeded: "success",
    approved: "success",
    rejected: "danger",
    executed: "info",
    failed: "danger"
  };
  return map[status] || "info";
}

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

async function fetchData() {
  loading.value = true;
  try {
    const params: Record<string, any> = {};
    if (filterStatus.value) params.approval_status = filterStatus.value;
    const res = await getOpsRuns(params);
    tableData.value = res.data?.items || [];
  } catch {
    ElMessage.error("获取执行申请失败");
  } finally {
    loading.value = false;
  }
}

function resetFilter() {
  filterStatus.value = "";
  fetchData();
}

function handleCreate() {
  form.tool_code = "";
  form.requested_by = "";
  form.input_params = "{}";
  dialogVisible.value = true;
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  let inputParams: Record<string, any> = {};
  try {
    inputParams = form.input_params.trim() ? JSON.parse(form.input_params) : {};
  } catch {
    ElMessage.error("输入参数必须是合法 JSON");
    return;
  }

  submitting.value = true;
  try {
    await createOpsRun({
      tool_code: form.tool_code,
      requested_by: form.requested_by,
      input_params: inputParams
    });
    ElMessage.success("申请已创建");
    dialogVisible.value = false;
    await fetchData();
  } catch {
    ElMessage.error("创建申请失败");
  } finally {
    submitting.value = false;
  }
}

async function promptOperator(title: string, field: string) {
  const { value } = await ElMessageBox.prompt(field, title, {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    inputPattern: /\S+/,
    inputErrorMessage: "不能为空"
  });
  return value;
}

async function handleSubmitRun(row: OpsRun) {
  try {
    const submittedBy = await promptOperator("提交审批", "提交人账号");
    await submitOpsRun(row.id, { submitted_by: submittedBy, note: "submitted from ops console" });
    ElMessage.success("已提交审批");
    await fetchData();
  } catch {
    // user cancelled
  }
}
async function handleApprove(row: OpsRun) {
  try {
    const approvedBy = await promptOperator("审批确认", "审批人账号");
    await approveOpsRun(row.id, { approved_by: approvedBy, note: "approved from ops console" });
    ElMessage.success("已审批");
    await fetchData();
  } catch {
    // user cancelled
  }
}

async function handleReject(row: OpsRun) {
  try {
    const approvedBy = await promptOperator("驳回确认", "审批人账号");
    await rejectOpsRun(row.id, { approved_by: approvedBy, note: "rejected from ops console" });
    ElMessage.success("已驳回");
    await fetchData();
  } catch {
    // user cancelled
  }
}

async function handleDryRun(row: OpsRun) {
  try {
    const executedBy = await promptOperator("Dry-run", "操作人账号");
    const res = await dryRunOpsRun(row.id, {
      dry_run: true,
      second_confirm: true,
      executed_by: executedBy
    });
    dryRunResult.value = res.data;
    dryRunVisible.value = true;
  } catch {
    // user cancelled or request failed
  }
}

async function handleExecute(row: OpsRun) {
  try {
    const executedBy = await promptOperator("执行确认", "执行人账号");
    await ElMessageBox.confirm(
      `确认执行申请 ${row.id}？执行前请先完成 dry-run 并核对影响范围。`,
      "二次确认",
      { type: "warning", confirmButtonText: "确认执行" }
    );
    await executeOpsRun(row.id, {
      second_confirm: true,
      dry_run: false,
      executed_by: executedBy
    });
    ElMessage.success("执行完成");
    await fetchData();
  } catch {
    // user cancelled or request failed
  }
}

async function handleAudit(row: OpsRun) {
  try {
    const res = await getOpsRunAudit(row.id);
    auditLogs.value = res.data || [];
    auditVisible.value = true;
  } catch {
    ElMessage.error("获取审计失败");
  }
}

onMounted(() => {
  // 146 E7：消费 ?run_id= 定位到该 run 所在页并打开抽屉
  const target = Number(new URLSearchParams(window.location.search).get("run_id") || 0);
  if (target) {
    getOpsRuns({ run_id: target, page: 1, page_size: 20 }).then((res: any) => {
      tableData.value = res.data?.items || [];
      const row = tableData.value.find((item: any) => item.id === target);
      if (row) handleAudit(row);
    }).catch(() => undefined);
  } else {
    fetchData();
  }
});
</script>

<style scoped lang="scss">
.ops-runs-page {
  min-height: calc(100vh - 84px);
  padding: 4px;
}


.pipeline-step strong {
  font-size: 14px;
  color: var(--text-primary);
}

.pipeline-step small {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

.runs-workflow,
.runs-toolbar {
  margin-bottom: 14px;
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  width: 100%;
  font-size: 13px;
  border-radius: var(--radius-base);
}

.json-preview {
  max-height: 360px;
  padding: 12px;
  margin: 12px 0 0;
  overflow: auto;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-regular);
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
}

.audit-title {
  font-weight: 600;
  color: var(--text-primary);
}

.audit-reason {
  margin-top: 4px;
  color: var(--text-secondary);
}

.status-filter { width: 180px; }
</style>
