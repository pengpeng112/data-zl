<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import noAccess from "@/assets/status/403.svg?component";

defineOptions({
  name: "403"
});

const router = useRouter();
const route = useRoute();

// 146 E11：只展示安全化信息——当前账号与所需权限来自路由 meta，绝不暴露 token/策略细节。
const currentAccount = computed(() => {
  const raw = String(route.query.account || "");
  return raw ? raw.slice(0, 60) : "";
});
const requiredAuth = computed(() => {
  const auths = route.meta?.auths;
  if (Array.isArray(auths) && auths.length) {
    return String(auths[0]).slice(0, 60);
  }
  return "";
});

function goBack() {
  if (window.history.length > 1) {
    router.back();
  } else {
    router.push("/");
  }
}
</script>

<template>
  <div
    class="flex flex-col md:flex-row justify-center items-center min-h-full w-full p-4 md:p-0"
  >
    <noAccess />
    <div class="mt-8 md:ml-12 md:mt-0 text-center md:text-left">
      <p
        v-motion
        class="font-medium text-4xl mb-4! dark:text-white"
        :initial="{
          opacity: 0,
          y: 100
        }"
        :enter="{
          opacity: 1,
          y: 0,
          transition: {
            delay: 80
          }
        }"
      >
        403
      </p>
      <p
        v-motion
        class="text-xl mb-4! text-gray-500"
        :initial="{
          opacity: 0,
          y: 100
        }"
        :enter="{
          opacity: 1,
          y: 0,
          transition: {
            delay: 120
          }
        }"
      >
        抱歉，你无权访问该页面
      </p>
      <p v-if="requiredAuth" class="text-sm mb-2! text-gray-400">
        需要权限：{{ requiredAuth }}
      </p>
      <p v-if="currentAccount" class="text-sm mb-4! text-gray-400">
        当前账号：{{ currentAccount }}
      </p>
      <el-button
        v-motion
        type="primary"
        class="block mx-auto md:inline-block md:mx-0"
        :initial="{
          opacity: 0,
          y: 100
        }"
        :enter="{
          opacity: 1,
          y: 0,
          transition: {
            delay: 160
          }
        }"
        @click="goBack"
      >
        返回上一页
      </el-button>
      <el-button
        v-motion
        class="block mx-auto md:inline-block md:mx-0 md:ml-2"
        :initial="{
          opacity: 0,
          y: 100
        }"
        :enter="{
          opacity: 1,
          y: 0,
          transition: {
            delay: 200
          }
        }"
        @click="router.push('/')"
      >
        返回首页
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.main-content {
  margin: 0 !important;
}
</style>
