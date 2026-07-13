<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    value?: string | number;
    label?: string;
    direction?: "up" | "down" | "flat";
  }>(),
  {
    value: "-",
    label: "",
    direction: "flat"
  }
);

const mark = computed(() => {
  if (props.direction === "up") return "↑";
  if (props.direction === "down") return "↓";
  return "-";
});
</script>

<template>
  <span class="re-trend-badge" :class="`is-${direction}`">
    <span class="trend-mark">{{ mark }}</span>
    <span>{{ value }}</span>
    <span v-if="label" class="trend-label">{{ label }}</span>
  </span>
</template>

<style scoped lang="scss">
.re-trend-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  min-height: 22px;
  padding: 2px 8px;
  overflow: hidden;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-secondary);
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgb(100 116 139 / 10%);
  border-radius: var(--radius-full);

  &.is-up {
    color: var(--success);
    background: rgb(13 148 136 / 12%);
  }

  &.is-down {
    color: var(--danger);
    background: rgb(225 29 72 / 12%);
  }
}

.trend-label {
  font-weight: 500;
  opacity: 0.78;
}
</style>
