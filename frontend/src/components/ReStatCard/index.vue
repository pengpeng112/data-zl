<script setup lang="ts">
import ReTrendBadge from "@/components/ReTrendBadge/index.vue";

withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    helper?: string;
    trend?: string | number;
    trendDirection?: "up" | "down" | "flat";
    tone?: "primary" | "accent" | "info" | "warning" | "danger";
  }>(),
  {
    helper: "",
    trend: "",
    trendDirection: "flat",
    tone: "primary"
  }
);
</script>

<template>
  <section class="re-stat-card" :class="`tone-${tone}`">
    <div class="stat-accent" />
    <div class="stat-main">
      <div class="stat-icon"><slot name="icon" /></div>
      <div class="stat-copy">
        <div class="stat-value">{{ value }}</div>
        <div class="stat-label">{{ label }}</div>
      </div>
    </div>
    <div v-if="helper || trend !== ''" class="stat-footer">
      <span v-if="helper">{{ helper }}</span>
      <ReTrendBadge
        v-if="trend !== ''"
        :value="trend"
        :direction="trendDirection"
      />
    </div>
  </section>
</template>

<style scoped lang="scss">
.re-stat-card {
  position: relative;
  padding: 18px;
  overflow: hidden;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--motion-base) var(--motion-ease),
    box-shadow var(--motion-base) var(--motion-ease);

  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
  }
}

.tone-primary {
  --stat-color: var(--primary-500);
}

.tone-accent {
  --stat-color: var(--accent-500);
}

.tone-info {
  --stat-color: var(--info-500);
}

.tone-warning {
  --stat-color: var(--warning);
}

.tone-danger {
  --stat-color: var(--danger);
}

.stat-accent {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--stat-color);
}

.stat-main,
.stat-footer {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
}

.stat-icon {
  display: grid;
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  place-items: center;
  color: var(--stat-color);
  background: color-mix(in srgb, var(--stat-color) 11%, transparent);
  border-radius: var(--radius-sm);
}

.stat-copy {
  min-width: 0;
  text-align: right;
}

.stat-value {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  color: var(--text-primary);
}

.stat-label,
.stat-footer {
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-label {
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stat-footer {
  margin-top: 14px;
}
</style>
