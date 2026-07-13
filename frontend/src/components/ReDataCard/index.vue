<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    glow?: boolean;
    compact?: boolean;
  }>(),
  {
    title: "",
    subtitle: "",
    glow: false,
    compact: false
  }
);
</script>

<template>
  <section class="re-data-card" :class="{ 'is-glow': glow, 'is-compact': compact }">
    <header v-if="title || subtitle || $slots.extra" class="card-header">
      <div class="card-title-wrap">
        <h3 v-if="title">{{ title }}</h3>
        <p v-if="subtitle">{{ subtitle }}</p>
      </div>
      <slot name="extra" />
    </header>
    <slot />
  </section>
</template>

<style scoped lang="scss">
.re-data-card {
  position: relative;
  padding: 20px;
  overflow: hidden;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-inset), var(--shadow-lg);
  backdrop-filter: var(--glass-backdrop);

  &.is-glow::before {
    position: absolute;
    inset: 0;
    pointer-events: none;
    content: "";
    background: var(--gradient-glow);
  }

  &.is-compact {
    padding: 16px;
  }
}

.card-header {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title-wrap {
  min-width: 0;

  h3 {
    margin: 0;
    overflow: hidden;
    font-size: 16px;
    font-weight: 700;
    line-height: 1.35;
    color: var(--dark-text-primary);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  p {
    margin: 4px 0 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--dark-text-secondary);
  }
}
</style>
