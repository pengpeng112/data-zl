<template>
  <div class="permission-requests">
    <RePageHeader title="权限申请审批" subtitle="申请、审批与执行分离；申请人不能审批自己的请求。">
      <template #actions>
        <el-button v-perms="'identity.permission_request.create'" type="primary" @click="openCreate">
          发起申请
        </el-button>
      </template>
    </RePageHeader>

    <el-card class="request-card" shadow="never">
      <template #header>待审批</template>
      <el-alert v-if="pendingError" type="warning" :closable="false" :title="pendingError" show-icon>
        <template #default><el-button size="small" @click="loadPending">重试</el-button></template>
      </el-alert>
      <el-table v-loading="pendingLoading" :data="pending" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="entity_ref" label="目标用户" min-width="140" />
        <el-table-column label="申请内容" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ requestContentLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="requested_by" label="申请人" width="130" />
        <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ row.created_at || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><el-tag size="small">{{ requestStatusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="处理意见" width="180">
          <template #default="{ row }">
            <el-input v-model="reviewNotes[row.id]" maxlength="300" placeholder="可选" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-perms="'identity.permission_request.approve'" link type="primary" :loading="isBusy(row.id, 'approve')" @click="decide(row.id, 'approve')">通过</el-button>
            <el-button v-perms="'identity.permission_request.approve'" link type="danger" :loading="isBusy(row.id, 'reject')" @click="decide(row.id, 'reject')">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!pendingLoading && !pendingError && !pending.length" description="暂无待审批申请" />
      <el-pagination v-model:current-page="pendingPage" :page-size="pageSize" :total="pendingTotal" layout="total, prev, pager, next" class="pager" @current-change="loadPending" />
    </el-card>

    <el-card class="request-card" shadow="never">
      <template #header>我的申请</template>
      <el-alert v-if="mineError" type="error" :closable="false" :title="mineError" show-icon>
        <template #default><el-button size="small" @click="loadMine">重试</el-button></template>
      </el-alert>
      <el-table v-loading="mineLoading" :data="mine" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="entity_ref" label="目标用户" min-width="140" />
        <el-table-column label="申请内容" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ requestContentLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="requested_by" label="申请人" width="130" />
        <el-table-column prop="reason" label="原因" min-width="160" show-overflow-tooltip />
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ row.created_at || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }"><el-tag size="small">{{ requestStatusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'approved'" v-perms="'identity.permission_request.execute'" link type="success" :loading="isBusy(row.id, 'execute')" @click="execute(row.id)">执行</el-button>
            <el-button v-if="row.status === 'executed'" v-perms="'identity.permission_request.execute'" link type="danger" :loading="isBusy(row.id, 'revoke')" @click="revoke(row.id)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!mineLoading && !mineError && !mine.length" description="暂无申请" />
      <el-pagination v-model:current-page="minePage" :page-size="pageSize" :total="mineTotal" layout="total, prev, pager, next" class="pager" @current-change="loadMine" />
    </el-card>

    <el-dialog v-model="createVisible" title="发起权限申请" width="560px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="110px">
        <el-form-item label="申请类型" prop="request_kind">
          <el-radio-group v-model="createForm.request_kind">
            <el-radio value="role">角色</el-radio>
            <el-radio value="data_scope">数据范围</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="目标用户" prop="target_user_identifier">
          <el-input v-model="createForm.target_user_identifier" maxlength="200" />
        </el-form-item>
        <el-form-item v-if="createForm.request_kind === 'role'" label="角色" prop="role_code">
          <el-select v-model="createForm.role_code" filterable class="full-width">
            <el-option v-for="role in roles" :key="role.role_code" :label="`${role.role_name_cn} (${role.role_code})`" :value="role.role_code" />
          </el-select>
        </el-form-item>
        <template v-else>
          <el-form-item label="范围类型" prop="scope_type"><el-input v-model="createForm.scope_type" placeholder="system / source / schema / domain" /></el-form-item>
          <el-form-item label="系统"><el-input v-model="createForm.system_code" /></el-form-item>
          <el-form-item label="连接"><el-input v-model="createForm.source_code" /></el-form-item>
          <el-form-item label="Schema"><el-input v-model="createForm.schema_name" /></el-form-item>
          <el-form-item label="业务域"><el-input v-model="createForm.domain" /></el-form-item>
        </template>
        <el-form-item label="申请原因" prop="reason"><el-input v-model="createForm.reason" type="textarea" :rows="3" maxlength="500" show-word-limit /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button v-perms="'identity.permission_request.create'" type="primary" :loading="creating" @click="submitCreate">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  createPermissionRequest,
  decidePermissionRequest,
  executePermissionRequest,
  getMyPermissionRequests,
  getPendingPermissionRequests,
  getPermissionRoles,
  revokePermissionRequest,
  type PermissionRequestCreate,
  type PermissionRequestItem,
  type PermissionRole
} from "@/api/permissions";
import { requestContentLabel, requestStatusLabel } from "./contracts";

