<template>
  <div class="dict-medical">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <div>
            <div class="title">诊断与手术编码体系</div>
            <div class="subtitle">维护院内编码、国家临床版、医保版及后续同步基础数据</div>
          </div>
          <el-radio-group v-model="categoryCode" @change="onCategoryChange">
            <el-radio-button value="diagnosis">诊断</el-radio-button>
            <el-radio-button value="operation">手术</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <div class="toolbar">
        <el-button type="primary" @click="openCodeSetDialog()">新增编码体系</el-button>
        <el-alert
          v-if="authHint"
          :title="authHint"
          type="warning"
          show-icon
          :closable="false"
          class="auth-alert"
        />
      </div>

      <el-table
        v-loading="loading"
        :data="codeSets"
        stripe
        style="margin-top: 12px"
        row-key="code_set_code"
        empty-text="暂无编码体系，请确认已设置 API Token 并完成导入"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="sub-table-wrap">
              <div class="toolbar sub-toolbar">
                <el-button type="primary" size="small" @click="openItemDialog(row.code_set_code)">新增编码项</el-button>
                <el-button size="small" @click="loadItems(row)">刷新编码项</el-button>
                <span class="sub-count">共 {{ row._itemsTotal || 0 }} 项</span>
              </div>
              <el-table
                v-loading="row._itemsLoading"
                :data="row._items || []"
                stripe
                size="small"
                empty-text="展开后点击刷新或等待加载编码项"
              >
                <el-table-column prop="item_code" label="编码" width="180" show-overflow-tooltip />
                <el-table-column prop="item_name_cn" label="名称" min-width="220" show-overflow-tooltip />
                <el-table-column prop="item_name_alias" label="别名" min-width="180" show-overflow-tooltip />
                <el-table-column label="状态" width="90" align="center">
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
        <el-table-column prop="code_set_code" label="编码体系" min-width="220" show-overflow-tooltip />
        <el-table-column prop="code_set_name_cn" label="名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="类别" width="90" align="center">
          <template #default="{ row }">{{ row.category_code === "diagnosis" ? "诊断" : "手术" }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="codeSetTypeTag(row.code_set_type)" size="small">{{ codeSetTypeText(row.code_set_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="standard_system" label="标准体系" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled === false ? 'info' : 'success'" size="small">
              {{ row.enabled === false ? "停用" : "启用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="loadItems(row)">查看编码</el-button>
            <el-button link type="primary" size="small" @click="openCodeSetDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="codeSetDialog.visible" :title="codeSetDialog.isEdit ? '编辑编码体系' : '新增编码体系'" width="520px" destroy-on-close>
      <el-form ref="codeSetFormRef" :model="codeSetDialog.form" label-width="110px">
        <el-form-item label="编码体系" prop="code_set_code">
          <el-input v-model="codeSetDialog.form.code_set_code" :disabled="codeSetDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="code_set_name_cn">
          <el-input v-model="codeSetDialog.form.code_set_name_cn" />
        </el-form-item>
        <el-form-item label="类型" prop="code_set_type">
          <el-select v-model="codeSetDialog.form.code_set_type" style="width: 100%">
            <el-option label="院内" value="clinical" />
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
        <el-form-item label="标准体系" prop="standard_system">
          <el-input v-model="codeSetDialog.form.standard_system" />
        </el-form-item>
        <el-form-item label="版本" prop="version_no">
          <el-input v-model="codeSetDialog.form.version_no" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="codeSetDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="codeSetDialog.submitting" @click="saveCodeSet">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="itemDialog.visible" :title="itemDialog.isEdit ? '编辑编码项' : '新增编码项'" width="520px" destroy-on-close>
      <el-form ref="itemFormRef" :model="itemDialog.form" label-width="100px">
        <el-form-item label="编码" prop="item_code">
          <el-input v-model="itemDialog.form.item_code" :disabled="itemDialog.isEdit" />
        </el-form-item>
        <el-form-item label="名称" prop="item_name_cn">
          <el-input v-model="itemDialog.form.item_name_cn" />
        </el-form-item>
        <el-form-item label="别名" prop="item_name_alias">
          <el-input v-model="itemDialog.form.item_name_alias" />
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
import { getMedicalCodeSets, upsertMedicalCodeSet, getMedicalItems, upsertMedicalItem } from "@/api/dict";

const categoryCode = ref("diagnosis");
const codeSets = ref<any[]>([]);
const loading = ref(false);
const authHint = ref("");

function normalizeCodeSet(cs: any) {
  return {
    ...cs,
    code_set_name_cn: cs.code_set_name_cn || cs.name_cn || "",
    enabled: cs.enabled ?? (cs.status ? cs.status === "active" : true),
    _items: [],
    _itemsLoading: false,
    _itemsPage: 1,
    _itemsPageSize: 20,
    _itemsTotal: 0
  };
}

async function loadCodeSets() {
  loading.value = true;
  authHint.value = "";
  try {
    const res = await getMedicalCodeSets({ category_code: categoryCode.value });
    codeSets.value = ((res as any).data || []).map(normalizeCodeSet);
  } catch (error: any) {
    if (error?.response?.status === 401) {
      authHint.value = "接口未授权：请先在资产管理/平台管理中设置 asset_api_token，或重新登录后刷新。";
    } else if (error?.response?.status === 403) {
      authHint.value = "API Token 无效或已禁用：请清理浏览器中的 asset_api_token 后重新设置有效 Token。";
    }
  } finally {
    loading.value = false;
  }
}

async function loadItems(row: any) {
  row._itemsLoading = true;
  try {
    const res = await getMedicalItems(row.code_set_code, { page: row._itemsPage, page_size: row._itemsPageSize });
    row._items = (res as any).data.items || [];
    row._itemsTotal = (res as any).data.total || 0;
  } finally {
    row._itemsLoading = false;
  }
}

function onCategoryChange() {
  loadCodeSets();
}

function codeSetTypeText(type: string) {
  return type === "clinical" ? "院内" : type === "national" ? "国标" : type === "insurance" ? "医保" : type || "-";
}

function codeSetTypeTag(type: string): any {
  return { clinical: "", national: "success", insurance: "warning" }[type] || "info";
}

const codeSetFormRef = ref<FormInstance>();
const codeSetDialog = reactive({
  visible: false,
  isEdit: false,
  submitting: false,
  form: {
    code_set_code: "",
    code_set_name_cn: "",
    code_set_type: "clinical",
    category_code: "diagnosis",
    standard_system: "",
    version_no: "",
    enabled: true
  }
});

function openCodeSetDialog(row?: any) {
  codeSetDialog.isEdit = !!row;
  codeSetDialog.form = row
    ? {
        code_set_code: row.code_set_code || "",
        code_set_name_cn: row.code_set_name_cn || "",
        code_set_type: row.code_set_type || "clinical",
        category_code: row.category_code || categoryCode.value,
        standard_system: row.standard_system || "",
        version_no: row.version_no || "",
        enabled: row.enabled ?? true
      }
    : {
        code_set_code: "",
        code_set_name_cn: "",
        code_set_type: "clinical",
        category_code: categoryCode.value,
        standard_system: "",
        version_no: "",
        enabled: true
      };
  codeSetDialog.visible = true;
}

async function saveCodeSet() {
  codeSetDialog.submitting = true;
  try {
    await upsertMedicalCodeSet(codeSetDialog.form);
    ElMessage.success(codeSetDialog.isEdit ? "编辑成功" : "新增成功");
    codeSetDialog.visible = false;
    loadCodeSets();
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
    item_name_alias: "",
    category_code: "diagnosis",
    status: "active"
  }
});

function openItemDialog(codeSetCode: string, item?: any) {
  itemDialog.isEdit = !!item;
  itemDialog.form = item
    ? {
        code_set_code: codeSetCode,
        item_code: item.item_code || "",
        item_name_cn: item.item_name_cn || "",
        item_name_alias: item.item_name_alias || "",
        category_code: item.category_code || categoryCode.value,
        status: item.status || "active"
      }
    : {
        code_set_code: codeSetCode,
        item_code: "",
        item_name_cn: "",
        item_name_alias: "",
        category_code: categoryCode.value,
        status: "active"
      };
  itemDialog.visible = true;
}

async function saveItem() {
  itemDialog.submitting = true;
  try {
    await upsertMedicalItem(itemDialog.form);
    ElMessage.success(itemDialog.isEdit ? "编辑成功" : "新增成功");
    itemDialog.visible = false;
    const row = codeSets.value.find(item => item.code_set_code === itemDialog.form.code_set_code);
    if (row) loadItems(row);
  } finally {
    itemDialog.submitting = false;
  }
}

onMounted(loadCodeSets);
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.title { font-size: 16px; font-weight: 600; color: var(--el-text-color-primary); }
.subtitle { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); }
.toolbar { display: flex; align-items: center; gap: 8px; }
.auth-alert { flex: 1; }
.sub-table-wrap { padding: 8px 40px 12px; }
.sub-toolbar { margin-bottom: 8px; }
.sub-count { color: var(--el-text-color-secondary); font-size: 12px; }
</style>