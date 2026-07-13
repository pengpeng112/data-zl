<template>
  <div class="local-accounts">
    <RePageHeader
      title="本地账号管理"
      subtitle="维护平台登录账号：启停、解锁、重置密码。密码不展示、不导出。"
    />

    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>账号列表</span>
          <div class="header-actions">
            <el-input
              v-model="keyword"
              clearable
              placeholder="搜索用户名/标识"
              class="search-input"
              @keyup.enter="loadData"
            />
            <el-button @click="loadData">刷新</el-button>
            <el-button type="primary" @click="openCreate">新建账号</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="items" stripe>
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="user_identifier" label="人员标识" min-width="140" />
        <el-table-column prop="enabled" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? "启用" : "停用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="must_change_password" label="强制改密" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.must_change_password" type="warning" size="small">是</el-tag>
            <span v-else>否</span>
          </template>
        </el-table-column>
        <el-table-column prop="locked_until" label="锁定至" min-width="160">
          <template #default="{ row }">
            <span v-if="row.locked_until">{{ row.locked_until }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_at" label="最近登录" min-width="160" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="toggleEnabled(row)">
              {{ row.enabled ? "停用" : "启用" }}
            </el-button>
            <el-button link type="primary" @click="unlock(row)">解锁</el-button>
            <el-button link type="warning" @click="forceChange(row)">强制改密</el-button>
            <el-button link type="danger" @click="resetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="events-card">
      <template #header>最近登录审计</template>
      <el-table v-loading="eventsLoading" :data="events" size="small" stripe>
        <el-table-column prop="created_at" label="时间" min-width="170" />
        <el-table-column prop="username" label="账号" width="140" />
        <el-table-column prop="result" label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.result === 'success' ? 'success' : 'danger'" size="small">
              {{ row.result }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reason_code" label="原因码" width="140" />
        <el-table-column prop="client_ip_masked" label="IP(脱敏)" width="140" />
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建本地账号" width="480px" destroy-on-close>
      <el-form :model="createForm" label-width="110px">
        <el-form-item label="用户名" required>
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="人员标识">
          <el-input v-model="createForm.user_identifier" placeholder="绑定 person_code，可空" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            placeholder="留空则自动生成一次性密码"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role_codes" multiple class="full-width">
            <el-option label="platform_admin" value="platform_admin" />
            <el-option label="identity_admin" value="identity_admin" />
            <el-option label="asset_viewer" value="asset_viewer" />
            <el-option label="quality_admin" value="quality_admin" />
            <el-option label="ops_admin" value="ops_admin" />
            <el-option label="approver" value="approver" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="doCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="pwdVisible" title="一次性密码" width="420px">
      <p class="pwd-warning">请通过安全渠道交付，关闭后无法再次查看。</p>
      <el-input :model-value="oneTimePassword" readonly>
        <template #append>
          <el-button @click="copyPwd">复制</el-button>
        </template>
      </el-input>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  createLocalUser,
  listLocalUsers,
  listLoginEvents,
  patchLocalUser,
  type LocalAuthUser,
  type LoginEvent
} from "@/api/auth-admin";

const items = ref<LocalAuthUser[]>([]);
const events = ref<LoginEvent[]>([]);
const loading = ref(false);
const eventsLoading = ref(false);
const keyword = ref("");

const createVisible = ref(false);
const createLoading = ref(false);
const createForm = reactive({
  username: "",
  user_identifier: "",
  password: "",
  role_codes: [] as string[]
});

const pwdVisible = ref(false);
const oneTimePassword = ref("");

async function loadData() {
  loading.value = true;
  try {
    const res = await listLocalUsers({ q: keyword.value || undefined, page_size: 100 });
    items.value = res.data?.items ?? [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.message || "加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadEvents() {
  eventsLoading.value = true;
  try {
    const res = await listLoginEvents({ page_size: 30 });
    events.value = res.data?.items ?? [];
  } catch {
    events.value = [];
  } finally {
    eventsLoading.value = false;
  }
}

function openCreate() {
  createForm.username = "";
  createForm.user_identifier = "";
  createForm.password = "";
  createForm.role_codes = [];
  createVisible.value = true;
}

async function doCreate() {
  if (!createForm.username.trim()) {
    ElMessage.warning("请输入用户名");
    return;
  }
  createLoading.value = true;
  try {
    const res = await createLocalUser({
      username: createForm.username.trim(),
      user_identifier: createForm.user_identifier || undefined,
      password: createForm.password || undefined,
      must_change_password: true,
      role_codes: createForm.role_codes
    });
    createVisible.value = false;
    if (res.data?.initial_password) {
      oneTimePassword.value = res.data.initial_password;
      pwdVisible.value = true;
    } else {
      ElMessage.success("账号已创建");
    }
    await loadData();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.message || "创建失败");
  } finally {
    createLoading.value = false;
  }
}

async function toggleEnabled(row: LocalAuthUser) {
  await patchLocalUser(row.id, { enabled: !row.enabled });
  ElMessage.success(row.enabled ? "已停用" : "已启用");
  await loadData();
}

async function unlock(row: LocalAuthUser) {
  await patchLocalUser(row.id, { unlock: true });
  ElMessage.success("已解锁");
  await loadData();
}

async function forceChange(row: LocalAuthUser) {
  await patchLocalUser(row.id, { must_change_password: true });
  ElMessage.success("已标记下次强制改密");
  await loadData();
}

async function resetPassword(row: LocalAuthUser) {
  const { value } = await ElMessageBox.prompt(
    "请输入新的一次性密码（至少 12 位，含复杂度）。不会写入日志。",
    `重置密码：${row.username}`,
    {
      inputType: "password",
      confirmButtonText: "重置",
      cancelButtonText: "取消"
    }
  );
  if (!value || value.length < 12) {
    ElMessage.error("密码至少 12 位");
    return;
  }
  await patchLocalUser(row.id, { reset_password: value, must_change_password: true });
  oneTimePassword.value = value;
  pwdVisible.value = true;
  await loadData();
}

async function copyPwd() {
  try {
    await navigator.clipboard.writeText(oneTimePassword.value);
    ElMessage.success("已复制");
  } catch {
    ElMessage.warning("复制失败，请手动选择");
  }
}

onMounted(() => {
  loadData();
  loadEvents();
});
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.search-input {
  width: 220px;
}
.events-card {
  margin-top: 16px;
}
.full-width {
  width: 100%;
}
.pwd-warning {
  color: var(--el-color-warning);
  margin-bottom: 12px;
}
</style>
