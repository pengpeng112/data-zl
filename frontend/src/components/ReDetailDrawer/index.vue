<script setup lang="ts">
defineProps<{
  modelValue: boolean;
  title: string;
  subtitle?: string;
  size?: string;
  status?: string;
  statusType?: "primary" | "success" | "warning" | "danger" | "info";
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: boolean): void;
}>();
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :size="size || '72vw'"
    class="re-detail-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div class="drawer-header">
        <div class="drawer-title-group">
          <h2>{{ title }}</h2>
          <p v-if="subtitle">{{ subtitle }}</p>
        </div>
        <el-tag v-if="status" :type="statusType || 'info'" effect="light">
          {{ status }}
        </el-tag>
      </div>
    </template>

    <div class="drawer-body">
      <section v-if="$slots.summary" class="drawer-section is-summary">
        <slot name="summary" />
      </section>
      <div class="drawer-layout">
        <main class="drawer-main">
          <slot />
        </main>
        <aside v-if="$slots.side" class="drawer-side">
          <slot name="side" />
        </aside>
      </div>
    </div>

    <template v-if="$slots.footer" #footer>
      <div class="drawer-footer">
        <slot name="footer" />
      </div>
    </template>
  </el-drawer>
</template>

<style scoped lang="scss">
.drawer-header {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  justify-content: space-between;
  min-width: 0;
}

.drawer-title-group {
  min-width: 0;

  h2 {
    margin: 0;
    overflow-wrap: anywhere;
    font-size: 18px;
    font-weight: 800;
    line-height: 1.3;
    color: var(--text-primary);
  }

  p {
    margin: 6px 0 0;
    font-size: 13px;
    line-height: 1.55;
    color: var(--text-secondary);
  }
}

.drawer-body {
  display: grid;
  gap: 14px;
}

.drawer-section {
  padding: 14px;
  background: var(--bg-page);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
}

.drawer-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 14px;
  align-items: start;
}

.drawer-main,
.drawer-side {
  min-width: 0;
}

.drawer-side {
  display: grid;
  gap: 12px;
}

.drawer-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

:deep(.el-descriptions__label) {
  width: 120px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .drawer-layout {
    grid-template-columns: 1fr;
  }
}
</style>
