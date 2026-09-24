<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
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
import { getMedicalItems } from "@/api/dict";

const step = ref(1);
const loading = ref(false);
const targetSystems = ref<string[]>([]);
const actionType = ref<"insert" | "sync_infectious">("insert");
const infectiousItemCodesText = ref("");
// 200 D01：普通新增同样必须明确选择编码（可搜索勾选），不提供"全选整库"
const insertSelectedItemCodes = ref<string[]>([]);
const insertCodeOptions = ref<Array<{ code: string; name: string }>>([]);
const insertOptionsLoading = ref(false);
const insertSearchKeyword = ref("");
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

const LOCAL_CODE_SETS: Record<"diagnosis" | "operation", string> = {
  diagnosis: "diagnosis_local_clinical",
  operation: "operation_local_clinical"
};

async function loadInsertCodeOptions() {
  insertOptionsLoading.value = true;
  try {
    const res = await getMedicalItems(LOCAL_CODE_SETS[categoryCode.value], {
      status: "active",
      // 后端上限 le=200：传 500 会 422，向导编码选项恒为空（T27 浏览器闭环实测发现）
      page_size: 200
    });
    const rows: Array<Record<string, unknown>> = (res.data as any)?.items || (res.data as any) || [];
    insertCodeOptions.value = rows
      .filter((row) => String(row.status ?? "active") === "active")
      .map((row) => ({
        code: String(row.item_code ?? ""),
        name: String(row.item_name_cn ?? "")
      }))
      .filter((item) => item.code);
    // 类别切换后，已选项若不在新类别中则剔除
    insertSelectedItemCodes.value = insertSelectedItemCodes.value.filter(code =>
      insertCodeOptions.value.some(option => option.code === code));
  } catch {
    insertCodeOptions.value = [];
  } finally {
    insertOptionsLoading.value = false;
  }
}

function onCategoryChange() {
  insertSelectedItemCodes.value = [];
  void loadInsertCodeOptions();
}

const filteredInsertOptions = computed(() => {
  const keyword = insertSearchKeyword.value.trim().toLowerCase();
  if (!keyword) return insertCodeOptions.value.slice(0, 200);
  return insertCodeOptions.value
    .filter(option => option.code.toLowerCase().includes(keyword) || option.name.toLowerCase().includes(keyword))
    .slice(0, 200);
});

