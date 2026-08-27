<template>
  <div class="identity-accounts">
    <RePageHeader title="跨系统账号" subtitle="维护 HIS、EMR、LIS、PACS 等系统账号与平台人员主数据的绑定关系。" />

    <section class="account-stat-grid">
      <ReStatCard label="账号总数" :value="total" tone="primary" />
      <ReStatCard label="当前页已关联" :value="linkedCount" tone="accent" />
      <ReStatCard label="当前页未关联" :value="unlinkedCount" tone="warning" />
    </section>

    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>跨系统账号管理</span>
          <el-button type="primary" @click="openBindDialog">绑定账号</el-button>
        </div>
      </template>
      <div class="filter-bar">
        <el-select
          v-model="params.system_code"
          placeholder="选择系统"
          clearable
          class="system-filter"
          @change="loadData"
        >
          <el-option label="HIS" value="HIS" />
          <el-option label="EMR" value="EMR" />
          <el-option label="LIS" value="LIS" />
          <el-option label="PACS" value="PACS" />
          <el-option label="YDHL" value="YDHL" />
          <el-option label="SM" value="SM" />
        </el-select>
        <el-input
          v-model="params.keyword"
          placeholder="搜索账号/人员"
          clearable
          class="keyword-filter"
          @keyup.enter="doSearch"
          @clear="doSearch"
        />
        <el-button class="refresh-button" @click="loadData">刷新</el-button>
      </div>
      <el-alert v-if="loadError" type="error" :closable="false" :title="loadError" show-icon class="load-error">
        <template #default><el-button size="small" @click="loadData">重试</el-button></template>
      </el-alert>
      <el-table v-loading="loading" :data="items" stripe class="accounts-table">
        <el-table-column prop="system_code" label="系统" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.system_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="account_id" label="账号" width="160" show-overflow-tooltip />
        <el-table-column prop="account_name" label="账号名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="person_code" label="关联人员" width="120">
          <template #default="{ row }">
            <span v-if="row.person_code">{{ row.person_code }}</span>
            <el-tag v-else size="small" type="warning">未关联</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="account_status" label="账号状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.account_status === 'active' ? 'success' : 'warning'">
              {{ row.account_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.person_code"
              v-perms="'identity.local_account.manage'"
              link
              type="danger"
              size="small"
              :loading="unbindingIds.has(row.id)"
              @click="doUnbind(row)"
            >
              解绑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        size="small"
        class="pager"
        @current-change="loadData"
      />
    </el-card>

    <el-dialog v-model="bindVisible" title="绑定账号" width="500px" destroy-on-close @closed="resetBindForm">
      <el-form ref="bindFormRef" :model="bindForm" :rules="bindRules" label-width="100px">
        <el-form-item label="系统" prop="system_code">
          <el-select v-model="bindForm.system_code" placeholder="选择系统" class="full-width">
            <el-option label="HIS" value="HIS" />
            <el-option label="EMR" value="EMR" />
            <el-option label="LIS" value="LIS" />
            <el-option label="PACS" value="PACS" />
            <el-option label="YDHL" value="YDHL" />
            <el-option label="SM" value="SM" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号ID" prop="account_id">
          <el-input v-model="bindForm.account_id" placeholder="输入系统账号ID" />
        </el-form-item>
        <el-form-item label="关联人员" prop="person_code">
          <el-select
            v-model="bindForm.person_code"
            filterable
            remote
            clearable
            reserve-keyword
            placeholder="输入工号/姓名搜索人员"
            :remote-method="searchPersons"
            :loading="personSearching"
            class="full-width"
          >
            <el-option
              v-for="p in personOptions"
              :key="p.person_code"
              :label="`${p.person_name || p.person_code}（${p.person_code}）`"
              :value="p.person_code"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bindVisible = false">取消</el-button>
        <el-button type="primary" :loading="bindLoading" @click="doBind">确认绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { computed, ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import { getAccounts, bindAccount, getPersons, unbindAccount } from "@/api/identity";

const items = ref<any[]>([]);
const loading = ref(false);
const loadError = ref("");
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const unbindingIds = ref(new Set<number>());
const personOptions = ref<any[]>([]);
const personSearching = ref(false);

async function searchPersons(query: string) {
  const keyword = query.trim();
  if (!keyword) {
    personOptions.value = [];
    return;
  }
  personSearching.value = true;
  try {
    const res = await getPersons({ keyword, page: 1, page_size: 20 });
    personOptions.value = res.data?.items || [];
  } catch {
    personOptions.value = [];
  } finally {
    personSearching.value = false;
  }
}
const linkedCount = computed(() => items.value.filter(item => !!item.person_code).length);
const unlinkedCount = computed(() => items.value.length - linkedCount.value);

const params = reactive({
  system_code: "",
  keyword: ""
});

function doSearch() {
  page.value = 1;
  loadData();
}

async function doUnbind(row: any) {
  // E5：解绑前确认（doUnbind 已有 catch+loading，仅补确认弹窗）。
  try {
    await ElMessageBox.confirm(
      `确认解绑账号 ${row.account_code || row.id}？账号保留，仅清空人员关联。`,
      "解绑确认",
      { type: "warning" }
    );
  } catch {
    return; // 用户取消
  }
  const next = new Set(unbindingIds.value);
  next.add(row.id);
  unbindingIds.value = next;
  try {
    await unbindAccount(row.id, "页面解绑");
    ElMessage.success("已解绑（账号保留，仅清空人员关联）");
    await loadData();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "解绑失败"));
  } finally {
    const done = new Set(unbindingIds.value);
    done.delete(row.id);
    unbindingIds.value = done;
  }
}

const bindVisible = ref(false);
const bindLoading = ref(false);
const bindFormRef = ref<FormInstance>();
const bindForm = reactive({
  system_code: "",
  account_id: "",
  person_code: ""
});
const bindRules: FormRules = {
  system_code: [{ required: true, message: "请选择系统", trigger: "change" }],
  account_id: [{ required: true, message: "请输入账号ID", trigger: "blur" }],
  person_code: [{ required: true, message: "请输入关联人员工号", trigger: "blur" }]
};

async function loadData() {
  loading.value = true;
  loadError.value = "";
  try {
    const res = await getAccounts({
      system_code: params.system_code || undefined,
      keyword: params.keyword || undefined,
      page: page.value,
      page_size: pageSize
    });
    items.value = res.data?.items ?? [];
    total.value = res.data?.total ?? 0;
  } catch (error: any) {
    items.value = [];
    total.value = 0;
    loadError.value = String(error?.response?.data?.detail || "账号列表加载失败");
  } finally {
    loading.value = false;
  }
}

function openBindDialog() {
  bindVisible.value = true;
}

function resetBindForm() {
  bindForm.system_code = "";
  bindForm.account_id = "";
  bindForm.person_code = "";
  bindFormRef.value?.resetFields();
}

async function doBind() {
  const valid = await bindFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  bindLoading.value = true;
  try {
    await bindAccount({
      system_code: bindForm.system_code,
      account_id: bindForm.account_id,
      person_code: bindForm.person_code
    });
    ElMessage.success("账号绑定成功");
    bindVisible.value = false;
    loadData();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "绑定失败"));
  } finally {
    bindLoading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.identity-accounts {
  padding: 4px;
}
.account-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 760px) {
  .account-stat-grid {
    grid-template-columns: 1fr;
  }
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.system-filter { width: 180px; }
.keyword-filter { width: 200px; }
.pager { justify-content: flex-end; margin-top: 12px; }
.load-error { margin-bottom: 12px; }
.refresh-button { margin-left: 12px; }
.accounts-table { margin-top: 12px; }
.full-width { width: 100%; }
</style>
