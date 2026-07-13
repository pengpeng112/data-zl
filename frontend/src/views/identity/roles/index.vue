<template>
  <div class="permission-page">
    <RePageHeader title="角色与权限矩阵" subtitle="维护平台角色，并给角色分配菜单、页面和按钮权限。">
      <template #actions>
        <el-button v-if="hasPerms('identity.role.manage')" @click="handleSeed">初始化内置角色</el-button>
        <el-button v-if="hasPerms('identity.role.manage')" type="primary" @click="() => openRoleDialog()">新增角色</el-button>
      </template>
    </RePageHeader>

    <div class="content-grid">
      <section class="panel roles-panel">
        <div class="panel-title">角色</div>
        <el-table v-loading="loading" :data="roles" highlight-current-row @current-change="handleRoleChange">
          <el-table-column prop="role_code" label="角色编码" min-width="150" show-overflow-tooltip />
          <el-table-column prop="role_name_cn" label="角色名称" min-width="130" show-overflow-tooltip />
          <el-table-column prop="role_type" label="类型" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.role_type === 'builtin' ? 'success' : 'info'">{{ row.role_type || 'platform' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button v-if="hasPerms('identity.role.manage')" link type="primary" size="small" @click.stop="openRoleDialog(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="panel matrix-panel">
        <div class="panel-title">
          <span>权限矩阵</span>
          <el-tag v-if="currentRole" size="small">{{ currentRole.role_code }}</el-tag>
        </div>
        <el-empty v-if="!currentRole" description="请选择角色" />
        <template v-else>
          <div class="matrix-toolbar">
            <el-input v-model="resourceKeyword" clearable placeholder="搜索资源编码或名称" />
            <el-button v-if="hasPerms('identity.role.grant')" type="primary" :loading="saving" @click="saveMatrix">保存权限</el-button>
          </div>
          <el-tree
            ref="treeRef"
            class="resource-tree"
            :data="resourceTree"
            node-key="code"
            show-checkbox
            default-expand-all
            :props="treeProps"
            :filter-node-method="filterResource"
          >
            <template #default="{ data }">
              <span class="resource-node">
                <el-tag size="small" effect="plain">{{ data.type }}</el-tag>
                <span>{{ data.name_cn }}</span>
                <code>{{ data.code }}</code>
              </span>
            </template>
          </el-tree>
        </template>
      </section>
    </div>

    <el-dialog v-model="roleDialogVisible" title="角色维护" width="520px" destroy-on-close>
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="100px">
        <el-form-item label="角色编码" prop="role_code">
          <el-input v-model="roleForm.role_code" :disabled="editingBuiltin" placeholder="quality_admin" />
        </el-form-item>
        <el-form-item label="角色名称" prop="role_name_cn">
          <el-input v-model="roleForm.role_name_cn" placeholder="质量管理员" />
        </el-form-item>
        <el-form-item label="角色类型">
          <el-select v-model="roleForm.role_type" class="full-width">
            <el-option label="platform" value="platform" />
            <el-option label="business" value="business" />
            <el-option label="builtin" value="builtin" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button v-if="hasPerms('identity.role.manage')" type="primary" :loading="roleSaving" @click="saveRole">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { hasPerms } from "@/utils/auth";
import {
  getPermissionRoles,
  getPermissionResources,
  getRoleMatrix,
  seedPermissions,
  updateRoleMatrix,
  upsertPermissionRole,
  type PermissionResource,
  type PermissionRole
} from "@/api/permissions";

const roles = ref<PermissionRole[]>([]);
const resources = ref<PermissionResource[]>([]);
const currentRole = ref<PermissionRole | null>(null);
const granted = ref<string[]>([]);
const loading = ref(false);
const saving = ref(false);
const roleSaving = ref(false);
const roleDialogVisible = ref(false);
const roleFormRef = ref<FormInstance>();
const treeRef = ref();
const resourceKeyword = ref("");

const roleForm = reactive({
  role_code: "",
  role_name_cn: "",
  role_type: "platform",
  description: ""
});

const roleRules: FormRules = {
  role_code: [{ required: true, message: "请输入角色编码", trigger: "blur" }],
  role_name_cn: [{ required: true, message: "请输入角色名称", trigger: "blur" }]
};

const treeProps = { label: "name_cn", children: "children" };
const editingBuiltin = computed(() => roleForm.role_type === "builtin" && roles.value.some(r => r.role_code === roleForm.role_code));

const resourceTree = computed(() => {
  const map = new Map<string, any>();
  resources.value.forEach(item => map.set(item.code, { ...item, children: [] }));
  const roots: any[] = [];
  map.forEach(node => {
    if (node.parent_code && map.has(node.parent_code)) {
      map.get(node.parent_code).children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
});

watch(resourceKeyword, value => treeRef.value?.filter(value));

function filterResource(keyword: string, data: PermissionResource) {
  if (!keyword) return true;
  const text = `${data.code} ${data.name_cn}`.toLowerCase();
  return text.includes(keyword.toLowerCase());
}

async function loadAll() {
  loading.value = true;
  try {
    const [roleRes, resourceRes] = await Promise.all([getPermissionRoles(), getPermissionResources()]);
    roles.value = roleRes.data || [];
    resources.value = resourceRes.data || [];
    if (!currentRole.value && roles.value.length) await handleRoleChange(roles.value[0]);
  } catch {
    ElMessage.error("加载角色权限失败");
  } finally {
    loading.value = false;
  }
}

async function handleSeed() {
  try {
    await seedPermissions("console");
    ElMessage.success("内置角色和权限已初始化");
    await loadAll();
  } catch {
    ElMessage.error("初始化失败");
  }
}

async function handleRoleChange(row: PermissionRole | null) {
  currentRole.value = row;
  granted.value = [];
  if (!row) return;
  try {
    const res = await getRoleMatrix(row.role_code);
    granted.value = res.data?.granted || [];
    await nextTick();
    treeRef.value?.setCheckedKeys(granted.value);
  } catch {
    ElMessage.error("加载角色权限矩阵失败");
  }
}

function openRoleDialog(row?: PermissionRole) {
  roleForm.role_code = row?.role_code || "";
  roleForm.role_name_cn = row?.role_name_cn || "";
  roleForm.role_type = row?.role_type || "platform";
  roleForm.description = row?.description || "";
  roleDialogVisible.value = true;
}

async function saveRole() {
  const valid = await roleFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  roleSaving.value = true;
  try {
    await upsertPermissionRole({ ...roleForm, operator: "console" });
    ElMessage.success("角色已保存");
    roleDialogVisible.value = false;
    await loadAll();
  } catch {
    ElMessage.error("保存角色失败");
  } finally {
    roleSaving.value = false;
  }
}

async function saveMatrix() {
  if (!currentRole.value) return;
  saving.value = true;
  try {
    const checked = treeRef.value?.getCheckedKeys(false) || [];
    const halfChecked = treeRef.value?.getHalfCheckedKeys?.() || [];
    const permissions = Array.from(new Set([...checked, ...halfChecked])) as string[];
    await updateRoleMatrix(currentRole.value.role_code, {
      permissions,
      operator: "console",
      reason: "updated from permission matrix"
    });
    ElMessage.success("权限矩阵已保存");
    await handleRoleChange(currentRole.value);
  } catch {
    ElMessage.error("保存权限矩阵失败");
  } finally {
    saving.value = false;
  }
}

onMounted(loadAll);
</script>

<style scoped>
.permission-page {
  min-height: calc(100vh - 84px);
  padding: 4px;
  background: transparent;
}
.panel-title,
.header-actions,
.matrix-toolbar,
.resource-node {
  display: flex;
  align-items: center;
}
.header-actions,
.matrix-toolbar {
  gap: 10px;
}
.content-grid {
  display: grid;
  grid-template-columns: minmax(360px, 42%) 1fr;
  gap: 16px;
}
.panel {
  min-height: 560px;
  padding: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
}
.panel-title {
  justify-content: space-between;
  margin-bottom: 12px;
  font-weight: 600;
}
.resource-tree {
  height: 500px;
  margin-top: 12px;
  overflow: auto;
}
.resource-node {
  gap: 8px;
}
.resource-node code {
  color: var(--text-secondary);
}
@media (max-width: 1100px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

.full-width { width: 100%; }
</style>
