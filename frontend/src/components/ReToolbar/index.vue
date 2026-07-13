<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    dense?: boolean;
  }>(),
  {
    title: "",
    dense: false
  }
);
</script>

<template>
  <div class="re-toolbar" :class="{ 'is-dense': dense }">
    <div class="toolbar-left">
      <strong v-if="title">{{ title }}</strong>
      <slot />
    </div>
    <div v-if="$slots.actions" class="toolbar-actions"><slot name="actions" /></div>
  </div>
</template>

<style scoped lang="scss">
.re-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
}

.is-dense {
  padding: 8px 10px;
}

.toolbar-left,
.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.toolbar-left {
  min-width: 0;

  strong {
    font-size: 14px;
    color: var(--text-primary);
  }
}

.toolbar-actions {
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .re-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-actions {
    justify-content: flex-start;
  }
}
</style>
