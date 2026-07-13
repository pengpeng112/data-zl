<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
  }>(),
  {
    title: "暂无数据",
    description: "当前条件下没有可展示内容"
  }
);
</script>

<template>
  <div class="re-empty-state">
    <div class="empty-icon"><slot name="icon">∅</slot></div>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <div v-if="$slots.action" class="empty-action"><slot name="action" /></div>
  </div>
</template>

<style scoped lang="scss">
.re-empty-state {
  display: grid;
  min-height: 180px;
  padding: 28px;
  place-items: center;
  text-align: center;
}

.empty-icon {
  display: grid;
  width: 48px;
  height: 48px;
  margin-bottom: 12px;
  place-items: center;
  font-size: 20px;
  font-weight: 700;
  color: var(--primary-500);
  background: var(--primary-50);
  border-radius: var(--radius-full);
}

h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}

p {
  max-width: 360px;
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.empty-action {
  margin-top: 16px;
}
</style>
