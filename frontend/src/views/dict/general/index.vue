<template>
  <div class="dict-general">
    <el-card shadow="never">
      <template #header>
        <span>通用字典管理</span>
      </template>

      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="字典分类" name="categories">
          <div class="toolbar">
            <el-button type="primary" size="small" @click="openCategoryDialog()">新增分类</el-button>
          </div>
          <el-table v-loading="catLoading" :data="categories" stripe style="margin-top: 8px" size="small">
            <el-table-column prop="category_code" label="分类编码" width="180" />
            <el-table-column prop="category_name_cn" label="分类名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="standard_system" label="标准系统" width="140" align="center" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openCategoryDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="标准项" name="standardItems">
          <div class="filter-bar">
            <el-input
              v-model="stdItemParams.keyword"
              placeholder="搜索编码/名称"
              clearable
              style="width: 240px"
              @keyup.enter="doSearchStdItems"
            />
            <el-select
              v-model="stdItemParams.category_code"
              placeholder="分类"
              clearable
              style="width: 180px"
              @change="doSearchStdItems"
            >
              <el-option
                v-for="cat in categories"
                :key="cat.category_code"
                :label="cat.category_name_cn || cat.category_code"
                :value="cat.category_code"
              />
            </el-select>
            <el-button type="primary" size="small" @click="doSearchStdItems">搜索</el-button>
            <el-button size="small" @click="openStdItemDialog()">新增标准项</el-button>
          </div>
          <el-table v-loading="stdItemLoading" :data="stdItems" stripe style="margin-top: 8px" size="small">
            <el-table-column prop="category_code" label="分类" width="140" />
            <el-table-column prop="item_code" label="编码" width="160" />
            <el-table-column prop="item_name_cn" label="名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="standard_system" label="标准系统" width="120" align="center" />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openStdItemDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="stdItemParams.page"
            v-model:page-size="stdItemParams.page_size"
            :total="stdItemTotal"
            layout="total, prev, pager, next, sizes"
            :page-sizes="[10, 20, 50, 100]"
            size="small"
            style="margin-top: 12px; justify-content: flex-end"
            @change="loadStdItems"
          />
        </el-tab-pane>

        <el-tab-pane label="系统项" name="systemItems">
          <div class="filter-bar">
            <el-select
              v-model="sysItemParams.target_system"
              placeholder="目标系统"
              clearable
              style="width: 180px"
              @change="loadSysItems"
            >
              <el-option label="HIS" value="HIS" />
              <el-option label="EMR" value="EMR" />
              <el-option label="LIS" value="LIS" />
              <el-option label="PACS" value="PACS" />
            </el-select>
            <el-input
              v-model="sysItemParams.keyword"
              placeholder="搜索编码/名称"
              clearable
              style="width: 240px; margin-left: 8px"
              @keyup.enter="loadSysItems"
            />
            <el-button type="primary" size="small" style="margin-left: 8px" @click="loadSysItems">搜索</el-button>
            <el-button size="small" style="margin-left: 8px" @click="openImportDialog()">导入系统字典</el-button>
          </div>
          <el-table v-loading="sysItemLoading" :data="sysItems" stripe style="margin-top: 8px" size="small">
            <el-table-column prop="target_system" label="目标系统" width="100" align="center" />
            <el-table-column prop="category_code" label="分类" width="140" />
            <el-table-column prop="system_code" label="系统编码" width="160" />
            <el-table-column prop="system_name" label="系统名称" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="映射" name="mappings">
          <div class="filter-bar">
            <el-select
              v-model="mapParams.category_code"
              placeholder="分类"
              clearable
              style="width: 180px"
              @change="doSearchMappings"
            >
              <el-option
                v-for="cat in categories"
                :key="cat.category_code"
                :label="cat.category_name_cn || cat.category_code"
                :value="cat.category_code"
              />
            </el-select>
            <el-button type="primary" size="small" style="margin-left: 8px" @click="openMapDialog()">新增映射</el-button>
          </div>
          <el-table v-loading="mapLoading" :data="mapItems" stripe style="margin-top: 8px" size="small">
            <el-table-column prop="category_code" label="分类" width="140" />
            <el-table-column prop="standard_code" label="标准编码" width="160" />
            <el-table-column prop="system_code" label="系统编码" width="160" />
            <el-table-column prop="target_system" label="目标系统" width="100" align="center" />
            <el-table-column label="映射类型" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small">{{ row.mapping_type || "-" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="80" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="row.confidence === 'high' ? 'success' : row.confidence === 'medium' ? 'warning' : 'info'"
                  size="small"
                >
                  {{ row.confidence === 'high' ? '高' : row.confidence === 'medium' ? '中' : '低' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openMapDialog(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-model:current-page="mapParams.page"
            v-model:page-size="mapParams.page_size"
            :total="mapTotal"
            layout="total, prev, pager, next, sizes"
            :page-sizes="[10, 20, 50, 100]"
            size="small"
            style="margin-top: 12px; justify-content: flex-end"
            @change="loadMappings"
          />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 字典分类 Dialog -->
    <el-dialog
      v-model="catDialog.visible"
      :title="catDialog.isEdit ? '编辑分类' : '新增分类'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="catFormRef" :model="catDialog.form" label-width="100px">
        <el-form-item label="分类编码" prop="category_code">
          <el-input v-model="catDialog.form.category_code" :disabled="catDialog.isEdit" />
        </el-form-item>
        <el-form-item label="分类名称" prop="category_name_cn">
          <el-input v-model="catDialog.form.category_name_cn" />
        </el-form-item>
        <el-form-item label="标准系统" prop="standard_system">
          <el-input v-model="catDialog.form.standard_system" />
        </el-form-item>
        <el-form-item label="状态" prop="enabled">
          <el-switch v-model="catDialog.form.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="catDialog.submitting" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>

    <!-- 标准项 Dialog -->
    <el-dialog
      v-model="stdItemDialog.visible"
      :title="stdItemDialog.isEdit ? '编辑标准项' : '新增标准项'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="stdItemFormRef" :model="stdItemDialog.form" label-width="100px">
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="stdItemDialog.form.category_code" style="width: 100%">
            <el-option
              v-for="cat in categories"
              :key="cat.category_code"
              :label="cat.category_name_cn || cat.category_code"
              :value="cat.category_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="编码" prop="item_code">
          <el-input v-model="stdItemDialog.form.item_code" :disabled="stdItemDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="item_name_cn">
          <el-input v-model="stdItemDialog.form.item_name_cn" />
        </el-form-item>
        <el-form-item label="标准系统" prop="standard_system">
          <el-input v-model="stdItemDialog.form.standard_system" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="stdItemDialog.form.status" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stdItemDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="stdItemDialog.submitting" @click="saveStdItem">保存</el-button>
      </template>
    </el-dialog>

    <!-- 映射 Dialog -->
    <el-dialog
      v-model="mapDialog.visible"
      :title="mapDialog.isEdit ? '编辑映射' : '新增映射'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="mapFormRef" :model="mapDialog.form" label-width="100px">
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="mapDialog.form.category_code" style="width: 100%">
            <el-option
              v-for="cat in categories"
              :key="cat.category_code"
              :label="cat.category_name_cn || cat.category_code"
              :value="cat.category_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标准编码" prop="standard_code">
          <el-input v-model="mapDialog.form.standard_code" />
        </el-form-item>
        <el-form-item label="系统编码" prop="system_code">
          <el-input v-model="mapDialog.form.system_code" />
        </el-form-item>
        <el-form-item label="目标系统" prop="target_system">
          <el-select v-model="mapDialog.form.target_system" style="width: 100%">
            <el-option label="HIS" value="HIS" />
            <el-option label="EMR" value="EMR" />
            <el-option label="LIS" value="LIS" />
            <el-option label="PACS" value="PACS" />
          </el-select>
        </el-form-item>
        <el-form-item label="映射类型" prop="mapping_type">
          <el-select v-model="mapDialog.form.mapping_type" style="width: 100%">
            <el-option label="等价" value="equivalent" />
            <el-option label="上位" value="broader" />
            <el-option label="下位" value="narrower" />
            <el-option label="关联" value="related" />
          </el-select>
        </el-form-item>
        <el-form-item label="置信度" prop="confidence">
          <el-select v-model="mapDialog.form.confidence" style="width: 100%">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mapDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="mapDialog.submitting" @click="saveMapping">保存</el-button>
      </template>
    </el-dialog>

    <!-- 导入系统字典 Dialog -->
    <el-dialog v-model="importDialog.visible" title="导入系统字典" width="480px" destroy-on-close>
      <el-form ref="importFormRef" :model="importDialog.form" label-width="100px">
        <el-form-item label="目标系统" prop="target_system">
          <el-select v-model="importDialog.form.target_system" style="width: 100%">
            <el-option label="HIS" value="HIS" />
            <el-option label="EMR" value="EMR" />
            <el-option label="LIS" value="LIS" />
            <el-option label="PACS" value="PACS" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="importDialog.form.category_code" style="width: 100%">
            <el-option
              v-for="cat in categories"
              :key="cat.category_code"
              :label="cat.category_name_cn || cat.category_code"
              :value="cat.category_code"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="importDialog.submitting" @click="doImport">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage } from "element-plus";
import {
  getDictCategories,
  upsertDictCategory,
  getDictStandardItems,
  upsertDictStandardItem,
  getDictSystemItems,
  getDictItemMappings,
  upsertDictItemMapping,
  importSystemDict
} from "@/api/dict";

// --- 当前 Tab ---
const activeTab = ref("categories");

function onTabChange(tab: string) {
  switch (tab) {
    case "categories": loadCategories(); break;
    case "standardItems": loadStdItems(); break;
    case "systemItems": loadSysItems(); break;
    case "mappings": loadMappings(); break;
  }
}

// ========== Tab1: 字典分类 ==========
const categories = ref<any[]>([]);
const catLoading = ref(false);

async function loadCategories() {
  catLoading.value = true;
  try {
    const res = await getDictCategories();
    categories.value = (res as any).data || [];
  } catch {
    // handled by interceptor
  } finally {
    catLoading.value = false;
  }
}

const catDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    category_code: "",
    category_name_cn: "",
    standard_system: "",
    enabled: true
  }
});

