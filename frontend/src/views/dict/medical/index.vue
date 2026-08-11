<template>
  <div class="dict-medical">
    <el-tabs v-model="activeTab" class="dict-tabs">
      <el-tab-pane label="字典总览" name="overview">
        <OverviewPanel />
      </el-tab-pane>
      <el-tab-pane label="映射维护" name="mapping">
    <el-card shadow="never">
      <template #header>
        <RePageHeader title="诊断与手术编码体系" subtitle="维护院内编码、国家临床版、医保版及后续同步基础数据。">
          <template #actions>
            <el-radio-group v-model="categoryCode" @change="onCategoryChange">
              <el-radio-button value="diagnosis">诊断</el-radio-button>
              <el-radio-button value="operation">手术</el-radio-button>
            </el-radio-group>
          </template>
        </RePageHeader>
      </template>

      <div class="toolbar">
        <el-button v-perms="'dict.medical.edit'" type="primary" @click="openCodeSetDialog()">新增编码体系</el-button>
        <el-alert
          v-if="authHint"
          :title="authHint"
          type="warning"
          show-icon
          :closable="false"
          class="auth-alert"
        />
      </div>

      <el-table
        v-loading="loading"
        :data="codeSets"
        stripe
        class="items-table"
        row-key="code_set_code"
        empty-text="暂无编码体系。请管理员在平台库执行：python scripts/import_medical_maintenance_dicts.py --dry-run（确认后 --apply --confirmation IMPORT-MEDICAL-DICTS）"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="sub-table-wrap">
              <div class="toolbar sub-toolbar">
                <el-button v-perms="'dict.medical.edit'" type="primary" size="small" @click="openItemDialog(row.code_set_code)">新增编码项</el-button>
                <el-button size="small" @click="loadItems(row)">刷新编码项</el-button>
                <span class="sub-count">共 {{ row._itemsTotal || 0 }} 项</span>
              </div>
              <el-table
                v-loading="row._itemsLoading"
                :data="row._items || []"
                stripe
                size="small"
                empty-text="展开后点击刷新或等待加载编码项"
              >
                <el-table-column prop="item_code" label="编码" width="180" show-overflow-tooltip />
                <el-table-column prop="item_name_cn" label="名称" min-width="220" show-overflow-tooltip />
                <el-table-column prop="item_name_alias" label="别名" min-width="180" show-overflow-tooltip />
                <el-table-column label="状态" width="90" align="center">
                  <template #default="{ row: it }">
                    <el-tag :type="it.status === 'active' ? 'success' : 'info'" size="small">
                      {{ it.status === 'active' ? '启用' : '停用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" align="center" fixed="right">
                  <template #default="{ row: it }">
                    <el-button v-perms="'dict.medical.edit'" link type="primary" size="small" @click="openItemDialog(it.code_set_code, it)">编辑</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-pagination
                v-if="row._itemsTotal > (row._itemsPageSize || 20)"
                v-model:current-page="row._itemsPage"
                v-model:page-size="row._itemsPageSize"
                :total="row._itemsTotal"
                layout="total, prev, pager, next"
                size="small"
                class="pager"
                @change="loadItems(row)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="code_set_code" label="编码体系" min-width="220" show-overflow-tooltip />
        <el-table-column prop="code_set_name_cn" label="名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="类别" width="90" align="center">
          <template #default="{ row }">{{ row.category_code === "diagnosis" ? "诊断" : "手术" }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="codeSetTypeTag(row.code_set_type)" size="small">{{ codeSetTypeText(row.code_set_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="standard_system" label="标准体系" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled === false ? 'info' : 'success'" size="small">
              {{ row.enabled === false ? "停用" : "启用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="loadItems(row)">查看编码</el-button>
            <el-button v-perms="'dict.medical.edit'" link type="primary" size="small" @click="openCodeSetDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="codeSetDialog.visible" :title="codeSetDialog.isEdit ? '编辑编码体系' : '新增编码体系'" width="520px" destroy-on-close>
      <el-form ref="codeSetFormRef" :model="codeSetDialog.form" label-width="110px">
        <el-form-item label="编码体系" prop="code_set_code">
          <el-input v-model="codeSetDialog.form.code_set_code" :disabled="codeSetDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="code_set_name_cn">
          <el-input v-model="codeSetDialog.form.code_set_name_cn" />
        </el-form-item>
        <el-form-item label="类型" prop="code_set_type">
          <el-select v-model="codeSetDialog.form.code_set_type" class="full-width">
            <el-option label="院内" value="clinical" />
            <el-option label="国标" value="national" />
            <el-option label="医保" value="insurance" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="codeSetDialog.form.category_code" class="full-width">
            <el-option label="诊断" value="diagnosis" />
            <el-option label="手术" value="operation" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准体系" prop="standard_system">
          <el-input v-model="codeSetDialog.form.standard_system" />
        </el-form-item>
        <el-form-item label="版本" prop="version_no">
          <el-input v-model="codeSetDialog.form.version_no" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="codeSetDialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.medical.edit'" type="primary" :loading="codeSetDialog.submitting" @click="saveCodeSet">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="itemDialog.visible" :title="itemDialog.isEdit ? '编辑编码项' : '新增编码项'" width="520px" destroy-on-close>
      <el-form ref="itemFormRef" :model="itemDialog.form" label-width="100px">
        <el-form-item label="编码" prop="item_code">
          <el-input v-model="itemDialog.form.item_code" :disabled="itemDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="item_name_cn">
          <el-input v-model="itemDialog.form.item_name_cn" />
        </el-form-item>
        <el-form-item label="别名" prop="item_name_alias">
          <el-input v-model="itemDialog.form.item_name_alias" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="itemDialog.form.status" class="full-width">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.medical.edit'" type="primary" :loading="itemDialog.submitting" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>

    <el-card shadow="never" class="push-card">
      <template #header>
        <RePageHeader
          title="下发 HIS / 海量（只增 + 单条停用）"
          subtitle="禁止改已有业务字段；禁止批量 UPDATE；医保灰码写 ybhm=灰码 且不写对照表。默认 dry_run，apply 需服务端开关。"
        />
      </template>
      <el-alert
        :title="pushConfig.push_enabled ? '写通道已开启（仍须 confirmation_token）' : '写通道关闭：仅可 plan / dry_run'"
        :type="pushConfig.push_enabled ? 'success' : 'info'"
        show-icon
        :closable="false"
        class="push-alert"
      />
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="push-alert"
        title="写账号在「业务系统与数据资源 → 数据连接」配置：对 HIS/海量连接点「写凭据」，策略选 medical_dict_push。只读凭据与写凭据分离。"
      />
      <el-form :inline="true" class="push-form" label-width="100px">
        <el-form-item label="目标">
          <el-checkbox-group v-model="pushForm.targets">
            <el-checkbox label="HIS_SOURCE">HIS</el-checkbox>
            <el-checkbox label="JHEMR_VASTBASE">海量</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="编码(可选)">
          <el-input v-model="pushForm.itemCodesText" placeholder="逗号分隔，空=按上限取平台启用项" style="width: 280px" />
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="pushForm.max_items" :min="1" :max="200" />
        </el-form-item>
        <el-form-item label="hospital_no">
          <el-input v-model="pushForm.hospital_no" style="width: 140px" />
        </el-form-item>
        <el-form-item>
          <el-button v-perms="'dict.medical.plan.create'" type="primary" :loading="pushLoading" @click="runPushPlan">生成计划</el-button>
          <el-button v-perms="'dict.medical.plan.create'" :loading="pushLoading" @click="runPushExport">导出预览</el-button>
        </el-form-item>
      </el-form>
      <div v-if="pushSummary" class="push-summary">
        计划 {{ pushSummary.action_count }} 条：planned={{ pushSummary.summary?.planned }} blocked={{ pushSummary.summary?.blocked }}
        grey/无对照跳过={{ pushSummary.summary?.skipped_grey_or_empty_contrast }}
      </div>
      <el-table v-loading="pushLoading" :data="pushActions" stripe size="small" max-height="420" empty-text="先生成下发计划">
        <el-table-column prop="action_type" label="动作" width="70" />
        <el-table-column prop="target_system" label="系统" width="130" show-overflow-tooltip />
        <el-table-column prop="target_table" label="表" min-width="180" show-overflow-tooltip />
        <el-table-column prop="item_code" label="编码" width="140" show-overflow-tooltip />
        <el-table-column prop="item_name" label="名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="plan_status" label="状态" width="100" />
        <el-table-column label="灰码" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.meta?.is_grey_insurance || row.params?.ybhm === '灰码'" type="warning" size="small">灰码</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-perms="'dict.medical.execute'" link type="primary" size="small" @click="dryRunOne(row)">dry-run</el-button>
            <el-button v-perms="'dict.medical.execute'" link type="danger" size="small" :disabled="!pushConfig.push_enabled" @click="applyOne(row)">apply</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="stop-box">
        <span class="stop-label">单条停用：</span>
        <el-select v-model="stopForm.target_system" style="width: 160px">
          <el-option label="HIS_SOURCE" value="HIS_SOURCE" />
          <el-option label="JHEMR_VASTBASE" value="JHEMR_VASTBASE" />
        </el-select>
        <el-input v-model="stopForm.item_code" placeholder="业务编码" style="width: 180px" />
        <el-button v-perms="'dict.medical.execute'" :loading="pushLoading" @click="stopOne('dry_run')">停用 dry-run</el-button>
        <el-button v-perms="'dict.medical.execute'" type="danger" :loading="pushLoading" :disabled="!pushConfig.push_enabled" @click="stopOne('apply')">停用 apply</el-button>
      </div>
      <el-input v-model="lastResultJson" type="textarea" :rows="6" readonly class="result-box" placeholder="最近一次执行结果 JSON" />
    </el-card>
      </el-tab-pane>
      <el-tab-pane label="导入审核" name="import">
        <ImportWizard />
      </el-tab-pane>
      <el-tab-pane label="同步下发" name="push">
        <PushWizard />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ImportWizard from './components/ImportWizard.vue';
import OverviewPanel from './components/OverviewPanel.vue';
import PushWizard from './components/PushWizard.vue';
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox, type FormInstance } from "element-plus";
import {
  getMedicalCodeSets,
  upsertMedicalCodeSet,
  getMedicalItems,
  upsertMedicalItem,
  getMedicalPushConfig,
  planMedicalPush,
  exportMedicalPushPreview,
  applyMedicalPushOne,
  stopMedicalPushOne
} from "@/api/dict";

const activeTab = ref('overview');
const categoryCode = ref("diagnosis");
const codeSets = ref<any[]>([]);
const loading = ref(false);
const authHint = ref("");

function normalizeCodeSet(cs: any) {
  return {
    ...cs,
    code_set_name_cn: cs.code_set_name_cn || cs.name_cn || "",
    enabled: cs.enabled ?? (cs.status ? cs.status === "active" : true),
    _items: [],
    _itemsLoading: false,
    _itemsPage: 1,
    _itemsPageSize: 20,
    _itemsTotal: 0
  };
}

async function loadCodeSets() {
  loading.value = true;
  authHint.value = "";
  try {
    const res = await getMedicalCodeSets({ category_code: categoryCode.value });
    codeSets.value = ((res as any).data || []).map(normalizeCodeSet);
  } catch (error: any) {
    if (error?.response?.status === 401) {
      authHint.value = "接口未授权：请先登录并使用部署脚本生成的 Token。";
    } else if (error?.response?.status === 403) {
      authHint.value = "API Token 无效或已禁用：请联系管理员重新生成并绑定 Token。";
    }
  } finally {
    loading.value = false;
  }
}

async function loadItems(row: any) {
  row._itemsLoading = true;
  try {
    const res = await getMedicalItems(row.code_set_code, { page: row._itemsPage, page_size: row._itemsPageSize });
    row._items = (res as any).data.items || [];
    row._itemsTotal = (res as any).data.total || 0;
  } finally {
    row._itemsLoading = false;
  }
}

function onCategoryChange() {
  loadCodeSets();
}

function codeSetTypeText(type: string) {
  return type === "clinical" ? "院内" : type === "national" ? "国标" : type === "insurance" ? "医保" : type || "-";
}

function codeSetTypeTag(type: string): any {
  return { clinical: "", national: "success", insurance: "warning" }[type] || "info";
}

const codeSetFormRef = ref<FormInstance>();
const codeSetDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    code_set_code: "",
    code_set_name_cn: "",
    code_set_type: "clinical",
    category_code: "diagnosis",
    standard_system: "",
    version_no: "",
    enabled: true
  }
});

