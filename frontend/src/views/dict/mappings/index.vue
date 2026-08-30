<template>
  <div class="dict-mappings">
    <el-card shadow="never" class="page-card">
      <template #header>
        <RePageHeader title="诊断手术映射维护" subtitle="按 Excel 维护表展示，一行一个院内编码；院内编码和名称作为主键口径，编辑时不可修改。">
          <template #actions>
            <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
            <el-button v-perms="'dict.medical.edit'" type="primary" @click="openDialog()">新增映射</el-button>
          </template>
        </RePageHeader>
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
        <el-button @click="() => resetFilters()">重置</el-button>
        <!-- 146 E8（R5）：列配置——可选列组按需显示 -->
        <el-dropdown trigger="click" :hide-on-click="false">
          <el-button>列配置<el-icon class="el-icon--right"><arrow-down /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-checkbox-group v-model="visibleColumnGroups" class="column-config">
                <el-checkbox value="national">国家临床版编码</el-checkbox>
                <el-checkbox value="insurance">医保版编码</el-checkbox>
                <el-checkbox v-if="isDiagnosis" value="diagnosisExtra">诊断扩展属性</el-checkbox>
                <el-checkbox v-if="isOperation" value="operationExtra">手术下发属性</el-checkbox>
                <el-checkbox value="source">来源文件</el-checkbox>
              </el-checkbox-group>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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
        :height="tableHeight"
        row-key="local_code"
        :row-class-name="tableRowClassName"
        class="full-width"
        empty-text="暂无映射数据，请确认已完成导入或调整筛选条件"
      >
        <el-table-column label="状态" width="76" fixed="left" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'inactive' ? 'info' : 'success'" size="small">
              {{ row.status === 'inactive' ? '停用' : '启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="dict_attribute" label="字典属性" width="120" fixed="left" show-overflow-tooltip :formatter="blankFormatter" />
        <el-table-column prop="local_code" :label="localCodeLabel" width="175" fixed="left" show-overflow-tooltip />
        <el-table-column prop="local_name" :label="localNameLabel" min-width="240" fixed="left" show-overflow-tooltip />
        <el-table-column v-if="isOperation" prop="operation_level" label="院内手术等级" width="110" align="center" :formatter="blankFormatter" />
        <template v-if="visibleColumnGroups.includes('national')">
          <el-table-column prop="national_code" :label="nationalCodeLabel" width="185" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="national_name" :label="nationalNameLabel" min-width="260" show-overflow-tooltip :formatter="blankFormatter" />
        </template>
        <template v-if="visibleColumnGroups.includes('insurance')">
          <el-table-column prop="insurance_code" :label="insuranceCodeLabel" width="185" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="insurance_name" :label="insuranceNameLabel" min-width="230" show-overflow-tooltip :formatter="blankFormatter" />
        </template>

        <template v-if="isDiagnosis && visibleColumnGroups.includes('diagnosisExtra')">
          <el-table-column prop="ybhm" label="JHEMR 灰码" width="110" align="center">
            <template #default="{ row }"><el-tag v-if="row.ybhm === '灰码'" type="warning" size="small">灰码</el-tag><span v-else>—</span></template>
          </el-table-column>
          <el-table-column prop="special_disease_code" label="门诊慢特病编码" width="150" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="special_disease_name" label="门诊慢特病名称" min-width="170" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="low_risk_category_code" label="ICD低风险编码类目" width="160" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="low_risk_disease_name" label="ICD低风险病种名称" min-width="190" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="infectious_disease_name" label="传染病诊断" min-width="160" show-overflow-tooltip :formatter="blankFormatter" />
        </template>

        <template v-if="isOperation && visibleColumnGroups.includes('operationExtra')">
          <el-table-column prop="operation_category" label="手术类别" width="140" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="performance_level4_flag" label="绩效四级" width="90" align="center" :formatter="blankFormatter" />
          <el-table-column prop="performance_minimally_invasive_flag" label="绩效微创" width="90" align="center" :formatter="blankFormatter" />
          <el-table-column prop="restricted_tech_flag" label="限制技术" width="90" align="center" :formatter="blankFormatter" />
        </template>

        <template v-if="visibleColumnGroups.includes('source')">
          <el-table-column prop="source_file" label="来源文件" min-width="260" show-overflow-tooltip :formatter="blankFormatter" />
          <el-table-column prop="source_sheet" label="来源工作表" width="150" show-overflow-tooltip :formatter="blankFormatter" />
        </template>
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

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? `编辑${categoryText}映射` : `新增${categoryText}映射`" width="min(980px, 94vw)" top="5vh" destroy-on-close>
      <el-form ref="mappingFormRef" :model="dialog.form" :rules="formRules" label-position="top" class="mapping-form">
        <div class="form-section-title">院内字典</div>
        <div class="form-grid">
        <el-form-item label="状态">
          <el-radio-group v-model="dialog.form.status">
            <el-radio-button value="active">启用</el-radio-button>
            <el-radio-button value="inactive">停用</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="字典属性" prop="dict_attribute"><el-select v-model="dialog.form.dict_attribute" filterable allow-create default-first-option class="full-width"><el-option v-for="value in optionData.dict_attributes" :key="value" :label="value" :value="value" /></el-select></el-form-item>
        <el-form-item :label="localCodeLabel" prop="local_code"><el-input v-model="dialog.form.local_code" :disabled="dialog.isEdit" /></el-form-item>
        <el-form-item :label="localNameLabel" prop="local_name"><el-input v-model="dialog.form.local_name" :disabled="dialog.isEdit" /></el-form-item>
        <el-form-item v-if="isOperation" label="院内手术等级"><el-select v-model="dialog.form.operation_level" clearable filterable class="full-width"><el-option v-for="value in optionData.operation_level" :key="value" :label="value" :value="value" /></el-select></el-form-item>
        <el-form-item v-if="isDiagnosis" label="JHEMR 医保灰码"><el-select v-model="dialog.form.ybhm" clearable placeholder="为空（非灰码）" class="full-width"><el-option label="灰码" value="灰码" /></el-select></el-form-item>
        </div>

        <div class="form-section-title">标准编码映射</div>
        <div class="form-grid">
        <el-form-item :label="nationalCodeLabel"><el-input v-model="dialog.form.national_code" /></el-form-item>
        <el-form-item :label="nationalNameLabel"><el-input v-model="dialog.form.national_name" /></el-form-item>
        <el-form-item :label="insuranceCodeLabel"><el-input v-model="dialog.form.insurance_code" /></el-form-item>
        <el-form-item :label="insuranceNameLabel"><el-input v-model="dialog.form.insurance_name" /></el-form-item>
        </div>

        <template v-if="isDiagnosis">
          <div class="form-section-title">诊断扩展属性</div><div class="form-grid">
          <el-form-item label="门诊慢特病编码"><el-input v-model="dialog.form.special_disease_code" /></el-form-item>
          <el-form-item label="门诊慢特病名称"><el-input v-model="dialog.form.special_disease_name" /></el-form-item>
          <el-form-item label="ICD低风险编码类目"><el-input v-model="dialog.form.low_risk_category_code" /></el-form-item>
          <el-form-item label="ICD低风险病种名称"><el-input v-model="dialog.form.low_risk_disease_name" /></el-form-item>
          <el-form-item label="传染病诊断"><el-input v-model="dialog.form.infectious_disease_name" /></el-form-item>
          </div>
        </template>

        <template v-if="isOperation">
          <div class="form-section-title">手术下发属性</div><div class="form-grid">
          <el-form-item label="手术类别"><el-select v-model="dialog.form.operation_category" clearable filterable class="full-width"><el-option v-for="value in optionData.operation_category" :key="value" :label="value" :value="value" /></el-select></el-form-item>
          <el-form-item label="绩效四级"><el-select v-model="dialog.form.performance_level4_flag" clearable placeholder="为空" class="full-width"><el-option v-for="value in optionData.performance_level4_flag" :key="value" :label="value" :value="value" /></el-select></el-form-item>
          <el-form-item label="绩效微创"><el-select v-model="dialog.form.performance_minimally_invasive_flag" clearable placeholder="为空" class="full-width"><el-option v-for="value in optionData.performance_minimally_invasive_flag" :key="value" :label="value" :value="value" /></el-select></el-form-item>
          <el-form-item label="限制技术"><el-select v-model="dialog.form.restricted_tech_flag" clearable placeholder="为空" class="full-width"><el-option v-for="value in optionData.restricted_tech_flag" :key="value" :label="value" :value="value" /></el-select></el-form-item>
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.medical.edit'" type="primary" :loading="dialog.submitting" @click="saveRow">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import { extractErrorDetail } from "@/utils/errorMessage";
import { authHintForStatus } from "@/utils/statusLabels";
import { exportMedicalMappingRows, getMedicalMappingOptions, getMedicalMappingRows, upsertMedicalMappingRow } from "@/api/dict";

const loading = ref(false);
const exporting = ref(false);
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
const mappingFormRef = ref<FormInstance>();
const optionData = reactive<Record<string, string[]>>({ dict_attributes: ["院内扩展"], operation_category: [], operation_level: [], performance_level4_flag: [], performance_minimally_invasive_flag: [], restricted_tech_flag: [] });
// 146 E8（R5）：列配置——可选列组（国家临床版/医保版/诊断扩展/手术属性/来源文件）
const visibleColumnGroups = ref<string[]>(["national", "insurance", "diagnosisExtra", "operationExtra", "source"]);
// 146 E8（R5）：弹性高度——随视口自适应并设下限，避免固定 calc 在筛选换行时溢出
const tableHeight = ref(520);
function refreshTableHeight() {
  tableHeight.value = Math.max(360, Math.min(window.innerHeight - 330, 900));
}
refreshTableHeight();
window.addEventListener("resize", refreshTableHeight);
onBeforeUnmount(() => window.removeEventListener("resize", refreshTableHeight));
// 146 E8（R5）：可读空值——空单元格统一显示“—”
function blankFormatter(row: any, _column: any, cellValue: any) {
  const text = cellValue == null ? "" : String(cellValue).trim();
  return text || "—";
}
const formRules: FormRules = {
  local_code: [{ required: true, whitespace: true, message: "请输入院内编码", trigger: "blur" }],
  local_name: [{ required: true, whitespace: true, message: "请输入院内名称", trigger: "blur" }],
  dict_attribute: [{ required: true, message: "请选择或填写字典属性", trigger: "change" }]
};

const categoryOptions = [
  { label: "诊断维护表", value: "diagnosis" },
  { label: "手术维护表", value: "operation" }
];

const isDiagnosis = computed(() => categoryCode.value === "diagnosis");
const isOperation = computed(() => categoryCode.value === "operation");
const categoryText = computed(() => isDiagnosis.value ? "诊断" : "手术");
const localCodeLabel = computed(() => isDiagnosis.value ? "院内临床诊断编码" : "院内临床手术编码");
const localNameLabel = computed(() => isDiagnosis.value ? "院内临床诊断名称" : "院内临床手术名称");
const nationalCodeLabel = computed(() => isDiagnosis.value ? "国家临床版2.0疾病编码" : "国家临床版3.0手术编码");
const nationalNameLabel = computed(() => isDiagnosis.value ? "国家临床版2.0疾病名称" : "国家临床版3.0手术名称");
const insuranceCodeLabel = computed(() => isDiagnosis.value ? "国家医保版2.0疾病编码" : "国家医保版2.0手术代码");
const insuranceNameLabel = computed(() => isDiagnosis.value ? "国家医保版2.0疾病名称" : "国家医保版2.0手术名称");

const emptyForm = () => ({
  category_code: categoryCode.value,
  local_code: "",
  local_name: "",
  dict_attribute: "院内扩展",
  ybhm: "",
  national_code: "",
  national_name: "",
  insurance_code: "",
  insurance_name: "",
  operation_level: "",
  operation_category: "",
  performance_level4_flag: "",
  performance_minimally_invasive_flag: "",
  restricted_tech_flag: "",
  special_disease_code: "",
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
  loadOptions();
}

// 146 E8（R5）：下拉值域按类别缓存，打开弹窗不重复请求；失败时提示可重试
const optionsCache = new Map<string, Record<string, string[]>>();

async function loadOptions() {
  const cached = optionsCache.get(categoryCode.value);
  if (cached) {
    Object.assign(optionData, cached);
    return;
  }
  try {
    const res = await getMedicalMappingOptions(categoryCode.value);
    const payload = res.data || {};
    Object.assign(optionData, payload);
    if (!optionData.dict_attributes?.includes("院内扩展")) optionData.dict_attributes = ["院内扩展", ...(optionData.dict_attributes || [])];
    optionsCache.set(categoryCode.value, JSON.parse(JSON.stringify(optionData)));
  } catch {
    ElMessage.warning("下拉值域加载失败，请重新打开编辑框重试");
  }
}

async function saveRow() {
  const valid = await mappingFormRef.value?.validate().catch(() => false);
  if (!valid) {
    ElMessage.warning("请先完善必填项（院内编码/名称、字典属性）");
    return;
  }
  dialog.submitting = true;
  try {
    await upsertMedicalMappingRow(dialog.form);
    ElMessage.success(dialog.isEdit ? "编辑成功" : "新增成功");
    dialog.visible = false;
    loadData();
  } catch (error) {
    // E8：保存失败提示（此前裸抛未处理拒绝）。
    ElMessage.error(extractErrorDetail(error, "映射保存失败"));
  } finally {
    dialog.submitting = false;
  }
}

async function toggleStatus(row: any) {
  const nextStatus = row.status === "inactive" ? "active" : "inactive";
  try {
    await upsertMedicalMappingRow({ ...row, status: nextStatus });
    ElMessage.success(nextStatus === "inactive" ? "已停用" : "已启用");
    loadData();
  } catch (error) {
    // E8：启停失败提示。
    ElMessage.error(extractErrorDetail(error, "状态切换失败"));
  }
}

function tableRowClassName({ row }: { row: any }) {
  return row.status === "inactive" ? "row-inactive" : "";
}

function buildQueryParams(withPage = true) {
  const params: Record<string, any> = {
    category_code: categoryCode.value
  };
  if (withPage) {
    params.page = page.value;
    params.page_size = pageSize.value;
  }
  if (keyword.value.trim()) params.keyword = keyword.value.trim();
  if (statusFilter.value) params.status = statusFilter.value;
  if (isDiagnosis.value && hasInfectious.value !== "") params.has_infectious = hasInfectious.value;
  if (isOperation.value) {
    if (operationLevel.value) params.operation_level = operationLevel.value;
    if (minimallyInvasiveFlag.value !== "") params.minimally_invasive_flag = minimallyInvasiveFlag.value;
    if (performanceLevel4Flag.value !== "") params.performance_level4_flag = performanceLevel4Flag.value;
    if (restrictedTechFlag.value !== "") params.restricted_tech_flag = restrictedTechFlag.value;
  }
  return params;
}

async function exportExcel() {
  exporting.value = true;
  authHint.value = "";
  try {
    const blob = await exportMedicalMappingRows(buildQueryParams(false));
    const url = window.URL.createObjectURL(blob as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${categoryText.value}映射维护.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    ElMessage.success("导出完成");
  } catch (error: any) {
    const hint = authHintForStatus(error?.response?.status);
    if (hint) authHint.value = hint;
    else ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

async function loadData() {
  loading.value = true;
  authHint.value = "";
  try {
    const res = await getMedicalMappingRows(buildQueryParams(true));
    items.value = res.data.items || [];
    total.value = res.data.total || 0;
  } catch (error: any) {
    const hint = authHintForStatus(error?.response?.status); // E8：非鉴权失败不再静默
    if (hint) authHint.value = hint;
    else ElMessage.error(extractErrorDetail(error, "映射列表加载失败"));
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.dict-mappings { padding: 4px; }
.page-card { min-height: calc(100vh - 130px); border-color: var(--border-light); border-radius: var(--radius-base); box-shadow: var(--shadow-sm); }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.title { font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); }
.subtitle { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
.filter-panel { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.keyword-input { width: 260px; }
.small-filter { width: 138px; }
.auth-alert { flex: 1; min-width: 260px; }
.column-config { display: grid; gap: 4px; padding: 4px 12px; }
.summary-row { display: flex; align-items: center; gap: 12px; margin: 12px 0; color: var(--el-text-color-regular); font-size: 13px; }
.hint { color: var(--el-text-color-secondary); }
.pager { margin-top: 16px; justify-content: flex-end; }
:deep(.row-inactive) { color: var(--el-text-color-secondary); background: var(--el-fill-color-lighter); }

.full-width { width: 100%; }
.mapping-form { max-height: 72vh; padding-right: 6px; overflow-y: auto; }
.form-section-title { margin: 4px 0 12px; padding-left: 9px; border-left: 3px solid var(--el-color-primary); font-weight: 600; color: var(--el-text-color-primary); }
.form-section-title:not(:first-child) { margin-top: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 22px; }
@media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
</style>