function openCategoryDialog(row?: any) {
  if (row) {
    catDialog.isEdit = true;
    catDialog.form = {
      category_code: row.category_code || "",
      category_name_cn: row.category_name_cn || "",
      standard_system: row.standard_system || "",
      enabled: !!row.enabled
    };
  } else {
    catDialog.isEdit = false;
    catDialog.form = { category_code: "", category_name_cn: "", standard_system: "", enabled: true };
  }
  catDialog.visible = true;
}

async function saveCategory() {
  catDialog.submitting = true;
  try {
    await upsertDictCategory(catDialog.form);
    ElMessage.success(catDialog.isEdit ? "编辑成功" : "新增成功");
    catDialog.visible = false;
    loadCategories();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    catDialog.submitting = false;
  }
}

// ========== Tab2: 标准项 ==========
const stdItems = ref<any[]>([]);
const stdItemLoading = ref(false);
const stdItemTotal = ref(0);
const stdItemParams = reactive({
  keyword: "",
  category_code: "",
  page: 1,
  page_size: 20
});

function doSearchStdItems() {
  stdItemParams.page = 1;
  loadStdItems();
}

async function loadStdItems() {
  stdItemLoading.value = true;
  try {
    const params: Record<string, any> = {
      page: stdItemParams.page,
      page_size: stdItemParams.page_size
    };
    if (stdItemParams.keyword) params.keyword = stdItemParams.keyword;
    if (stdItemParams.category_code) params.category_code = stdItemParams.category_code;
    const res = await getDictStandardItems(params);
    stdItems.value = (res as any).data.items;
    stdItemTotal.value = (res as any).data.total;
  } catch {
    // handled
  } finally {
    stdItemLoading.value = false;
  }
}

const stdItemDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    category_code: "",
    item_code: "",
    item_name_cn: "",
    standard_system: "",
    status: "active"
  }
});

function openStdItemDialog(row?: any) {
  if (row) {
    stdItemDialog.isEdit = true;
    stdItemDialog.form = {
      category_code: row.category_code || "",
      item_code: row.item_code || "",
      item_name_cn: row.item_name_cn || "",
      standard_system: row.standard_system || "",
      status: row.status || "active"
    };
  } else {
    stdItemDialog.isEdit = false;
    stdItemDialog.form = { category_code: "", item_code: "", item_name_cn: "", standard_system: "", status: "active" };
  }
  stdItemDialog.visible = true;
}

async function saveStdItem() {
  stdItemDialog.submitting = true;
  try {
    await upsertDictStandardItem(stdItemDialog.form);
    ElMessage.success(stdItemDialog.isEdit ? "编辑成功" : "新增成功");
    stdItemDialog.visible = false;
    loadStdItems();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    stdItemDialog.submitting = false;
  }
}

// ========== Tab3: 系统项 ==========
const sysItems = ref<any[]>([]);
const sysItemLoading = ref(false);
const sysItemParams = reactive({
  target_system: "",
  keyword: ""
});

async function loadSysItems() {
  sysItemLoading.value = true;
  try {
    const params: Record<string, any> = {};
    if (sysItemParams.target_system) params.target_system = sysItemParams.target_system;
    if (sysItemParams.keyword) params.keyword = sysItemParams.keyword;
    const res = await getDictSystemItems(params);
    sysItems.value = (res as any).data || [];
  } catch {
    // handled
  } finally {
    sysItemLoading.value = false;
  }
}

