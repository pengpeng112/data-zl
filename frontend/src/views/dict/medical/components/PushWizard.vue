<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  approveMedicalPushPlan,
  createMedicalPushPlan,
  executeMedicalPushPlan,
  getMedicalPushPlan,
  type MedicalPushPlanSummary
} from "@/api/dict";
import { listSystems } from "@/api/asset";
import { useUserStoreHook } from "@/store/modules/user";
import { extractErrorDetail } from "@/utils/errorMessage";
import { parseInfectiousSyncItemCodes } from "@/utils/medicalPushPlan";

const step = ref(1);
const loading = ref(false);
const targetSystems = ref<string[]>([]);
const actionType = ref<"insert" | "sync_infectious">("insert");
const infectiousItemCodesText = ref("");
const existingPlanId = ref("");
const currentUsername = useUserStoreHook().username;
// 146 E8（R5）：下发类别可选（此前硬编码 diagnosis，手术计划无法生成）
const categoryCode = ref<"diagnosis" | "operation">("diagnosis");
const plan = ref<MedicalPushPlanSummary | null>(null);
const executeResult = ref<Record<string, unknown> | null>(null);

// 146 E8（R5）：目标系统动态加载（listSystems 驱动，含已知兜底，不再纯硬编码）
const systemOptions = ref<Array<{ label: string; value: string }>>([
  { label: "HIS", value: "HIS_SOURCE" },
  { label: "JHEMR（海量）", value: "JHEMR_VASTBASE" }
]);
const systemOptionsLoading = ref(false);
const SYSTEM_LABELS: Record<string, string> = {
  HIS_SOURCE: "HIS",
  JHEMR_VASTBASE: "JHEMR（海量）"
};

async function loadSystemOptions() {
  systemOptionsLoading.value = true;
  try {
    const res = await listSystems();
    const dynamic = (res.data || [])
      .filter((sys: any) => SYSTEM_LABELS[sys.system_code])
      .map((sys: any) => ({ label: sys.system_name_cn ? `${sys.system_name_cn}（${SYSTEM_LABELS[sys.system_code]}）` : SYSTEM_LABELS[sys.system_code], value: sys.system_code }));
    if (dynamic.length) {
      systemOptions.value = dynamic;
      // 旧默认值 HIS 与后端登记码不一致时，自动对齐到动态选项
      targetSystems.value = targetSystems.value.filter(value => dynamic.some(item => item.value === value));
    }
  } catch {
    // 加载失败保留已知兜底选项
  } finally {
    systemOptionsLoading.value = false;
  }
}

async function createPlan() {
  const isInfectiousSync = actionType.value === "sync_infectious";
  const uniqueItemCodes = parseInfectiousSyncItemCodes(infectiousItemCodesText.value);
  if (isInfectiousSync && (uniqueItemCodes.length < 1 || uniqueItemCodes.length > 500)) {
    ElMessage.warning("专项同步必须填写 1–500 个明确的院内诊断编码");
    return;
  }
  if (!isInfectiousSync && targetSystems.value.length === 0) {
    ElMessage.warning("请至少选择一个目标系统");
    return;
  }
  loading.value = true;
  try {
    const res = await createMedicalPushPlan({
      category_code: isInfectiousSync ? "diagnosis" : categoryCode.value,
      target_systems: isInfectiousSync ? ["HIS_SOURCE"] : targetSystems.value,
      action_type: actionType.value,
      ...(isInfectiousSync ? { item_codes: uniqueItemCodes } : {})
    });
    plan.value = res.data;
    step.value = 2;
    ElMessage.success(`计划已生成：${res.data.item_count} 项`);
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, "创建计划失败"));
  } finally {
    loading.value = false;
  }
}

async function loadExistingPlan() {
  const planId = Number(existingPlanId.value.trim());
  if (!Number.isInteger(planId) || planId <= 0) {
    ElMessage.warning("请输入有效的计划 ID");
    return;
  }
  loading.value = true;
  try {
    const res = await getMedicalPushPlan(planId);
    plan.value = res.data;
    actionType.value = res.data.actions?.some(action => action.action_type === "sync_infectious")
      ? "sync_infectious"
      : "insert";
    categoryCode.value = res.data.category_code === "operation" ? "operation" : "diagnosis";
    step.value = 2;
    ElMessage.success(`已加载计划 ${res.data.plan_code || planId}`);
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, "加载计划失败"));
  } finally {
    loading.value = false;
  }
}

function infectiousPreviewIsComplete(value: MedicalPushPlanSummary | null): boolean {
  if (!value || !Array.isArray(value.actions) || value.actions.length === 0) return false;
  if (value.item_count != null && value.actions.length !== value.item_count) return false;
  return value.actions.every(action => Object.prototype.hasOwnProperty.call(action, "infectious_disease_name"));
}

