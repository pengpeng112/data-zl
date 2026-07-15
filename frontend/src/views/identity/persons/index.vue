<template>
  <div class="identity-persons">
    <RePageHeader title="人员主数据" subtitle="查看平台人员、科室、账号与来源系统映射，用于权限授权和跨系统人员识别。">
      <template #icon><PersonIcon /></template>
    </RePageHeader>

    <section class="person-stats">
      <ReStatCard label="当前页人员" :value="items.length" tone="primary" helper="点击行查看详情">
        <template #icon><PersonIcon /></template>
      </ReStatCard>
      <ReStatCard label="总人员数" :value="total" tone="accent" helper="按当前筛选统计">
        <template #icon><TeamIcon /></template>
      </ReStatCard>
      <ReStatCard label="在职人员" :value="activeCount" tone="info" helper="当前页统计">
        <template #icon><CheckIcon /></template>
      </ReStatCard>
      <ReStatCard label="来源系统" :value="sourceCount" tone="warning" helper="当前页去重">
        <template #icon><SourceIcon /></template>
      </ReStatCard>
    </section>

    <el-card shadow="never" class="person-card">
      <ReToolbar title="人员筛选" class="person-toolbar">
        <div class="filter-bar">
          <el-input
            v-model="params.keyword"
            placeholder="搜索工号、姓名或科室"
            clearable
            class="keyword"
            @keyup.enter="doSearch"
          />
          <el-select v-model="params.person_type" placeholder="人员类型" clearable class="type" @change="doSearch">
            <el-option label="医生" value="doctor" />
            <el-option label="护士" value="nurse" />
            <el-option label="技师" value="technician" />
            <el-option label="行政" value="admin" />
            <el-option label="其他" value="other" />
          </el-select>
        </div>
        <template #actions>
          <el-button type="primary" :icon="SearchIcon" @click="doSearch">查询</el-button>
        </template>
      </ReToolbar>

      <el-table v-loading="loading" :data="items" stripe class="medical-data-table" @row-click="showProfile">
        <el-table-column prop="person_code" label="人员编码" width="130" />
        <el-table-column prop="person_name_cn" label="姓名" width="130" />
        <el-table-column prop="dept_code" label="科室编码" width="130" />
        <el-table-column prop="dept_name_cn" label="科室" min-width="160" show-overflow-tooltip />
        <el-table-column prop="person_type" label="类型" width="120">
          <template #default="{ row }"><el-tag size="small" type="info">{{ personTypeLabel(row.person_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="employment_status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.employment_status === 'active' ? 'success' : 'warning'">
              {{ employmentLabel(row.employment_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="primary_source_system" label="主来源" width="150" />
      </el-table>

      <el-pagination
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        class="pager"
        @change="loadData"
      />
    </el-card>

    <el-dialog v-model="profileVisible" title="人员档案" width="760px" destroy-on-close>
      <div v-if="profileLoading" class="loading-panel">
        <el-icon class="is-loading"><i-ep-loading /></el-icon>
      </div>
      <template v-else-if="profile">
        <el-descriptions :column="2" border class="profile-block">
          <el-descriptions-item label="人员编码">{{ profile.person_code }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ profile.person_name_cn }}</el-descriptions-item>
          <el-descriptions-item label="主科室">{{ profile.dept_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ personTypeLabel(profile.person_type) }}</el-descriptions-item>
          <el-descriptions-item label="主来源">{{ profile.primary_source_system || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="profile.profile" type="info" :closable="false" class="profile-block" title="画像变更需要审批后生效" />
        <el-form v-if="profile.profile" :model="profileForm" label-width="90px" class="profile-block">
          <el-form-item label="画像摘要"><el-input v-model="profileForm.profile_summary" type="textarea" :rows="2" maxlength="2000" show-word-limit /></el-form-item>
          <el-form-item label="标签"><el-input v-model="profileForm.tagsText" placeholder="多个标签用逗号分隔" /></el-form-item>
          <el-form-item label="变更原因"><el-input v-model="profileForm.reason" maxlength="500" /></el-form-item>
          <el-button type="primary" :loading="profileSaving" @click="submitProfileChange">提交画像变更审批</el-button>
        </el-form>

        <h4>科室关系</h4>
        <el-table :data="profile.departments ?? []" size="small" border class="profile-block medical-data-table">
          <el-table-column prop="dept_code" label="科室编码" width="140" />
          <el-table-column prop="source_table" label="来源表" min-width="180" show-overflow-tooltip />
          <el-table-column prop="source_dept_code" label="源科室" width="140" />
          <el-table-column label="主科室" width="100" align="center">
            <template #default="{ row }"><el-tag size="small" :type="row.is_primary ? 'success' : 'info'">{{ row.is_primary ? '是' : '否' }}</el-tag></template>
          </el-table-column>
        </el-table>

        <h4>账号</h4>
        <el-table :data="profile.accounts ?? []" size="small" border class="profile-block medical-data-table">
          <el-table-column prop="system_code" label="系统" width="120" />
          <el-table-column prop="account_id" label="账号" width="160" show-overflow-tooltip />
          <el-table-column prop="account_status" label="状态" width="120" />
        </el-table>

        <h4>来源</h4>
        <el-table :data="profile.sources ?? []" size="small" border class="medical-data-table">
          <el-table-column prop="source_system" label="系统" width="120" />
          <el-table-column prop="source_person_id" label="源人员ID" min-width="160" show-overflow-tooltip />
          <el-table-column prop="is_temporary" label="临时" width="120" />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createProfileChangeRequest, getPersonProfile, getPersons } from "@/api/identity";
import CheckIcon from "~icons/ri/checkbox-circle-line";
import PersonIcon from "~icons/ri/user-3-line";
import SearchIcon from "~icons/ri/search-line";
import SourceIcon from "~icons/ri/database-2-line";
import TeamIcon from "~icons/ri/team-line";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const params = reactive({ keyword: "", person_type: "", page: 1, page_size: 20 });
const profileVisible = ref(false);
const profileLoading = ref(false);
const profile = ref<any>(null);
const profileSaving = ref(false);
const profileForm = reactive({ profile_summary: "", tagsText: "", reason: "" });
const activeCount = computed(() => items.value.filter(item => item.employment_status === "active").length);
const sourceCount = computed(() => new Set(items.value.map(item => item.primary_source_system).filter(Boolean)).size);

function personTypeLabel(value: string) {
  const map: Record<string, string> = { doctor: "医生", nurse: "护士", technician: "技师", admin: "行政", other: "其他" };
  return map[value] || value || "-";
}

function employmentLabel(value: string) {
  const map: Record<string, string> = { active: "在职", inactive: "停用", retired: "离职" };
  return map[value] || value || "-";
}

async function loadData() {
  loading.value = true;
  try {
    const res = await getPersons({ keyword: params.keyword || undefined, person_type: params.person_type || undefined, page: params.page, page_size: params.page_size });
    items.value = res.data.items ?? [];
    total.value = res.data.total ?? 0;
  } catch {
    ElMessage.error("加载人员失败");
  } finally {
    loading.value = false;
  }
}
function doSearch() { params.page = 1; loadData(); }
async function showProfile(row: any) {
  profileVisible.value = true;
  profileLoading.value = true;
  profile.value = null;
  try {
    const res = await getPersonProfile(row.person_code);
    profile.value = res.data;
    profileForm.profile_summary = res.data?.profile?.summary || "";
    profileForm.tagsText = (res.data?.profile?.tags || []).join(",");
    profileForm.reason = "";
  } catch {
    ElMessage.error("加载人员档案失败");
  } finally {
    profileLoading.value = false;
  }
}
async function submitProfileChange() {
  const personCode = profile.value?.person_code;
  if (!personCode || !profileForm.reason.trim()) { ElMessage.warning("请填写变更原因"); return; }
  profileSaving.value = true;
  try {
    await createProfileChangeRequest(personCode, { profile_summary: profileForm.profile_summary || null, profile_tags: profileForm.tagsText.split(",").map(item => item.trim()).filter(Boolean), reason: profileForm.reason.trim() });
    ElMessage.success("画像变更已提交审批");
    profileForm.reason = "";
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || "提交失败"); }
  finally { profileSaving.value = false; }
}

onMounted(loadData);
</script>

<style scoped lang="scss">
.identity-persons {
  padding: 4px;
}

.person-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.person-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);

  :deep(.el-card__body) {
    display: grid;
    gap: 12px;
  }
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.keyword {
  width: 280px;
}

.type {
  width: 160px;
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  font-size: 13px;
}

.pager {
  justify-content: flex-end;
  margin-top: 4px;
}

.loading-panel {
  padding: 40px;
  text-align: center;
}

.profile-block {
  margin-bottom: 16px;
}

h4 {
  margin: 12px 0 8px;
  font-weight: 600;
  color: var(--text-primary);
}

@media (max-width: 1180px) {
  .person-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .person-stats {
    grid-template-columns: 1fr;
  }

  .keyword,
  .type {
    width: 100%;
  }
}
</style>
