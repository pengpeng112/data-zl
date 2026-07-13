<script setup lang="ts">
import ReTrendBadge from "@/components/ReTrendBadge/index.vue";

withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    unit?: string;
    helper?: string;
    trend?: string | number;
    trendDirection?: "up" | "down" | "flat";
    tone?: "primary" | "accent" | "info" | "warning" | "danger";
  }>(),
  {
    unit: "",
    helper: "",
    trend: "",
    trendDirection: "flat",
    tone: "primary"
  }
);
</script>

<template>
  <section class="re-kpi-panel" :class="`tone-${tone}`">
    <div class="kpi-icon"><slot name="icon" /></div>
    <div class="kpi-content">
      <div class="kpi-label">{{ label }}</div>
      <div class="kpi-value-row">
        <span class="kpi-value">{{ value }}</span>
        <span v-if="unit" class="kpi-unit">{{ unit }}</span>
      </div>
      <div class="kpi-footer">
        <span v-if="helper" class="kpi-helper">{{ helper }}</span>
        <ReTrendBadge
          v-if="trend !== ''"
          :value="trend"
          :direction="trendDirection"
          label="近期"
        />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.re-kpi-panel {
  position: relative;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 14px;
  min-height: 136px;
  padding: 18px;
  overflow: hidden;
  background: rgb(15 23 42 / 68%);
  border: 1px solid rgb(148 163 184 / 16%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-inset), 0 12px 32px rgb(2 6 23 / 28%);
  transition:
    transform var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);

  &::after {
    position: absolute;
    inset: auto -20% -55% 22%;
    height: 90px;
    pointer-events: none;
    content: "";
    background: radial-gradient(circle, var(--panel-glow), transparent 68%);
  }

  &:hover {
    box-shadow: var(--shadow-inset), 0 16px 38px rgb(2 6 23 / 34%), 0 0 24px var(--panel-glow);
    transform: translateY(-2px);
  }
}

.tone-primary {
  --panel-color: var(--primary-500);
  --panel-glow: rgb(14 165 233 / 24%);
}

.tone-accent {
  --panel-color: var(--accent-400);
  --panel-glow: rgb(45 212 191 / 22%);
}

.tone-info {
  --panel-color: var(--info-500);
  --panel-glow: rgb(99 102 241 / 22%);
}

.tone-warning {
  --panel-color: var(--warning);
  --panel-glow: rgb(245 158 11 / 20%);
}

.tone-danger {
  --panel-color: var(--danger);
  --panel-glow: rgb(225 29 72 / 18%);
}

.kpi-icon {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  color: var(--panel-color);
  background: color-mix(in srgb, var(--panel-color) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--panel-color) 24%, transparent);
  border-radius: var(--radius-sm);
}

.kpi-label,
.kpi-helper,
.kpi-unit {
  color: var(--dark-text-secondary);
}

.kpi-label {
  font-size: 13px;
  font-weight: 600;
}

.kpi-value-row {
  display: flex;
  gap: 6px;
  align-items: baseline;
  margin-top: 10px;
}

.kpi-value {
  font-size: 34px;
  font-weight: 800;
  line-height: 1.05;
  color: var(--dark-text-primary);
}

.kpi-unit,
.kpi-helper {
  font-size: 13px;
}

.kpi-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 12px;
}
</style>