async function approvePlan() {
  if (!plan.value) return;
  if (actionType.value === "sync_infectious" && !infectiousPreviewIsComplete(plan.value)) {
    ElMessage.error("服务端计划缺少完整的传染病名称快照，不能审批；请重新加载或重建计划");
    return;
  }
  if (plan.value.created_by === currentUsername) {
    ElMessage.warning("计划创建人不能自审，请由另一位审批人加载此计划 ID 后审批");
    return;
  }
  // 146 E8（R5）：取消确认时静默返回，不再把取消当失败弹错
  const approvalMessage = actionType.value === "sync_infectious"
    ? "审批后计划会进入受控同步队列，启用的 worker 可能据此更新 HIS 的 DIAGNOSIS_NAME_CRB。请核对每条编码和目标名称（空值表示清空）。"
    : "审批后计划会进入受控同步队列，启用的 worker 可能据此写入目标业务字典。请核对目标系统和计划内容。";
  const confirmed = await ElMessageBox.confirm(approvalMessage, "审批并排入受控同步队列").catch(() => null);
  if (!confirmed) return;
  loading.value = true;
  try {
    const res = await approveMedicalPushPlan(plan.value.id, "工作台审批");
    plan.value = { ...plan.value, ...res.data };
    step.value = 3;
    ElMessage.success("计划已审批并进入受控同步队列");
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, "审批失败"));
  } finally {
    loading.value = false;
  }
}

async function executePlan() {
  if (!plan.value || plan.value.status !== "approved" || plan.value.is_expired) return;
  const confirmed = await ElMessageBox.confirm(
    "此操作仅生成 dry-run 预览。此前的审批已将计划提交受控同步队列；worker 是否写入业务库由独立开关、执行器白名单及来源写策略共同控制。",
    "生成执行预览"
  ).catch(() => null);
  if (!confirmed) return;
  loading.value = true;
  try {
    const res = await executeMedicalPushPlan(plan.value.id);
    executeResult.value = res.data as Record<string, unknown>;
    step.value = 4;
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, "执行失败"));
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadSystemOptions();
});
</script>