const importDialog = reactive({
  visible: false,
  submitting: false,
  form: { target_system: "", category_code: "" }
});

function openImportDialog() {
  importDialog.form = { target_system: "", category_code: "" };
  importDialog.visible = true;
}

async function doImport() {
  importDialog.submitting = true;
  try {
    await importSystemDict(importDialog.form);
    ElMessage.success("导入完成");
    importDialog.visible = false;
    loadSysItems();
  } catch {
    ElMessage.error("导入失败");
  } finally {
    importDialog.submitting = false;
  }
}

// ========== Tab4: 映射 ==========
const mapItems = ref<any[]>([]);
const mapLoading = ref(false);
const mapTotal = ref(0);
const mapParams = reactive({
  category_code: "",
  page: 1,
  page_size: 20
});

function doSearchMappings() {
  mapParams.page = 1;
  loadMappings();
}

async function loadMappings() {
  mapLoading.value = true;
  try {
    const params: Record<string, any> = {
      page: mapParams.page,
      page_size: mapParams.page_size
    };
    if (mapParams.category_code) params.category_code = mapParams.category_code;
    const res = await getDictItemMappings(params);
    mapItems.value = (res as any).data.items;
    mapTotal.value = (res as any).data.total;
  } catch {
    // handled
  } finally {
    mapLoading.value = false;
  }
}

const mapDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    category_code: "",
    standard_code: "",
    system_code: "",
    target_system: "",
    mapping_type: "equivalent",
    confidence: "high"
  }
});

function openMapDialog(row?: any) {
  if (row) {
    mapDialog.isEdit = true;
    mapDialog.form = {
      category_code: row.category_code || "",
      standard_code: row.standard_code || "",
      system_code: row.system_code || "",
      target_system: row.target_system || "",
      mapping_type: row.mapping_type || "equivalent",
      confidence: row.confidence || "high"
    };
  } else {
    mapDialog.isEdit = false;
    mapDialog.form = {
      category_code: mapParams.category_code || "",
      standard_code: "",
      system_code: "",
      target_system: "",
      mapping_type: "equivalent",
      confidence: "high"
    };
  }
  mapDialog.visible = true;
}

async function saveMapping() {
  mapDialog.submitting = true;
  try {
    await upsertDictItemMapping(mapDialog.form);
    ElMessage.success(mapDialog.isEdit ? "编辑成功" : "新增成功");
    mapDialog.visible = false;
    loadMappings();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    mapDialog.submitting = false;
  }
}

onMounted(loadCategories);
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
