<template>
  <div class="ops-runs-container">
    <div class="page-header">
      <h2>运维任务申请与执行</h2>
      <el-button type="primary" @click="handleCreate">创建任务</el-button>
    </div>

    <div class="filter-bar">
      <el-select v-model="filterStatus" placeholder="审批状态筛选" clearable style="width: 200px" @change="fetchData">
        <el-option label="待审批" value="待审批" />
        <el-option label="已通过" value="已通过" />
        <el-option label="已拒绝" value="已拒绝" />
        <el-option label="已执行" value="已执行" />
      </el-select>
      <el-button @click="filterStatus = ''; fetchData()">重置</el-button>
    </div>

    <el-table :data="tableData" border stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="id" label="任务ID" width="80" />
      <el-table-column prop="tool_code" label="工具编码" min-width="150" />
      <el-table-column prop="requested_by" label="申请人" width="120" />
      <el-table-column prop="approval_status" label="审批状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.approval_status)" effect="dark">
            {{ row.approval_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.approval_status === '待审批'"
            type="success" link size="small"
            @click="handleApprove(row)"
          >审批通过</el-button>
          <el-button
            v-if="row.approval_status === '待审批'"
            type="danger" link size="small"
            @click="handleReject(row)"
          >审批拒绝</el-button>
          <el-button
            v-if="row.approval_status === '已通过'"
            type="primary" link size="small"
            @click="handleExecute(row)"
          >执行</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="创建运维任务" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="工具编码" prop="tool_code">
          <el-input v-model="form.tool_code" placeholder="请输入工具编码" />
        </el-form-item>
        <el-form-item label="申请人" prop="requested_by">
          <el-input v-model="form.requested_by" placeholder="请输入申请人" />
        </el-form-item>
        <el-form-item label="输入参数">
          <el-input
            v-model="form.input_params"
            type="textarea"
            :rows="4"
            placeholder='JSON 格式参数, 如: {"sql": "SELECT 1 FROM DUAL"}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue"
import { http } from "@/utils/http"
import { getOpsRuns, createOpsRun, approveOpsRun, rejectOpsRun, executeOpsRun } from "@/api/ops"
import { ElMessage, ElMessageBox } from "element-plus"

interface OpsRun {
  id: number
  tool_code: string
  requested_by: string
  approval_status: string
  input_params?: string
  created_at: string
}

const tableData = ref<OpsRun[]>([])
const loading = ref(false)
const filterStatus = ref("")
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  tool_code: "",
  requested_by: "",
  input_params: ""
})

const formRules = {
  tool_code: [{ required: true, message: "请输入工具编码", trigger: "blur" }],
  requested_by: [{ required: true, message: "请输入申请人", trigger: "blur" }]
}

function statusTagType(status: string): any {
  const map: Record<string, string> = {
    "待审批": "warning",
    "已通过": "success",
    "已拒绝": "danger",
    "已执行": "info"
  }
  return map[status] || "info"
}

async function fetchData() {
  loading.value = true
  try {
    const params: any = {}
    if (filterStatus.value) params.approval_status = filterStatus.value
    const res = await getOpsRuns(params)
    tableData.value = res.data?.items || []
  } catch {
    ElMessage.error("获取任务列表失败")
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  form.tool_code = ""
  form.requested_by = ""
  form.input_params = ""
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await createOpsRun({ ...form })
    ElMessage.success("任务创建成功")
    dialogVisible.value = false
    fetchData()
  } catch {
    ElMessage.error("创建任务失败")
  } finally {
    submitting.value = false
  }
}

async function handleApprove(row: OpsRun) {
  try {
    await ElMessageBox.confirm(`确认审批通过任务 ${row.id}？`, "审批确认", { type: "warning" })
    await approveOpsRun(row.id, { approved_by: "admin" })
    ElMessage.success("审批通过")
    fetchData()
  } catch {
    // 取消操作
  }
}

async function handleReject(row: OpsRun) {
  try {
    await ElMessageBox.confirm(`确认拒绝任务 ${row.id}？`, "审批确认", { type: "warning" })
    await rejectOpsRun(row.id, { approved_by: "admin" })
    ElMessage.success("已拒绝")
    fetchData()
  } catch {
    // 取消操作
  }
}

async function handleExecute(row: OpsRun) {
  try {
    await ElMessageBox.confirm(`确认执行任务 ${row.id}？此操作不可撤销。`, "执行确认", { type: "warning" })
    await executeOpsRun(row.id)
    ElMessage.success("执行成功")
    fetchData()
  } catch {
    // 取消操作
  }
}

onMounted(fetchData)
</script>

<style scoped>
.ops-runs-container {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  min-height: calc(100vh - 84px);
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
</style>
