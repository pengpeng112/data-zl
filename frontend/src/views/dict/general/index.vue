<template>
  <div class="dict-general">
    <RePageHeader title="通用字典管理" subtitle="维护平台通用分类、标准项、系统项和编码映射。" />

    <el-card class="dict-card" shadow="never">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="字典分类" name="categories">
          <div class="toolbar">
            <el-button v-perms="'dict.general.edit'" type="primary" size="small" @click="openCategoryDialog()">新增分类</el-button>
          </div>
          <el-alert v-if="catError" type="error" :closable="false" :title="catError" show-icon>
            <template #default><el-button size="small" @click="loadCategories">重试</el-button></template>
          </el-alert>
          <el-table v-loading="catLoading" :data="categories" stripe class="tab-table" size="small">
            <el-table-column prop="category_code" label="分类编码" width="180" />
            <el-table-column prop="category_name_cn" label="分类名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="standard_system" label="标准系统" width="140" align="center" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? "启用" : "停用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'dict.general.edit'" link type="primary" size="small" @click="openCategoryDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!catLoading && !catError && !categories.length" description="暂无分类" />
        </el-tab-pane>

        <el-tab-pane label="标准项" name="standardItems">
          <div class="filter-bar">
            <el-input v-model="stdItemParams.keyword" placeholder="搜索编码/名称" clearable class="keyword-input" @keyup.enter="doSearchStdItems" />
            <el-select v-model="stdItemParams.category_code" placeholder="分类" clearable class="category-select" @change="doSearchStdItems">
              <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
            </el-select>
            <el-button type="primary" size="small" @click="doSearchStdItems">搜索</el-button>
            <el-button v-perms="'dict.general.edit'" size="small" @click="openStdItemDialog()">新增标准项</el-button>
          </div>
          <el-alert v-if="stdItemError" type="error" :closable="false" :title="stdItemError" show-icon>
            <template #default><el-button size="small" @click="() => loadStdItems()">重试</el-button></template>
          </el-alert>
          <el-table v-loading="stdItemLoading" :data="stdItems" stripe class="tab-table" size="small">
            <el-table-column prop="category_code" label="分类" width="140" />
            <el-table-column prop="standard_code" label="标准编码" width="160" />
            <el-table-column prop="standard_name_cn" label="标准名称" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status === "active" ? "启用" : "停用" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'dict.general.edit'" link type="primary" size="small" @click="openStdItemDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!stdItemLoading && !stdItemError && !stdItems.length" description="暂无标准项" />
          <el-pagination
            v-model:current-page="stdPage"
            v-model:page-size="stdPageSize"
            :total="stdItemTotal"
            layout="total, prev, pager, next, sizes"
            :page-sizes="[10, 20, 50, 100]"
            size="small"
            class="pager"
            @change="loadStdItems"
          />
        </el-tab-pane>

        <el-tab-pane label="系统项" name="systemItems">
          <div class="filter-bar">
            <el-select v-model="sysItemParams.system_code" placeholder="系统" clearable filterable class="category-select" @change="doSearchSysItems">
              <el-option v-for="sys in systemOptions" :key="sys.system_code" :label="sys.system_name_cn || sys.system_code" :value="sys.system_code" />
            </el-select>
            <el-select v-model="sysItemParams.category_code" placeholder="分类" clearable class="category-select" @change="doSearchSysItems">
              <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
            </el-select>
            <el-input v-model="sysItemParams.keyword" placeholder="搜索编码/名称" clearable class="keyword-input" @keyup.enter="doSearchSysItems" />
            <el-button type="primary" size="small" @click="doSearchSysItems">搜索</el-button>
            <el-button v-perms="'dict.general.edit'" size="small" @click="openSysItemDialog()">新增系统项</el-button>
            <el-button v-perms="'dict.general.import'" size="small" @click="openImportDialog">导入系统字典</el-button>
          </div>
          <el-alert v-if="sysItemError" type="error" :closable="false" :title="sysItemError" show-icon>
            <template #default><el-button size="small" @click="() => loadSysItems()">重试</el-button></template>
          </el-alert>
          <el-table v-loading="sysItemLoading" :data="sysItems" stripe class="tab-table" size="small">
            <el-table-column prop="system_code" label="系统" width="110" align="center" />
            <el-table-column prop="category_code" label="分类" width="140" />
            <el-table-column prop="system_item_code" label="系统项编码" width="170" />
            <el-table-column prop="system_item_name_cn" label="系统项名称" min-width="200" show-overflow-tooltip />
            <el-table-column label="来源状态" width="100" align="center">
              <template #default="{ row }">{{ rawStatusLabel(row.raw_status) }}</template>
            </el-table-column>
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-switch
                  v-perms="'dict.general.edit'"
                  :model-value="row.enabled"
                  :loading="togglingIds.has(row.id)"
                  @change="toggleSysItem(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'dict.general.edit'" link type="primary" size="small" @click="openSysItemDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!sysItemLoading && !sysItemError && !sysItems.length" description="暂无系统项" />
          <el-pagination
            v-model:current-page="sysPage"
            v-model:page-size="sysPageSize"
            :total="sysItemTotal"
            layout="total, prev, pager, next, sizes"
            :page-sizes="[10, 20, 50, 100]"
            size="small"
            class="pager"
            @change="loadSysItems"
          />
        </el-tab-pane>

        <el-tab-pane label="映射" name="mappings">
          <div class="filter-bar">
            <el-select v-model="mapParams.category_code" placeholder="分类" clearable class="category-select" @change="doSearchMappings">
              <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
            </el-select>
            <el-select v-model="mapParams.system_code" placeholder="系统" clearable filterable class="category-select" @change="doSearchMappings">
              <el-option v-for="sys in systemOptions" :key="sys.system_code" :label="sys.system_name_cn || sys.system_code" :value="sys.system_code" />
            </el-select>
            <el-button v-perms="'dict.general.edit'" type="primary" size="small" @click="openMapDialog()">新增映射</el-button>
          </div>
          <el-alert v-if="mapError" type="error" :closable="false" :title="mapError" show-icon>
            <template #default><el-button size="small" @click="() => loadMappings()">重试</el-button></template>
          </el-alert>
          <el-table v-loading="mapLoading" :data="mapItems" stripe class="tab-table" size="small">
            <el-table-column prop="category_code" label="分类" width="140" />
            <el-table-column prop="standard_code" label="标准编码" width="160" />
            <el-table-column prop="system_code" label="系统" width="110" align="center" />
            <el-table-column prop="system_item_code" label="系统项编码" width="170" />
            <el-table-column label="映射类型" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small">{{ row.mapping_type || "-" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="80" align="center">
              <template #default="{ row }">{{ confidenceLabel(row.confidence) }}</template>
            </el-table-column>
            <el-table-column prop="review_status" label="复核状态" width="100" align="center" />
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'dict.general.edit'" link type="primary" size="small" @click="openMapDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!mapLoading && !mapError && !mapItems.length" description="暂无映射" />
          <el-pagination
            v-model:current-page="mapPage"
            v-model:page-size="mapPageSize"
            :total="mapTotal"
            layout="total, prev, pager, next, sizes"
            :page-sizes="[10, 20, 50, 100]"
            size="small"
            class="pager"
            @change="loadMappings"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 字典分类 Dialog -->
    <el-dialog v-model="catDialog.visible" :title="catDialog.isEdit ? '编辑分类' : '新增分类'" width="480px" destroy-on-close>
      <el-form ref="catFormRef" :model="catDialog.form" :rules="catRules" label-width="100px">
        <el-form-item label="分类编码" prop="category_code">
          <el-input v-model="catDialog.form.category_code" :disabled="catDialog.isEdit" maxlength="100" />
        </el-form-item>
        <el-form-item label="分类名称" prop="category_name_cn">
          <el-input v-model="catDialog.form.category_name_cn" maxlength="200" />
        </el-form-item>
        <el-form-item label="标准系统" prop="standard_system">
          <el-input v-model="catDialog.form.standard_system" maxlength="100" />
        </el-form-item>
        <el-form-item label="状态" prop="enabled">
          <el-switch v-model="catDialog.form.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.general.edit'" type="primary" :loading="catDialog.submitting" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>

    <!-- 标准项 Dialog -->
    <el-dialog v-model="stdItemDialog.visible" :title="stdItemDialog.isEdit ? '编辑标准项' : '新增标准项'" width="480px" destroy-on-close>
      <el-form ref="stdItemFormRef" :model="stdItemDialog.form" :rules="stdItemRules" label-width="100px">
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="stdItemDialog.form.category_code" class="full-width">
            <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准编码" prop="standard_code">
          <el-input v-model="stdItemDialog.form.standard_code" :disabled="stdItemDialog.isEdit" maxlength="200" />
        </el-form-item>
        <el-form-item label="标准名称" prop="standard_name_cn">
          <el-input v-model="stdItemDialog.form.standard_name_cn" maxlength="500" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="stdItemDialog.form.status" class="full-width">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stdItemDialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.general.edit'" type="primary" :loading="stdItemDialog.submitting" @click="saveStdItem">保存</el-button>
      </template>
    </el-dialog>

    <!-- 系统项 Dialog -->
    <el-dialog v-model="sysItemDialog.visible" :title="sysItemDialog.isEdit ? '编辑系统项' : '新增系统项'" width="480px" destroy-on-close>
      <el-form ref="sysItemFormRef" :model="sysItemDialog.form" :rules="sysItemRules" label-width="110px">
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="sysItemDialog.form.category_code" class="full-width">
            <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统" prop="system_code">
          <el-select v-model="sysItemDialog.form.system_code" class="full-width" filterable allow-create>
            <el-option v-for="sys in systemOptions" :key="sys.system_code" :label="sys.system_name_cn || sys.system_code" :value="sys.system_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统项编码" prop="system_item_code">
          <el-input v-model="sysItemDialog.form.system_item_code" :disabled="sysItemDialog.isEdit" maxlength="200" />
        </el-form-item>
        <el-form-item label="系统项名称" prop="system_item_name_cn">
          <el-input v-model="sysItemDialog.form.system_item_name_cn" maxlength="500" />
        </el-form-item>
        <el-form-item label="启用" prop="enabled">
          <el-switch v-model="sysItemDialog.form.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sysItemDialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.general.edit'" type="primary" :loading="sysItemDialog.submitting" @click="saveSysItem">保存</el-button>
      </template>
    </el-dialog>

    <!-- 映射 Dialog -->
    <el-dialog v-model="mapDialog.visible" :title="mapDialog.isEdit ? '编辑映射' : '新增映射'" width="480px" destroy-on-close>
      <el-form ref="mapFormRef" :model="mapDialog.form" :rules="mapRules" label-width="100px">
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="mapDialog.form.category_code" class="full-width">
            <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准编码" prop="standard_code">
          <el-input v-model="mapDialog.form.standard_code" maxlength="200" />
        </el-form-item>
        <el-form-item label="系统" prop="system_code">
          <el-select v-model="mapDialog.form.system_code" class="full-width" filterable allow-create>
            <el-option v-for="sys in systemOptions" :key="sys.system_code" :label="sys.system_name_cn || sys.system_code" :value="sys.system_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="系统项编码" prop="system_item_code">
          <el-input v-model="mapDialog.form.system_item_code" maxlength="200" />
        </el-form-item>
        <el-form-item label="映射类型" prop="mapping_type">
          <el-select v-model="mapDialog.form.mapping_type" class="full-width">
            <el-option label="等价" value="equivalent" />
            <el-option label="上位" value="broader" />
            <el-option label="下位" value="narrower" />
            <el-option label="关联" value="related" />
          </el-select>
        </el-form-item>
        <el-form-item label="置信度" prop="confidence">
          <el-select v-model="mapDialog.form.confidence" class="full-width">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mapDialog.visible = false">取消</el-button>
        <el-button v-perms="'dict.general.edit'" type="primary" :loading="mapDialog.submitting" @click="saveMapping">保存</el-button>
      </template>
    </el-dialog>

    <!-- 导入系统字典 Dialog -->
    <el-dialog v-model="importDialog.visible" title="导入系统字典" width="640px" destroy-on-close>
      <el-form ref="importFormRef" :model="importDialog.form" :rules="importRules" label-width="100px">
        <el-form-item label="系统" prop="system_code">
          <el-select v-model="importDialog.form.system_code" class="full-width" filterable allow-create>
            <el-option v-for="sys in systemOptions" :key="sys.system_code" :label="sys.system_name_cn || sys.system_code" :value="sys.system_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="importDialog.form.category_code" class="full-width">
            <el-option v-for="cat in categories" :key="cat.category_code" :label="cat.category_name_cn || cat.category_code" :value="cat.category_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据" prop="text">
          <el-input
            v-model="importDialog.form.text"
            type="textarea"
            :rows="8"
            placeholder='粘贴 JSON 数组（system_item_code/system_item_name_cn）或每行 编码,名称'
          />
        </el-form-item>
      </el-form>
      <el-alert v-if="importDialog.parseError" type="error" :closable="false" :title="importDialog.parseError" show-icon class="import-alert" />
      <el-descriptions v-if="importDialog.result" :column="3" border size="small" class="import-alert">
        <el-descriptions-item label="新增">{{ importDialog.result.created }}</el-descriptions-item>
        <el-descriptions-item label="更新">{{ importDialog.result.updated }}</el-descriptions-item>
        <el-descriptions-item label="拒绝">{{ importDialog.result.rejected }}</el-descriptions-item>
      </el-descriptions>
      <el-table v-if="importDialog.result?.errors.length" :data="importDialog.result.errors" size="small" max-height="200" class="import-alert">
        <el-table-column prop="index" label="行号" width="70" />
        <el-table-column prop="system_item_code" label="编码" width="160" />
        <el-table-column prop="reason" label="原因" min-width="180" />
      </el-table>
      <template #footer>
        <el-button @click="importDialog.visible = false">关闭</el-button>
        <el-button :loading="importDialog.previewing" @click="previewImport">预览校验</el-button>
        <el-button type="primary" :disabled="!importDialog.result || importDialog.result.dry_run" :loading="importDialog.submitting" @click="submitImport">正式导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { listSystems, type AssetSystemItem } from "@/api/asset";
