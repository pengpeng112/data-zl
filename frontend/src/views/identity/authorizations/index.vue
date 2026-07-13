<template>
  <div class="authorization-page">
    <RePageHeader
      title="人员授权与 Token 绑定"
      subtitle="维护平台用户角色、有效权限和 API Token 到人员编码的绑定关系。"
    >
      <template #actions>
        <el-button @click="loadAll">刷新</el-button>
      </template>
    </RePageHeader>

    <div class="layout-grid">
      <section class="panel">
        <div class="panel-title">人员角色授权</div>
        <div class="toolbar">
          <el-input v-model="userIdentifier" clearable placeholder="人员编码或平台账号" @keyup.enter="loadUser" />
          <el-button type="primary" @click="loadUser">查询</el-button>
        </div>

        <el-form label-width="86px" class="grant-form">
          <el-form-item label="授权角色">
            <el-select v-model="selectedRoles" multiple filterable class="full-width" placeholder="选择角色">
              <el-option
                v-for="role in roles"
                :key="role.role_code"
                :label="`${role.role_name_cn} (${role.role_code})`"
                :value="role.role_code"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="授权人">
            <el-input v-model="grantedBy" placeholder="当前操作人" />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="grantReason" type="textarea" :rows="3" placeholder="授权或撤权原因" />
          </el-form-item>
          <el-form-item>
            <el-button
              v-if="hasPerms('identity.role.grant')"
              type="primary"
              :disabled="!userIdentifier"
              :loading="savingRoles"
              @click="saveUserRoles"
            >保存授权</el-button>
          </el-form-item>
        </el-form>

        <el-descriptions v-if="effective" title="有效权限" :column="1" border>
          <el-descriptions-item label="用户">{{ effective.user_identifier }}</el-descriptions-item>
          <el-descriptions-item label="人员姓名">{{ effective.person_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            <el-tag v-for="role in effective.roles" :key="role" size="small" class="tag-gap">{{ role }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="权限">
            <el-tag v-for="perm in effective.permissions" :key="perm" size="small" effect="plain" class="tag-gap">{{ perm }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </section>

      <section class="panel">
        <div class="panel-title">API Token 绑定</div>
        <el-alert
          title="生产建议：管理类 Token 必须绑定 user_identifier；未绑定 Token 仅作为兼容过渡。"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-table v-loading="loadingKeys" :data="apiKeys" stripe class="token-table">
          <el-table-column prop="key_name" label="Key 名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="token_masked" label="Token" width="130" />
          <el-table-column prop="enabled" label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.enabled ? 'success' : 'danger'">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="user_identifier" label="绑定用户" min-width="150">
            <template #default="{ row }">
              <el-input v-model="row.user_identifier" placeholder="人员编码/账号" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button
                v-if="hasPerms('identity.role.grant')"
                link
                type="primary"
                size="small"
                @click="saveKeyBinding(row)"
              >保存</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel audit-panel">
        <div class="panel-title">权限审计</div>
        <el-table v-loading="loadingAudit" :data="auditLogs" stripe>
          <el-table-column prop="created_at" label="时间" min-width="170" show-overflow-tooltip />
          <el-table-column prop="action" label="动作" width="160" show-overflow-tooltip />
          <el-table-column prop="entity_type" label="对象类型" width="100" />
          <el-table-column prop="entity_ref" label="对象" min-width="150" show-overflow-tooltip />
          <el-table-column prop="operator" label="操作人" width="120" show-overflow-tooltip />
          <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
        </el-table>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { hasPerms } from "@/utils/auth";
import {
  bindPermissionApiKey,
  getPermissionApiKeys,
  getPermissionAuditLogs,
  getPermissionRoles,
  getUserPermissions,
  getUserRoles,
  replaceUserRoles,
  type ApiKeyBinding,
  type PermissionAuditLog,
  type PermissionRole
} from "@/api/permissions";

const roles = ref<PermissionRole[]>([]);
const apiKeys = ref<ApiKeyBinding[]>([]);
const auditLogs = ref<PermissionAuditLog[]>([]);
const userIdentifier = ref("");
const selectedRoles = ref<string[]>([]);
const grantedBy = ref("console");
const grantReason = ref("");
const effective = ref<any | null>(null);
const loadingKeys = ref(false);
const loadingAudit = ref(false);
const savingRoles = ref(false);

async function loadAll() {
  try {
    const roleRes = await getPermissionRoles();
    roles.value = roleRes.data || [];
    await loadApiKeys();
    await loadAudit();
  } catch {
    ElMessage.error("加载授权数据失败");
  }
}

async function loadApiKeys() {
  loadingKeys.value = true;
  try {
    const res = await getPermissionApiKeys();
    apiKeys.value = res.data || [];
  } catch {
    ElMessage.error("加载 Token 列表失败");
  } finally {
    loadingKeys.value = false;
  }
}

async function loadAudit() {
  loadingAudit.value = true;
  try {
    const params: Record<string, any> = { limit: 50 };
    if (userIdentifier.value) {
      params.entity_type = "user";
      params.entity_ref = userIdentifier.value;
    }
    const res = await getPermissionAuditLogs(params);
    auditLogs.value = res.data || [];
  } catch {
    ElMessage.error("加载权限审计失败");
  } finally {
    loadingAudit.value = false;
  }
}

async function loadUser() {
  if (!userIdentifier.value) return;
  try {
    const [roleRes, permRes] = await Promise.all([
      getUserRoles({ user_identifier: userIdentifier.value }),
      getUserPermissions(userIdentifier.value)
    ]);
    selectedRoles.value = (roleRes.data || []).map(item => item.role_code);
    effective.value = permRes.data;
    await loadAudit();
  } catch {
    ElMessage.error("查询用户授权失败");
  }
}

async function saveUserRoles() {
  if (!userIdentifier.value) return;
  savingRoles.value = true;
  try {
    await replaceUserRoles(userIdentifier.value, {
      user_identifier: userIdentifier.value,
      role_codes: selectedRoles.value,
      granted_by: grantedBy.value,
      reason: grantReason.value
    });
    ElMessage.success("人员授权已保存");
    await loadUser();
  } catch {
    ElMessage.error("保存人员授权失败");
  } finally {
    savingRoles.value = false;
  }
}

async function saveKeyBinding(row: ApiKeyBinding) {
  try {
    await bindPermissionApiKey(row.id, {
      key_id: row.id,
      user_identifier: row.user_identifier || null,
      operator: grantedBy.value || "console"
    });
    ElMessage.success("Token 绑定已保存");
    await loadApiKeys();
    await loadAudit();
  } catch {
    ElMessage.error("保存 Token 绑定失败");
  }
}

onMounted(loadAll);
</script>

<style scoped>
.authorization-page {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}
.toolbar,
.panel-title {
  display: flex;
  align-items: center;
}
.layout-grid {
  display: grid;
  grid-template-columns: minmax(420px, 46%) 1fr;
  gap: 16px;
}
.panel {
  min-height: 560px;
  padding: 14px;
  border: 1px solid var(--re-border-color);
  background: var(--re-card-bg);
  box-shadow: var(--re-shadow-sm);
  border-radius: 8px;
}
.audit-panel {
  grid-column: 1 / -1;
  min-height: 320px;
}
.panel-title {
  justify-content: space-between;
  margin-bottom: 12px;
  font-weight: 600;
}
.toolbar {
  gap: 10px;
  margin-bottom: 16px;
}
.grant-form {
  margin-bottom: 18px;
}
.tag-gap {
  margin: 0 6px 6px 0;
}
.full-width { width: 100%; }
.token-table { margin-top: 12px; }
@media (max-width: 1100px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }
}
</style>