function openCodeSetDialog(row?: any) {
  codeSetDialog.isEdit = !!row;
  codeSetDialog.form = row
    ? {
        code_set_code: row.code_set_code || "",
        code_set_name_cn: row.code_set_name_cn || "",
        code_set_type: row.code_set_type || "clinical",
        category_code: row.category_code || categoryCode.value,
        standard_system: row.standard_system || "",
        version_no: row.version_no || "",
        enabled: row.enabled ?? true
      }
    : {
        code_set_code: "",
        code_set_name_cn: "",
        code_set_type: "clinical",
        category_code: categoryCode.value,
        standard_system: "",
        version_no: "",
        enabled: true
      };
  codeSetDialog.visible = true;
}

async function saveCodeSet() {
  codeSetDialog.submitting = true;
  try {
    await upsertMedicalCodeSet(codeSetDialog.form);
    ElMessage.success(codeSetDialog.isEdit ? "编辑成功" : "新增成功");
    codeSetDialog.visible = false;
    loadCodeSets();
  } finally {
    codeSetDialog.submitting = false;
  }
}

const itemFormRef = ref<FormInstance>();
const itemDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    code_set_code: "",
    item_code: "",
    item_name_cn: "",
    item_name_alias: "",
    category_code: "diagnosis",
    status: "active"
  }
});

