<template>
  <div class="identity-persons">
    <div class="page-head">
      <strong>人员管理</strong>
      <span>HIS 人员主档：科室、职务、在职状态和来源。点行看详情。</span>
    </div>

    <div class="metric-strip">
      <ReStatCard label="总人员" :value="stats.total" />
      <ReStatCard label="在职" :value="stats.active" tone="accent" />
      <ReStatCard label="停用" :value="stats.inactive" tone="warning" />
      <ReStatCard label="来源系统" :value="stats.source_count" />
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="list-head">
          <strong>人员列表（{{ total }}）</strong>
          <div class="filters">
            <el-input v-model="params.keyword" clearable placeholder="工号/姓名/科室" class="keyword" @keyup.enter="doSearch" @clear="doSearch" />
            <el-select v-model="params.classification" clearable placeholder="岗位分类" class="type" @change="doSearch">
              <el-option label="医生" value="doctor" />
              <el-option label="护士" value="nurse" />
              <el-option label="药师" value="pharmacist" />
            </el-select>
            <el-select v-model="params.person_type" clearable placeholder="人员类型" class="type" @change="doSearch">
              <el-option label="正式" value="formal" />
              <el-option label="临时" value="temporary" />
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
      <el-alert v-else-if="profileError" type="error" :closable="false" :title="profileError" show-icon>
        <template #default><el-button size="small" @click="retryProfile">重试</el-button></template>
      </el-alert>
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
        <el-form v-if="profile.profile" ref="profileFormRef" :model="profileForm" :rules="profileRules" label-width="90px" class="profile-block">
          <el-form-item label="画像摘要" prop="profile_summary"><el-input v-model="profileForm.profile_summary" type="textarea" :rows="2" maxlength="2000" show-word-limit /></el-form-item>
          <el-form-item label="标签" prop="tags">
            <el-select v-model="profileForm.tags" multiple filterable allow-create default-first-option placeholder="输入后回车添加标签" class="tags-select" />
          </el-form-item>
          <el-form-item label="变更原因" prop="reason"><el-input v-model="profileForm.reason" maxlength="500" /></el-form-item>
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
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { createProfileChangeRequest, getPersonProfile, getPersons } from "@/api/identity";
import { classificationLabel, employmentLabel, personTypeLabel } from "@/views/identity/persons/personLabels";

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);
const params = reactive({ keyword: "", classification: "", person_type: "", page: 1, page_size: 20 });
const stats = reactive({ total: 0, active: 0, inactive: 0, source_count: 0 });
const profileVisible = ref(false);
const profileLoading = ref(false);
const profile = ref<any>(null);
const profileError = ref("");
const profileTarget = ref<any>(null);
const profileSaving = ref(false);
const profileFormRef = ref<FormInstance>();
const profileForm = reactive({ profile_summary: "", tags: [] as string[], reason: "" });
const profileRules: FormRules<typeof profileForm> = {
  profile_summary: [{ max: 2000, message: "画像摘要不能超过 2000 字", trigger: "blur" }],
  tags: [{
    validator: (_rule, value: string[], callback) => {
      if ((value || []).length > 20) callback(new Error("标签不能超过 20 个"));
      else callback();
    },
    trigger: "change"
  }],
  reason: [{ required: true, message: "请填写变更原因", trigger: "blur" }]
};

async function loadData() {
  loading.value = true;
  try {
    const res = await getPersons({
      keyword: params.keyword || undefined,
      classification: params.classification || undefined,
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
  profileTarget.value = row;
  profileVisible.value = true;
  profileLoading.value = true;
  profile.value = null;
  profileError.value = "";
  try {
    const res = await getPersonProfile(row.person_code);
    profile.value = res.data;
    const detail = res.data as unknown as {
      profile?: { summary?: string | null; tags?: string[] | null };
    };
    profileForm.profile_summary = detail.profile?.summary || "";
    profileForm.tags = [...(detail.profile?.tags || [])];
    profileForm.reason = "";
  } catch (error: any) {
    profileError.value = error?.response?.data?.detail || "加载人员档案失败";
  } finally {
    profileLoading.value = false;
  }
}

function retryProfile() {
  if (profileTarget.value) void showProfile(profileTarget.value);
}

async function submitProfileChange() {
  const personCode = profile.value?.person_code;
  if (!personCode) return;
  const valid = await profileFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  profileSaving.value = true;
  try {
    await createProfileChangeRequest(personCode, {
      profile_summary: profileForm.profile_summary || null,
      profile_tags: profileForm.tags.map(item => item.trim()).filter(Boolean),
      reason: profileForm.reason.trim()
    });
    ElMessage.success("画像变更已提交审批");
    profileForm.reason = "";
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "提交失败"));
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
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.filters { display: flex; gap: 8px; }
.keyword { width: 220px; }
.type { width: 130px; }
.tags-select { width: 100%; }
.tech-name { color: var(--text-secondary, #64748b); font-size: 12px; }
.pager { justify-content: flex-end; margin-top: 12px; }
.loading-panel { padding: 24px; text-align: center; }
.profile-block { margin-bottom: 16px; }
h4 { margin: 12px 0 8px; font-size: 14px; }
@media (max-width: 900px) {
  .metric-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filters { flex-wrap: wrap; }
}
</style>
