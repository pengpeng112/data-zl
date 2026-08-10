<template>
  <div class="permission-page">
    <RePageHeader title="角色权限" subtitle="按菜单模块维护页面与操作权限，保存后立即用于鉴权。">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button v-if="canManage" :icon="Plus" type="primary" @click="openRoleDialog()">新增角色</el-button>
      </template>
    </RePageHeader>

    <div class="workspace">
      <aside class="role-pane">
        <div class="pane-toolbar">
          <el-input v-model="roleKeyword" :prefix-icon="Search" clearable placeholder="搜索角色" />
        </div>
        <div v-loading="loading" class="role-list">
          <button
            v-for="role in filteredRoles"
            :key="role.role_code"
            type="button"
            class="role-item"
            :class="{ active: currentRole?.role_code === role.role_code }"
            @click="selectRole(role)"
          >
            <span class="role-main">
              <strong>{{ role.role_name_cn }}</strong>
              <small>{{ role.role_code }}</small>
            </span>
            <el-tag size="small" :type="role.role_type === 'builtin' ? 'info' : 'primary'">
              {{ role.role_type === "builtin" ? "内置" : "自定义" }}
            </el-tag>
          </button>
          <el-empty v-if="!filteredRoles.length && !loading" :image-size="64" description="没有匹配角色" />
        </div>
        <div v-if="canManage" class="role-footer">
          <el-button :disabled="!currentRole" :icon="Edit" @click="openRoleDialog(currentRole || undefined)">编辑当前角色</el-button>
          <el-button plain @click="handleSeed">同步权限目录</el-button>
        </div>
      </aside>

      <main class="matrix-pane">
        <el-empty v-if="!currentRole" description="请先选择角色" />
        <template v-else>
          <header class="matrix-header">
            <div>
              <div class="matrix-title">
                <span>{{ currentRole.role_name_cn }}</span>
                <el-tag size="small" effect="plain">{{ selectedCodes.size }} 项权限</el-tag>
                <el-tag v-if="dirty" size="small" type="warning">尚未保存</el-tag>
              </div>
              <p>{{ currentRole.description || "暂无角色说明" }}</p>
            </div>
            <div class="matrix-actions">
              <el-input v-model="resourceKeyword" :prefix-icon="Search" clearable placeholder="搜索菜单或权限" />
              <el-button v-if="canGrant" :disabled="!dirty" :loading="saving" type="primary" :icon="Check" @click="saveMatrix">
                保存更改
              </el-button>
            </div>
          </header>

          <div class="legend">
            <span><i class="dot menu" />菜单</span><span><i class="dot page" />页面</span><span><i class="dot button" />操作</span>
            <span class="legend-note">选择子权限时会自动保留上级菜单访问权限</span>
          </div>

          <div v-loading="matrixLoading" class="module-list">
            <section v-for="module in filteredModules" :key="module.code" class="module-section">
              <div class="module-heading">
                <el-checkbox
                  :model-value="moduleChecked(module)"
                  :indeterminate="moduleIndeterminate(module)"
                  :disabled="!canGrant"
                  @change="value => toggleModule(module, Boolean(value))"
                >
                  <strong>{{ module.name_cn }}</strong>
                  <code>{{ module.code }}</code>
                </el-checkbox>
                <div v-if="canGrant" class="module-commands">
                  <el-button link type="primary" @click="toggleModule(module, true)">全选</el-button>
                  <el-button link @click="toggleModule(module, false)">清空</el-button>
                </div>
              </div>
              <div class="permission-grid">
                <label v-for="item in module.items" :key="item.code" class="permission-cell">
                  <el-checkbox
                    :model-value="selectedCodes.has(item.code)"
                    :disabled="!canGrant"
                    @change="value => togglePermission(item, Boolean(value))"
                  />
                  <span class="permission-copy">
                    <span><i class="dot" :class="item.type" />{{ item.name_cn }}</span>
                    <code>{{ item.code }}</code>
                  </span>
                </label>
              </div>
            </section>
            <el-empty v-if="!filteredModules.length && !matrixLoading" description="没有匹配权限" />
          </div>
        </template>
      </main>
    </div>

    <el-dialog v-model="roleDialogVisible" title="角色维护" width="520px" destroy-on-close>
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="88px">
        <el-form-item label="角色编码" prop="role_code">
          <el-input v-model="roleForm.role_code" :disabled="editingBuiltin" placeholder="例如 quality_reviewer" />
        </el-form-item>
        <el-form-item label="角色名称" prop="role_name_cn"><el-input v-model="roleForm.role_name_cn" /></el-form-item>
        <el-form-item label="角色类型">
          <el-select v-model="roleForm.role_type" class="full-width" :disabled="editingBuiltin">
            <el-option label="平台角色" value="platform" /><el-option label="业务角色" value="business" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色说明"><el-input v-model="roleForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleSaving" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { Check, Edit, Plus, Refresh, Search } from "@element-plus/icons-vue";