function openItemDialog(codeSetCode: string, item?: any) {
  itemDialog.isEdit = !!item;
  itemDialog.form = item
    ? {
        code_set_code: codeSetCode,
        item_code: item.item_code || "",
        item_name_cn: item.item_name_cn || "",
        item_name_alias: item.item_name_alias || "",
        category_code: item.category_code || categoryCode.value,
        status: item.status || "active"
      }
    : {
        code_set_code: codeSetCode,
        item_code: "",
        item_name_cn: "",
        item_name_alias: "",
        category_code: categoryCode.value,
        status: "active"
      };
  itemDialog.visible = true;
}

async function saveItem() {
  itemDialog.submitting = true;
  try {
    await upsertMedicalItem(itemDialog.form);
    ElMessage.success(itemDialog.isEdit ? "编辑成功" : "新增成功");
    itemDialog.visible = false;
    const row = codeSets.value.find(item => item.code_set_code === itemDialog.form.code_set_code);
    if (row) loadItems(row);
  } finally {
    itemDialog.submitting = false;
  }
}

const pushConfig = reactive<{ push_enabled: boolean; default_hospital_no?: string }>({
  push_enabled: false
});
const pushLoading = ref(false);
const pushActions = ref<any[]>([]);
const pushSummary = ref<any>(null);
const lastResultJson = ref("");
const pushForm = reactive({
  targets: ["HIS_SOURCE", "JHEMR_VASTBASE"] as string[],
  itemCodesText: "",
  max_items: 20,
  hospital_no: "1110002"
});
const stopForm = reactive({
  target_system: "HIS_SOURCE",
  item_code: ""
});

