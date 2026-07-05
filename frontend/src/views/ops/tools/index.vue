<template>
  <div class="ops-tools-container">
    <div class="page-header">
      <h2>工具模板管理</h2>
      <el-button type="primary" @click="handleCreate">新增工具</el-button>
    </div>

    <el-table :data="tableData" border stripe v-loading="loading" style="width: 100%">
      <el-table-column prop="tool_code" label="工具编码" min-width="160" />
      <el-table-column prop="tool_name_cn" label="工具名称" min-width="140" />
      <el-table-column prop="tool_type" label="工具类型" width="120" />
      <el-table-column prop="risk_level" label="风险等级" width="100">
        <template #default="{ row }">
          <el-tag :type="riskTagType(row.risk_level)" effect="dark">
            {{ row.risk_level }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="execution_mode" label="执行模式" width="120" />
      <el-table-column prop="require_approval" label="需要审批" width="100">
        <template #default="{ row }">
          <el-tag :type="row.require_approval ? 'warning' : 'info'">
            {{ row.require_approval ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="启用状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'danger'">
            {{ row.enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑工具' : '新增工具'"
      width="580px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="工具编码" prop="tool_code">
          <el-input v-model="form.tool_code" :disabled="isEdit" placeholder="请输入工具编码" />
        </el-form-item>
        <el-form-item label="工具名称" prop="tool_name_cn">
          <el-input v-model="form.tool_name_cn" placeholder="请输入工具名称" />
        </el-form-item>
        <el-form-item label="工具类型" prop="tool_type">
          <el-input v-model="form.tool_type" placeholder="如: SQL执行 / 脚本调用 / API调用" />
        </el-form-item>
        <el-form-item label="风险等级" prop="risk_level">
          <el-select v-model="form.risk_level" placeholder="请选择" style="width: 100%">
            <el-option label="低" value="低" />
            <el-option label="中" value="中" />
            <el-option label="高" value="高" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行模式" prop="execution_mode">
          <el-select v-model="form.execution_mode" placeholder="请选择" style="width: 100%">
            <el-option label="同步" value="同步" />
            <el-option label="异步" value="异步" />
          </el-select>
        </el-form-item>
        <el-form-item label="需要审批" prop="require_approval">
          <el-switch v-model="form.require_approval" />
        </el-form-item>
        <el-form-item label="启用状态" prop="enabled">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="工具描述（可选）" />
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
import { getOpsTools, upsertOpsTool } from "@/api/ops"
import { ElMessage } from "element-plus"

interface OpsTool {
  tool_code: string
  tool_name_cn: string
  tool_type: string
  risk_level: string
  execution_mode: string
  require_approval: boolean
  enabled: boolean
  description?: string
}

const tableData = ref<OpsTool[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref()

const form = reactive<OpsTool>({
  tool_code: "",
  tool_name_cn: "",
  tool_type: "",
  risk_level: "低",
  execution_mode: "同步",
  require_approval: false,
  enabled: true,
  description: ""
})

const formRules = {
  tool_code: [{ required: true, message: "请输入工具编码", trigger: "blur" }],
  tool_name_cn: [{ required: true, message: "请输入工具名称", trigger: "blur" }],
  tool_type: [{ required: true, message: "请输入工具类型", trigger: "blur" }],
  risk_level: [{ required: true, message: "请选择风险等级", trigger: "change" }],
  execution_mode: [{ required: true, message: "请选择执行模式", trigger: "change" }]
}

function riskTagType(level: string): any {
  const map: Record<string, string> = { "低": "info", "中": "warning", "高": "danger" }
  return map[level] || "info"
}

function resetForm() {
  form.tool_code = ""
  form.tool_name_cn = ""
  form.tool_type = ""
  form.risk_level = "低"
  form.execution_mode = "同步"
  form.require_approval = false
  form.enabled = true
  form.description = ""
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getOpsTools()
    tableData.value = res.data || []
  } catch {
    ElMessage.error("获取工具列表失败")
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: OpsTool) {
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await upsertOpsTool({ ...form })
    ElMessage.success(isEdit.value ? "更新成功" : "创建成功")
    dialogVisible.value = false
    fetchData()
  } catch {
    ElMessage.error("操作失败")
  } finally {
    submitting.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped>
.ops-tools-container {
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
</style>