import {
  getDictCategories,
  upsertDictCategory,
  getDictStandardItems,
  upsertDictStandardItem,
  getDictSystemItems,
  upsertDictSystemItem,
  setDictSystemItemEnabled,
  getDictItemMappings,
  upsertDictItemMapping,
  importSystemDict,
  type DictCategory,
  type DictImportResult,
  type DictItemMapping,
  type DictStandardItem,
  type DictSystemItem
} from "@/api/dict";
import { usePagedList } from "@/composables/usePagedList";
import { confidenceLabel, parseImportText, rawStatusLabel } from "./contracts";

const activeTab = ref("categories");

function detailMessage(error: unknown, fallback: string) {
  return String((error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback).slice(0, 300);
}

const systemOptions = ref<AssetSystemItem[]>([]);
const systemsError = ref("");

async function loadSystems() {
  systemsError.value = "";
  try {
    const res = await listSystems();
    systemOptions.value = res.data || [];
  } catch (error) {
    systemsError.value = detailMessage(error, "系统选项加载失败");
  }
}

function onTabChange(tab: string | number) {
  const name = String(tab);
  if (name === "categories") loadCategories();
  else if (name === "standardItems") { loadCategories(); loadStdItems(); }
  else if (name === "systemItems") { loadCategories(); loadSystems(); loadSysItems(); }
  else if (name === "mappings") { loadCategories(); loadSystems(); loadMappings(); }
}

// ========== Tab1: 字典分类 ==========
const categories = ref<DictCategory[]>([]);
const catLoading = ref(false);
const catError = ref("");

async function loadCategories() {
  catLoading.value = true;
  catError.value = "";
  try {
    const res = await getDictCategories();
    categories.value = res.data || [];
  } catch (error) {
    categories.value = [];
    catError.value = detailMessage(error, "分类加载失败");
  } finally {
    catLoading.value = false;
  }
}

const catDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: { category_code: "", category_name_cn: "", standard_system: "", enabled: true }
});
const catFormRef = ref<FormInstance>();
const catRules: FormRules = {
  category_code: [{ required: true, message: "请填写分类编码", trigger: "blur" }],
  category_name_cn: [{ required: true, message: "请填写分类名称", trigger: "blur" }]
};

