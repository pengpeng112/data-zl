<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { hasPerms } from "@/utils/auth";
import {
  activateRecipeVersion,
  approveRecipeVersion,
  copyRecipeVersion,
  createRecipe,
  deprecateRecipeVersion,
  generateRecipeSql,
  getRecipeVersion,
  listRecipeVersions,
  listRecipes,
  rejectRecipeVersion,
  submitRecipeVersion,
  updateRecipeVersion,
  validateRecipeDraft,
  type RecipeItem,
  type RecipeJoin,
  type RecipePrimaryTable
} from "@/api/recipes";

const statusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "已提交",
  approved: "已批准",
  active: "已启用",
  deprecated: "已停用"
};

const rows = ref<RecipeItem[]>([]);
const total = ref(0);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(30);
const filters = reactive({ keyword: "", status: "", domain: "", business_domain: "" });
const statusOptions = Object.entries(statusLabels).map(([value, label]) => ({ value, label }));

const editorVisible = ref(false);
const editorLoading = ref(false);
const editorMode = ref<"create" | "edit" | "view">("create");
const editorForm = reactive({
  recipe_id: "",
  version: 0,
  recipe_name: "",
  description: "",
  domain: "",
  business_domain: "",
  primary_tables: "[]",
  joins: "[]"
});
const editorTitle = computed(() => {
  if (editorMode.value === "create") return "新建关系配方草稿";
  return `${editorMode.value === "edit" ? "编辑" : "查看"}配方 ${editorForm.recipe_id} v${editorForm.version}`;
});

const versionsVisible = ref(false);
const versionsLoading = ref(false);
const versions = ref<RecipeItem[]>([]);
const selectedRecipeId = ref("");
const selectedVersion = ref<number | null>(null);
const selectedVersionItem = computed(() => versions.value.find(item => item.version === selectedVersion.value) || null);

const sqlVisible = ref(false);
const sqlLoading = ref(false);
const sqlText = ref("");
const sqlTitle = ref("SQL 预览（仅生成，不执行）");

function errorMessage(error: unknown, fallback: string) {
  const candidate = error as { response?: { data?: { detail?: string; message?: string } }; message?: string };
  return candidate?.response?.data?.detail || candidate?.response?.data?.message || candidate?.message || fallback;
}

function resetEditor() {
  Object.assign(editorForm, { recipe_id: "", version: 0, recipe_name: "", description: "", domain: "", business_domain: "", primary_tables: "[]", joins: "[]" });
}

function setEditor(item: RecipeItem, mode: "create" | "edit" | "view") {
  editorMode.value = mode;
  editorForm.recipe_id = item.recipe_id;
  editorForm.version = item.version;
  editorForm.recipe_name = item.recipe_name || "";
  editorForm.description = item.description || "";
  editorForm.domain = item.domain || "";
  editorForm.business_domain = item.business_domain || "";
  editorForm.primary_tables = JSON.stringify(item.primary_tables || [], null, 2);
  editorForm.joins = JSON.stringify(item.joins || [], null, 2);
  editorVisible.value = true;
}

function validatePayload() {
  return validateRecipeDraft(editorForm.primary_tables, editorForm.joins);
}

async function load() {
  loading.value = true;
  try {
    const response = await listRecipes({ ...filters, page: page.value, page_size: pageSize.value });
    rows.value = response.data?.items || [];
    total.value = response.data?.total || 0;
  } catch (error) {
    ElMessage.error(errorMessage(error, "加载关系配方失败，请检查筛选条件或登录状态"));
  } finally {
    loading.value = false;
  }
}

function search() {
  page.value = 1;
  void load();
}

const transitioning = ref(false);

