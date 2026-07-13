<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    subtitle?: string;
    align?: "start" | "center";
  }>(),
  {
    subtitle: "",
    align: "start"
  }
);
</script>

<template>
  <header class="re-page-header" :class="`align-${align}`">
    <div class="title-group">
      <div v-if="$slots.icon" class="page-icon"><slot name="icon" /></div>
      <div class="page-copy">
        <h1>{{ title }}</h1>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
    </div>
    <div v-if="$slots.actions" class="page-actions"><slot name="actions" /></div>
  </header>
</template>

<style scoped lang="scss">
.re-page-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
}

.align-center {
  align-items: center;
}

.title-group {
  display: flex;
  min-width: 0;
  gap: 12px;
  align-items: center;
}

.page-icon {
  display: grid;
  flex: 0 0 42px;
  width: 42px;
  height: 42px;
  place-items: center;
  color: var(--primary-500);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-sm);
}

.page-copy {
  min-width: 0;

  h1 {
    margin: 0;
    overflow-wrap: anywhere;
    font-size: 22px;
    font-weight: 800;
    line-height: 1.25;
    color: var(--text-primary);
  }

  p {
    margin: 6px 0 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-secondary);
  }
}

.page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .re-page-header {
    flex-direction: column;
  }

  .page-actions {
    justify-content: flex-start;
    width: 100%;
  }
}
</style>