<template>
  <div class="push-wizard">
    <el-steps :active="step - 1" finish-status="success" class="mb-4">
      <el-step title="选择目标" />
      <el-step title="预检/审批" />
      <el-step title="执行" />
      <el-step title="对账" />
    </el-steps>

    <div v-if="step === 1" class="step-content">
      <div class="step-form-row">
        <span class="step-label">计划动作</span>
        <el-radio-group v-model="actionType">
          <el-radio-button value="insert">新增字典项</el-radio-button>
          <el-radio-button value="sync_infectious">同步传染病诊断名称</el-radio-button>
        </el-radio-group>
      </div>
      <el-alert
        v-if="actionType === 'sync_infectious'"
        class="mb-4"
        type="warning"
        show-icon
        :closable="false"
        title="专项范围：仅诊断类别、HIS_SOURCE，仅更新 COMM.DIAGNOSIS_DICT.DIAGNOSIS_NAME_CRB。必须明确填写 1–500 个院内诊断编码；不修改 CRB_CODE 或其他字段。空传染病名称表示明确清空 HIS 字段。"
      />
      <el-input
        v-if="actionType === 'sync_infectious'"
        v-model="infectiousItemCodesText"
        type="textarea"
        :rows="3"
        maxlength="12000"
        show-word-limit
        placeholder="逐行或用逗号分隔院内诊断编码（1–500 个）；不会默认选择全部诊断"
        class="mb-4"
      />
      <div v-if="actionType === 'insert'" class="step-form-row">
        <span class="step-label">下发类别</span>
        <el-radio-group v-model="categoryCode">
          <el-radio-button value="diagnosis">诊断</el-radio-button>
          <el-radio-button value="operation">手术</el-radio-button>
        </el-radio-group>
      </div>
      <div v-if="actionType === 'insert'" class="step-form-row">
        <span class="step-label">目标系统</span>
        <el-checkbox-group v-model="targetSystems" class="mb-4" :loading="systemOptionsLoading">
          <el-checkbox v-for="opt in systemOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
        </el-checkbox-group>
      </div>
      <el-empty
        v-if="!systemOptions.length && !systemOptionsLoading"
        description="未发现可下发的目标系统：请先在「业务系统与数据资源」完成 HIS/海量连接登记"
        :image-size="72"
      />
      <el-button v-perms="'dict.medical.plan.create'" type="primary" :loading="loading" @click="createPlan">生成推送计划</el-button>
      <el-divider />
      <div class="step-form-row">
        <span class="step-label">审批已有计划</span>
        <el-input v-model="existingPlanId" placeholder="计划 ID" style="width: 180px" />
        <el-button :loading="loading" @click="loadExistingPlan">加载计划</el-button>
      </div>
    </div>

    <div v-if="step === 2 && plan" class="step-content">
      <!-- 146 E8（R5）：下发规则（约束）在预检/审批步骤明示 -->
      <el-alert
        class="mb-4"
        :type="actionType === 'sync_infectious' ? 'info' : 'warning'"
        show-icon
        :closable="false"
        :title="actionType === 'sync_infectious'
          ? '专项动作仅更新 HIS COMM.DIAGNOSIS_DICT.DIAGNOSIS_NAME_CRB；审批会将计划排入受控同步队列，worker 可能执行实际字段更新。'
          : '下发规则：只增不改已有业务字段；停用仅按“单条停用”执行；医保灰码只写 ybhm=灰码、不写对照表。审批会将计划排入受控同步队列。'"
      />
      <el-descriptions :column="2" border size="small" class="mb-4">
        <el-descriptions-item label="计划 ID">{{ plan.id }}</el-descriptions-item>
        <el-descriptions-item label="计划编号">{{ plan.plan_code }}</el-descriptions-item>
        <el-descriptions-item label="编码数">{{ plan.item_count }}</el-descriptions-item>
        <el-descriptions-item label="目标系统">{{ plan.target_systems.join(", ") }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="plan.status === 'approved' ? 'success' : 'info'" size="small">{{ plan.status }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="actionType === 'sync_infectious'"
        class="mb-4"
        type="info"
        show-icon
        :closable="false"
        title="以下预览来自服务端计划快照；名称为空表示审批后清空 HIS 的 DIAGNOSIS_NAME_CRB。审批仍要求非创建人操作。"
      />
      <el-table v-if="actionType === 'sync_infectious'" :data="plan.actions || []" stripe size="small" max-height="320" class="mb-4">
        <el-table-column prop="item_code" label="院内诊断编码" min-width="150" />
        <el-table-column prop="item_name_cn" label="诊断名称" min-width="180" />
        <el-table-column label="HIS 传染病诊断名称（空值=清空）" min-width="240">
          <template #default="{ row }">
            <el-tag v-if="row.infectious_disease_name === null || row.infectious_disease_name === ''" type="warning">明确清空</el-tag>
            <el-tag v-else-if="row.infectious_disease_name === undefined" type="danger">缺少服务端快照</el-tag>
            <span v-else>{{ row.infectious_disease_name }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-alert
        v-if="plan.created_by && plan.created_by === currentUsername && plan.status === 'draft'"
        class="mb-4"
        type="warning"
        show-icon
        :closable="false"
        title="当前用户是计划创建人，不能审批。请将计划 ID 提供给另一位审批人加载。"
      />
      <el-button v-if="plan.status === 'draft' && !plan.is_expired" v-perms="'dict.medical.approve'" type="primary" :loading="loading" :disabled="actionType === 'sync_infectious' && !infectiousPreviewIsComplete(plan)" @click="approvePlan">审批计划并排队</el-button>
      <el-button v-if="plan.status === 'approved' && !plan.is_expired" type="success" @click="step = 3">查看执行预览</el-button>
      <el-alert v-else-if="plan.is_expired" class="mt-3" type="error" show-icon :closable="false" title="计划已过期，不能审批或进入执行预览；请重新创建计划。" />
      <el-alert v-else-if="plan.status !== 'draft' && plan.status !== 'approved'" class="mt-3" type="info" show-icon :closable="false" :title="`当前状态 ${plan.status} 不支持审批或执行。`" />
    </div>

    <div v-if="step === 3 && plan" class="step-content">
      <el-alert title="以下按钮只生成 dry-run 预览。计划审批已进入受控同步队列；worker 可能独立执行实际同步。" type="warning" show-icon :closable="false" class="mb-4" />
      <el-button v-perms="'dict.medical.execute'" type="primary" :loading="loading" @click="executePlan">生成 dry-run 预览</el-button>
    </div>

    <div v-if="step === 4" class="step-content">
      <el-result icon="success" title="Dry-run 预览完成" sub-title="此预览不改变队列状态；此前审批的计划仍由受控 worker 独立处理">
        <template #extra>
          <pre v-if="executeResult" class="result-json">{{ JSON.stringify(executeResult, null, 2) }}</pre>
          <el-button @click="step = 1; plan = null">新建计划</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<style scoped>
.push-wizard { padding: 16px 0; }

.step-content { min-height: 200px; }

.result-json { max-height: 300px; padding: 12px; overflow: auto; font-size: 12px; text-align: left; background: var(--el-fill-color-light); border-radius: 4px; }

.step-form-row { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }

.step-label { font-size: 13px; color: var(--el-text-color-regular); }
</style>
