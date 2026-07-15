<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  validateOpsSql,
  createSqlTemplate,
  createSqlRun,
  previewSqlRun,
  getOpsTools,
  getOpsConfig,
  listConnectionTargets,
  executeOpsRun,
  type OpsTool
} from "@/api/ops";

const router = useRouter();
const sql = ref(
  "UPDATE asset.asset_table_owners SET owner_name = :owner_name WHERE full_table_name = :full_table_name"
);
const dryRunSql = ref(
  "SELECT count(*) FROM asset.asset_table_owners WHERE full_table_name = :full_table_name"
);
const toolCode = ref("sql_wb_" + Date.now().toString(36));
const toolName = ref("SQL工作台模板");
const allowedTables = ref("asset.asset_table_owners");
const paramsJson = ref('{"owner_name":"demo","full_table_name":"HIS.PAT_VISIT"}');
const validateResult = ref<any>(null);
const templates = ref<OpsTool[]>([]);
const loading = ref(false);
const runId = ref<number | null>(null);
const preview = ref<any>(null);
const writeEnabled = ref(false);
const approvalUiEnabled = ref(false);
const targets = ref<any[]>([]);
const selectedTarget = ref("asset");

const selectedTargetMeta = computed(() =>
  targets.value.find(t => t.source_code === selectedTarget.value)
);

async function loadConfig() {
  try {
    const res = await getOpsConfig();
    writeEnabled.value = !!res.data?.ops_write_enabled;
    approvalUiEnabled.value = !!res.data?.ops_approval_ui_enabled;
  } catch {
    writeEnabled.value = false;
    approvalUiEnabled.value = false;
  }
}

async function loadTargets() {
  try {
    const res = await listConnectionTargets();
    targets.value = res.data || [];
    if (!targets.value.find(t => t.source_code === selectedTarget.value)) {
      selectedTarget.value = targets.value[0]?.source_code || "asset";
    }
  } catch {
    targets.value = [
      {
        source_code: "asset",
        label: "平台库 / data_asset / asset",
        write_allowed: true,
        readonly_reason: null
      }
    ];
  }
}

async function loadTemplates() {
  loading.value = true;
  try {
    const res = await getOpsTools({ tool_type: "sql_workbench" });
    templates.value = (res.data || []).filter(
      (t: OpsTool) => t.tool_type === "sql_workbench" || t.execution_mode === "whitelist_dml"
    );
  } finally {
    loading.value = false;
  }
}

function parseParams(): Record<string, any> {
  try {
    return JSON.parse(paramsJson.value || "{}");
  } catch {
    ElMessage.error("参数 JSON 无效");
    return {};
  }
}

function ensureTargetWritable() {
  const meta = selectedTargetMeta.value;
  if (!meta) {
    ElMessage.warning("请选择目标数据库");
    return false;
  }
  if (!meta.write_allowed) {
    ElMessage.error(meta.readonly_reason || "业务源库只读，禁止写模板");
    return false;
  }
  return true;
}

async function onValidate() {
  if (!ensureTargetWritable()) return;
  try {
    const res = await validateOpsSql({
      sql: sql.value,
      dry_run_sql: dryRunSql.value || undefined,
      allowed_tables: allowedTables.value
        .split(",")
        .map(s => s.trim())
        .filter(Boolean),
      allowed_operations: ["INSERT", "UPDATE"],
      params: parseParams()
    });
    validateResult.value = res.data;
    ElMessage[res.data?.valid ? "success" : "warning"](res.data?.valid ? "校验通过" : "校验未通过");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "校验失败");
  }
}

async function onSaveTemplate() {
  if (!ensureTargetWritable()) return;
  try {
    const meta = selectedTargetMeta.value;
    const res = await createSqlTemplate({
      tool_code: toolCode.value,
      tool_name_cn: toolName.value,
      sql: sql.value,
      dry_run_sql: dryRunSql.value || undefined,
      allowed_tables: allowedTables.value
        .split(",")
        .map(s => s.trim())
        .filter(Boolean),
      allowed_operations: ["INSERT", "UPDATE"],
      max_affected_rows: 100,
      description_cn: "SQL 工作台创建的受控模板",
      target_source_code: selectedTarget.value,
      target_connection_id: meta?.id ?? null,
      target_database_key: meta?.database_key,
      target_schema: "asset",
      admin_publish: !approvalUiEnabled.value
    });
    ElMessage.success(
      res.data?.status === "approved" ? "模板已发布（管理员模式）" : "模板草稿已保存"
    );
    writeEnabled.value = !!res.data?.ops_write_enabled;
    loadTemplates();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  }
}

async function onCreateRun(code: string) {
  try {
    const res = await createSqlRun({ tool_code: code, input_params: parseParams() });
    runId.value = res.data?.id;
    ElMessage.success(`已创建任务 #${runId.value}`);
    if (res.data?.task_path) {
      // keep user on workbench but offer navigation
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "创建 run 失败");
  }
}

async function onPreview() {
  if (!runId.value) {
    ElMessage.warning("请先创建任务");
    return;
  }
  try {
    const res = await previewSqlRun(runId.value);
    preview.value = res.data;
    ElMessage.success(`预估影响行: ${res.data?.estimated_count}`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "预览失败");
  }
}

