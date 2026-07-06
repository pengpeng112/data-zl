<template>
  <div class="dict-mappings">
    <el-card shadow="never" class="page-card">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">诊断手术映射维护</div>
            <div class="subtitle">按 Excel 维护表展示，一行一个院内编码；院内编码和名称作为主键口径，编辑时不可修改</div>
          </div>
          <el-button type="primary" @click="openDialog()">新增映射</el-button>
        </div>
      </template>

      <div class="filter-panel">
        <el-segmented v-model="categoryCode" :options="categoryOptions" @change="onCategoryChange" />
        <el-input
          v-model="keyword"
          clearable
          placeholder="搜索院内编码、院内名称"
          class="keyword-input"
          @keyup.enter="doSearch"
          @clear="doSearch"
        />
        <el-select v-model="statusFilter" placeholder="状态" clearable class="small-filter" @change="doSearch">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>

        <template v-if="isDiagnosis">
          <el-select v-model="hasInfectious" placeholder="传染病诊断" clearable class="small-filter" @change="doSearch">
            <el-option label="有传染病诊断" :value="true" />
            <el-option label="无传染病诊断" :value="false" />
          </el-select>
        </template>

        <template v-if="isOperation">
          <el-select v-model="operationLevel" placeholder="手术等级" clearable class="small-filter" @change="doSearch">
            <el-option label="四" value="四" />
            <el-option label="三" value="三" />
            <el-option label="二" value="二" />
            <el-option label="一" value="一" />
          </el-select>
          <el-select v-model="minimallyInvasiveFlag" placeholder="是否微创" clearable class="small-filter" @change="doSearch">
            <el-option label="是" value="是" />
            <el-option label="否/空" value="__empty" />
          </el-select>
          <el-select v-model="performanceLevel4Flag" placeholder="绩效四级" clearable class="small-filter" @change="doSearch">
            <el-option label="是" value="是" />
            <el-option label="否/空" value="__empty" />
          </el-select>
          <el-select v-model="restrictedTechFlag" placeholder="限制技术" clearable class="small-filter" @change="doSearch">
            <el-option label="是" value="是" />
            <el-option label="否/空" value="__empty" />
          </el-select>
        </template>

        <el-button type="primary" @click="doSearch">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <el-alert v-if="authHint" :title="authHint" type="warning" show-icon :closable="false" class="auth-alert" />
      </div>

      <div class="summary-row">
        <el-tag type="info" effect="plain">{{ categoryText }}维护表</el-tag>
        <span>共 {{ total }} 条</span>
        <span class="hint">编辑时只能维护映射、标识和状态；院内编码/名称锁定，防止主键口径漂移。</span>
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        stripe
        border
        height="calc(100vh - 330px)"
        row-key="local_code"
        :row-class-name="tableRowClassName"
        style="width: 100%"
        empty-text="暂无映射数据，请确认已完成导入或调整筛选条件"
      >
        <el-table-column label="状态" width="76" fixed="left" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'inactive' ? 'info' : 'success'" size="small">
              {{ row.status === 'inactive' ? '停用' : '启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dict_attribute" label="字典属性" width="120" fixed="left" show-overflow-tooltip />
        <el-table-column prop="local_code" :label="localCodeLabel" width="175" fixed="left" show-overflow-tooltip />
        <el-table-column prop="local_name" :label="localNameLabel" min-width="240" fixed="left" show-overflow-tooltip />
        <el-table-column v-if="isOperation" prop="operation_level" label="院内手术等级" width="110" align="center" />
        <el-table-column prop="national_code" :label="nationalCodeLabel" width="185" show-overflow-tooltip />
        <el-table-column prop="national_name" :label="nationalNameLabel" min-width="260" show-overflow-tooltip />
        <el-table-column prop="insurance_code" :label="insuranceCodeLabel" width="185" show-overflow-tooltip />
        <el-table-column prop="insurance_name" :label="insuranceNameLabel" min-width="230" show-overflow-tooltip />

        <template v-if="isDiagnosis">
          <el-table-column prop="special_disease_name" label="病种名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="low_risk_category_code" label="ICD低风险编码类目" width="160" show-overflow-tooltip />
          <el-table-column prop="low_risk_disease_name" label="ICD低风险病种名称" min-width="190" show-overflow-tooltip />
          <el-table-column prop="infectious_disease_name" label="传染病诊断" min-width="160" show-overflow-tooltip />
        </template>

        <template v-if="isOperation">
          <el-table-column prop="operation_category" label="手术类别" width="140" show-overflow-tooltip />
          <el-table-column prop="performance_level4_flag" label="绩效四级" width="90" align="center" />
          <el-table-column prop="performance_minimally_invasive_flag" label="绩效微创" width="90" align="center" />
          <el-table-column prop="restricted_tech_flag" label="限制技术" width="90" align="center" />
        </template>

        <el-table-column prop="source_file" label="来源文件" min-width="260" show-overflow-tooltip />
        <el-table-column prop="source_sheet" label="来源工作表" width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="138" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button link :type="row.status === 'inactive' ? 'success' : 'warning'" size="small" @click="toggleStatus(row)">
              {{ row.status === 'inactive' ? '启用' : '停用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        :page-sizes="[20, 50, 100, 200]"
        class="pager"
        @change="loadData"
      />
    </el-card>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑映射行' : '新增映射行'" width="780px" destroy-on-close>
      <el-form :model="dialog.form" label-width="170px">
        <el-form-item label="状态">
          <el-radio-group v-model="dialog.form.status">
            <el-radio-button value="active">启用</el-radio-button>
            <el-radio-button value="inactive">停用</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="字典属性"><el-input v-model="dialog.form.dict_attribute" /></el-form-item>
        <el-form-item :label="localCodeLabel"><el-input v-model="dialog.form.local_code" :disabled="dialog.isEdit" /></el-form-item>
        <el-form-item :label="localNameLabel"><el-input v-model="dialog.form.local_name" :disabled="dialog.isEdit" /></el-form-item>
        <el-form-item v-if="isOperation" label="院内手术等级"><el-input v-model="dialog.form.operation_level" /></el-form-item>
        <el-form-item :label="nationalCodeLabel"><el-input v-model="dialog.form.national_code" /></el-form-item>
        <el-form-item :label="nationalNameLabel"><el-input v-model="dialog.form.national_name" /></el-form-item>
        <el-form-item :label="insuranceCodeLabel"><el-input v-model="dialog.form.insurance_code" /></el-form-item>
        <el-form-item :label="insuranceNameLabel"><el-input v-model="dialog.form.insurance_name" /></el-form-item>

        <template v-if="isDiagnosis">
          <el-form-item label="病种名称"><el-input v-model="dialog.form.special_disease_name" /></el-form-item>
          <el-form-item label="ICD低风险编码类目"><el-input v-model="dialog.form.low_risk_category_code" /></el-form-item>
          <el-form-item label="ICD低风险病种名称"><el-input v-model="dialog.form.low_risk_disease_name" /></el-form-item>
          <el-form-item label="传染病诊断"><el-input v-model="dialog.form.infectious_disease_name" /></el-form-item>
        </template>

        <template v-if="isOperation">
          <el-form-item label="手术类别"><el-input v-model="dialog.form.operation_category" /></el-form-item>
          <el-form-item label="绩效四级"><el-input v-model="dialog.form.performance_level4_flag" /></el-form-item>
          <el-form-item label="绩效微创"><el-input v-model="dialog.form.performance_minimally_invasive_flag" /></el-form-item>
          <el-form-item label="限制技术"><el-input v-model="dialog.form.restricted_tech_flag" /></el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.submitting" @click="saveRow">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import { getMedicalMappingRows, upsertMedicalMappingRow } from "@/api/dict";

const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(50);
const categoryCode = ref("diagnosis");
const keyword = ref("");
const statusFilter = ref("");
const hasInfectious = ref<boolean | "">("");
const minimallyInvasiveFlag = ref("");
const performanceLevel4Flag = ref("");
const restrictedTechFlag = ref("");
const operationLevel = ref("");
const authHint = ref("");

const categoryOptions = [
  { label: "诊断维护表", value: "diagnosis" },
  { label: "手术维护表", value: "operation" }
];

const isDiagnosis = computed(() => categoryCode.value === "diagnosis");
const isOperation = computed(() => categoryCode.value === "operation");
const categoryText = computed(() => isDiagnosis.value ? "诊断" : "手术");
const localCodeLabel = computed(() => isDiagnosis.value ? "院内临床诊断疾病编码" : "院内临床手术编码");
const localNameLabel = computed(() => isDiagnosis.value ? "院内临床诊断疾病名称" : "院内临床手术名称");
const nationalCodeLabel = computed(() => isDiagnosis.value ? "国家临床版2.0疾病编码" : "国家临床版3.0手术编码");
const nationalNameLabel = computed(() => isDiagnosis.value ? "国家临床版2.0疾病名称" : "国家临床版3.0手术名称");
const insuranceCodeLabel = computed(() => isDiagnosis.value ? "国家医保版2.0疾病编码" : "国家医保版2.0手术代码");
const insuranceNameLabel = computed(() => isDiagnosis.value ? "国家医保版2.0疾病名称" : "国家医保版2.0手术名称");

const emptyForm = () => ({
  category_code: categoryCode.value,
  local_code: "",
  local_name: "",
  dict_attribute: "",
  national_code: "",
  national_name: "",
  insurance_code: "",
  insurance_name: "",
  operation_level: "",
  operation_category: "",
  performance_level4_flag: "",
  performance_minimally_invasive_flag: "",
  restricted_tech_flag: "",
  special_disease_name: "",
  low_risk_category_code: "",
  low_risk_disease_name: "",
  infectious_disease_name: "",
  status: "active"
});

const dialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: emptyForm()
});

function onCategoryChange() {
  resetFilters(false);
  doSearch();
}

function resetFilters(search = true) {
  keyword.value = "";
  statusFilter.value = "";
  hasInfectious.value = "";
  minimallyInvasiveFlag.value = "";
  performanceLevel4Flag.value = "";
  restrictedTechFlag.value = "";
  operationLevel.value = "";
  if (search) doSearch();
}

function doSearch() {
  page.value = 1;
  loadData();
}

function openDialog(row?: any) {
  dialog.isEdit = !!row;
  dialog.form = row
    ? { ...emptyForm(), ...row, category_code: categoryCode.value, status: row.status || "active" }
    : emptyForm();
  dialog.visible = true;
}

async function saveRow() {
  dialog.submitting = true;
  try {
    await upsertMedicalMappingRow(dialog.form);
    ElMessage.success(dialog.isEdit ? "编辑成功" : "新增成功");
    dialog.visible = false;
    loadData();
  } finally {
    dialog.submitting = false;
  }
}

async function toggleStatus(row: any) {
  const nextStatus = row.status === "inactive" ? "active" : "inactive";
  await upsertMedicalMappingRow({ ...row, status: nextStatus });
  ElMessage.success(nextStatus === "inactive" ? "已停用" : "已启用");
  loadData();
}

function tableRowClassName({ row }: { row: any }) {
  return row.status === "inactive" ? "row-inactive" : "";
}

async function loadData() {
  loading.value = true;
  authHint.value = "";
  try {
    const params: Record<string, any> = {
      category_code: categoryCode.value,
      page: page.value,
      page_size: pageSize.value
    };
    if (keyword.value.trim()) params.keyword = keyword.value.trim();
    if (statusFilter.value) params.status = statusFilter.value;
    if (isDiagnosis.value && hasInfectious.value !== "") params.has_infectious = hasInfectious.value;
    if (isOperation.value) {
      if (operationLevel.value) params.operation_level = operationLevel.value;
      if (minimallyInvasiveFlag.value !== "") params.minimally_invasive_flag = minimallyInvasiveFlag.value;
      if (performanceLevel4Flag.value !== "") params.performance_level4_flag = performanceLevel4Flag.value;
      if (restrictedTechFlag.value !== "") params.restricted_tech_flag = restrictedTechFlag.value;
    }
    const res = await getMedicalMappingRows(params);
    items.value = (res as any).data.items || [];
    total.value = (res as any).data.total || 0;
  } catch (error: any) {
    if (error?.response?.status === 401) authHint.value = "接口未授权：请先设置 asset_api_token，或重新登录后刷新。";
    else if (error?.response?.status === 403) authHint.value = "API Token 无效或已禁用：请清理浏览器中的 asset_api_token 后重新设置有效 Token。";
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.page-card { min-height: calc(100vh - 130px); }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.title { font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); }
.subtitle { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
.filter-panel { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.keyword-input { width: 260px; }
.small-filter { width: 138px; }
.auth-alert { flex: 1; min-width: 260px; }
.summary-row { display: flex; align-items: center; gap: 12px; margin: 12px 0; color: var(--el-text-color-regular); font-size: 13px; }
.hint { color: var(--el-text-color-secondary); }
.pager { margin-top: 16px; justify-content: flex-end; }
:deep(.row-inactive) { color: var(--el-text-color-secondary); background: var(--el-fill-color-lighter); }
</style>