const pageSize = 20;
const mine = ref<PermissionRequestItem[]>([]);
const pending = ref<PermissionRequestItem[]>([]);
const roles = ref<PermissionRole[]>([]);
const minePage = ref(1);
const pendingPage = ref(1);
const mineTotal = ref(0);
const pendingTotal = ref(0);
const mineLoading = ref(false);
const pendingLoading = ref(false);
const mineError = ref("");
const pendingError = ref("");
const busyKeys = ref(new Set<string>());
const reviewNotes = reactive<Record<number, string>>({});
const createVisible = ref(false);
const creating = ref(false);
const createFormRef = ref<FormInstance>();
const createForm = reactive<PermissionRequestCreate>({
  request_kind: "role",
  target_user_identifier: "",
  role_code: "",
  scope_type: "",
  system_code: "",
  source_code: "",
  schema_name: "",
  domain: "",
  reason: ""
});
const createRules: FormRules<PermissionRequestCreate> = {
  target_user_identifier: [{ required: true, message: "请填写目标用户", trigger: "blur" }],
  role_code: [{ validator: (_rule, value, callback) => createForm.request_kind !== "role" || value ? callback() : callback(new Error("请选择角色")), trigger: "change" }],
  scope_type: [{ validator: (_rule, value, callback) => createForm.request_kind !== "data_scope" || value ? callback() : callback(new Error("请填写范围类型")), trigger: "blur" }],
  reason: [{ required: true, min: 2, max: 500, message: "原因需为 2–500 字", trigger: "blur" }]
};

function detailMessage(error: any, fallback: string) {
  return String(error?.response?.data?.detail || fallback).slice(0, 300);
}

async function loadMine() {
  mineLoading.value = true;
  mineError.value = "";
  try {
    const res = await getMyPermissionRequests({ page: minePage.value, page_size: pageSize });
    mine.value = res.data?.items || [];
    mineTotal.value = res.data?.total || 0;
  } catch (error: any) {
    mine.value = [];
    mineTotal.value = 0;
    mineError.value = detailMessage(error, "我的权限申请加载失败");
  } finally {
    mineLoading.value = false;
  }
}

async function loadPending() {
  pendingLoading.value = true;
  pendingError.value = "";
  try {
    const res = await getPendingPermissionRequests({ page: pendingPage.value, page_size: pageSize });
    pending.value = res.data?.items || [];
    pendingTotal.value = res.data?.total || 0;
  } catch (error: any) {
    pending.value = [];
    pendingTotal.value = 0;
    pendingError.value = detailMessage(error, "待审批申请不可用或无审批权限");
  } finally {
    pendingLoading.value = false;
  }
}

function setBusy(id: number, action: string, value: boolean) {
  const next = new Set(busyKeys.value);
  const key = `${id}:${action}`;
  if (value) next.add(key);
  else next.delete(key);
  busyKeys.value = next;
}

function isBusy(id: number, action: string) {
  return busyKeys.value.has(`${id}:${action}`);
}

async function decide(id: number, action: "approve" | "reject") {
  setBusy(id, action, true);
  try {
    await decidePermissionRequest(id, action, reviewNotes[id]?.trim() || undefined);
    ElMessage.success(action === "approve" ? "已通过" : "已驳回");
    await Promise.all([loadMine(), loadPending()]);
  } catch (error: any) {
    ElMessage.error(detailMessage(error, "处理失败"));
  } finally {
    setBusy(id, action, false);
  }
}

async function execute(id: number) {
  setBusy(id, "execute", true);
  try {
    await executePermissionRequest(id);
    ElMessage.success("执行成功");
    await loadMine();
  } catch (error: any) {
    ElMessage.error(detailMessage(error, "执行失败"));
  } finally {
    setBusy(id, "execute", false);
  }
}

async function revoke(id: number) {
  setBusy(id, "revoke", true);
  try {
    await revokePermissionRequest(id);
    ElMessage.success("已撤销");
    await loadMine();
  } catch (error: any) {
    ElMessage.error(detailMessage(error, "撤销失败"));
  } finally {
    setBusy(id, "revoke", false);
  }
}

function openCreate() {
  Object.assign(createForm, {
    request_kind: "role",
    target_user_identifier: "",
    role_code: "",
    scope_type: "",
    system_code: "",
    source_code: "",
    schema_name: "",
    domain: "",
    reason: ""
  });
  createVisible.value = true;
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  creating.value = true;
  try {
    const payload: PermissionRequestCreate = {
      request_kind: createForm.request_kind,
      target_user_identifier: createForm.target_user_identifier.trim(),
      reason: createForm.reason.trim()
    };
    if (createForm.request_kind === "role") payload.role_code = createForm.role_code;
    else Object.assign(payload, {
      scope_type: createForm.scope_type,
      system_code: createForm.system_code || undefined,
      source_code: createForm.source_code || undefined,
      schema_name: createForm.schema_name || undefined,
      domain: createForm.domain || undefined
    });
    await createPermissionRequest(payload);
    ElMessage.success("申请已提交");
    createVisible.value = false;
    minePage.value = 1;
    await loadMine();
  } catch (error: any) {
    ElMessage.error(detailMessage(error, "提交申请失败"));
  } finally {
    creating.value = false;
  }
}

onMounted(async () => {
  try {
    const res = await getPermissionRoles();
    roles.value = res.data || [];
  } catch (error: any) {
    ElMessage.error(detailMessage(error, "角色选项加载失败"));
  }
  await Promise.all([loadMine(), loadPending()]);
});
</script>

<style scoped>
.permission-requests { padding: 4px; }
.request-card { margin-top: 16px; }
.pager { justify-content: flex-end; margin-top: 12px; }
.full-width { width: 100%; }
</style>