async function onExecute() {
  if (!runId.value) return;
  try {
    const res = await executeOpsRun(runId.value, { second_confirm: true, dry_run: false });
    ElMessage.success(`执行结果: ${res.data?.status}`);
  } catch (e: any) {
    const detail = e?.response?.data?.detail || "执行失败";
    ElMessage.error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

function goTask() {
  if (runId.value) router.push({ path: "/ops/runs", query: { run_id: String(runId.value) } });
  else router.push("/ops/runs");
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadTargets(), loadTemplates()]);
});
</script>

<template>
  <div class="sql-wb">
    <RePageHeader
      title="SQL 工作台"
      subtitle="必须先选择目标数据库。仅平台 asset schema 支持受控 INSERT/UPDATE；业务源库只读。"
    >
      <template #actions>
        <el-button @click="goTask">运维任务{{ runId ? ` #${runId}` : '' }}</el-button>
      </template>
    </RePageHeader>

    <el-alert
      type="warning"
      :closable="false"
      show-icon
      class="mb-12"
      :title="writeEnabled ? '写开关状态请以服务端为准' : '写开关默认关闭：可设计与 dry-run，正式执行将 403'"
    />
    <el-alert
      v-if="!approvalUiEnabled"
      type="info"
      :closable="false"
      show-icon
      class="mb-12"
      title="管理员简化流程：模板保存后直接发布；任务创建后先预览再二次确认执行（仍禁止跳过预览）。"
    />

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card>
          <template #header>目标数据库与 SQL</template>
          <el-form label-width="120px">
            <el-form-item label="目标数据库" required>
              <el-select v-model="selectedTarget" class="full-width" filterable>
                <el-option
                  v-for="t in targets"
                  :key="t.source_code"
                  :label="t.label + (t.write_allowed ? ' [可写]' : ' [只读]')"
                  :value="t.source_code"
                />
              </el-select>
              <div v-if="selectedTargetMeta" class="target-meta">
                <el-tag size="small">{{ selectedTargetMeta.db_type || 'n/a' }}</el-tag>
                <span>{{ selectedTargetMeta.endpoint_masked }}</span>
                <span>{{ selectedTargetMeta.database_or_service }}</span>
                <el-tag :type="selectedTargetMeta.write_allowed ? 'success' : 'info'" size="small">
                  {{ selectedTargetMeta.write_allowed ? '允许受控写' : '只读源库' }}
                </el-tag>
              </div>
            </el-form-item>
            <el-form-item label="模板编码">
              <el-input v-model="toolCode" />
            </el-form-item>
            <el-form-item label="模板名称">
              <el-input v-model="toolName" />
            </el-form-item>
            <el-form-item label="允许表">
              <el-input v-model="allowedTables" placeholder="asset.xxx" />
            </el-form-item>
            <el-form-item label="DML SQL">
              <el-input v-model="sql" type="textarea" :rows="5" />
            </el-form-item>
            <el-form-item label="dry-run SQL">
              <el-input v-model="dryRunSql" type="textarea" :rows="3" />
            </el-form-item>
            <el-form-item label="参数 JSON">
              <el-input v-model="paramsJson" type="textarea" :rows="3" />
            </el-form-item>
            <el-space>
              <el-button @click="onValidate">安全扫描</el-button>
              <el-button type="primary" @click="onSaveTemplate">
                {{ approvalUiEnabled ? '保存草稿' : '保存并发布' }}
              </el-button>
            </el-space>
          </el-form>
          <pre v-if="validateResult" class="result-box">{{ JSON.stringify(validateResult, null, 2) }}</pre>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card v-loading="loading">
          <template #header>已发布/草稿模板</template>
          <el-table :data="templates" size="small" max-height="320">
            <el-table-column prop="tool_code" label="编码" min-width="110" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  link
                  size="small"
                  type="primary"
                  :disabled="!row.enabled"
                  @click="onCreateRun(row.tool_code)"
                >
                  建任务
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="mt-12">
          <template #header>任务闭环 · #{{ runId || '-' }}</template>
          <el-space wrap>
            <el-button :disabled="!runId" @click="onPreview">影响行预览</el-button>
            <el-button :disabled="!runId" type="danger" @click="onExecute">二次确认执行</el-button>
            <el-button :disabled="!runId" type="primary" @click="goTask">查看任务</el-button>
          </el-space>
          <pre v-if="preview" class="result-box">{{ JSON.stringify(preview, null, 2) }}</pre>
          <p class="hint">创建            必须先预览；写开关关闭时正式执行拒绝。业务源库目标不可创建写模板。
          </p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.sql-wb { padding: 4px; }
.mb-12 { margin-bottom: 12px; }
.mt-12 { margin-top: 12px; }
.full-width { width: 100%; }
.target-meta {
  margin-top: 6px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-secondary);
}
.result-box {
  margin-top: 12px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 12px;
  max-height: 280px;
  overflow: auto;
}
.hint { margin-top: 12px; font-size: 12px; color: var(--text-secondary); }
</style>
