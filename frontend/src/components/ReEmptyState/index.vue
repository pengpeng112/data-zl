<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    variant?: "empty" | "error";
    retryable?: boolean;
  }>(),
  {
    title: undefined,
    description: undefined,
    variant: "empty",
    retryable: false
  }
);

const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <div class="re-empty-state" :class="{ 'is-error': variant === 'error' }">
    <div class="empty-icon">
      <slot name="icon">{{ variant === "error" ? "⚠" : "∅" }}</slot>
    </div>
    <h3>{{ title ?? (variant === "error" ? "加载失败" : "暂无数据") }}</h3>
    <p>{{ description ?? (variant === "error" ? "请求未完成，可重试或调整条件后再试。" : "当前条件下没有可展示内容") }}</p>
    <div v-if="$slots.action || (variant === 'error' && retryable)" class="empty-action">
      <slot name="action">
        <el-button type="primary" size="small" @click="emit('retry')">重试</el-button>
      </slot>
    </div>
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

.is-error {
  .empty-icon {
    color: var(--el-color-danger);
    background: var(--el-color-danger-light-9);
  }

  h3 {
    color: var(--el-color-danger);
  }
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