import { computed, onMounted, reactive, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { hasPerms } from "@/utils/auth";
import {
  getPermissionRoles, getPermissionResources, getRoleMatrix, seedPermissions,
  updateRoleMatrix, upsertPermissionRole, type PermissionResource, type PermissionRole
} from "@/api/permissions";

type PermissionModule = PermissionResource & { items: PermissionResource[] };
const roles = ref<PermissionRole[]>([]);
const resources = ref<PermissionResource[]>([]);
const currentRole = ref<PermissionRole | null>(null);
const selectedCodes = ref(new Set<string>());
const savedCodes = ref(new Set<string>());
const loading = ref(false);
const matrixLoading = ref(false);
const saving = ref(false);
const roleSaving = ref(false);
const roleDialogVisible = ref(false);
const roleFormRef = ref<FormInstance>();
const roleKeyword = ref("");
const resourceKeyword = ref("");
const roleForm = reactive({ role_code: "", role_name_cn: "", role_type: "platform", description: "" });
const roleRules: FormRules = {
  role_code: [{ required: true, message: "请输入角色编码", trigger: "blur" }, { pattern: /^[a-z][a-z0-9_]{1,63}$/, message: "仅支持小写字母、数字和下划线", trigger: "blur" }],
  role_name_cn: [{ required: true, message: "请输入角色名称", trigger: "blur" }]
};
const canManage = computed(() => hasPerms("identity.role.manage"));
const canGrant = computed(() => hasPerms("identity.role.grant"));
const editingBuiltin = computed(() => roleForm.role_type === "builtin");
const dirty = computed(() => {
  if (selectedCodes.value.size !== savedCodes.value.size) return true;
  return [...selectedCodes.value].some(code => !savedCodes.value.has(code));
});
const filteredRoles = computed(() => {
  const q = roleKeyword.value.trim().toLowerCase();
  return q ? roles.value.filter(r => `${r.role_name_cn} ${r.role_code}`.toLowerCase().includes(q)) : roles.value;
});
const modules = computed<PermissionModule[]>(() => {
  const roots = resources.value.filter(item => !item.parent_code || item.type === "menu");
  return roots.map(root => ({ ...root, items: resources.value.filter(item => item.code !== root.code && (item.parent_code === root.code || item.code.startsWith(`${root.code}.`))) }));
});
const filteredModules = computed(() => {
  const q = resourceKeyword.value.trim().toLowerCase();
  if (!q) return modules.value;
  return modules.value.map(module => ({ ...module, items: module.items.filter(item => `${item.name_cn} ${item.code}`.toLowerCase().includes(q)) }))
    .filter(module => `${module.name_cn} ${module.code}`.toLowerCase().includes(q) || module.items.length);
});

function replaceSelection(codes: string[]) {
  selectedCodes.value = new Set(codes);
  savedCodes.value = new Set(codes);
}
async function loadAll() {
  loading.value = true;
  try {
    const [roleRes, resourceRes] = await Promise.all([getPermissionRoles(), getPermissionResources()]);
    roles.value = roleRes.data || [];
    resources.value = resourceRes.data || [];
    const selected = roles.value.find(r => r.role_code === currentRole.value?.role_code) || roles.value[0];
    if (selected) await selectRole(selected, true);
  } catch { ElMessage.error("加载角色权限失败"); } finally { loading.value = false; }
}
async function selectRole(role: PermissionRole, force = false) {
  if (!force && dirty.value) {
    try { await ElMessageBox.confirm("当前权限尚未保存，切换角色将丢失更改。", "确认切换", { type: "warning" }); }
    catch { return; }
  }
  currentRole.value = role;
  matrixLoading.value = true;
  try {
    const res = await getRoleMatrix(role.role_code);
    if (res.data?.resources?.length) resources.value = res.data.resources;
    replaceSelection(res.data?.granted || []);
  } catch { ElMessage.error("加载权限矩阵失败"); } finally { matrixLoading.value = false; }
}
function moduleCodes(module: PermissionModule) { return [module.code, ...module.items.map(item => item.code)]; }
function moduleChecked(module: PermissionModule) { const codes = moduleCodes(module); return codes.every(code => selectedCodes.value.has(code)); }
function moduleIndeterminate(module: PermissionModule) { const count = moduleCodes(module).filter(code => selectedCodes.value.has(code)).length; return count > 0 && count < moduleCodes(module).length; }
function commitSelection(next: Set<string>) { selectedCodes.value = next; }
function toggleModule(module: PermissionModule, checked: boolean) {
  const next = new Set(selectedCodes.value);
  moduleCodes(module).forEach(code => checked ? next.add(code) : next.delete(code));
  commitSelection(next);
}
function togglePermission(item: PermissionResource, checked: boolean) {
  const next = new Set(selectedCodes.value);
  if (checked) {
    next.add(item.code);
    let parent = item.parent_code;
    while (parent) { next.add(parent); parent = resources.value.find(resource => resource.code === parent)?.parent_code || null; }
  } else {
    next.delete(item.code);
    resources.value.filter(resource => resource.parent_code === item.code || resource.code.startsWith(`${item.code}.`)).forEach(resource => next.delete(resource.code));
  }
  commitSelection(next);
}
async function handleSeed() {
  try { await seedPermissions(); ElMessage.success("权限目录已同步"); await loadAll(); }
  catch { ElMessage.error("同步权限目录失败"); }
}
function openRoleDialog(role?: PermissionRole) {
  Object.assign(roleForm, { role_code: role?.role_code || "", role_name_cn: role?.role_name_cn || "", role_type: role?.role_type || "platform", description: role?.description || "" });
  roleDialogVisible.value = true;
}
async function saveRole() {
  if (!(await roleFormRef.value?.validate().catch(() => false))) return;
  roleSaving.value = true;
  try { await upsertPermissionRole({ ...roleForm }); roleDialogVisible.value = false; ElMessage.success("角色已保存"); await loadAll(); }
  catch { ElMessage.error("保存角色失败"); } finally { roleSaving.value = false; }
}
async function saveMatrix() {
  if (!currentRole.value) return;
  saving.value = true;
  try {
    await updateRoleMatrix(currentRole.value.role_code, { permissions: [...selectedCodes.value].sort(), reason: "角色权限矩阵维护" });
    ElMessage.success("权限已保存并生效");
    await selectRole(currentRole.value, true);
  } catch { ElMessage.error("保存权限失败"); } finally { saving.value = false; }
}
onBeforeRouteLeave(() => !dirty.value || window.confirm("当前权限尚未保存，确定离开吗？"));
onMounted(loadAll);
</script>

<style scoped>
.permission-page { min-height: calc(100vh - 84px); }
.workspace { display: grid; grid-template-columns: 300px minmax(0, 1fr); min-height: 650px; border: 1px solid var(--border-light); background: var(--bg-card); border-radius: 6px; overflow: hidden; }
.role-pane { display: flex; flex-direction: column; border-right: 1px solid var(--border-light); background: var(--el-fill-color-extra-light); }
.pane-toolbar, .role-footer { padding: 14px; background: var(--bg-card); }
.role-footer { display: flex; gap: 8px; border-top: 1px solid var(--border-light); }
.role-list { flex: 1; padding: 8px; overflow: auto; }
.role-item { width: 100%; min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 12px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--text-primary); text-align: left; cursor: pointer; }
.role-item:hover { background: var(--el-fill-color-light); }
.role-item.active { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); }
.role-main { min-width: 0; display: grid; gap: 4px; }
.role-main strong, .role-main small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.role-main small, code { color: var(--text-secondary); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.matrix-pane { min-width: 0; padding: 18px; }
.matrix-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding-bottom: 16px; border-bottom: 1px solid var(--border-light); }
.matrix-title, .matrix-actions, .legend, .module-heading, .module-commands { display: flex; align-items: center; gap: 10px; }
.matrix-title { font-size: 18px; font-weight: 600; }
.matrix-header p { margin: 6px 0 0; color: var(--text-secondary); }
.matrix-actions .el-input { width: 260px; }
.legend { padding: 12px 2px; color: var(--text-secondary); font-size: 13px; }
.legend-note { margin-left: auto; }
.dot { display: inline-block; width: 7px; height: 7px; margin-right: 6px; border-radius: 50%; background: var(--el-color-info); }
.dot.menu { background: var(--el-color-primary); }.dot.page { background: var(--el-color-success); }.dot.button { background: var(--el-color-warning); }
.module-list { display: grid; gap: 12px; }
.module-section { border: 1px solid var(--border-light); border-radius: 6px; overflow: hidden; }
.module-heading { min-height: 48px; justify-content: space-between; padding: 0 14px; background: var(--el-fill-color-light); }
.module-heading code { margin-left: 8px; font-weight: 400; }
.permission-grid { display: grid; grid-template-columns: repeat(3, minmax(190px, 1fr)); }
.permission-cell { min-width: 0; min-height: 62px; display: flex; align-items: flex-start; gap: 7px; padding: 11px 14px; border-top: 1px solid var(--border-light); border-right: 1px solid var(--border-light); cursor: pointer; }
.permission-cell:nth-child(3n) { border-right: 0; }
.permission-copy { min-width: 0; display: grid; gap: 4px; }
.permission-copy code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.full-width { width: 100%; }
@media (max-width: 1100px) { .workspace { grid-template-columns: 240px minmax(0, 1fr); }.permission-grid { grid-template-columns: repeat(2, minmax(180px, 1fr)); }.permission-cell:nth-child(3n) { border-right: 1px solid var(--border-light); }.permission-cell:nth-child(2n) { border-right: 0; } }
@media (max-width: 760px) { .workspace { grid-template-columns: 1fr; }.role-pane { max-height: 340px; border-right: 0; border-bottom: 1px solid var(--border-light); }.matrix-header { flex-direction: column; }.matrix-actions { width: 100%; flex-wrap: wrap; }.matrix-actions .el-input { width: 100%; }.permission-grid { grid-template-columns: 1fr; }.permission-cell { border-right: 0 !important; }.legend-note { display: none; } }
</style>
