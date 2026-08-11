<script setup lang="ts">
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "@/utils/http";
import type { ApiResponse } from "@/api/dict";

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
const plan = ref<PlanSummary | null>(null);
const executeResult = ref<Record<string, unknown> | null>(null);

const systemOptions = [
  { label: "HIS", value: "HIS" },
  { label: "JHEMR（海量）", value: "JHEMR_VASTBASE" }
];

async function createPlan() {
  if (targetSystems.value.length === 0) {
    ElMessage.warning("请至少选择一个目标系统");
    return;
  }
  loading.value = true;
  try {
    const res = await http.request<ApiResponse<PlanSummary>>(
      "post", "/api/v1/dict-medical/push/plans",
      { data: { category_code: "diagnosis", target_systems: targetSystems.value } }
    );
    plan.value = res.data;
    step.value = 2;
    ElMessage.success(`计划已生成：${res.data.item_count} 项`);
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "创建计划失败");
  } finally {
    loading.value = false;
  }
}

async function approvePlan() {
  if (!plan.value) return;
  await ElMessageBox.confirm("确认审批此推送计划？审批后不可撤回。", "审批确认");
  loading.value = true;
  try {
    const res = await http.request<ApiResponse<PlanSummary>>(
      "post", `/api/v1/dict-medical/push/plans/${plan.value.id}/approve`,
      { data: { note: "工作台审批" } }
    );
    plan.value = res.data;
    step.value = 3;
    ElMessage.success("计划已审批");
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "审批失败");
  } finally {
    loading.value = false;
  }
}

async function executePlan() {
  if (!plan.value) return;
  await ElMessageBox.confirm(
    "确认执行已审批计划？本轮仅 dry-run，不会实际写入业务库。",
    "执行确认"
  );
  loading.value = true;
  try {
    const res = await http.request<ApiResponse<Record<string, unknown>>>(
      "post", `/api/v1/dict-medical/push/plans/${plan.value.id}/execute`
    );
    executeResult.value = res.data;
    step.value = 4;
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "执行失败");
  } finally {
    loading.value = false;
  }
}
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
      <el-checkbox-group v-model="targetSystems" class="mb-4">
        <el-checkbox v-for="opt in systemOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
      </el-checkbox-group>
      <el-button v-perms="'dict.medical.plan.create'" type="primary" :loading="loading" @click="createPlan">生成推送计划</el-button>
    </div>

    <div v-if="step === 2 && plan" class="step-content">
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
</style>
