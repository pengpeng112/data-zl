<template>
  <div>
    <h2 class="page-title">治理管理</h2>

    <el-card class="mb20">
      <template #header>
        <span>API Token</span>
        <el-button
          type="primary"
          size="small"
          style="margin-left: 12px"
          @click="initToken"
          >初始化默认 Token</el-button
        >
        <el-button size="small" style="margin-left: 8px" @click="createKey"
          >创建新 Token</el-button
        >
      </template>
      <div v-if="tokenInput" style="margin-bottom: 10px">
        <span>当前 Token：</span>
        <el-input
          v-model="tokenInput"
          readonly
          style="width: 260px"
          size="small"
        />
        <el-button
          size="small"
          type="success"
          style="margin-left: 8px"
          @click="saveToken"
          >使用此 Token</el-button
        >
        <span style="margin-left: 8px; color: #909399; font-size: 12px"
          >Token 保存在浏览器，仅用于当前会话</span
        >
      </div>
      <el-table :data="keys" stripe size="small">
        <el-table-column prop="key_name" label="名称" width="180" />
        <el-table-column label="Token" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.token }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{
              row.enabled ? "启用" : "禁用"
            }}</el-tag>
          </template>
        </el-table-column>
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
          style="margin-left: 12px"
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
            style="width: 250px"
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
          style="margin-left: 12px"
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
            style="width: 250px"
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
          style="margin-left: 12px"
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
          style="margin-left: 8px"
          @click="
            compareIds = [];
            compareResult = null;
          "
          >清除</el-button
        >
      </div>
      <div class="mt15" style="display: flex; gap: 8px">
        <el-button type="info" size="small" @click="goToChanges">
          查看变更事件
        </el-button>
        <el-button type="info" size="small" @click="goToMetadataChanges">
          元数据变更检测
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { http } from "@/utils/http";
import { ElMessage } from "element-plus";

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

const tokenInput = ref(localStorage.getItem("asset_api_token") || "");
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
  http.get<any, any>("/api/v1/admin/keys").then(d => {
    keys.value = d.data;
  });
}

function initToken() {
  http.get<any, any>("/api/v1/admin/init").then(d => {
    tokenInput.value = d.data.token;
    localStorage.setItem("asset_api_token", d.data.token);
    ElMessage.success("Token 已生成并保存");
    loadKeys();
  });
}

function createKey() {
  const name = prompt("Token 名称：");
  if (!name) return;
  http
    .post<any, any>("/api/v1/admin/keys", { data: { key_name: name } })
    .then(d => {
      ElMessage.success(`新 Token: ${d.data.token}`);
      loadKeys();
    });
}

function toggleKey(row: KeyItem) {
  http
    .patch<any, any>(`/api/v1/admin/keys/${row.id}?enabled=${!row.enabled}`)
    .then(() => loadKeys());
}

function saveToken() {
  localStorage.setItem("asset_api_token", tokenInput.value);
  ElMessage.success("Token 已保存，刷新页面生效");
}

function loadOwners() {
  ownersLoading.value = true;
  http
    .get<any, any>("/api/v1/admin/owners", {
      params: {
        page: ownerPage.value,
        page_size: ownerPageSize.value,
        keyword: ownerKeyword.value || undefined
      }
    })
    .then(d => {
      owners.value = d.data.items;
      ownerTotal.value = d.data.total;
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
  http
    .put<any, any>("/api/v1/admin/owners", { data: ownerForm.value })
    .then(() => {
      ElMessage.success("已保存");
      ownerDialogVisible.value = false;
      loadOwners();
    });
}

function delOwner(row: OwnerItem) {
  if (!confirm("确定删除？")) return;
  http.delete<any, any>(`/api/v1/admin/owners/${row.id}`).then(() => {
    ElMessage.success("已删除");
    loadOwners();
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
  http
    .get<any, any>("/api/v1/admin/terms", {
      params: {
        page: termPage.value,
        page_size: termPageSize.value,
        keyword: termKeyword.value || undefined
      }
    })
    .then(d => {
      terms.value = d.data.items;
      termTotal.value = d.data.total;
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
  http
    .put<any, any>("/api/v1/admin/terms", { data: termForm.value })
    .then(() => {
      ElMessage.success("已保存");
      termDialogVisible.value = false;
      loadTerms();
    });
}

function delTerm(row: TermItem) {
  if (!confirm("确定删除？")) return;
  http.delete<any, any>(`/api/v1/admin/terms/${row.id}`).then(() => {
    ElMessage.success("已删除");
    loadTerms();
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
  http
    .get<any, any>("/api/v1/admin/snapshots")
    .then(d => {
      snapshots.value = d.data.items;
    })
    .finally(() => {
      snapLoading.value = false;
    });
}

function createSnapshot() {
  http.post<any, any>("/api/v1/admin/snapshots", { data: {} }).then(() => {
    ElMessage.success("快照已创建");
    loadSnapshots();
  });
}

function selectCompare(row: SnapItem) {
  if (compareIds.value.length >= 2) compareIds.value = [];
  compareIds.value.push(row.id);
  compareResult.value = null;
}

function runCompare() {
  if (compareIds.value.length !== 2) return;
  http
    .get<any, any>("/api/v1/admin/snapshots/compare", {
      params: { id1: compareIds.value[0], id2: compareIds.value[1] }
    })
    .then(d => {
      compareResult.value = d.data;
    });
}

function goToChanges() {
  router.push("/metadata/changes");
}

function goToMetadataChanges() {
  router.push("/metadata/changes");
}

onMounted(() => {
  loadKeys();
  loadOwners();
  loadTerms();
  loadSnapshots();
});
</script>

<style scoped>
.page-title {
  margin-bottom: 20px;
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
.mr5 {
  margin-right: 5px;
}
.mb5 {
  margin-bottom: 5px;
}
.mt10 {
  margin-top: 10px;
}
</style>
