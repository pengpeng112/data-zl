<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getMedicalCodeSets, getMedicalMappings, getMedicalPushConfig } from "@/api/dict";

const stats = ref({
  diagnosisCodeSets: 0,
  diagnosisMappings: 0,
  operationCodeSets: 0,
  operationMappings: 0,
  pushEnabled: false
});
const loading = ref(false);
const loadError = ref("");

async function loadOverview() {
  loading.value = true;
  loadError.value = "";
  try {
    const [diagnosisSetsRes, diagnosisMappingsRes, operationSetsRes, operationMappingsRes, cfgRes] = await Promise.all([
      getMedicalCodeSets({ category_code: "diagnosis" }),
      getMedicalMappings({ category_code: "diagnosis", page_size: 1 }),
      getMedicalCodeSets({ category_code: "operation" }),
      getMedicalMappings({ category_code: "operation", page_size: 1 }),
      getMedicalPushConfig()
    ]);
    stats.value.diagnosisCodeSets = (diagnosisSetsRes.data || []).length;
    stats.value.diagnosisMappings = diagnosisMappingsRes.data?.total || 0;
    stats.value.operationCodeSets = (operationSetsRes.data || []).length;
    stats.value.operationMappings = operationMappingsRes.data?.total || 0;
    stats.value.pushEnabled = (cfgRes.data as { push_enabled?: boolean } | undefined)?.push_enabled === true;
  } catch (error: any) {
    loadError.value = error?.response?.data?.detail || "字典总览加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadOverview);
</script>

<template>
  <div v-loading="loading" class="overview-panel">
    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon class="mb-4">
      <template #default><el-button link type="primary" @click="loadOverview">重试</el-button></template>
    </el-alert>
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="诊断编码体系" :value="stats.diagnosisCodeSets" />
          <div class="stat-hint">映射关系 {{ stats.diagnosisMappings.toLocaleString() }} 条</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="手术编码体系" :value="stats.operationCodeSets" />
          <div class="stat-hint">映射关系 {{ stats.operationMappings.toLocaleString() }} 条</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">写通道状态</div>
          <el-tag :type="stats.pushEnabled ? 'danger' : 'success'" size="large">
            {{ stats.pushEnabled ? '已开启' : '关闭' }}
          </el-tag>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">数据连接</div>
          <div class="stat-value">平台字典库</div>
          <div class="stat-hint">统一事实来源</div>
        </el-card>
      </el-col>
    </el-row>
    <el-alert
      title="HIS/JHEMR 下发写通道默认关闭。实际执行需审批、生产窗口和专用写凭据。"
      type="info"
      show-icon
      :closable="false"
      class="mt-4"
    />
  </div>
</template>

<style scoped>
.overview-panel { padding: 8px 0; }
.mb-4 { margin-bottom: 16px; }
.stat-label { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 8px; }
.stat-value { font-size: 20px; font-weight: 600; }
.stat-hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 4px; }
</style>
