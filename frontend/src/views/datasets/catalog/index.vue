<script setup lang="ts">
/**
 * 193 B16：数据集目录（真实平台 API，无 mock）。
 * 210 S8：数据集安全治理前端闭环——目录 / 分类治理 / 用途授权 / 受控导出四页签，
 *        操作按钮按权限码显隐（hasPerms），错误经 extractErrorDetail 脱敏后提示。
 */
import { computed, onMounted, reactive, ref, watch } from "vue";
import { QuestionFilled, Refresh } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { hasPerms } from "@/utils/auth";
import { extractErrorDetail } from "@/utils/errorMessage";
import {
  datasetStatusLabel,
  datasetDecisionLabel,
  datasetPurposeLabel,
  datasetGrainLabel
} from "@/utils/statusLabels";
import {
  createExport,
  createGrant,
  downloadExport,
  generateExport,
  getDatasetBatch,
  listClassifications,
  listDatasets,
  listExports,
  listGrants,
  reviewClassification,
  reviewExport,
  reviewGrant,
  revokeGrant,
  submitClassification,
  type BatchDetail,
  type ClassificationItem,
  type DatasetListItem,
  type ExportItem,
  type GrantItem,
  type GrantOperation,
  type PersonalInfoKind,
  type ProtectionLevel
} from "@/api/datasets";

defineOptions({ name: "DatasetCatalog" });

// ---------- 通用 ----------

function errText(e: unknown, fallback = "请求失败"): string {
  return extractErrorDetail(e, fallback);
}

/** ElMessageBox 取消/关闭时 reject 的是字符串，不是 Error */
function isBoxCancel(e: unknown): boolean {
  return e === "cancel" || e === "close";
}

function fmtDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = value.slice(0, 10);
  const time = value.length >= 19 ? value.slice(11, 19) : "";
  return time ? `${date} ${time}` : date;
}