async function createPlan() {
  const isInfectiousSync = actionType.value === "sync_infectious";
  const uniqueItemCodes = isInfectiousSync
    ? parseInfectiousSyncItemCodes(infectiousItemCodesText.value)
    : Array.from(new Set(insertSelectedItemCodes.value.map(code => code.trim()).filter(Boolean)));
  if (uniqueItemCodes.length < 1 || uniqueItemCodes.length > 500) {
    ElMessage.warning(isInfectiousSync
      ? "专项同步必须填写 1–500 个明确的院内诊断编码"
      : "必须先勾选 1–500 个明确的院内编码：不支持空选或隐式整库下发");
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
      item_codes: uniqueItemCodes
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

// 202 D2-1：审批前动作预览完整性（全 action_type 通用）。一个编码在一个目标
// 系统可能生成多条动作（如 JHEMR 诊断=字典+对照+ICD 三条），因此完整性按
// 「编码去重数=item_count 且 编码×目标全覆盖」判定，不沿用传染病单目标假设。
function planActionsAreComplete(value: MedicalPushPlanSummary | null): boolean {
  if (!value || !Array.isArray(value.actions) || value.actions.length === 0) return false;
  const codes = new Set(value.actions.map(action => String(action.item_code ?? "")));
  if (value.item_count != null && codes.size !== value.item_count) return false;
  const targets = value.target_systems || [];
  if (targets.length) {
    const covered = new Set(value.actions.map(action => `${action.item_code}::${action.target_system}`));
    for (const code of codes) {
      for (const target of targets) {
        if (!covered.has(`${code}::${target}`)) return false;
      }
    }
  }
  if (actionType.value === "sync_infectious") return infectiousPreviewIsComplete(value);
  return true;
}

function actionTypeLabel(actionTypeValue: string): string {
  if (actionTypeValue === "sync_infectious") return "传染病名称同步";
  if (actionTypeValue === "stop") return "停用";
  if (actionTypeValue === "insert") return "新增";
  return actionTypeValue;
}

async function approvePlan() {
  if (!plan.value) return;
  // 202 D2-1：所有 action_type 统一完整性门禁（按钮 disabled 之外的双保险）
  if (!planActionsAreComplete(plan.value)) {
    ElMessage.error(
      actionType.value === "sync_infectious"
        ? "服务端计划缺少完整的传染病名称快照，不能审批；请重新加载或重建计划"
        : "计划动作预览不完整（编码×目标覆盖缺失），不能审批；请重新生成计划"
    );
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
  void loadInsertCodeOptions();
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
        <el-radio-group v-model="categoryCode" @change="onCategoryChange">
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
      <!-- 200 D01/§4.3：普通新增必须明确勾选院内编码（可搜索），
           不提供整库"全选"，空选择无法生成计划 -->
      <div v-if="actionType === 'insert'" class="step-form-row" style="align-items: flex-start">
        <span class="step-label">选择院内编码</span>
        <div style="flex: 1">
          <el-input
            v-model="insertSearchKeyword"
            placeholder="按编码或名称过滤（每次最多展示 200 项）"
            size="small"
            clearable
            class="mb-2"
            style="max-width: 360px"
          />
          <el-select
            v-model="insertSelectedItemCodes"
            multiple
            filterable
            clearable
            :loading="insertOptionsLoading"
            placeholder="勾选要下发的院内编码（1–500 个）"
            style="width: 100%"
            :max-collapse-tags="8"
          >
            <el-option
              v-for="opt in filteredInsertOptions"
              :key="opt.code"
              :value="opt.code"
              :label="`${opt.code}｜${opt.name}`"
            />
          </el-select>
          <div class="selection-summary">
            已选 {{ insertSelectedItemCodes.length }} 项
            <span v-if="insertSelectedItemCodes.length > 0">｜模式：仅预览+受控排队（实际写入由 worker 按开关执行）</span>
          </div>
        </div>
      </div>
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
        <el-descriptions-item label="执行状态">
          <el-tag
            size="small"
            :type="(plan.execution_status === 'succeeded') ? 'success'
              : (['failed', 'blocked', 'unknown_commit'].includes(plan.execution_status || '')) ? 'danger'
              : 'info'"
          >{{ plan.execution_status || "未执行" }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <!-- 200 D06/§4.3：分目标结果卡（run + outbox 关联；未启用=尚未执行，不是失败） -->
      <div v-if="plan.target_systems?.length" class="target-cards mb-4">
        <div v-for="target in plan.target_systems" :key="target" class="target-card">
          <div class="target-card-title">{{ SYSTEM_LABELS[target] || target }}</div>
          <template v-if="plan.latest_runs?.[target]">
            <div>run #{{ plan.latest_runs[target].run_id }}｜{{ plan.latest_runs[target].status }}</div>
            <div class="target-card-counts">
              <span>已写 {{ plan.latest_runs[target].succeeded_count ?? 0 }}</span>
              <span>无需变更 {{ plan.latest_runs[target].skipped_count ?? 0 }}</span>
              <span>失败 {{ plan.latest_runs[target].failed_count ?? 0 }}</span>
            </div>
            <div v-if="plan.latest_runs[target].error_masked" class="target-card-error">
              {{ plan.latest_runs[target].error_masked }}
            </div>
            <div v-if="plan.latest_runs[target].finished_at" class="target-card-time">
              最后检查 {{ plan.latest_runs[target].finished_at }}
            </div>
          </template>
          <template v-else>
            <div class="target-card-pending">
              {{ plan.outbox?.[target]?.status === 'dead_letter'
                ? "队列死信：请查看审计并处理后重试"
                : plan.outbox?.[target]?.status
                  ? `排队中（${plan.outbox[target].status}）：尚未执行，实际写入由受控 worker 按开关执行`
                  : "尚未执行：下发开关关闭或未入队" }}
            </div>
          </template>
        </div>
      </div>
      <el-alert
        v-if="actionType === 'sync_infectious'"
        class="mb-4"
        type="info"
        show-icon
        :closable="false"
        title="以下预览来自服务端计划快照；名称为空表示审批后清空 HIS 的 DIAGNOSIS_NAME_CRB。审批仍要求非创建人操作。"
      />
      <!-- 202 D2-1：全部 action_type 渲染逐条动作预览（200 D06/T27 完成定义）。
           公共列：编码/名称/动作/目标/状态；传染病专项加"空值=清空"列，
           普通新增显示国标/医保目标值，stop 显示精确键停用含义。 -->
      <el-table
        v-if="plan.actions?.length"
        :data="plan.actions"
        stripe
        size="small"
        max-height="320"
        class="mb-4"
        data-testid="plan-actions-table"
      >
        <el-table-column prop="item_code" label="院内编码" min-width="140" />
        <el-table-column prop="item_name_cn" label="名称" min-width="160" />
        <el-table-column label="动作" min-width="110">
          <template #default="{ row }">{{ actionTypeLabel(row.action_type) }}</template>
        </el-table-column>
        <el-table-column label="目标" min-width="110">
          <template #default="{ row }">{{ SYSTEM_LABELS[row.target_system] || row.target_system }}</template>
        </el-table-column>
        <el-table-column v-if="actionType === 'sync_infectious'" label="HIS 传染病诊断名称（空值=清空）" min-width="230">
          <template #default="{ row }">
            <el-tag v-if="row.infectious_disease_name === null || row.infectious_disease_name === ''" type="warning">明确清空</el-tag>
            <el-tag v-else-if="row.infectious_disease_name === undefined" type="danger">缺少服务端快照</el-tag>
            <span v-else>{{ row.infectious_disease_name }}</span>
          </template>
        </el-table-column>
        <el-table-column v-else label="国标 / 医保目标值" min-width="170">
          <template #default="{ row }">
            <span v-if="row.action_type === 'stop'" class="action-stop-note">停用：按精确业务键单条停用</span>
            <span v-else>{{ [row.national_clinical_code, row.insurance_code].filter(Boolean).join(" / ") || "—" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'blocked'" type="danger" size="small">blocked</el-tag>
            <el-tag v-else-if="row.status === 'conflict'" type="warning" size="small">conflict</el-tag>
            <span v-else>{{ row.status || "planned" }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-alert
        v-if="plan.status === 'draft' && !planActionsAreComplete(plan)"
        class="mb-4"
        type="error"
        show-icon
        :closable="false"
        title="计划动作预览不完整（编码×目标覆盖缺失或服务端快照缺失），不能审批；请重新生成计划。"
        data-testid="actions-incomplete-alert"
      />
      <el-alert
        v-if="plan.created_by && plan.created_by === currentUsername && plan.status === 'draft'"
        class="mb-4"
        type="warning"
        show-icon
        :closable="false"
        title="当前用户是计划创建人，不能审批。请将计划 ID 提供给另一位审批人加载。"
      />
      <el-button v-if="plan.status === 'draft' && !plan.is_expired" v-perms="'dict.medical.approve'" type="primary" :loading="loading" :disabled="!planActionsAreComplete(plan)" @click="approvePlan">审批计划并排队</el-button>
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

.selection-summary { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); }

.action-stop-note { color: var(--el-text-color-secondary); }

.target-cards { display: flex; gap: 12px; flex-wrap: wrap; }

.target-card { flex: 1 1 220px; padding: 10px 12px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; font-size: 13px; }

.target-card-title { font-weight: 600; margin-bottom: 6px; }

.target-card-counts { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 4px; color: var(--el-text-color-regular); }

.target-card-pending { color: var(--el-text-color-secondary); }

.target-card-error { margin-top: 4px; color: var(--el-color-danger); word-break: break-all; }

.target-card-time { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