function openCategoryDialog(row?: DictCategory) {
  catDialog.isEdit = !!row;
  catDialog.form = row
    ? { category_code: row.category_code, category_name_cn: row.category_name_cn, standard_system: row.standard_system || "", enabled: !!row.enabled }
    : { category_code: "", category_name_cn: "", standard_system: "", enabled: true };
  catDialog.visible = true;
}

async function saveCategory() {
  const valid = await catFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  catDialog.submitting = true;
  try {
    await upsertDictCategory({
      category_code: catDialog.form.category_code.trim(),
      category_name_cn: catDialog.form.category_name_cn.trim(),
      standard_system: catDialog.form.standard_system.trim() || null,
      enabled: catDialog.form.enabled
    });
    ElMessage.success(catDialog.isEdit ? "编辑成功" : "新增成功");
    catDialog.visible = false;
    loadCategories();
  } catch (error) {
    ElMessage.error(detailMessage(error, "保存失败"));
  } finally {
    catDialog.submitting = false;
  }
}

// ========== Tab2: 标准项 ==========
const stdItemParams = reactive({ keyword: "", category_code: "" });
// F6：分页五件套收敛到 usePagedList（含请求序号守卫；错误保持页内横幅语义）。
const {
  items: stdItems,
  total: stdItemTotal,
  page: stdPage,
  pageSize: stdPageSize,
  loading: stdItemLoading,
  loadData: loadStdItems,
  doSearch: doSearchStdItems
} = usePagedList<DictStandardItem, any>({
  pageSize: 20,
  extraParams: () => ({
    keyword: stdItemParams.keyword || undefined,
    category_code: stdItemParams.category_code || undefined
  }),
  onError: error => {
    stdItemError.value = detailMessage(error, "标准项加载失败");
    return false;
  },
  fetcher: async query => {
    stdItemError.value = "";
    const res = await getDictStandardItems(query);
    return { items: res.data?.items || [], total: res.data?.total || 0 };
  }
});
const stdItemError = ref("");

const stdItemDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: { category_code: "", standard_code: "", standard_name_cn: "", status: "active" }
});
const stdItemFormRef = ref<FormInstance>();
const stdItemRules: FormRules = {
  category_code: [{ required: true, message: "请选择分类", trigger: "change" }],
  standard_code: [{ required: true, message: "请填写标准编码", trigger: "blur" }],
  standard_name_cn: [{ required: true, message: "请填写标准名称", trigger: "blur" }]
};

function openStdItemDialog(row?: DictStandardItem) {
  stdItemDialog.isEdit = !!row;
  stdItemDialog.form = row
    ? { category_code: row.category_code, standard_code: row.standard_code, standard_name_cn: row.standard_name_cn, status: row.status || "active" }
    : { category_code: stdItemParams.category_code || "", standard_code: "", standard_name_cn: "", status: "active" };
  stdItemDialog.visible = true;
}

async function saveStdItem() {
  const valid = await stdItemFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  stdItemDialog.submitting = true;
  try {
    await upsertDictStandardItem({
      category_code: stdItemDialog.form.category_code,
      standard_code: stdItemDialog.form.standard_code.trim(),
      standard_name_cn: stdItemDialog.form.standard_name_cn.trim(),
      status: stdItemDialog.form.status
    });
    ElMessage.success(stdItemDialog.isEdit ? "编辑成功" : "新增成功");
    stdItemDialog.visible = false;
    loadStdItems();
  } catch (error) {
    ElMessage.error(detailMessage(error, "保存失败"));
  } finally {
    stdItemDialog.submitting = false;
  }
}

