<template>
  <div class="identity-persons">
    <div class="page-head">
      <strong>人员管理</strong>
      <span>HIS 人员主档：科室、职务、在职状态和来源。点行看详情。</span>
    </div>

    <div class="metric-strip">
      <span>总人员 <b>{{ stats.total }}</b></span>
      <span>在职 <b>{{ stats.active }}</b></span>
      <span>停用 <b>{{ stats.inactive }}</b></span>
      <span>来源系统 <b>{{ stats.source_count }}</b></span>
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="list-head">
          <strong>人员列表（{{ total }}）</strong>
          <div class="filters">
            <el-input v-model="params.keyword" clearable placeholder="工号/姓名/科室" class="keyword" @keyup.enter="doSearch" @clear="doSearch" />
            <el-select v-model="params.person_type" clearable placeholder="人员分类" class="type" @change="doSearch">
              <el-option label="医生" value="doctor" />
              <el-option label="护士" value="nurse" />
              <el-option label="药师" value="pharmacist" />
              <el-option label="正式" value="formal" />
            </el-select>
            <el-button type="primary" size="small" @click="doSearch">查询</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="items" stripe size="small" class="person-table" @row-click="showProfile">
        <el-table-column prop="person_code" label="人员编码" width="110" />
        <el-table-column prop="person_name_cn" label="姓名" width="100" show-overflow-tooltip />
        <el-table-column label="科室" width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.dept_name_cn || "-" }}</div>
            <small v-if="row.dept_code" class="tech-name">{{ row.dept_code }}</small>
          </template>
        </el-table-column>
        <el-table-column prop="job_title" label="职务" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.job_title || "-" }}</template>
        </el-table-column>
        <el-table-column label="分类" width="100">
          <template #default="{ row }">{{ row.classification_name || classificationLabel(row.classification) }}</template>
        </el-table-column>
        <el-table-column label="编制" width="80">
          <template #default="{ row }">{{ row.person_type_name || personTypeLabel(row.person_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.employment_status === 'active' ? 'success' : 'warning'">
              {{ row.employment_status_name || employmentLabel(row.employment_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="主来源" min-width="90">
          <template #default="{ row }">{{ row.primary_source_system || "-" }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="params.page"
        v-model:page-size="params.page_size"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[20, 50, 100]"
        class="pager"
        @current-change="loadData"
        @size-change="loadData"
      />
    </el-card>

    <el-dialog v-model="profileVisible" title="人员档案" width="760px" destroy-on-close>
      <div v-if="profileLoading" class="loading-panel">加载中…</div>
      <template v-else-if="profile">
        <el-descriptions :column="2" border size="small" class="profile-block">
          <el-descriptions-item label="人员编码">{{ profile.person_code }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ profile.person_name_cn }}</el-descriptions-item>
          <el-descriptions-item label="主科室">{{ profile.dept_name_cn || profile.dept_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="职务">{{ profile.job_title || "-" }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ profile.classification_name || classificationLabel(profile.classification) }}</el-descriptions-item>
          <el-descriptions-item label="编制">{{ profile.person_type_name || personTypeLabel(profile.person_type) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ profile.employment_status_name || employmentLabel(profile.employment_status) }}</el-descriptions-item>
          <el-descriptions-item label="主来源">{{ profile.primary_source_system || "-" }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="profile.profile" type="info" :closable="false" class="profile-block" title="画像变更需要审批后生效" />
        <el-form v-if="profile.profile" :model="profileForm" label-width="90px" class="profile-block">
          <el-form-item label="画像摘要"><el-input v-model="profileForm.profile_summary" type="textarea" :rows="2" maxlength="2000" show-word-limit /></el-form-item>
          <el-form-item label="标签"><el-input v-model="profileForm.tagsText" placeholder="多个标签用逗号分隔" /></el-form-item>
          <el-form-item label="变更原因"><el-input v-model="profileForm.reason" maxlength="500" /></el-form-item>
          <el-button type="primary" :loading="profileSaving" @click="submitProfileChange">提交画像变更审批</el-button>
        </el-form>

        <h4>科室关系</h4>
        <el-table :data="profile.departments ?? []" size="small" class="profile-block">
          <el-table-column prop="dept_name_cn" label="科室" min-width="140">
            <template #default="{ row }">{{ row.dept_name_cn || row.dept_code || "-" }}</template>
          </el-table-column>
          <el-table-column prop="dept_code" label="编码" width="110" />
          <el-table-column prop="source_table" label="来源表" min-width="160" show-overflow-tooltip />
          <el-table-column label="主科室" width="80" align="center">
            <template #default="{ row }">{{ row.is_primary ? "是" : "否" }}</template>
          </el-table-column>
        </el-table>

        <h4>账号</h4>
        <el-table :data="profile.accounts ?? []" size="small" class="profile-block">
          <el-table-column prop="system_code" label="系统" width="120" />
          <el-table-column prop="account_id" label="账号" min-width="160" show-overflow-tooltip />
          <el-table-column prop="account_status" label="状态" width="120" />
        </el-table>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createProfileChangeRequest, getPersonProfile, getPersons } from "@/api/identity";
import { classificationLabel, employmentLabel, personTypeLabel } from "@/views/identity/persons/personLabels";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const params = reactive({ keyword: "", person_type: "", page: 1, page_size: 20 });
const stats = reactive({ total: 0, active: 0, inactive: 0, source_count: 0 });
const profileVisible = ref(false);
const profileLoading = ref(false);
const profile = ref<any>(null);
const profileSaving = ref(false);
const profileForm = reactive({ profile_summary: "", tagsText: "", reason: "" });

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
    const next = res.data.stats || {};
    stats.total = next.total ?? total.value;
    stats.active = next.active ?? 0;
    stats.inactive = next.inactive ?? 0;
    stats.source_count = next.source_count ?? 0;
  } catch {
    ElMessage.error("加载人员失败");
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
  if (!personCode || !profileForm.reason.trim()) {
    ElMessage.warning("请填写变更原因");
    return;
  }
  profileSaving.value = true;
  try {
    await createProfileChangeRequest(personCode, {
      profile_summary: profileForm.profile_summary || null,
      profile_tags: profileForm.tagsText.split(",").map(item => item.trim()).filter(Boolean),
      reason: profileForm.reason.trim()
    });
    ElMessage.success("画像变更已提交审批");
    profileForm.reason = "";
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || "提交失败");
  } finally {
    profileSaving.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.identity-persons { padding: 4px; }
.page-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}
.page-head span { color: var(--text-secondary, #64748b); font-size: 12px; }
.metric-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
  font-size: 13px;
  color: var(--text-secondary, #64748b);
}
.metric-strip b { color: var(--text-primary, #0f172a); margin-left: 4px; }
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.filters { display: flex; gap: 8px; }
.keyword { width: 220px; }
.type { width: 130px; }
.tech-name { color: var(--text-secondary, #64748b); font-size: 12px; }
.pager { justify-content: flex-end; margin-top: 12px; }
.loading-panel { padding: 24px; text-align: center; }
.profile-block { margin-bottom: 16px; }
h4 { margin: 12px 0 8px; font-size: 14px; }
</style>
