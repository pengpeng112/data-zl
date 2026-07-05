<template>
  <div class="dict-medical">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>诊断与手术编码体系</span>
          <el-radio-group v-model="categoryCode" @change="onCategoryChange">
            <el-radio-button value="diagnosis">诊断</el-radio-button>
            <el-radio-button value="operation">手术</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <div class="toolbar">
        <el-button type="primary" @click="openCodeSetDialog()">新增编码体系</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="codeSets"
        stripe
        style="margin-top: 12px"
        row-key="code_set_code"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="sub-table-wrap">
              <div class="toolbar sub-toolbar">
                <el-button type="primary" size="small" @click="openItemDialog(row.code_set_code)">新增编码项</el-button>
              </div>
              <el-table
                v-loading="row._itemsLoading"
                :data="row._items || []"
                stripe
                size="small"
              >
                <el-table-column prop="item_code" label="编码" width="160" />
                <el-table-column prop="item_name_cn" label="名称" min-width="200" show-overflow-tooltip />
                <el-table-column prop="alias" label="别名" width="200" show-overflow-tooltip />
                <el-table-column label="状态" width="80" align="center">
                  <template #default="{ row: it }">
                    <el-tag :type="it.status === 'active' ? 'success' : 'info'" size="small">
                      {{ it.status === 'active' ? '启用' : '停用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" align="center" fixed="right">
                  <template #default="{ row: it }">
                    <el-button link type="primary" size="small" @click="openItemDialog(it.code_set_code, it)">编辑</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-pagination
                v-if="row._itemsTotal > (row._itemsPageSize || 20)"
                v-model:current-page="row._itemsPage"
                v-model:page-size="row._itemsPageSize"
                :total="row._itemsTotal"
                layout="total, prev, pager, next"
                size="small"
                style="margin-top: 8px; justify-content: flex-end"
                @change="loadItems(row)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="code_set_code" label="编码体系编码" width="160" />
        <el-table-column prop="name_cn" label="名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="codeSetTypeTag(row.code_set_type)" size="small">
              {{ row.code_set_type === 'clinical' ? '临床' : row.code_set_type === 'national' ? '国标' : '医保' }}
            </el-tag>
          </template>
        </el-table-column>
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
            <el-button link type="primary" size="small" @click="openCodeSetDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="codeSetDialog.visible"
      :title="codeSetDialog.isEdit ? '编辑编码体系' : '新增编码体系'"
      width="520px"
      destroy-on-close
    >
      <el-form ref="codeSetFormRef" :model="codeSetDialog.form" label-width="100px">
        <el-form-item label="编码体系编码" prop="code_set_code">
          <el-input v-model="codeSetDialog.form.code_set_code" :disabled="codeSetDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="name_cn">
          <el-input v-model="codeSetDialog.form.name_cn" />
        </el-form-item>
        <el-form-item label="类型" prop="code_set_type">
          <el-select v-model="codeSetDialog.form.code_set_type" style="width: 100%">
            <el-option label="临床" value="clinical" />
            <el-option label="国标" value="national" />
            <el-option label="医保" value="insurance" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类" prop="category_code">
          <el-select v-model="codeSetDialog.form.category_code" style="width: 100%">
            <el-option label="诊断" value="diagnosis" />
            <el-option label="手术" value="operation" />
          </el-select>
        </el-form-item>
        <el-form-item label="标准系统" prop="standard_system">
          <el-input v-model="codeSetDialog.form.standard_system" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="codeSetDialog.form.status" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="codeSetDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="codeSetDialog.submitting" @click="saveCodeSet">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="itemDialog.visible"
      :title="itemDialog.isEdit ? '编辑编码项' : '新增编码项'"
      width="520px"
      destroy-on-close
    >
      <el-form ref="itemFormRef" :model="itemDialog.form" label-width="100px">
        <el-form-item label="编码" prop="item_code">
          <el-input v-model="itemDialog.form.item_code" :disabled="itemDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="item_name_cn">
          <el-input v-model="itemDialog.form.item_name_cn" />
        </el-form-item>
        <el-form-item label="别名" prop="alias">
          <el-input v-model="itemDialog.form.alias" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="itemDialog.form.status" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="itemDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="itemDialog.submitting" @click="saveItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { ElMessage, type FormInstance } from "element-plus";
import {
  getMedicalCodeSets,
  upsertMedicalCodeSet,
  getMedicalItems,
  upsertMedicalItem
} from "@/api/dict";

const categoryCode = ref("diagnosis");
const codeSets = ref<any[]>([]);
const loading = ref(false);

async function loadCodeSets() {
  loading.value = true;
  try {
    const res = await getMedicalCodeSets({ category_code: categoryCode.value });
    codeSets.value = (res as any).data.map((cs: any) => ({
      ...cs,
      _items: [],
      _itemsLoading: false,
      _itemsPage: 1,
      _itemsPageSize: 20,
      _itemsTotal: 0
    }));
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false;
  }
}

async function loadItems(row: any) {
  row._itemsLoading = true;
  try {
    const res = await getMedicalItems(row.code_set_code, {
      page: row._itemsPage,
      page_size: row._itemsPageSize
    });
    row._items = (res as any).data.items;
    row._itemsTotal = (res as any).data.total;
  } catch {
    // handled by interceptor
  } finally {
    row._itemsLoading = false;
  }
}

function onCategoryChange() {
  loadCodeSets();
}

function codeSetTypeTag(type: string): any {
  const map: Record<string, string> = { clinical: "", national: "success", insurance: "warning" }
  return map[type] || ""
}

const codeSetFormRef = ref<FormInstance>();
const codeSetDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    code_set_code: "",
    name_cn: "",
    code_set_type: "clinical",
    category_code: "diagnosis",
    standard_system: "",
    status: "active"
  }
});