// ========== Tab3: 系统项 ==========
const togglingIds = ref(new Set<number>());
const sysItemParams = reactive({ system_code: "", category_code: "", keyword: "" });
const sysItemError = ref("");
// F6：同上。
const {
  items: sysItems,
  total: sysItemTotal,
  page: sysPage,
  pageSize: sysPageSize,
  loading: sysItemLoading,
  loadData: loadSysItems,
  doSearch: doSearchSysItems
} = usePagedList<DictSystemItem, any>({
  pageSize: 20,
  extraParams: () => ({
    system_code: sysItemParams.system_code || undefined,
    category_code: sysItemParams.category_code || undefined,
    keyword: sysItemParams.keyword || undefined
  }),
  onError: error => {
    sysItemError.value = detailMessage(error, "系统项加载失败");
    return false;
  },
  fetcher: async query => {
    sysItemError.value = "";
    const res = await getDictSystemItems(query);
    return { items: res.data?.items || [], total: res.data?.total || 0 };
  }
});

async function toggleSysItem(row: DictSystemItem) {
  const next = new Set(togglingIds.value);
  next.add(row.id);
  togglingIds.value = next;
  try {
    const res = await setDictSystemItemEnabled(row.id, !row.enabled);
    row.enabled = res.data?.enabled ?? !row.enabled;
  } catch (error) {
    ElMessage.error(detailMessage(error, "启停失败"));
  } finally {
    const done = new Set(togglingIds.value);
    done.delete(row.id);
    togglingIds.value = done;
  }
}

const sysItemDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: { category_code: "", system_code: "", system_item_code: "", system_item_name_cn: "", enabled: true }
});
const sysItemFormRef = ref<FormInstance>();
const sysItemRules: FormRules = {
  category_code: [{ required: true, message: "请选择分类", trigger: "change" }],
  system_code: [{ required: true, message: "请选择系统", trigger: "change" }],
  system_item_code: [{ required: true, message: "请填写系统项编码", trigger: "blur" }],
  system_item_name_cn: [{ required: true, message: "请填写系统项名称", trigger: "blur" }]
};

function openSysItemDialog(row?: DictSystemItem) {
  sysItemDialog.isEdit = !!row;
  sysItemDialog.form = row
    ? {
        category_code: row.category_code,
        system_code: row.system_code,
        system_item_code: row.system_item_code,
        system_item_name_cn: row.system_item_name_cn,
        enabled: row.enabled
      }
    : {
        category_code: sysItemParams.category_code || "",
        system_code: sysItemParams.system_code || "",
        system_item_code: "",
        system_item_name_cn: "",
        enabled: true
      };
  sysItemDialog.visible = true;
}

async function saveSysItem() {
  const valid = await sysItemFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  sysItemDialog.submitting = true;
  try {
    await upsertDictSystemItem({
      category_code: sysItemDialog.form.category_code,
      system_code: sysItemDialog.form.system_code,
      system_item_code: sysItemDialog.form.system_item_code.trim(),
      system_item_name_cn: sysItemDialog.form.system_item_name_cn.trim(),
      enabled: sysItemDialog.form.enabled
    });
    ElMessage.success(sysItemDialog.isEdit ? "编辑成功" : "新增成功");
    sysItemDialog.visible = false;
    loadSysItems();
  } catch (error) {
    ElMessage.error(detailMessage(error, "保存失败"));
  } finally {
    sysItemDialog.submitting = false;
  }
}

const importDialog = reactive({
  visible: false,
  submitting: false,
  previewing: false,
  parseError: "",
  result: null as DictImportResult | null,
  form: { system_code: "", category_code: "", text: "" }
});
const importFormRef = ref<FormInstance>();
const importRules: FormRules = {
  system_code: [{ required: true, message: "请选择系统", trigger: "change" }],
  category_code: [{ required: true, message: "请选择分类", trigger: "change" }],
  text: [{ required: true, message: "请粘贴导入数据", trigger: "blur" }]
};

function openImportDialog() {
  importDialog.form = { system_code: sysItemParams.system_code || "", category_code: sysItemParams.category_code || "", text: "" };
  importDialog.parseError = "";
  importDialog.result = null;
  importDialog.visible = true;
}

function parsedItems() {
  const parsed = parseImportText(importDialog.form.text);
  importDialog.parseError = parsed.error || "";
  return parsed;
}

async function previewImport() {
  const valid = await importFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  const parsed = parsedItems();
  if (parsed.error) return;
  importDialog.previewing = true;
  try {
    const res = await importSystemDict({
      category_code: importDialog.form.category_code,
      system_code: importDialog.form.system_code,
      items: parsed.items,
      dry_run: true
    });
    importDialog.result = res.data;
    ElMessage.success("预览完成，请核对后正式导入");
  } catch (error) {
    ElMessage.error(detailMessage(error, "预览校验失败"));
  } finally {
    importDialog.previewing = false;
  }
}