function parseItemCodes() {
  return pushForm.itemCodesText
    .split(/[,，\s]+/)
    .map(s => s.trim())
    .filter(Boolean);
}

async function loadPushConfig() {
  try {
    const res = await getMedicalPushConfig();
    const data = (res as any).data || {};
    pushConfig.push_enabled = !!data.push_enabled;
    if (data.default_hospital_no) pushForm.hospital_no = data.default_hospital_no;
  } catch {
    pushConfig.push_enabled = false;
  }
}

async function runPushPlan() {
  if (!pushForm.targets.length) {
    ElMessage.warning("请选择目标系统");
    return;
  }
  pushLoading.value = true;
  try {
    const res = await planMedicalPush({
      category_code: categoryCode.value,
      targets: pushForm.targets,
      item_codes: parseItemCodes().length ? parseItemCodes() : null,
      max_items: pushForm.max_items,
      hospital_no: pushForm.hospital_no,
      include_jhdict: true
    });
    const data = (res as any).data;
    pushSummary.value = data;
    pushActions.value = data.actions || [];
    lastResultJson.value = JSON.stringify(data.summary || {}, null, 2);
    ElMessage.success(`已生成 ${data.action_count || 0} 条动作`);
  } finally {
    pushLoading.value = false;
  }
}

async function runPushExport() {
  pushLoading.value = true;
  try {
    const res = await exportMedicalPushPreview({
      category_code: categoryCode.value,
      item_codes: parseItemCodes().length ? parseItemCodes() : null,
      max_items: pushForm.max_items
    });
    lastResultJson.value = JSON.stringify((res as any).data, null, 2);
    ElMessage.success("导出预览完成");
  } finally {
    pushLoading.value = false;
  }
}

