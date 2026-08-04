<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getMedicalCodeSets, getMedicalMappings, getMedicalPushConfig } from "@/api/dict";

const stats = ref({
  codeSets: 0,
  mappings: 0,
  pushEnabled: false
});
const loading = ref(false);

onMounted(async () => {
  loading.value = true;
  try {
    const [setsRes, mappingsRes] = await Promise.all([
      getMedicalCodeSets({ category_code: "diagnosis" }),
      getMedicalMappings({ category_code: "diagnosis", page_size: 1 })
    ]);
    stats.value.codeSets = (setsRes.data || []).length;
    stats.value.mappings = mappingsRes.data?.total || 0;
  } catch { /* ignore */ }
  try {
    const cfgRes = await getMedicalPushConfig();
    stats.value.pushEnabled = (cfgRes.data as Record<string, unknown>)?.enabled === true;
  } catch { /* ignore */ }
  loading.value = false;
});
</script>

<template>
  <div v-loading="loading" class="overview-panel">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="诊断编码体系" :value="stats.codeSets" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <el-statistic title="映射关系数" :value="stats.mappings" />
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
          <div class="stat-label">数据源</div>
          <div class="stat-value">PostgreSQL</div>
          <div class="stat-hint">唯一事实源</div>
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
.stat-label { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 8px; }
.stat-value { font-size: 20px; font-weight: 600; }
.stat-hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 4px; }
</style>