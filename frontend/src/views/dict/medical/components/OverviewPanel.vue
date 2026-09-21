<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  getMedicalCodeSets,
  getMedicalMappings,
  getMedicalPushConfig
} from "@/api/dict";
import DiagnosisIcon from "~icons/ri/stethoscope-line";
import OperationIcon from "~icons/ri/surgical-mask-line";
import ChannelIcon from "~icons/ri/upload-cloud-2-line";
import DbIcon from "~icons/ri/database-2-line";
import ShieldIcon from "~icons/ri/shield-check-line";
import RefreshIcon from "~icons/ri/refresh-line";

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
    const [
      diagnosisSetsRes,
      diagnosisMappingsRes,
      operationSetsRes,
      operationMappingsRes,
      cfgRes
    ] = await Promise.all([
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
    stats.value.pushEnabled =
      (cfgRes.data as { push_enabled?: boolean } | undefined)?.push_enabled ===
      true;
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
    <el-alert
      v-if="loadError"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
      class="mb-4"
    >
      <template #default
        ><el-button link type="primary" @click="loadOverview"
          >重试</el-button
        ></template
      >
    </el-alert>

    <header class="overview-header">
      <div class="overview-headline">
        <h2 class="overview-title">字典总览</h2>
        <p class="overview-sub">诊断与手术编码体系运行状态一览</p>
      </div>
      <el-button
        :icon="RefreshIcon"
        :loading="loading"
        class="refresh-btn"
        @click="loadOverview"
        >刷新</el-button
      >
    </header>

    <div class="stat-grid">
      <section class="ov-card tone-primary">
        <div class="ov-accent" />
        <div class="ov-main">
          <div class="ov-icon"><DiagnosisIcon /></div>
          <div class="ov-copy">
            <div class="ov-value">{{ stats.diagnosisCodeSets }}</div>
            <div class="ov-label">诊断编码体系</div>
          </div>
        </div>
        <div class="ov-footer">
          映射关系 {{ stats.diagnosisMappings.toLocaleString() }} 条
        </div>
      </section>

      <section class="ov-card tone-accent">
        <div class="ov-accent" />
        <div class="ov-main">
          <div class="ov-icon"><OperationIcon /></div>
          <div class="ov-copy">
            <div class="ov-value">{{ stats.operationCodeSets }}</div>
            <div class="ov-label">手术编码体系</div>
          </div>
        </div>
        <div class="ov-footer">
          映射关系 {{ stats.operationMappings.toLocaleString() }} 条
        </div>
      </section>

      <section
        class="ov-card"
        :class="stats.pushEnabled ? 'tone-danger' : 'tone-success'"
      >
        <div class="ov-accent" />
        <div class="ov-main">
          <div class="ov-icon"><ChannelIcon /></div>
          <div class="ov-copy">
            <div class="ov-status">
              <span class="status-dot" :class="{ on: stats.pushEnabled }" />
              {{ stats.pushEnabled ? "已开启" : "关闭" }}
            </div>
            <div class="ov-label">写通道状态</div>
          </div>
        </div>
        <div class="ov-footer">
          {{
            stats.pushEnabled
              ? "执行需审批与生产窗口"
              : "默认关闭，按需申请开启"
          }}
        </div>
      </section>

      <section class="ov-card tone-violet">
        <div class="ov-accent" />
        <div class="ov-main">
          <div class="ov-icon"><DbIcon /></div>
          <div class="ov-copy">
            <div class="ov-value ov-value-text">平台字典库</div>
            <div class="ov-label">数据连接</div>
          </div>
        </div>
        <div class="ov-footer">统一事实来源</div>
      </section>
    </div>

    <div class="ov-notice">
      <ShieldIcon class="notice-icon" />
      <span
        >HIS/JHEMR
        下发写通道默认关闭。实际执行需审批、生产窗口和专用写凭据。</span
      >
    </div>
  </div>
</template>

<style scoped lang="scss">
.overview-panel {
  padding: 8px 0;
}

.mb-4 {
  margin-bottom: 16px;
}

.overview-header {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.overview-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.overview-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.refresh-btn {
  flex: 0 0 auto;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.ov-card {
  --ov-color: var(--primary-500);

  position: relative;
  padding: 18px;
  overflow: hidden;
  background:
    radial-gradient(
      120% 140% at 100% 0%,
      color-mix(in srgb, var(--ov-color) 7%, transparent),
      transparent 55%
    ),
    var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);

  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
  }
}

.tone-primary {
  --ov-color: var(--primary-500);
}

.tone-accent {
  --ov-color: var(--accent-500);
}

.tone-success {
  --ov-color: var(--success);
}

.tone-danger {
  --ov-color: var(--danger);
}

.tone-violet {
  --ov-color: var(--violet-500);
}

.ov-accent {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--ov-color);
}

.ov-main {
  display: flex;
  gap: 12px;
  align-items: center;
}

.ov-icon {
  display: grid;
  flex: 0 0 46px;
  place-items: center;
  width: 46px;
  height: 46px;
  font-size: 22px;
  color: var(--ov-color);
  background: color-mix(in srgb, var(--ov-color) 11%, transparent);
  border-radius: var(--radius-sm);
}

.ov-copy {
  min-width: 0;
  text-align: left;
}

.ov-value {
  font-size: 30px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  color: var(--text-primary);
}

.ov-value-text {
  font-size: 22px;
  letter-spacing: 0.01em;
}

.ov-status {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.status-dot {
  width: 9px;
  height: 9px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--success) 18%, transparent);
}

.status-dot.on {
  background: var(--danger);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--danger) 18%, transparent);
  animation: dot-pulse 1.8s var(--motion-ease) infinite;
}

@keyframes dot-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--danger) 18%, transparent);
  }

  50% {
    box-shadow: 0 0 0 7px color-mix(in srgb, var(--danger) 8%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-dot.on {
    animation: none;
  }
}

.ov-label {
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.ov-footer {
  padding-top: 10px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-secondary);
  border-top: 1px dashed var(--border-light);
}

.ov-notice {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
  margin-top: 16px;
  font-size: 13px;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--primary-500) 5%, var(--bg-card));
  border: 1px solid color-mix(in srgb, var(--primary-500) 18%, transparent);
  border-radius: var(--radius-base);
}

.notice-icon {
  flex: 0 0 auto;
  font-size: 16px;
  color: var(--primary-500);
}

@media (width <= 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (width <= 640px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }

  .overview-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
