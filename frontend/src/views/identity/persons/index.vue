<template>
  <div class="identity-persons">
    <el-card shadow="never">
      <template #header>
        <span>人员管理</span>
      </template>
      <div class="filter-bar">
        <el-input
          v-model="params.keyword"
          placeholder="搜索工号/姓名/科室"
          clearable
          style="width: 280px"
          @keyup.enter="doSearch"
        />
        <el-select
          v-model="params.person_type"
          placeholder="人员类型"
          clearable
          style="width: 160px; margin-left: 12px"
          @change="doSearch"
        >
          <el-option label="医生" value="doctor" />
          <el-option label="护士" value="nurse" />
          <el-option label="技师" value="technician" />
          <el-option label="行政" value="admin" />
          <el-option label="其他" value="other" />
        </el-select>
        <el-button type="primary" style="margin-left: 12px" @click="doSearch">搜索</el-button>
      </div>
      <el-table
        v-loading="loading"
        :data="items"
        stripe
        style="margin-top: 12px"
        @row-click="showProfile"
      >
        <el-table-column prop="person_code" label="工号" width="120" />
        <el-table-column prop="person_name_cn" label="姓名" width="100" />
        <el-table-column prop="dept_name_cn" label="科室" min-width="150" show-overflow-tooltip />
        <el-table-column prop="person_type" label="人员类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.person_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="employment_status" label="在职状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.employment_status === 'active' ? 'success' : 'danger'">
              {{ row.employment_status === 'active' ? '在职' : '离职' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="primary_source_system" label="主来源" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.primary_source_system }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        style="margin-top: 16px; justify-content: flex-end"
        @change="loadData"
      />
    </el-card>

    <el-dialog v-model="profileVisible" title="人员档案" width="700px" destroy-on-close>
      <div v-if="profileLoading" style="text-align:center;padding:40px">
        <el-icon class="is-loading"><i-ep-loading /></el-icon>
      </div>
      <template v-else-if="profile">
        <el-descriptions :column="2" border style="margin-bottom:16px">
          <el-descriptions-item label="工号">{{ profile.person_code }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ profile.person_name_cn }}</el-descriptions-item>
          <el-descriptions-item label="科室">{{ profile.dept_name_cn }}</el-descriptions-item>
          <el-descriptions-item label="人员类型">{{ profile.person_type }}</el-descriptions-item>
          <el-descriptions-item label="在职状态">
            <el-tag size="small" :type="profile.employment_status === 'active' ? 'success' : 'danger'">
              {{ profile.employment_status === 'active' ? '在职' : '离职' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="主来源系统">{{ profile.primary_source_system }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin-bottom:8px">关联系统账号</h4>
        <el-table :data="profile.accounts ?? []" size="small" border>
          <el-table-column prop="system_code" label="系统" width="120" />
          <el-table-column prop="account_id" label="账号" width="140" show-overflow-tooltip />
          <el-table-column prop="account_name" label="账号名" min-width="120" />
          <el-table-column prop="account_status" label="账号状态" width="100">
            <template #default="{ row: acc }">
              <el-tag size="small" :type="acc.account_status === 'active' ? 'success' : 'warning'">
                {{ acc.account_status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { getPersons, getPersonProfile } from "@/api/identity";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);

const params = reactive({
  keyword: "",
  person_type: "",
  page: 1,
  page_size: 20
});

const profileVisible = ref(false);
const profileLoading = ref(false);
const profile = ref<any>(null);

async function loadData() {
  loading.value = true;
  try {
    const res = await getPersons({
      keyword: params.keyword || undefined,
      person_type: params.person_type || undefined,
      page: params.page,
      page_size: params.page_size
    });
    items.value = res.data.items ?? [];
    total.value = res.data.total ?? 0;
  } catch {
    ElMessage.error("加载人员列表失败");
  } finally {
    loading.value = false;
  }
}

function doSearch() {
  params.page = 1;
  loadData();
}

async function showProfile(row: any) {
  profileVisible.value = true;
  profileLoading.value = true;
  profile.value = null;
  try {
    const res = await getPersonProfile(row.person_code);
    profile.value = res.data;
  } catch {
    ElMessage.error("加载人员档案失败");
  } finally {
    profileLoading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