async function submitImport() {
  const parsed = parsedItems();
  if (parsed.error) return;
  importDialog.submitting = true;
  try {
    const res = await importSystemDict({
      category_code: importDialog.form.category_code,
      system_code: importDialog.form.system_code,
      items: parsed.items,
      dry_run: false
    });
    importDialog.result = res.data;
    ElMessage.success(`导入完成：新增 ${res.data.created} / 更新 ${res.data.updated} / 拒绝 ${res.data.rejected}`);
    loadSysItems();
  } catch (error) {
    ElMessage.error(detailMessage(error, "导入失败"));
  } finally {
    importDialog.submitting = false;
  }
}

// ========== Tab4: 映射 ==========
const mapParams = reactive({ category_code: "", system_code: "" });
const mapError = ref("");
// F6：同上。
const {
  items: mapItems,
  total: mapTotal,
  page: mapPage,
  pageSize: mapPageSize,
  loading: mapLoading,
  loadData: loadMappings,
  doSearch: doSearchMappings
} = usePagedList<DictItemMapping, any>({
  pageSize: 20,
  extraParams: () => ({
    category_code: mapParams.category_code || undefined,
    system_code: mapParams.system_code || undefined
  }),
  onError: error => {
    mapError.value = detailMessage(error, "映射加载失败");
    return false;
  },
  fetcher: async query => {
    mapError.value = "";
    const res = await getDictItemMappings(query);
    return { items: res.data?.items || [], total: res.data?.total || 0 };
  }
});

const mapDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: { category_code: "", standard_code: "", system_code: "", system_item_code: "", mapping_type: "equivalent", confidence: "high" }
});
const mapFormRef = ref<FormInstance>();
const mapRules: FormRules = {
  category_code: [{ required: true, message: "请选择分类", trigger: "change" }],
  system_code: [{ required: true, message: "请选择系统", trigger: "change" }],
  system_item_code: [{ required: true, message: "请填写系统项编码", trigger: "blur" }]
};

function openMapDialog(row?: DictItemMapping) {
  mapDialog.isEdit = !!row;
  mapDialog.form = row
    ? {
        category_code: row.category_code,
        standard_code: row.standard_code || "",
        system_code: row.system_code,
        system_item_code: row.system_item_code,
        mapping_type: row.mapping_type === "manual" ? "equivalent" : row.mapping_type || "equivalent",
        confidence: row.confidence || "high"
      }
    : {
        category_code: mapParams.category_code || "",
        standard_code: "",
        system_code: mapParams.system_code || "",
        system_item_code: "",
        mapping_type: "equivalent",
        confidence: "high"
      };
  mapDialog.visible = true;
}

async function saveMapping() {
  const valid = await mapFormRef.value?.validate().catch(() => false);
  if (!valid) return;
  mapDialog.submitting = true;
  try {
    await upsertDictItemMapping({
      category_code: mapDialog.form.category_code,
      standard_code: mapDialog.form.standard_code.trim() || null,
      system_code: mapDialog.form.system_code,
      system_item_code: mapDialog.form.system_item_code.trim(),
      mapping_type: mapDialog.form.mapping_type,
      confidence: mapDialog.form.confidence
    });
    ElMessage.success(mapDialog.isEdit ? "编辑成功" : "新增成功");
    mapDialog.visible = false;
    loadMappings();
  } catch (error) {
    ElMessage.error(detailMessage(error, "保存失败"));
  } finally {
    mapDialog.submitting = false;
  }
}

onMounted(() => {
  loadCategories();
  loadSystems();
});
</script>

<style scoped>
.dict-general {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}

.dict-card {
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-md);
  box-shadow: var(--re-shadow-sm);
}

.toolbar,
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.tab-table {
  margin-top: 8px;
}

.pager {
  justify-content: flex-end;
  margin-top: 12px;
}

.keyword-input {
  width: 240px;
}

.category-select {
  width: 180px;
}

.import-alert {
  margin-top: 12px;
}

.full-width {
  width: 100%;
}
</style>
