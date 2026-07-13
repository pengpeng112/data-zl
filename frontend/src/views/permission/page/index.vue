<script setup lang="ts">
import { initRouter } from "@/router/utils";
import { storageLocal } from "@pureadmin/utils";
import { ref } from "vue";
import { useUserStoreHook } from "@/store/modules/user";
import { usePermissionStoreHook } from "@/store/modules/permission";

defineOptions({
  name: "PermissionPage"
});

const username = ref(useUserStoreHook()?.username);
const password = ref("");

const options = [
  {
    value: "admin",
    label: "管理员角色"
  },
  {
    value: "common",
    label: "普通角色"
  }
];

function onChange() {
  useUserStoreHook()
    .loginByUsername({ username: username.value, password: password.value })
    .then(res => {
      if (res.success) {
        storageLocal().removeItem("async-routes");
        usePermissionStoreHook().clearAllCachePage();
        initRouter();
      }
    });
}
</script>

<template>
  <div class="permission-page">
    <RePageHeader
      title="页面权限示例"
      subtitle="模拟后台根据不同角色返回对应路由，观察左侧菜单变化。"
    />
    <el-card shadow="never" class="role-card">
      <template #header>
        <div class="card-header">
          <span>当前角色：{{ username }}</span>
        </div>
      </template>
      <el-select v-model="username" class="w-[160px]!" @change="onChange">
        <el-option
          v-for="item in options"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
    </el-card>
  </div>
</template>


<style scoped>
.permission-page {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}

.role-card {
  width: min(85vw, 960px);
}

.role-card :deep(.el-card__body) {
  display: flex;
  justify-content: flex-start;
}
</style>
