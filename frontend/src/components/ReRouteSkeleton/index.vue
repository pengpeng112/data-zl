<script setup lang="ts">
/** 213 UI-02：路由级骨架屏——异步路由组件挂载前的占位，消除长驻半透明/白屏。 */
defineOptions({ name: "ReRouteSkeleton" });
</script>

<template>
  <div class="route-skeleton" aria-hidden="true">
    <div class="rs-head">
      <div class="rs-title skeleton-bar" />
      <div class="rs-sub skeleton-bar" />
    </div>
    <div class="rs-body">
      <div class="rs-card skeleton-card" />
      <div class="rs-card skeleton-card" />
      <div class="rs-card skeleton-card" />
    </div>
  </div>
</template>

<style scoped>
.route-skeleton {
  padding: 4px 0;
}

.rs-head {
  margin-bottom: 16px;
}

.rs-title {
  width: 180px;
  height: 22px;
  margin-bottom: 10px;
}

.rs-sub {
  width: 320px;
  height: 14px;
}

.rs-body {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.rs-card {
  height: 96px;
  border-radius: 4px;
}

.skeleton-bar,
.skeleton-card {
  background: linear-gradient(
    90deg,
    var(--el-fill-color-light, #f2f4f7) 25%,
    var(--el-fill-color, #e9edf2) 37%,
    var(--el-fill-color-light, #f2f4f7) 63%
  );
  background-size: 400% 100%;
  animation: rs-shimmer 1.2s ease infinite;
}

@keyframes rs-shimmer {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}
</style>
