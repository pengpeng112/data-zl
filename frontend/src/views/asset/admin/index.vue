<template>
  <div class="admin-page">
    <RePageHeader
      title="治理基础配置"
      subtitle="责任归属、业务术语、安全接入（API Token）与元数据快照入口。Token 仅在创建时显示一次明文。"
    />

    <el-alert
      class="mb20"
      type="info"
      :closable="false"
      title="本页用于平台治理底座，不承担业务统计指标或日常查询版本管理；相关能力请前往查询与指标中心。"
    />

    <el-card class="mb20">
      <template #header>
        <span>安全接入 · API Token</span>
        <el-button size="small" class="ml8" @click="createKey"
          >创建新 Token</el-button
        >
      </template>
      <el-table :data="keys" stripe size="small">
        <el-table-column prop="key_name" label="名称" width="180" />
        <el-table-column prop="user_identifier" label="绑定用户" width="140" />
        <el-table-column label="凭证" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.has_legacy_token || row.token ? 'success' : 'info'">
              {{ row.token ? "刚创建（请立即保存）" : row.has_legacy_token ? "已签发" : "无明文" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{
              row.enabled ? "启用" : "禁用"
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_used_at" label="最后使用" width="170" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.enabled ? 'warning' : 'success'"
              @click="toggleKey(row)"
            >
              {{ row.enabled ? "禁用" : "启用" }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <span>表 Owner</span>
        <el-button
          type="primary"
          size="small"
          class="ml12"
          @click="openOwnerDialog()"
          >新增</el-button
        >
      </template>
      <el-form :inline="true">
        <el-form-item>
          <el-input
            v-model="ownerKeyword"
            placeholder="搜索表名"
            clearable
            class="search-input"
            @clear="loadOwners"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadOwners">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table v-loading="ownersLoading" :data="owners" stripe size="small">
        <el-table-column prop="full_table_name" label="表" min-width="200" />
        <el-table-column prop="owner_name" label="负责人" width="120" />
        <el-table-column prop="department" label="部门" width="150" />
        <el-table-column prop="contact" label="联系方式" width="150" />
        <el-table-column
          prop="note"
          label="备注"
          min-width="150"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openOwnerDialog(row)"
              >编辑</el-button
            >
            <el-button size="small" type="danger" @click="delOwner(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="ownerPage"
        class="mt15"
        :page-size="ownerPageSize"
        :total="ownerTotal"
        layout="total, prev, pager, next"
        @current-change="loadOwners"
      />
    </el-card>

    <el-card class="mt20">
      <template #header>
        <span>业务术语</span>
        <el-button
          type="primary"
          size="small"
          class="ml12"
          @click="openTermDialog()"
          >新增术语</el-button
        >
      </template>
      <el-form :inline="true">
        <el-form-item>
          <el-input
            v-model="termKeyword"
            placeholder="搜索术语或映射"
            clearable
            class="search-input"
            @clear="loadTerms"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTerms">查询</el-button>
        </el-form-item>
      </el-form>
      <el-table v-loading="termsLoading" :data="terms" stripe size="small">
        <el-table-column prop="term" label="业务术语" width="120" />
        <el-table-column prop="mapping_target" label="映射目标" min-width="200">
          <template #default="{ row }">
            <span class="mono">{{ row.mapping_target }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="description"
          label="说明"
          min-width="150"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openTermDialog(row)"
              >编辑</el-button
            >
            <el-button size="small" type="danger" @click="delTerm(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="termPage"
        class="mt15"
        :page-size="termPageSize"
        :total="termTotal"
        layout="total, prev, pager, next"
        @current-change="loadTerms"
      />
    </el-card>

    <el-dialog v-model="termDialogVisible" title="业务术语" width="450px">
      <el-form>
        <el-form-item label="术语">
          <el-input v-model="termForm.term" placeholder="如 住院号" />
        </el-form-item>
        <el-form-item label="映射目标">
          <el-input
            v-model="termForm.mapping_target"
            placeholder="如 HIS.PAT_MASTER_INDEX.INP_NO"
          />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="termForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="termDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTerm">保存</el-button>
      </template>
    </el-dialog>

    <el-card class="mt20">
      <template #header>
        <span>元数据快照</span>
        <el-button
          type="primary"
          size="small"
          class="ml12"
          @click="createSnapshot"
          >新建快照</el-button
        >
      </template>
      <el-table v-loading="snapLoading" :data="snapshots" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="label" label="标签" width="200" />
        <el-table-column prop="table_count" label="表数" width="80" />
        <el-table-column prop="column_count" label="字段数" width="80" />
        <el-table-column prop="relation_count" label="关系数" width="80" />
        <el-table-column prop="snapshot_time" label="时间" width="170" />
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button size="small" @click="selectCompare(row)"
              >对比选中</el-button
            >
          </template>
        </el-table-column>
      </el-table>
      <div v-if="compareIds.length === 2" class="mt15">
        <el-button type="warning" size="small" @click="runCompare">
          对比快照 #{{ compareIds[0] }} vs #{{ compareIds[1] }}
        </el-button>
        <el-button
          size="small"
          class="ml8"
          @click="
            compareIds = [];
            compareResult = null;
          "
          >清除</el-button
        >
      </div>
      <div class="mt15 action-row">
        <el-button type="info" size="small" @click="goToChanges">
          打开元数据变更事件
        </el-button>
        <el-button type="info" size="small" @click="goToMetadataChanges">
          打开快照管理页
        </el-button>
      </div>
      <div v-if="compareResult" class="mt15 compare-result">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="新增表">{{
            compareResult.tables_added
          }}</el-descriptions-item>
          <el-descriptions-item label="移除表">{{
            compareResult.tables_removed
          }}</el-descriptions-item>
          <el-descriptions-item label="关系变化">{{
            compareResult.relation_delta
          }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="compareResult.added?.length" class="mt10">
          <strong>新增：</strong>
          <el-tag
            v-for="t in compareResult.added"
            :key="t"
            class="mr5 mb5"
            type="success"
            size="small"
            >{{ t }}</el-tag
          >
        </div>
        <div v-if="compareResult.removed?.length" class="mt10">
          <strong>移除：</strong>
          <el-tag
            v-for="t in compareResult.removed"
            :key="t"
            class="mr5 mb5"
            type="danger"
            size="small"
            >{{ t }}</el-tag
          >
        </div>
      </div>
    </el-card>

    <el-dialog v-model="ownerDialogVisible" title="表 Owner" width="450px">
      <el-form>
        <el-form-item label="表名">
          <el-input
            v-model="ownerForm.full_table_name"
            placeholder="如 HIS.PAT_VISIT"
          />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="ownerForm.owner_name" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="ownerForm.department" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="ownerForm.contact" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="ownerForm.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ownerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveOwner">保存</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="keyDialog.visible" title="创建 API Token" width="460px" destroy-on-close>
      <el-form ref="keyFormRef" :model="keyDialog.form" :rules="keyDialog.rules" label-width="110px">
        <el-form-item label="Token 名称" prop="key_name">
          <el-input v-model="keyDialog.form.key_name" maxlength="100" />
        </el-form-item>
        <el-form-item label="绑定用户标识" prop="user_identifier">
          <el-input v-model="keyDialog.form.user_identifier" maxlength="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="keyDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="keyDialog.submitting" @click="submitCreateKey">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tokenOnce.visible" title="Token 创建成功（仅显示一次）" width="560px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" title="请立即复制保存；关闭后平台不再显示明文，也不会写入日志。" show-icon class="mb8" />
      <pre class="token-once">{{ tokenOnce.value }}</pre>
      <template #footer>
        <el-button @click="copyTokenOnce">复制</el-button>
        <el-button type="primary" @click="tokenOnce.visible = false">我已保存，关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { ref, onMounted, reactive } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  listAdminKeys,
  createAdminKey,
  toggleAdminKey,
  listAdminOwners,
  upsertAdminOwner,
  deleteAdminOwner,
  listAdminTerms,
  upsertAdminTerm,
  deleteAdminTerm,
  listAdminSnapshots,
  createAdminSnapshot,
  compareAdminSnapshots
} from "@/api/admin";
import { extractErrorDetail } from "@/utils/errorMessage";

const router = useRouter();

interface KeyItem {
  id: number;
  key_name: string;
  token: string;
  enabled: boolean;
  created_at: string | null;
  last_used_at: string | null;
}

interface OwnerItem {
  id: number;
  full_table_name: string;
  owner_name: string | null;
  department: string | null;
  contact: string | null;
  note: string | null;
}

const keys = ref<KeyItem[]>([]);
const owners = ref<OwnerItem[]>([]);
const ownersLoading = ref(false);
const ownerTotal = ref(0);
const ownerPage = ref<number>(1);
const ownerPageSize = ref<number>(30);
const ownerKeyword = ref("");

const ownerDialogVisible = ref(false);
const ownerForm = ref({
  full_table_name: "",
  owner_name: "",
  department: "",
  contact: "",
  note: ""
});
const editId = ref<number | null>(null);

function loadKeys() {
  listAdminKeys()
    .then(({ data }) => {
      keys.value = data as any;
    })
    .catch(error => {
      // E12：无 catch 链补齐。
      ElMessage.error(extractErrorDetail(error, "API Key 列表加载失败"));
    });
}

const keyDialog = reactive({
  visible: false,
  submitting: false,
  form: { key_name: "", user_identifier: "" },
  rules: {
    key_name: [{ required: true, message: "请填写 Token 名称", trigger: "blur" }],
    user_identifier: [{ required: true, message: "请填写绑定用户标识", trigger: "blur" }]
  }
});
const keyFormRef = ref();
const tokenOnce = reactive({ visible: false, value: "" });

function createKey() {
  keyDialog.form = { key_name: "", user_identifier: "" };
  keyDialog.visible = true;
}

async function submitCreateKey() {
  const valid = await keyFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  keyDialog.submitting = true;
  try {
    const d = await createAdminKey({
      key_name: keyDialog.form.key_name.trim(),
      user_identifier: keyDialog.form.user_identifier.trim()
    });
    keyDialog.visible = false;
    tokenOnce.value = String(d.data?.token || "");
    tokenOnce.visible = true;
    loadKeys();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "创建失败"));
  } finally {
    keyDialog.submitting = false;
  }
}

async function copyTokenOnce() {
  try {
    await navigator.clipboard.writeText(tokenOnce.value);
    ElMessage.success("已复制");
  } catch {
    ElMessage.warning("剪贴板不可用，请手动选择复制");
  }
}

function toggleKey(row: KeyItem) {
  toggleAdminKey(row.id, !row.enabled)
    .then(() => loadKeys())
    .catch(error => {
      // E12：无 catch 链补齐。
      ElMessage.error(extractErrorDetail(error, "API Key 启停失败"));
    });
}

function loadOwners() {
  ownersLoading.value = true;
  listAdminOwners({
    page: ownerPage.value,
    page_size: ownerPageSize.value,
    keyword: ownerKeyword.value || undefined
  })
    .then(({ data }) => {
      owners.value = data.items as any;
      ownerTotal.value = data.total;
    })
    .catch(error => {
      owners.value = [];
      ElMessage.error(extractErrorDetail(error, "表 Owner 列表加载失败"));
    })
    .finally(() => {
      ownersLoading.value = false;
    });
}

function openOwnerDialog(row?: OwnerItem) {
  editId.value = row ? row.id : null;
  ownerForm.value = row
    ? {
        full_table_name: row.full_table_name,
        owner_name: row.owner_name || "",
        department: row.department || "",
        contact: row.contact || "",
        note: row.note || ""
      }
    : {
        full_table_name: "",
        owner_name: "",
        department: "",
        contact: "",
        note: ""
      };
  ownerDialogVisible.value = true;
}

function saveOwner() {
  upsertAdminOwner(ownerForm.value)
    .then(() => {
      ElMessage.success("已保存");
      ownerDialogVisible.value = false;
      loadOwners();
    })
    .catch(error => {
      // E12：无 catch 链补齐。
      ElMessage.error(extractErrorDetail(error, "表 Owner 保存失败"));
    });
}

function delOwner(row: OwnerItem) {
  // E12：原生 confirm 改 ElMessageBox（统一交互）。
  ElMessageBox.confirm(`确定删除表 ${row.full_table_name} 的 Owner 登记？`, "删除确认", {
    type: "warning"
  })
    .then(() => deleteAdminOwner(row.id))
    .then(() => {
      ElMessage.success("已删除");
      loadOwners();
    })
    .catch(error => {
      if (error === "cancel" || (error as Error)?.message === "cancel") return;
      ElMessage.error(extractErrorDetail(error, "删除失败"));
    });
}

interface TermItem {
  id: number;
  term: string;
  mapping_target: string;
  mapping_type: string | null;
  description: string | null;
}

const terms = ref<TermItem[]>([]);
const termsLoading = ref(false);
const termTotal = ref(0);
const termPage = ref<number>(1);
const termPageSize = ref<number>(30);
const termKeyword = ref("");
const termDialogVisible = ref(false);
const termForm = ref({ term: "", mapping_target: "", description: "" });

function loadTerms() {
  termsLoading.value = true;
  listAdminTerms({
    page: termPage.value,
    page_size: termPageSize.value,
    keyword: termKeyword.value || undefined
  })
    .then(({ data }) => {
      terms.value = data.items as any;
      termTotal.value = data.total;
    })
    .catch(error => {
      terms.value = [];
      ElMessage.error(extractErrorDetail(error, "业务术语列表加载失败"));
    })
    .finally(() => {
      termsLoading.value = false;
    });
}

function openTermDialog(row?: TermItem) {
  termForm.value = row
    ? {
        term: row.term,
        mapping_target: row.mapping_target,
        description: row.description || ""
      }
    : { term: "", mapping_target: "", description: "" };
  termDialogVisible.value = true;
}

function saveTerm() {
  upsertAdminTerm(termForm.value)
    .then(() => {
      ElMessage.success("已保存");
      termDialogVisible.value = false;
      loadTerms();
    })
    .catch(error => {
      // E12：无 catch 链补齐。
      ElMessage.error(extractErrorDetail(error, "业务术语保存失败"));
    });
}

function delTerm(row: TermItem) {
  // E12：原生 confirm 改 ElMessageBox。
  ElMessageBox.confirm(`确定删除术语「${row.term}」？`, "删除确认", {
    type: "warning"
  })
    .then(() => deleteAdminTerm(row.id))
    .then(() => {
      ElMessage.success("已删除");
      loadTerms();
    })
    .catch(error => {
      if (error === "cancel" || (error as Error)?.message === "cancel") return;
      ElMessage.error(extractErrorDetail(error, "删除失败"));
    });
}

interface SnapItem {
  id: number;
  label: string;
  table_count: number;
  column_count: number;
  relation_count: number;
  snapshot_time: string;
}

const snapshots = ref<SnapItem[]>([]);
const snapLoading = ref(false);
const compareIds = ref<number[]>([]);
const compareResult = ref<any>(null);

function loadSnapshots() {
  snapLoading.value = true;
  listAdminSnapshots()
    .then(({ data }) => {
      snapshots.value = data.items as any;
    })
    .catch(error => {
      snapshots.value = [];
      ElMessage.error(extractErrorDetail(error, "快照列表加载失败"));
    })
    .finally(() => {
      snapLoading.value = false;
    });
}

function createSnapshot() {
  createAdminSnapshot()
    .then(() => {
      ElMessage.success("快照已创建");
      loadSnapshots();
    })
    .catch(error => {
      // E12：无 catch 链补齐。
      ElMessage.error(extractErrorDetail(error, "快照创建失败"));
    });
}

function selectCompare(row: SnapItem) {
  if (compareIds.value.length >= 2) compareIds.value = [];
  compareIds.value.push(row.id);
  compareResult.value = null;
}

function runCompare() {
  if (compareIds.value.length !== 2) return;
  compareAdminSnapshots(compareIds.value[0], compareIds.value[1])
    .then(({ data }) => {
      compareResult.value = data;
    })
    .catch(error => {
      // E12：无 catch 链补齐。
      ElMessage.error(extractErrorDetail(error, "快照对比失败"));
    });
}

function goToChanges() {
  router.push("/metadata/changes");
}

function goToMetadataChanges() {
  // 专用快照工作台，避免与变更事件重复入口
  router.push("/metadata/snapshots");
}

onMounted(() => {
  loadKeys();
  loadOwners();
  loadTerms();
  loadSnapshots();
});
</script>

<style scoped>
.admin-page {
  padding: 4px;
}
.mb20 {
  margin-bottom: 20px;
}
.mt15 {
  margin-top: 15px;
}
.mt20 {
  margin-top: 20px;
}
.mono {
  font-family: "Courier New", monospace;
  font-size: 12px;
}
.compare-result {
  padding: 8px 0;
}
.token-hint {
  margin-left: 8px;
  color: var(--re-text-secondary);
  font-size: 12px;
}
.mr5 {
  margin-right: 5px;
}
.mb5 {
  margin-bottom: 5px;
}
.mt10 {
  margin-top: 10px;
}
.ml12 {
  margin-left: 12px;
}
.ml8 {
  margin-left: 8px;
}
.token-row {
  margin-bottom: 10px;
}
.token-input {
  width: 260px;
}
.search-input {
  width: 250px;
}
.action-row {
  display: flex;
  gap: 8px;
}
.token-once { margin: 0; padding: 12px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 13px; word-break: break-all; background: var(--el-fill-color-light); border-radius: 6px; }
.mb8 { margin-bottom: 8px; }
</style>