function openCodeSetDialog(row?: any) {
  if (row) {
    codeSetDialog.isEdit = true;
    codeSetDialog.form = {
      code_set_code: row.code_set_code || "",
      name_cn: row.name_cn || "",
      code_set_type: row.code_set_type || "clinical",
      category_code: row.category_code || categoryCode.value,
      standard_system: row.standard_system || "",
      status: row.status || "active"
    };
  } else {
    codeSetDialog.isEdit = false;
    codeSetDialog.form = {
      code_set_code: "",
      name_cn: "",
      code_set_type: "clinical",
      category_code: categoryCode.value,
      standard_system: "",
      status: "active"
    };
  }
  codeSetDialog.visible = true;
}

async function saveCodeSet() {
  codeSetDialog.submitting = true;
  try {
    await upsertMedicalCodeSet(codeSetDialog.form);
    ElMessage.success(codeSetDialog.isEdit ? "编辑成功" : "新增成功");
    codeSetDialog.visible = false;
    loadCodeSets();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    codeSetDialog.submitting = false;
  }
}

const itemFormRef = ref<FormInstance>();
const itemDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    code_set_code: "",
    item_code: "",
    item_name_cn: "",
    alias: "",
    status: "active"
  }
});

function openItemDialog(codeSetCode: string, item?: any) {
  if (item) {
    itemDialog.isEdit = true;
    itemDialog.form = {
      code_set_code: codeSetCode,
      item_code: item.item_code || "",
      item_name_cn: item.item_name_cn || "",
      alias: item.alias || "",
      status: item.status || "active"
    };
  } else {
    itemDialog.isEdit = false;
    itemDialog.form = {
      code_set_code: codeSetCode,
      item_code: "",
      item_name_cn: "",
      alias: "",
      status: "active"
    };
  }
  itemDialog.visible = true;
}

async function saveItem() {
  itemDialog.submitting = true;
  try {
    await upsertMedicalItem(itemDialog.form);
    ElMessage.success(itemDialog.isEdit ? "编辑成功" : "新增成功");
    itemDialog.visible = false;
    loadCodeSets();
  } catch {
    ElMessage.error("保存失败");
  } finally {
    itemDialog.submitting = false;
  }
}

onMounted(loadCodeSets);
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sub-table-wrap {
  padding: 8px 40px 12px;
}
.sub-toolbar {
  margin-bottom: 8px;
}
</style>