function parseJsonObject(text: string): Record<string, unknown> | null {
  const trimmed = text.trim();
  if (!trimmed) return {};
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

// ---------- 权限（无权限时按钮隐藏，不是 disabled） ----------

const canManageClassification = computed(() => hasPerms("ds.classification.manage"));
const canReviewClassification = computed(() => hasPerms("ds.classification.review"));
const canRequestGrant = computed(() => hasPerms("ds.grant.request"));
const canApproveGrant = computed(() => hasPerms("ds.grant.approve"));
const canManageGrant = computed(() => hasPerms("ds.grant.manage"));
const canApproveExport = computed(() => hasPerms("ds.export.approve"));
const canExecuteExport = computed(() => hasPerms("ds.export.execute"));

// ---------- 页签（首次切入时懒加载，各页签独立 loading） ----------

const activeTab = ref("catalog");
const loadedTabs = new Set<string>(["catalog"]);

watch(activeTab, tab => {
  if (loadedTabs.has(tab)) return;
  loadedTabs.add(tab);
  if (tab === "classification") void loadClassifications();
  else if (tab === "grants") void loadGrants();
  else if (tab === "exports") void loadExports();
});

// ---------- 页签一：目录（B16 + 待定级标记） ----------

const catalogLoading = ref(false);
const datasetItems = ref<DatasetListItem[]>([]);

async function loadCatalog() {
  catalogLoading.value = true;
  try {
    const res = await listDatasets();
    datasetItems.value = res.data || [];
  } catch (e) {
    ElMessage.error(errText(e, "加载数据集目录失败"));
  } finally {
    catalogLoading.value = false;
  }
}

// B07 批次检查点查询（幂等与断点恢复）
const batchRunId = ref("");
const batch = ref<BatchDetail | null>(null);

async function loadBatch() {
  const runId = batchRunId.value.trim();
  if (!runId) return;
  try {
    const res = await getDatasetBatch(runId);
    batch.value = res.data ?? null;
  } catch (e) {
    batch.value = null;
    ElMessage.error(errText(e, "批次不存在或无权限"));
  }
}

// ---------- 页签二：分类治理 ----------

const OBJECT_TYPE_OPTIONS = ["dataset_version", "table", "view", "column", "export"] as const;
const CLASS_STATUS_OPTIONS = ["active", "superseded", "pending_approval", "retired"] as const;
/** 保护等级为工程草案口径，非法定分级 */
const LEVEL_TOOLTIP = "P1已批准公开 / P2内部 / P3敏感 / P4严格受限（工程草案，非法定分级）";
const LEVEL_TAG: Record<string, "success" | "info" | "warning" | "danger"> = {
  P1: "success",
  P2: "info",
  P3: "warning",
  P4: "danger"
};
const PROTECTION_LEVEL_OPTIONS: Array<{ value: ProtectionLevel; label: string }> = [
  { value: "P1", label: "P1 已批准公开" },
  { value: "P2", label: "P2 内部" },
  { value: "P3", label: "P3 敏感" },
  { value: "P4", label: "P4 严格受限" }
];
const PERSONAL_INFO_OPTIONS: Array<{ value: PersonalInfoKind; label: string }> = [
  { value: "none", label: "无个人信息" },
  { value: "personal", label: "含个人信息" },
  { value: "sensitive_personal", label: "含敏感个人信息" },
  { value: "pending", label: "待定级" }
];
const PERSONAL_INFO_LABEL: Record<string, string> = {
  none: "无个人信息",
  personal: "含个人信息",
  sensitive_personal: "含敏感个人信息",
  pending: "待定级"
};
const CLASS_STATUS_LABEL: Record<string, string> = {
  active: "生效中",
  superseded: "已被替代",
  pending_approval: "待审批",
  retired: "已退役"
};
const CLASS_STATUS_TAG: Record<string, "success" | "info" | "warning" | "danger"> = {
  active: "success",
  superseded: "info",
  pending_approval: "warning",
  retired: "danger"
};
const LABEL_SOURCE_LABEL: Record<string, string> = {
  manual: "手工标注",
  candidate: "候选导入",
  confirmed: "已确认"
};

const classLoading = ref(false);
const classifications = ref<ClassificationItem[]>([]);
const classFilter = reactive({ object_type: "", status: "" });

const filteredClassifications = computed(() =>
  classifications.value.filter(
    item =>
      (!classFilter.object_type || item.object_type === classFilter.object_type) &&
      (!classFilter.status || item.status === classFilter.status)
  )
);

async function loadClassifications() {
  classLoading.value = true;
  try {
    const res = await listClassifications();
    classifications.value = res.data || [];
  } catch (e) {
    ElMessage.error(errText(e, "加载分类清单失败"));
  } finally {
    classLoading.value = false;
  }
}

// 分类提案折叠表单（仅 ds.classification.manage 可见）
const classFormOpen = ref<string[]>([]);
const classSubmitting = ref(false);
const classForm = reactive({
  dataset_code: "",
  version_id: undefined as number | undefined,
  protection_level: "P3" as ProtectionLevel,
  personal_info: "pending" as PersonalInfoKind,
  purposes: "",
  export_allowed: false,
  training_allowed: false,
  expected_version: 0
});

async function submitClassForm() {
  const code = classForm.dataset_code.trim();
  if (!code) {
    ElMessage.warning("请输入 dataset_code");
    return;
  }
  const versionId = classForm.version_id;
  if (!versionId || versionId <= 0) {
    ElMessage.warning("请输入有效的 version_id");
    return;
  }
  const purposes = classForm.purposes
    .split(/[,，]/)
    .map(s => s.trim())
    .filter(Boolean);
  classSubmitting.value = true;
  try {
    const res = await submitClassification({
      object_type: "dataset_version",
      object_ref: `dataset:${code}:${versionId}`,
      labels: {
        protection_level: classForm.protection_level,
        personal_info: classForm.personal_info,
        usage_constraints: {
          purposes,
          export_allowed: classForm.export_allowed,
          training_allowed: classForm.training_allowed
        }
      },
      expected_version: classForm.expected_version,
      label_source: "manual"
    });
    const result = res.data;
    if (result?.needs_approval) {
      ElMessage.success(`提案已提交，等待独立审批（${(result.reasons || []).join("；") || "策略要求审批"}）`);
    } else {
      ElMessage.success(`分类已生效（版本 ${result?.version ?? "-"}，等级 ${result?.protection_level ?? "-"}）`);
    }
    await loadClassifications();
    void loadCatalog(); // 目录页"待定级"标记同步刷新
  } catch (e) {
    ElMessage.error(errText(e, "提交分类提案失败"));
  } finally {
    classSubmitting.value = false;
  }
}

async function reviewClassRow(row: ClassificationItem, decision: "approve" | "reject") {
  const approve = decision === "approve";
  let note = "";
  try {
    const { value } = await ElMessageBox.prompt(
      `对象：${row.object_ref}（保护等级 ${row.protection_level}）`,
      approve ? "通过分类提案" : "拒绝分类提案",
      { inputPlaceholder: "审批意见（note）", type: approve ? "success" : "warning" }
    );
    note = (value || "").trim();
  } catch (e) {
    if (isBoxCancel(e)) return;
    ElMessage.error(errText(e));
    return;
  }
  try {
    await reviewClassification(row.id, { decision, note });
    ElMessage.success(approve ? "分类提案已通过" : "分类提案已拒绝");
    await loadClassifications();
    void loadCatalog();
  } catch (e) {
    ElMessage.error(errText(e, "分类审批失败"));
  }
}

// ---------- 页签三：用途授权 ----------

const OPERATION_OPTIONS: Array<{ value: GrantOperation; label: string }> = [
  { value: "read", label: "读取" },
  { value: "export", label: "导出" },
  { value: "train", label: "训练" },
  { value: "derive", label: "派生" }
];
const OPERATION_LABEL: Record<string, string> = {
  read: "读取",
  export: "导出",
  train: "训练",
  derive: "派生"
};
const GRANT_STATUS_LABEL: Record<string, string> = {
  pending: "待审批",
  active: "生效中",
  rejected: "已拒绝",
  revoked: "已撤权",
  expired: "已过期"
};
const GRANT_STATUS_TAG: Record<string, "success" | "info" | "warning" | "danger"> = {
  pending: "warning",
  active: "success",
  rejected: "danger",
  revoked: "info",
  expired: "info"
};

const grantLoading = ref(false);
const grants = ref<GrantItem[]>([]);

async function loadGrants() {
  grantLoading.value = true;
  try {
    const res = await listGrants();
    grants.value = res.data || [];
  } catch (e) {
    ElMessage.error(errText(e, "加载授权清单失败"));
  } finally {
    grantLoading.value = false;
  }
}

// 授权申请折叠表单（仅 ds.grant.request 可见）
const grantFormOpen = ref<string[]>([]);
const grantSubmitting = ref(false);
const grantForm = reactive({
  principal: "",
  purpose_code: "",
  resource_ref: "*",
  operations: ["read"] as GrantOperation[],
  legal_basis_ref: "",
  valid_hours: 24,
  row_scope: ""
});

async function submitGrantForm() {
  const principal = grantForm.principal.trim();
  if (!principal) {
    ElMessage.warning("请输入授权主体 principal");
    return;
  }
  const purpose = grantForm.purpose_code.trim();
  if (!purpose) {
    ElMessage.warning("请输入用途码 purpose_code");
    return;
  }
  if (!grantForm.operations.length) {
    ElMessage.warning("请至少选择一个操作");
    return;
  }
  const legalBasis = grantForm.legal_basis_ref.trim();
  if (!legalBasis) {
    ElMessage.warning("请输入法律/合规依据引用 legal_basis_ref");
    return;
  }
  const rowScope = parseJsonObject(grantForm.row_scope);
  if (rowScope === null) {
    ElMessage.error("row_scope 必须是合法的 JSON 对象");
    return;
  }
  grantSubmitting.value = true;
  try {
    await createGrant({
      principal,
      purpose_code: purpose,
      resource_ref: grantForm.resource_ref.trim() || "*",
      operations: grantForm.operations,
      legal_basis_ref: legalBasis,
      valid_hours: grantForm.valid_hours,
      row_scope: rowScope
    });
    ElMessage.success("授权申请已提交，等待独立审批");
    await loadGrants();
  } catch (e) {
    ElMessage.error(errText(e, "提交授权申请失败"));
  } finally {
    grantSubmitting.value = false;
  }
}

async function reviewGrantRow(row: GrantItem, decision: "approve" | "reject") {
  const approve = decision === "approve";
  try {
    await ElMessageBox.confirm(
      `确认${approve ? "通过" : "拒绝"}主体「${row.principal}」的「${row.purpose_code}」授权申请？`,
      approve ? "通过授权申请" : "拒绝授权申请",
      { type: "warning" }
    );
  } catch {
    return;
  }
  try {
    await reviewGrant(row.id, { decision });
    ElMessage.success(approve ? "授权已通过并生效" : "授权申请已拒绝");
    await loadGrants();
  } catch (e) {
    ElMessage.error(errText(e, "授权审批失败"));
  }
}

async function revokeGrantRow(row: GrantItem) {
  let reason = "";
  try {
    const { value } = await ElMessageBox.prompt(
      `撤权将即时生效并传播到关联导出。主体：${row.principal}（用途 ${row.purpose_code}）`,
      `撤权：${row.principal}`,
      {
        inputPlaceholder: "撤权原因（必填，记入账本）",
        inputValidator: (v: string) => Boolean(v && v.trim()) || "撤权原因不能为空"
      }
    );
    reason = (value || "").trim();
  } catch (e) {
    if (isBoxCancel(e)) return;
    ElMessage.error(errText(e));
    return;
  }
  try {
    await revokeGrant(row.id, { reason });
    ElMessage.success("授权已撤销");
    await loadGrants();
  } catch (e) {
    ElMessage.error(errText(e, "撤权失败"));
  }
}

// ---------- 页签四：受控导出 ----------

const EXPORT_FIELD_OPTIONS = [
  "fact_key",
  "fact_kind",
  "internal_patient_id",
  "source_code",
  "standard_value",
  "business_time",
  "available_time",
  "quality_flag"
];
const EXPORT_STATUS_LABEL: Record<string, string> = {
  review_pending: "待审批",
  approved: "已批准",
  generated: "已生成",
  revoked: "已撤销",
  expired: "已过期",
  failed: "生成失败"
};
const EXPORT_STATUS_TAG: Record<string, "success" | "info" | "warning" | "danger" | "primary"> = {
  review_pending: "warning",
  approved: "primary",
  generated: "success",
  revoked: "danger",
  expired: "info",
  failed: "danger"
};

const exportLoading = ref(false);
const exportItems = ref<ExportItem[]>([]);

async function loadExports() {
  exportLoading.value = true;
  try {
    const res = await listExports();
    exportItems.value = res.data || [];
  } catch (e) {
    ElMessage.error(errText(e, "加载导出清单失败"));
  } finally {
    exportLoading.value = false;
  }
}

function exportFieldCount(row: ExportItem): number {
  return row.field_whitelist?.length ?? row.requested_fields?.length ?? 0;
}

function shortSha(value: string | null): string {
  return value ? value.slice(0, 12) : "-";
}

// 导出申请折叠表单（登录用户可见，能否通过由后端裁决）
const exportFormOpen = ref<string[]>([]);
const exportSubmitting = ref(false);
const exportForm = reactive({
  dataset_code: "",
  version_id: undefined as number | undefined,
  fields: [] as string[],
  project_code: ""
});

async function submitExportForm() {
  const code = exportForm.dataset_code.trim();
  if (!code) {
    ElMessage.warning("请输入 dataset_code");
    return;
  }
  const versionId = exportForm.version_id;
  if (!versionId || versionId <= 0) {
    ElMessage.warning("请输入有效的 version_id");
    return;
  }
  if (!exportForm.fields.length) {
    ElMessage.warning("请至少选择一个导出字段");
    return;
  }
  exportSubmitting.value = true;
  try {
    const res = await createExport(code, versionId, {
      fields: exportForm.fields,
      project_code: exportForm.project_code.trim() || null
    });
    const result = res.data;
    ElMessage.success(
      `导出申请已提交：${result?.export_code ?? ""}（${EXPORT_STATUS_LABEL[result?.status ?? ""] ?? result?.status ?? ""}）`
    );
    await loadExports();
  } catch (e) {
    ElMessage.error(errText(e, "提交导出申请失败"));
  } finally {
    exportSubmitting.value = false;
  }
}

async function reviewExportRow(row: ExportItem, decision: "approve" | "reject") {
  const approve = decision === "approve";
  let note = "";
  try {
    const { value } = await ElMessageBox.prompt(
      `导出：${row.export_code}（${exportFieldCount(row)} 个字段）`,
      approve ? "通过导出申请" : "拒绝导出申请",
      { inputPlaceholder: "审批意见（note）", type: approve ? "success" : "warning" }
    );
    note = (value || "").trim();
  } catch (e) {
    if (isBoxCancel(e)) return;
    ElMessage.error(errText(e));
    return;
  }
  try {
    await reviewExport(row.export_code, { decision, note });
    ElMessage.success(approve ? "导出申请已通过" : "导出申请已拒绝");
    await loadExports();
  } catch (e) {
    ElMessage.error(errText(e, "导出审批失败"));
  }
}

const generatingCode = ref("");
const downloadingCode = ref("");

async function generateExportRow(row: ExportItem) {
  generatingCode.value = row.export_code;
  try {
    await generateExport(row.export_code);
    ElMessage.success(`工件已生成：${row.export_code}`);
    await loadExports();
  } catch (e) {
    ElMessage.error(errText(e, "生成导出工件失败"));
  } finally {
    generatingCode.value = "";
  }
}

async function downloadExportRow(row: ExportItem) {
  downloadingCode.value = row.export_code;
  try {
    const blob = await downloadExport(row.export_code);
    const url = URL.createObjectURL(new Blob([blob], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${row.export_code}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    ElMessage.success(`已下载 ${row.export_code}.csv`);
  } catch (e) {
    ElMessage.error(errText(e, "下载导出工件失败"));
  } finally {
    downloadingCode.value = "";
  }
}

onMounted(loadCatalog);
</script>

<template>
  <div class="dataset-catalog-page">
    <RePageHeader
      title="数据集目录"
      subtitle="患者纵向数据集目录：分类分级、版本状态与批次；含安全治理闭环（分类/授权/受控导出）"
    />
    <el-card shadow="never">
      <el-tabs v-model="activeTab" class="ds-tabs">
        <!-- 页签一：目录 -->
        <el-tab-pane label="目录" name="catalog">
          <div class="tab-toolbar">
            <el-button :icon="Refresh" :loading="catalogLoading" @click="loadCatalog">刷新目录</el-button>
          </div>
          <el-table v-loading="catalogLoading" :data="datasetItems" stripe>
            <el-table-column prop="dataset_code" label="编码" min-width="160" show-overflow-tooltip />
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column label="用途" width="130">
              <template #default="{ row }">{{ datasetPurposeLabel(row.purpose_code) }}</template>
            </el-table-column>
            <el-table-column label="粒度" width="90">
              <template #default="{ row }">{{ datasetGrainLabel(row.grain) }}</template>
            </el-table-column>
            <el-table-column label="最新版本" width="80" align="right">
              <template #default="{ row }">{{ row.version ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'published' ? 'success' : row.status === 'revoked' ? 'danger' : 'info'">
                  {{ datasetStatusLabel(row.status || "draft") }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="访问" width="130">
              <template #default="{ row }">
                <el-tag size="small" :type="row.readable ? 'success' : 'warning'">
                  {{ row.readable ? "已授权" : datasetDecisionLabel(row.decision) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="待定级" width="90" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.pending_classification" size="small" type="warning">待定级</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :image-size="70" description="暂无数据集" />
            </template>
          </el-table>

          <el-divider content-position="left">批次检查点查询</el-divider>
          <div class="batch-bar">
            <el-input
              v-model="batchRunId"
              placeholder="输入批次 run_id"
              clearable
              class="batch-input"
              @keyup.enter="loadBatch"
            />
            <el-button @click="loadBatch">查询批次</el-button>
          </div>
          <pre v-if="batch" class="batch-json">{{ JSON.stringify(batch, null, 2) }}</pre>
          <div v-else class="batch-hint">输入批次号后显示计数与检查点</div>
        </el-tab-pane>

        <!-- 页签二：分类治理 -->
        <el-tab-pane label="分类治理" name="classification">
          <div class="tab-toolbar">
            <el-select v-model="classFilter.object_type" placeholder="对象类型（全部）" clearable class="filter-select">
              <el-option v-for="t in OBJECT_TYPE_OPTIONS" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="classFilter.status" placeholder="状态（全部）" clearable class="filter-select">
              <el-option v-for="s in CLASS_STATUS_OPTIONS" :key="s" :label="CLASS_STATUS_LABEL[s] || s" :value="s" />
            </el-select>
            <el-button :icon="Refresh" :loading="classLoading" @click="loadClassifications">刷新</el-button>
          </div>

          <el-collapse v-if="canManageClassification" v-model="classFormOpen" class="propose-collapse">
            <el-collapse-item name="form" title="提交分类提案（dataset_version，CAS 并发控制）">
              <el-form label-width="130px" class="propose-form" @submit.prevent>
                <div class="form-grid">
                  <el-form-item label="dataset_code">
                    <el-input v-model="classForm.dataset_code" placeholder="如 ds_high_quality" />
                  </el-form-item>
                  <el-form-item label="version_id">
                    <el-input-number v-model="classForm.version_id" :min="1" :step="1" />
                  </el-form-item>
                  <el-form-item label="保护等级">
                    <el-select v-model="classForm.protection_level">
                      <el-option v-for="opt in PROTECTION_LEVEL_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="个人信息属性">
                    <el-select v-model="classForm.personal_info">
                      <el-option v-for="opt in PERSONAL_INFO_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="用途码">
                    <el-input v-model="classForm.purposes" placeholder="逗号分隔，如 research,quality" />
                  </el-form-item>
                  <el-form-item label="expected_version">
                    <el-input-number v-model="classForm.expected_version" :min="0" :step="1" />
                  </el-form-item>
                  <el-form-item label="允许导出">
                    <el-switch v-model="classForm.export_allowed" />
                  </el-form-item>
                  <el-form-item label="允许训练">
                    <el-switch v-model="classForm.training_allowed" />
                  </el-form-item>
                </div>
                <el-form-item>
                  <el-button type="primary" :loading="classSubmitting" @click="submitClassForm">
                    提交提案（object_ref 自动拼接）
                  </el-button>
                </el-form-item>
              </el-form>
            </el-collapse-item>
          </el-collapse>

          <el-table v-loading="classLoading" :data="filteredClassifications" stripe>
            <el-table-column prop="object_type" label="对象类型" width="130" />
            <el-table-column prop="object_ref" label="对象键" min-width="220" show-overflow-tooltip />
            <el-table-column width="100" align="center">
              <template #header>
                <span>保护等级
                  <el-tooltip :content="LEVEL_TOOLTIP" placement="top">
                    <el-icon class="level-help"><QuestionFilled /></el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <el-tag size="small" :type="LEVEL_TAG[row.protection_level] || 'info'">
                  {{ row.protection_level || "-" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="100">
              <template #default="{ row }">{{ LABEL_SOURCE_LABEL[row.label_source] || row.label_source || "-" }}</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="CLASS_STATUS_TAG[row.status] || 'info'">
                  {{ CLASS_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="version" label="版本" width="70" align="right" />
            <el-table-column prop="classified_by" label="标注人" min-width="130" show-overflow-tooltip />
            <el-table-column label="时间" width="150">
              <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column v-if="canReviewClassification" label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <template v-if="row.status === 'pending_approval'">
                  <el-button link type="primary" size="small" @click="reviewClassRow(row, 'approve')">通过</el-button>
                  <el-button link type="danger" size="small" @click="reviewClassRow(row, 'reject')">拒绝</el-button>
                </template>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :image-size="70" description="暂无分类记录" />
            </template>
          </el-table>
        </el-tab-pane>

        <!-- 页签三：用途授权 -->
        <el-tab-pane label="用途授权" name="grants">
          <div class="tab-toolbar">
            <el-button :icon="Refresh" :loading="grantLoading" @click="loadGrants">刷新</el-button>
          </div>

          <el-collapse v-if="canRequestGrant" v-model="grantFormOpen" class="propose-collapse">
            <el-collapse-item name="form" title="新建授权申请（需独立审批，审批人≠申请人）">
              <el-form label-width="130px" class="propose-form" @submit.prevent>
                <div class="form-grid">
                  <el-form-item label="principal">
                    <el-input v-model="grantForm.principal" placeholder="授权主体，如 user:zhang" />
                  </el-form-item>
                  <el-form-item label="purpose_code">
                    <el-input v-model="grantForm.purpose_code" placeholder="用途码，如 research" />
                  </el-form-item>
                  <el-form-item label="resource_ref">
                    <el-input v-model="grantForm.resource_ref" placeholder="资源键，* 表示全部" />
                  </el-form-item>
                  <el-form-item label="operations">
                    <el-select v-model="grantForm.operations" multiple collapse-tags class="full-width">
                      <el-option v-for="opt in OPERATION_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="legal_basis_ref">
                    <el-input v-model="grantForm.legal_basis_ref" placeholder="法律/合规依据引用" />
                  </el-form-item>
                  <el-form-item label="valid_hours">
                    <el-input-number v-model="grantForm.valid_hours" :min="1" :max="8760" :step="1" />
                  </el-form-item>
                  <el-form-item label="row_scope" class="span-all">
                    <el-input
                      v-model="grantForm.row_scope"
                      type="textarea"
                      :rows="2"
                      placeholder='行范围 JSON 对象，如 {"dataset_code":"ds_x"}；留空表示不限定'
                    />
                  </el-form-item>
                </div>
                <el-form-item>
                  <el-button type="primary" :loading="grantSubmitting" @click="submitGrantForm">提交申请</el-button>
                </el-form-item>
              </el-form>
            </el-collapse-item>
          </el-collapse>

          <el-table v-loading="grantLoading" :data="grants" stripe>
            <el-table-column prop="principal" label="主体" min-width="150" show-overflow-tooltip />
            <el-table-column prop="purpose_code" label="用途" width="110" show-overflow-tooltip />
            <el-table-column prop="resource_ref" label="资源" min-width="190" show-overflow-tooltip />
            <el-table-column label="操作集" width="150">
              <template #default="{ row }">
                <el-tag v-for="op in row.operations || []" :key="op" size="small" class="op-tag">
                  {{ OPERATION_LABEL[op] || op }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="GRANT_STATUS_TAG[row.status] || 'info'">
                  {{ GRANT_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="有效期" width="170">
              <template #default="{ row }">
                <div class="validity">
                  <span>{{ fmtDateTime(row.valid_from) }}</span>
                  <span>~ {{ fmtDateTime(row.valid_until) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="requested_by" label="申请人" min-width="120" show-overflow-tooltip />
            <el-table-column label="审批人" width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.approved_by || "-" }}</template>
            </el-table-column>
            <el-table-column prop="grant_version" label="版本" width="70" align="right" />
            <el-table-column
              v-if="canApproveGrant || canManageGrant"
              label="操作"
              width="150"
              fixed="right"
            >
              <template #default="{ row }">
                <template v-if="row.status === 'pending' && canApproveGrant">
                  <el-button link type="primary" size="small" @click="reviewGrantRow(row, 'approve')">通过</el-button>
                  <el-button link type="danger" size="small" @click="reviewGrantRow(row, 'reject')">拒绝</el-button>
                </template>
                <el-button
                  v-if="row.status === 'active' && canManageGrant"
                  link
                  type="danger"
                  size="small"
                  @click="revokeGrantRow(row)"
                >
                  撤权
                </el-button>
                <span v-if="!(row.status === 'pending' && canApproveGrant) && !(row.status === 'active' && canManageGrant)">-</span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :image-size="70" description="暂无授权记录" />
            </template>
          </el-table>
        </el-tab-pane>

        <!-- 页签四：受控导出 -->
        <el-tab-pane label="受控导出" name="exports">
          <div class="tab-toolbar">
            <el-button :icon="Refresh" :loading="exportLoading" @click="loadExports">刷新</el-button>
          </div>

          <el-collapse v-model="exportFormOpen" class="propose-collapse">
            <el-collapse-item name="form" title="新建导出申请（登录用户可提交，是否放行由后端裁决）">
              <el-form label-width="130px" class="propose-form" @submit.prevent>
                <div class="form-grid">
                  <el-form-item label="dataset_code">
                    <el-input v-model="exportForm.dataset_code" placeholder="如 ds_high_quality" />
                  </el-form-item>
                  <el-form-item label="version_id">
                    <el-input-number v-model="exportForm.version_id" :min="1" :step="1" />
                  </el-form-item>
                  <el-form-item label="project_code">
                    <el-input v-model="exportForm.project_code" placeholder="项目代码（可选）" />
                  </el-form-item>
                  <el-form-item label="导出字段" class="span-all">
                    <el-select v-model="exportForm.fields" multiple collapse-tags class="full-width" placeholder="选择导出字段">
                      <el-option v-for="f in EXPORT_FIELD_OPTIONS" :key="f" :label="f" :value="f" />
                    </el-select>
                  </el-form-item>
                </div>
                <el-form-item>
                  <el-button type="primary" :loading="exportSubmitting" @click="submitExportForm">提交导出申请</el-button>
                </el-form-item>
              </el-form>
            </el-collapse-item>
          </el-collapse>

          <el-table v-loading="exportLoading" :data="exportItems" stripe>
            <el-table-column prop="export_code" label="导出码" min-width="170" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="EXPORT_STATUS_TAG[row.status] || 'info'">
                  {{ EXPORT_STATUS_LABEL[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="dataset_version_id" label="版本ID" width="90" align="right" />
            <el-table-column label="字段数" width="80" align="right">
              <template #default="{ row }">{{ exportFieldCount(row) }}</template>
            </el-table-column>
            <el-table-column label="审批人" width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.approved_by || "-" }}</template>
            </el-table-column>
            <el-table-column label="行数" width="90" align="right">
              <template #default="{ row }">{{ row.row_count ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="SHA256" width="130">
              <template #default="{ row }">
                <code v-if="row.file_sha256" class="sha-cell">{{ shortSha(row.file_sha256) }}</code>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="到期" width="150">
              <template #default="{ row }">{{ fmtDateTime(row.expires_at) }}</template>
            </el-table-column>
            <el-table-column label="备注" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.review_note || row.generation_error || "-" }}</template>
            </el-table-column>
            <!-- 操作列常驻：下载按钮不挂权限码（后端下载时全量重验），审批/生成按权限显隐 -->
            <el-table-column label="操作" width="190" fixed="right">
              <template #default="{ row }">
                <template v-if="row.status === 'review_pending' && canApproveExport">
                  <el-button link type="primary" size="small" @click="reviewExportRow(row, 'approve')">通过</el-button>
                  <el-button link type="danger" size="small" @click="reviewExportRow(row, 'reject')">拒绝</el-button>
                </template>
                <el-button
                  v-if="row.status === 'approved' && canExecuteExport"
                  link
                  type="primary"
                  size="small"
                  :loading="generatingCode === row.export_code"
                  @click="generateExportRow(row)"
                >
                  生成
                </el-button>
                <el-button
                  v-if="row.status === 'generated'"
                  link
                  type="success"
                  size="small"
                  :loading="downloadingCode === row.export_code"
                  @click="downloadExportRow(row)"
                >
                  下载
                </el-button>
                <span
                  v-if="
                    !(row.status === 'review_pending' && canApproveExport) &&
                    !(row.status === 'approved' && canExecuteExport) &&
                    row.status !== 'generated'
                  "
                >
                  -
                </span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty :image-size="70" description="暂无导出记录" />
            </template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped lang="scss">
.dataset-catalog-page {
  padding: 4px;
}

.tab-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.filter-select {
  width: 190px;
}

.propose-collapse {
  margin-bottom: 10px;
}

.propose-form {
  .form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 0 16px;
  }

  .span-all {
    grid-column: 1 / -1;
  }
}

.full-width {
  width: 100%;
}

.level-help {
  margin-left: 2px;
  color: var(--el-text-color-secondary);
  cursor: help;
  vertical-align: middle;
}

.op-tag {
  margin: 1px 4px 1px 0;
}

.validity {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  line-height: 1.4;
}

.sha-cell {
  font-size: 12px;
}

.batch-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;

  .batch-input {
    width: 280px;
  }
}

.batch-json {
  padding: 8px;
  overflow: auto;
  font-size: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
.batch-hint {
  padding: 8px 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
