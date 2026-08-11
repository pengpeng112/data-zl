<script setup lang="ts">
/**
 * 兼容薄页：旧“数据连接”入口重定向到统一系统页连接 Tab。
 * 业务逻辑已合并到 views/asset/systems/index.vue。
 */
import { onMounted } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
onMounted(() => {
  router.replace({ path: "/asset/systems", query: { tab: "connections" } });
});
</script>

<template>
  <div class="redirect-hint">正在跳转到「业务系统与数据资源」…</div>
</template>

<style scoped>
.redirect-hint {
  padding: 24px;
  color: var(--text-secondary);
}
</style>
