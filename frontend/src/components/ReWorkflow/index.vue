<script setup lang="ts">
export interface WorkflowStep {
  title: string;
  desc?: string;
  status?: "done" | "active" | "pending" | "failed" | "warning";
  meta?: string;
}

withDefaults(
  defineProps<{
    steps: WorkflowStep[];
    compact?: boolean;
  }>(),
  {
    compact: false
  }
);
</script>

<template>
  <section class="re-workflow" :class="{ 'is-compact': compact }">
    <div v-for="(step, index) in steps" :key="`${step.title}-${index}`" class="workflow-step" :class="`is-${step.status || 'pending'}`">
      <div class="step-head">
        <span class="step-dot">{{ index + 1 }}</span>
        <span v-if="index < steps.length - 1" class="step-line" />
      </div>
      <div class="step-copy">
        <strong>{{ step.title }}</strong>
        <small v-if="step.desc">{{ step.desc }}</small>
        <em v-if="step.meta">{{ step.meta }}</em>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.re-workflow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.workflow-step {
  position: relative;
  min-height: 92px;
  padding: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
}

.step-head {
  position: relative;
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.step-dot {
  z-index: 1;
  display: grid;
  width: 24px;
  height: 24px;
  place-items: center;
  font-size: 12px;
  font-weight: 800;
  color: var(--workflow-color);
  background: color-mix(in srgb, var(--workflow-color) 12%, white);
  border: 1px solid color-mix(in srgb, var(--workflow-color) 28%, white);
  border-radius: var(--radius-full);
}

.step-line {
  position: absolute;
  left: 26px;
  width: calc(100% + 10px);
  height: 1px;
  background: var(--border);
}

.step-copy strong,
.step-copy small,
.step-copy em {
  display: block;
}

.step-copy strong {
  font-size: 14px;
  color: var(--text-primary);
}

.step-copy small,
.step-copy em {
  margin-top: 5px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-secondary);
}

.step-copy em {
  font-style: normal;
  color: var(--workflow-color);
}

.is-done {
  --workflow-color: var(--success);
}

.is-active {
  --workflow-color: var(--primary-500);
}

.is-warning {
  --workflow-color: var(--warning);
}

.is-failed {
  --workflow-color: var(--danger);
}

.is-pending {
  --workflow-color: var(--neutral);
}

.is-compact {
  grid-template-columns: 1fr;

  .workflow-step {
    min-height: auto;
  }
}
</style>