async function dryRunOne(row: any) {
  pushLoading.value = true;
  try {
    const res = await applyMedicalPushOne({ action: row, mode: "dry_run" });
    lastResultJson.value = JSON.stringify((res as any).data, null, 2);
    ElMessage.success("dry-run 完成");
  } finally {
    pushLoading.value = false;
  }
}

async function applyOne(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认对 ${row.target_table} / ${row.item_code} 执行单条 apply？仅新增或停用，不可改业务字段。`,
      "二次确认",
      { type: "warning" }
    );
  } catch {
    return;
  }
  const { value: token } = await ElMessageBox.prompt("请输入 confirmation_token", "写通道确认", {
    inputType: "password",
    confirmButtonText: "执行",
    cancelButtonText: "取消"
  }).catch(() => ({ value: "" }));
  if (!token) return;
  pushLoading.value = true;
  try {
    const res = await applyMedicalPushOne({
      action: row,
      mode: "apply",
      confirmation_token: token,
      his_source_code: "his_source_10_10_10_15",
      jhemr_source_code: "jhemr_vastbase_10_10_8_177"
    });
    lastResultJson.value = JSON.stringify((res as any).data, null, 2);
    ElMessage.success("apply 已提交");
  } finally {
    pushLoading.value = false;
  }
}

async function stopOne(mode: "dry_run" | "apply") {
  if (!stopForm.item_code.trim()) {
    ElMessage.warning("请填写要停用的编码");
    return;
  }
  let token = "";
  if (mode === "apply") {
    const prompt = await ElMessageBox.prompt("请输入 confirmation_token", "停用确认", {
      inputType: "password"
    }).catch(() => null);
    if (!prompt?.value) return;
    token = prompt.value;
  }
  pushLoading.value = true;
  try {
    const res = await stopMedicalPushOne({
      category_code: categoryCode.value,
      target_system: stopForm.target_system,
      item_code: stopForm.item_code.trim(),
      hospital_no: pushForm.hospital_no,
      mode,
      confirmation_token: token || null,
      his_source_code: "his_source_10_10_10_15",
      jhemr_source_code: "jhemr_vastbase_10_10_8_177"
    });
    lastResultJson.value = JSON.stringify((res as any).data, null, 2);
    ElMessage.success(mode === "dry_run" ? "停用 dry-run 完成" : "停用 apply 已提交");
  } finally {
    pushLoading.value = false;
  }
}

onMounted(() => {
  loadCodeSets();
  loadPushConfig();
});
</script>

<style scoped>
.dict-medical { padding: 4px; }
.dict-medical :deep(.el-card) { border-color: var(--border-light); border-radius: var(--radius-base); box-shadow: var(--shadow-sm); }
.toolbar { display: flex; align-items: center; gap: 8px; }
.auth-alert { flex: 1; }
.sub-table-wrap { padding: 8px 40px 12px; }
.sub-toolbar { margin-bottom: 8px; }
.sub-count { color: var(--el-text-color-secondary); font-size: 12px; }

.items-table { margin-top: 12px; }
.pager { justify-content: flex-end; margin-top: 8px; }
.full-width { width: 100%; }
.push-card { margin-top: 16px; }
.push-alert { margin-bottom: 12px; }
.push-form { margin-bottom: 8px; }
.push-summary { margin: 8px 0; font-size: 13px; color: var(--el-text-color-secondary); }
.stop-box { display: flex; align-items: center; gap: 8px; margin: 12px 0; flex-wrap: wrap; }
.stop-label { font-size: 13px; }
.result-box { margin-top: 8px; font-family: ui-monospace, monospace; font-size: 12px; }
</style>
