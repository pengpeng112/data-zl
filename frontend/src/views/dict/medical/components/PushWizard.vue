<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { approveMedicalPushPlan, createMedicalPushPlan, executeMedicalPushPlan } from "@/api/dict";
import { listSystems } from "@/api/asset";
import { extractErrorDetail } from "@/utils/errorMessage";

interface PlanSummary {
  id: number;
  plan_code: string;
  status: string;
  item_count: number;
  target_systems: string[];
  is_expired: boolean;
  created_by: string;
  approved_by: string;
  actions_by_system: Record<string, Record<string, number>>;
}

const step = ref(1);
const loading = ref(false);
const targetSystems = ref<string[]>([]);
// 146 E8（R5）：下发类别可选（此前硬编码 diagnosis，手术计划无法生成）
const categoryCode = ref<"diagnosis" | "operation">("diagnosis");
const plan = ref<PlanSummary | null>(null);
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
  if (targetSystems.value.length === 0) {
    ElMessage.warning("请至少选择一个目标系统");
    return;
  }
  loading.value = true;
  try {
    const res = await createMedicalPushPlan({
      category_code: categoryCode.value,
      target_systems: targetSystems.value
    });
    plan.value = res.data as unknown as PlanSummary;
    step.value = 2;
    ElMessage.success(`计划已生成：${res.data.item_count} 项`);
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, "创建计划失败"));
  } finally {
    loading.value = false;
  }
}

async function approvePlan() {
  if (!plan.value) return;
  // 146 E8（R5）：取消确认时静默返回，不再把取消当失败弹错
  const confirmed = await ElMessageBox.confirm("确认审批此推送计划？审批后不可撤回。", "审批确认").catch(() => null);
  if (!confirmed) return;
  loading.value = true;
  try {
    const res = await approveMedicalPushPlan(plan.value.id, "工作台审批");
    plan.value = res.data as unknown as PlanSummary;
    step.value = 3;
    ElMessage.success("计划已审批");
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, "审批失败"));
  } finally {
    loading.value = false;
  }
}

async function executePlan() {
  if (!plan.value) return;
  const confirmed = await ElMessageBox.confirm(
    "确认执行已审批计划？本轮仅 dry-run，不会实际写入业务库。",
    "执行确认"
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
        <span class="step-label">下发类别</span>
        <el-radio-group v-model="categoryCode">
          <el-radio-button value="diagnosis">诊断</el-radio-button>
          <el-radio-button value="operation">手术</el-radio-button>
        </el-radio-group>
      </div>
      <div class="step-form-row">
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
    </div>

    <div v-if="step === 2 && plan" class="step-content">
      <!-- 146 E8（R5）：下发规则（约束）在预检/审批步骤明示 -->
      <el-alert
        class="mb-4"
        type="warning"
        show-icon
        :closable="false"
        title="下发规则：只增不改已有业务字段；停用仅按“单条停用”执行；医保灰码只写 ybhm=灰码、不写对照表；apply 需服务端开关 + confirmation_token + 二次确认。"
      />
      <el-descriptions :column="2" border size="small" class="mb-4">
        <el-descriptions-item label="计划编号">{{ plan.plan_code }}</el-descriptions-item>
        <el-descriptions-item label="编码数">{{ plan.item_count }}</el-descriptions-item>
        <el-descriptions-item label="目标系统">{{ plan.target_systems.join(", ") }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="plan.status === 'approved' ? 'success' : 'info'" size="small">{{ plan.status }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <el-button v-if="plan.status === 'draft'" v-perms="'dict.medical.approve'" type="primary" :loading="loading" @click="approvePlan">审批计划</el-button>
      <el-button v-else type="success" @click="step = 3">进入执行</el-button>
    </div>

    <div v-if="step === 3 && plan" class="step-content">
      <el-alert title="本轮仅 dry-run，不会实际写入 HIS/JHEMR 业务库。" type="warning" show-icon :closable="false" class="mb-4" />
      <el-button v-perms="'dict.medical.execute'" type="primary" :loading="loading" @click="executePlan">执行已审批计划（dry-run）</el-button>
    </div>

    <div v-if="step === 4" class="step-content">
      <el-result icon="success" title="Dry-run 完成" sub-title="实际执行需生产窗口授权">
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
.result-json { font-size: 12px; background: var(--el-fill-color-light); padding: 12px; border-radius: 4px; text-align: left; max-height: 300px; overflow: auto; }
.step-form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.step-label { color: var(--el-text-color-regular); font-size: 13px; }
</style>
