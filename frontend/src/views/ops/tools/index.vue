<template>
  <div class="ops-tools-page">
    <RePageHeader
      title="运维工具模板"
      subtitle="第一阶段仅允许平台库 asset schema 的白名单参数化 INSERT/UPDATE。"
    >
      <template #actions>
        <el-button type="primary" @click="handleCreate">新建工具</el-button>
      </template>
    </RePageHeader>

    <el-alert
      class="guard-alert"
      type="warning"
      show-icon
      :closable="false"
      title="源业务库默认只读，HIS/ODS/HRP/LIS/PACS 等业务源库禁止写入；写操作必须走审批、二次确认和审计。"
    />

    <el-table v-loading="loading" :data="tableData" border stripe class="full-table">
      <el-table-column prop="tool_code" label="工具编码" min-width="170" />
      <el-table-column prop="tool_name_cn" label="工具名称" min-width="160" />
      <el-table-column prop="system_code" label="系统" width="130" />
      <el-table-column prop="source_code" label="数据源" width="110" />
      <el-table-column prop="execution_mode" label="执行模式" width="140">
        <template #default="{ row }">
          <el-tag :type="row.execution_mode === 'whitelist_dml' ? 'danger' : 'info'">
            {{ row.execution_mode }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="risk_level" label="风险" width="100">
        <template #default="{ row }">
          <el-tag :type="riskTagType(row.risk_level)" effect="dark">{{ row.risk_level }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="审批/确认" width="120">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag :type="row.require_approval ? 'warning' : 'info'" size="small">审批</el-tag>
            <el-tag :type="row.require_second_confirm ? 'warning' : 'info'" size="small">二确</el-tag>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column prop="enabled" label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑工具模板' : '新建工具模板'"
      width="860px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="130px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工具编码" prop="tool_code">
              <el-input v-model="form.tool_code" :disabled="isEdit" placeholder="unique-tool-code" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工具名称" prop="tool_name_cn">
              <el-input v-model="form.tool_name_cn" placeholder="平台库字段修正" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="系统编码" prop="system_code">
              <el-input v-model="form.system_code" placeholder="ASSET_PLATFORM" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="数据源" prop="source_code">
              <el-input v-model="form.source_code" placeholder="asset" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="工具类型" prop="tool_type">
              <el-select v-model="form.tool_type" class="full-width">
                <el-option label="write" value="write" />
                <el-option label="query" value="query" />
                <el-option label="admin" value="admin" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="风险等级" prop="risk_level">
              <el-select v-model="form.risk_level" class="full-width">
                <el-option label="low" value="low" />
                <el-option label="medium" value="medium" />
                <el-option label="high" value="high" />
                <el-option label="critical" value="critical" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="执行模式" prop="execution_mode">
              <el-select v-model="form.execution_mode" class="full-width">
                <el-option label="whitelist_dml" value="whitelist_dml" />
                <el-option label="readonly_sql" value="readonly_sql" />
                <el-option label="stored_procedure" value="stored_procedure" />
                <el-option label="http_api" value="http_api" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="SQL/端点模板" prop="sql_or_endpoint_ref">
          <el-input
            v-model="form.sql_or_endpoint_ref"
            type="textarea"
            :rows="4"
            placeholder="UPDATE asset.asset_table SET col = :value WHERE id = :id"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="允许表">
              <el-input
                v-model="allowedTablesText"
                type="textarea"
                :rows="3"
                placeholder="每行一个表，例如 asset.asset_ops_tool_templates"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="允许动作">
              <el-checkbox-group v-model="form.allowed_operations">
                <el-checkbox label="UPDATE" />
                <el-checkbox label="INSERT" />
              </el-checkbox-group>
            </el-form-item>
            <el-form-item label="Dry-run SQL">
              <el-input
                v-model="form.dry_run_sql"
                type="textarea"
                :rows="3"
                placeholder="SELECT count(*) FROM asset.xxx WHERE id = :id"
              />
            </el-form-item>
            <el-form-item label="写凭据引用">
              <el-input
                v-model="form.write_credential_ref"
                placeholder="env:CRED_ASSET_WRITE 或 file:///etc/data-asset/credentials/asset_write"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="需要审批">
              <el-switch v-model="form.require_approval" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="二次确认">
              <el-switch v-model="form.require_second_confirm" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="写审计">
              <el-switch v-model="form.require_audit" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="参数 Schema">
          <el-input v-model="inputSchemaText" type="textarea" :rows="4" placeholder='{"fields": []}' />
        </el-form-item>
        <el-form-item label="回滚说明">
          <el-input v-model="form.rollback_note_cn" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description_cn" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { getOpsTools, upsertOpsTool, type OpsTool } from "@/api/ops";

const tableData = ref<OpsTool[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const isEdit = ref(false);
const submitting = ref(false);
const formRef = ref();
const allowedTablesText = ref("");
const inputSchemaText = ref("{}");

const form = reactive<OpsTool>({
  tool_code: "",
  tool_name_cn: "",
  system_code: "ASSET_PLATFORM",
  source_code: "asset",
  tool_type: "write",
  risk_level: "high",
  input_schema: {},
  execution_mode: "whitelist_dml",
  sql_or_endpoint_ref: "",
  allowed_tables: [],
  allowed_operations: ["UPDATE"],
  require_audit: true,
  dry_run_sql: "",
  write_credential_ref: "env:CRED_ASSET_WRITE",
  require_approval: true,
  require_second_confirm: true,
  enabled: false,
  description_cn: "",
  rollback_note_cn: ""
});

const formRules = {
  tool_code: [{ required: true, message: "请输入工具编码", trigger: "blur" }],
  tool_name_cn: [{ required: true, message: "请输入工具名称", trigger: "blur" }],
  system_code: [{ required: true, message: "请输入系统编码", trigger: "blur" }],
  source_code: [{ required: true, message: "请输入数据源", trigger: "blur" }],
  tool_type: [{ required: true, message: "请选择工具类型", trigger: "change" }],
  risk_level: [{ required: true, message: "请选择风险等级", trigger: "change" }],
  execution_mode: [{ required: true, message: "请选择执行模式", trigger: "change" }]
};

type ElTagType = "primary" | "success" | "warning" | "danger" | "info";

function riskTagType(level: string): ElTagType {
  const map: Record<string, ElTagType> = {
    low: "info",
    medium: "warning",
    high: "danger",
    critical: "danger"
  };
  return map[level] || "info";
}

function resetForm() {
  Object.assign(form, {
    tool_code: "",
    tool_name_cn: "",
    system_code: "ASSET_PLATFORM",
    source_code: "asset",
    tool_type: "write",
    risk_level: "high",
    input_schema: {},
    execution_mode: "whitelist_dml",
    sql_or_endpoint_ref: "",
    allowed_tables: [],
    allowed_operations: ["UPDATE"],
    require_audit: true,
    dry_run_sql: "",
    write_credential_ref: "env:CRED_ASSET_WRITE",
    require_approval: true,
    require_second_confirm: true,
    enabled: false,
    description_cn: "",
    rollback_note_cn: ""
  });
  allowedTablesText.value = "";
  inputSchemaText.value = "{}";
}

async function fetchData() {
  loading.value = true;
  try {
    const res = await getOpsTools();
    tableData.value = res.data || [];
  } catch {
    ElMessage.error("获取工具列表失败");
  } finally {
    loading.value = false;
  }
}

function handleCreate() {
  isEdit.value = false;
  resetForm();
  dialogVisible.value = true;
}

function handleEdit(row: OpsTool) {
  isEdit.value = true;
  resetForm();
  Object.assign(form, row);
  form.allowed_operations = row.allowed_operations?.length ? [...row.allowed_operations] : ["UPDATE"];
  allowedTablesText.value = (row.allowed_tables || []).join("\n");
  inputSchemaText.value = JSON.stringify(row.input_schema || {}, null, 2);
  dialogVisible.value = true;
}

function parseJson(text: string) {
  if (!text.trim()) return {};
  return JSON.parse(text);
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;

  let inputSchema: Record<string, any>;
  try {
    inputSchema = parseJson(inputSchemaText.value);
  } catch {
    ElMessage.error("参数 Schema 必须是合法 JSON");
    return;
  }

  submitting.value = true;
  try {
    await upsertOpsTool({
      ...form,
      input_schema: inputSchema,
      allowed_tables: allowedTablesText.value.split(/\r?\n/).map(item => item.trim()).filter(Boolean),
      allowed_operations: form.allowed_operations || []
    });
    ElMessage.success(isEdit.value ? "工具已更新" : "工具已创建");
    dialogVisible.value = false;
    await fetchData();
  } catch {
    ElMessage.error("保存工具失败");
  } finally {
    submitting.value = false;
  }
}

onMounted(fetchData);
</script>

<style scoped>
.ops-tools-page {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
  border-radius: 8px;
}


.guard-alert {
  margin-bottom: 14px;
}

.full-table,
.full-width {
  width: 100%;
}
</style>