async function transition(row: RecipeItem, action: "submit" | "approve" | "reject" | "activate" | "deprecate") {
  if (transitioning.value) return;
  transitioning.value = true;
  try {
    let response;
    if (action === "submit") response = await submitRecipeVersion(row.recipe_id, row.version);
    else if (action === "approve") response = await approveRecipeVersion(row.recipe_id, row.version);
    else if (action === "reject") response = await rejectRecipeVersion(row.recipe_id, row.version);
    else if (action === "activate") response = await activateRecipeVersion(row.recipe_id, row.version);
    else response = await deprecateRecipeVersion(row.recipe_id, row.version);
    const labels: Record<string, string> = { submit: "已提交审核", approve: "已批准", reject: "已驳回", activate: "已激活", deprecate: "已停用" };
    ElMessage.success(`${labels[action]}（当前状态：${response.data?.status || row.status}）`);
    await load();
  } catch (error) {
    ElMessage.error(errorMessage(error, "状态流转失败"));
  } finally {
    transitioning.value = false;
  }
}

function openCreate() {
  resetEditor();
  editorMode.value = "create";
  editorVisible.value = true;
}

async function openEdit(row: RecipeItem) {
  editorLoading.value = true;
  try {
    const response = await getRecipeVersion(row.recipe_id, row.version);
    setEditor(response.data, row.status === "draft" && hasPerms("recipe.edit") ? "edit" : "view");
  } catch (error) {
    ElMessage.error(errorMessage(error, "读取配方版本失败"));
  } finally {
    editorLoading.value = false;
  }
}

async function saveEditor() {
  try {
    const { primaryTables, joins } = validatePayload();
    const payload = {
      recipe_name: editorForm.recipe_name.trim() || undefined,
      description: editorForm.description.trim() || undefined,
      domain: editorForm.domain.trim() || undefined,
      business_domain: editorForm.business_domain.trim() || undefined,
      primary_tables: primaryTables as RecipePrimaryTable[],
      joins: joins as RecipeJoin[]
    };
    if (editorMode.value === "create") {
      if (!editorForm.recipe_id.trim()) throw new Error("请输入配方编码");
      await createRecipe({ recipe_id: editorForm.recipe_id.trim(), ...payload });
      ElMessage.success("关系配方草稿已创建");
    } else {
      await updateRecipeVersion(editorForm.recipe_id, editorForm.version, payload);
      ElMessage.success("关系配方草稿已保存");
    }
    editorVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(errorMessage(error, "保存失败，请修正表结构或关联 JSON 后重试"));
  }
}

async function openVersions(row: RecipeItem) {
  selectedRecipeId.value = row.recipe_id;
  selectedVersion.value = row.version;
  versionsVisible.value = true;
  versionsLoading.value = true;
  try {
    const response = await listRecipeVersions(row.recipe_id);
    versions.value = response.data || [];
  } catch (error) {
    ElMessage.error(errorMessage(error, "加载版本列表失败"));
  } finally {
    versionsLoading.value = false;
  }
}

async function switchVersion(version: number) {
  if (version === selectedVersion.value) return;
  versionsLoading.value = true;
  try {
    const response = await getRecipeVersion(selectedRecipeId.value, version);
    selectedVersion.value = response.data.version;
    versions.value = versions.value.map(item => (item.version === version ? response.data : item));
    ElMessage.success(`已切换到 ${selectedRecipeId.value} v${version}`);
  } catch (error) {
    ElMessage.error(errorMessage(error, "切换版本失败"));
  } finally {
    versionsLoading.value = false;
  }
}

async function copyVersion(row: RecipeItem) {
  try {
    await copyRecipeVersion(row.recipe_id, row.version);
    ElMessage.success(`已基于 v${row.version} 创建新的草稿版本`);
    await load();
  } catch (error) {
    ElMessage.error(errorMessage(error, "复制版本失败"));
  }
}

async function previewSql(row: RecipeItem) {
  sqlLoading.value = true;
  sqlVisible.value = true;
  sqlText.value = "";
  sqlTitle.value = `${row.recipe_id} v${row.version} · SQL 预览（仅生成，不执行）`;
  try {
    const response = await generateRecipeSql(row.recipe_id, row.version);
    sqlText.value = response.data.sql;
  } catch (error) {
    sqlVisible.value = false;
    ElMessage.error(errorMessage(error, "SQL 生成失败；请确认主表和关联条件完整且安全"));
  } finally {
    sqlLoading.value = false;
  }
}

function downloadText(fileName: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName.replace(/[^A-Za-z0-9._-]+/g, "_");
  link.click();
  URL.revokeObjectURL(url);
}

function exportRecipe(row: RecipeItem) {
  const payload = {
    recipe_id: row.recipe_id,
    version: row.version,
    recipe_name: row.recipe_name,
    status: row.status,
    domain: row.domain,
    business_domain: row.business_domain,
    description: row.description,
    primary_tables: row.primary_tables || [],
    joins: row.joins || []
  };
  downloadText(`${row.recipe_id}-v${row.version}.json`, JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
}

function downloadSql() {
  if (!sqlText.value) return;
  const stem = sqlTitle.value.split(" · ")[0] || "recipe";
  downloadText(`${stem}.sql`, sqlText.value, "text/plain;charset=utf-8");
}

onMounted(load);
</script>

<template>
  <div class="p-4">
    <RePageHeader title="关系配方库" subtitle="检索、版本化维护、复制和只读 SQL 预览；不执行目标库 DDL。">
      <template #actions><el-button v-perms="'recipe.create'" type="primary" @click="openCreate">新建草稿</el-button></template>
    </RePageHeader>

    <el-card class="mt-4">
      <el-form inline @submit.prevent="search">
        <el-form-item label="关键词"><el-input v-model="filters.keyword" clearable placeholder="编码、名称、说明或主表" @keyup.enter="search" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 130px"><el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" /></el-select></el-form-item>
        <el-form-item label="业务域"><el-input v-model="filters.domain" clearable placeholder="精确匹配" /></el-form-item>
        <el-form-item label="业务分类"><el-input v-model="filters.business_domain" clearable placeholder="精确匹配" /></el-form-item>
        <el-form-item><el-button type="primary" @click="search">查询</el-button><el-button @click="Object.assign(filters, { keyword: '', status: '', domain: '', business_domain: '' }); search()">重置</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" class="mt-4">
      <el-table :data="rows" row-key="id" @row-dblclick="openEdit">
        <el-table-column prop="recipe_id" label="配方编码" min-width="180" show-overflow-tooltip />
        <el-table-column prop="recipe_name" label="名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="version" label="版本" width="75" />
        <el-table-column label="状态" width="95"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : row.status === 'draft' ? 'info' : 'warning'">{{ statusLabels[row.status] || row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="domain" label="业务域" min-width="110" show-overflow-tooltip />
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">{{ row.status === "draft" && hasPerms("recipe.edit") ? "详情/编辑" : "详情" }}</el-button>
            <el-button size="small" text @click="openVersions(row)">版本</el-button>
            <el-button v-perms="'recipe.create'" size="small" text @click="copyVersion(row)">复制版本</el-button>
            <el-button v-perms="'recipe.sql_generate'" size="small" text type="success" @click="previewSql(row)">SQL预览</el-button>
            <el-button v-if="row.status === 'draft'" v-perms="'recipe.edit'" size="small" text type="warning" @click="transition(row, 'submit')">提交审核</el-button>
            <el-button v-if="row.status === 'submitted'" v-perms="'recipe.review'" size="small" text type="success" @click="transition(row, 'approve')">批准</el-button>
            <el-button v-if="row.status === 'submitted'" v-perms="'recipe.review'" size="small" text type="danger" @click="transition(row, 'reject')">驳回</el-button>
            <el-button v-if="row.status === 'approved'" v-perms="'recipe.activate'" size="small" text type="success" @click="transition(row, 'activate')">激活</el-button>
            <el-button v-if="row.status === 'active'" v-perms="'recipe.activate'" size="small" text type="info" @click="transition(row, 'deprecate')">停用</el-button>
            <el-button size="small" text @click="exportRecipe(row)">导出JSON</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !rows.length" description="暂无符合条件的关系配方" />
      <div class="mt-4 flex justify-end"><el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[30, 60, 100]" layout="total, sizes, prev, pager, next" @current-change="load" @size-change="search" /></div>
    </el-card>

    <el-dialog v-model="editorVisible" :title="editorTitle" width="900px" destroy-on-close>
      <el-form v-loading="editorLoading" label-width="105px">
        <el-form-item label="配方编码" required><el-input v-model="editorForm.recipe_id" :disabled="editorMode !== 'create'" maxlength="200" show-word-limit /></el-form-item>
        <el-form-item label="配方名称"><el-input v-model="editorForm.recipe_name" :disabled="editorMode === 'view'" maxlength="200" /></el-form-item>
        <el-form-item label="业务域"><el-input v-model="editorForm.domain" :disabled="editorMode === 'view'" /></el-form-item>
        <el-form-item label="业务分类"><el-input v-model="editorForm.business_domain" :disabled="editorMode === 'view'" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="editorForm.description" :disabled="editorMode === 'view'" type="textarea" :rows="2" maxlength="2000" show-word-limit /></el-form-item>
        <el-form-item label="主表 JSON" required><el-input v-model="editorForm.primary_tables" :readonly="editorMode === 'view'" type="textarea" :rows="7" placeholder='例如：[ { "table": "HIS.PAT_VISIT", "alias": "v" } ]' /><div class="text-xs text-gray-500">至少一张表；每项使用 table 或 name 字段。多张表时还需按顺序填写关联条件。</div></el-form-item>
        <el-form-item label="关联 JSON"><el-input v-model="editorForm.joins" :readonly="editorMode === 'view'" type="textarea" :rows="7" placeholder='例如：[ { "join_type": "LEFT", "from": "v", "to": "m", "on": "v.PATIENT_ID = m.PATIENT_ID" } ]' /><div class="text-xs text-gray-500">只填写结构化关联条件；SQL 预览接口会拒绝危险字符和非支持的连接类型。</div></el-form-item>
      </el-form>
      <template #footer><el-button @click="editorVisible = false">{{ editorMode === "view" ? "关闭" : "取消" }}</el-button><el-button v-if="editorMode !== 'view'" v-perms="editorMode === 'create' ? 'recipe.create' : 'recipe.edit'" type="primary" @click="saveEditor">保存草稿</el-button></template>
    </el-dialog>

    <el-dialog v-model="versionsVisible" :title="`${selectedRecipeId} · 版本列表`" width="850px">
      <el-table v-loading="versionsLoading" :data="versions" row-key="id">
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column label="状态" width="100"><template #default="{ row }">{{ statusLabels[row.status] || row.status }}</template></el-table-column>
        <el-table-column prop="description" label="说明" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="190" />
        <el-table-column label="操作" width="120"><template #default="{ row }"><el-button size="small" text type="primary" :disabled="row.version === selectedVersion" @click="switchVersion(row.version)">{{ row.version === selectedVersion ? "当前版本" : "切换查看" }}</el-button></template></el-table-column>
      </el-table>
      <el-descriptions v-if="selectedVersionItem" class="mt-3" :column="2" border>
        <el-descriptions-item label="配方名称">{{ selectedVersionItem.recipe_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="业务域">{{ selectedVersionItem.domain || "-" }}</el-descriptions-item>
        <el-descriptions-item label="主表 JSON" :span="2"><pre class="m-0 whitespace-pre-wrap">{{ JSON.stringify(selectedVersionItem.primary_tables || [], null, 2) }}</pre></el-descriptions-item>
        <el-descriptions-item label="关联 JSON" :span="2"><pre class="m-0 whitespace-pre-wrap">{{ JSON.stringify(selectedVersionItem.joins || [], null, 2) }}</pre></el-descriptions-item>
      </el-descriptions>
      <el-alert class="mt-3" type="info" :closable="false" title="版本切换只改变当前查看版本，不会激活、停用或执行任何目标库操作。" />
    </el-dialog>

    <el-dialog v-model="sqlVisible" :title="sqlTitle" width="850px"><el-input v-loading="sqlLoading" :model-value="sqlText" type="textarea" :rows="18" readonly /><template #footer><el-button v-perms="'recipe.sql_generate'" :disabled="!sqlText" @click="downloadSql">下载SQL</el-button><el-button @click="sqlVisible = false">关闭</el-button></template></el-dialog>
  </div>
</template>
