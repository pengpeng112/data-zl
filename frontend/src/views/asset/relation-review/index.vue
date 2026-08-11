<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { http } from "@/utils/http";
import { ElMessage } from "element-plus";

interface Relation {
  id: number;
  rel_id: number;
  from_table: string;
  from_columns: string;
  to_table: string;
  to_columns: string;
  join_condition: string;
  cardinality: string;
  confidence: string;
  validation_level: string;
  validation_status: string;
  validation_note: string;
  note: string;
  system_code?: string;
  relation_class?: string;
  from_system_code?: string;
  to_system_code?: string;
  from_table_name_cn?: string;
  to_table_name_cn?: string;
  validation_metrics?: string;
}

interface FieldMapping {
  from_table?: string;
  from_column?: string;
  to_table?: string;
  to_column?: string;
  match_type?: string;
  note?: string;
}

interface SystemOption {
  system_code: string;
  system_name_cn?: string;
}

const router = useRouter();
const route = useRoute();
const relations = ref<Relation[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(30);
const loading = ref(false);
const dialogVisible = ref(false);
const isEdit = ref(false);
const editId = ref(0);
const form = ref({ from_table: "", from_columns: "", to_table: "", to_columns: "", join_condition: "", cardinality: "", confidence: "", note: "" });

const systemOptions = ref<SystemOption[]>([]);
const filters = reactive({ system_code: "", confidence: "", review_status: "", keyword: "" });
const relationClass = ref(String(route.query.class || ""));
const selectedRelations = ref<Relation[]>([]);
const classTabs = [
  { value: "", label: "全部关系" },
  { value: "pending", label: "待复核" },
  { value: "confirmed", label: "已确认" },
  { value: "rejected", label: "已拒绝" },
  { value: "candidate", label: "候选关系" },
  { value: "lineage", label: "同步/镜像血缘" },
  { value: "dependency", label: "视图依赖" }
];

const mappingsDrawerVisible = ref(false);
const mappings = ref<FieldMapping[]>([]);
const mappingsLoading = ref(false);
const currentMappingRel = ref<Relation | null>(null);

async function loadSystemOptions() {
  try {
    const res = await http.request<any>("get", "/api/v1/systems");
    systemOptions.value = res.data || [];
  } catch { /* ignore */ }
}

function resetFilters() {
  filters.system_code = "";
  filters.confidence = "";
  filters.review_status = "";
  filters.keyword = "";
  relationClass.value = "";
  page.value = 1;
  loadRelations();
}

async function loadRelations() {
  loading.value = true;
  try {
    const params: Record<string, string | number> = { page: page.value, page_size: pageSize.value };
    if (filters.system_code) params.system_code = filters.system_code;
    if (filters.confidence) params.confidence = filters.confidence;
    if (filters.review_status) params.review_status = filters.review_status;
    if (filters.keyword) params.keyword = filters.keyword;
    if (relationClass.value) params.relation_class = relationClass.value;
    const res = await http.request<any>("get", "/api/v1/relations/list", { params });
    relations.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } finally {
    loading.value = false;
  }
}

function changeClass() {
  page.value = 1;
  router.replace({ path: "/asset/relation-review", query: relationClass.value ? { class: relationClass.value } : {} });
  loadRelations();
}

function openEdit(row: Relation) {
  isEdit.value = true;
  editId.value = row.id;
  form.value = {
    from_table: row.from_table || "",
    from_columns: row.from_columns || "",
    to_table: row.to_table || "",
    to_columns: row.to_columns || "",
    join_condition: row.join_condition || "",
    cardinality: row.cardinality || "",
    confidence: row.confidence || "",
    note: row.note || ""
  };
  dialogVisible.value = true;
}

async function saveRelation() {
  try {
    if (isEdit.value) {
      await http.request("patch", `/api/v1/relations/${editId.value}`, { data: form.value });
      ElMessage.success("修改成功");
    }
    dialogVisible.value = false;
    loadRelations();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  }
}

async function updateField(relId: number, field: string, value: string) {
  try {
    await http.request("patch", `/api/v1/relations/${relId}`, { data: { [field]: value } });
    ElMessage.success("已更新");
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "更新失败");
  }
}

function getConfidenceType(c: string) {
  if (c === "A") return "success";
  if (c === "B") return "warning";
  if (c === "C") return "danger";
  return "info";
}

async function handleApprove(relId: number) {
  try {
    await http.request("patch", `/api/v1/relations/${relId}/review`, { params: { action: "approve" } });
    ElMessage.success("已批准");
    loadRelations();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function handleReject(relId: number) {
  try {
    await http.request("patch", `/api/v1/relations/${relId}/review`, { params: { action: "reject" } });
    ElMessage.success("已驳回");
    loadRelations();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function batchReview(action: "approve" | "reject") {
  if (!selectedRelations.value.length) {
    ElMessage.warning("请先选择关系");
    return;
  }
  try {
    await http.request("post", "/api/v1/relations/batch-review", {
      data: { relation_ids: selectedRelations.value.map(row => row.id), action }
    });
    ElMessage.success(`已批量${action === "approve" ? "批准" : "驳回"} ${selectedRelations.value.length} 条关系`);
    selectedRelations.value = [];
    loadRelations();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "批量处理失败");
  }
}

async function showMappings(relId: number) {
  currentMappingRel.value = relations.value.find(r => r.id === relId) || null;
  mappingsDrawerVisible.value = true;
  mappingsLoading.value = true;
  mappings.value = [];
  try {
    const res = await http.request<any>("get", "/api/v1/relations/field-mappings", { params: { rel_id: relId } });
    mappings.value = res.data || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "获取字段映射失败");
  } finally {
    mappingsLoading.value = false;
  }
}

function openAudit(row: Relation) {
  router.push({ path: "/ops/audit", query: { entity_ref: `relation:${row.id}` } });
}

onMounted(() => {
  loadSystemOptions();
  loadRelations();
});
</script>

<template>
  <div class="relation-review-page">
    <RePageHeader
      title="关系复核中心"
      subtitle="统一查询正式、候选、同步血缘和视图依赖关系；所有人工操作保留审计。"
    />

    <el-tabs v-model="relationClass" class="relation-tabs" @change="changeClass">
      <el-tab-pane v-for="tab in classTabs" :key="tab.value" :label="tab.label" :name="tab.value" />
    </el-tabs>

    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters" size="small">
        <el-form-item label="所属系统">
          <el-select v-model="filters.system_code" placeholder="全部" clearable class="system-filter" @change="loadRelations">
            <el-option v-for="s in systemOptions" :key="s.system_code" :label="s.system_name_cn || s.system_code" :value="s.system_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="置信度">
          <el-select v-model="filters.confidence" placeholder="全部" clearable class="confidence-filter" @change="loadRelations">
            <el-option label="A - 高" value="A" />
            <el-option label="B - 中" value="B" />
            <el-option label="C - 低" value="C" />
          </el-select>
        </el-form-item>
        <el-form-item label="验证状态">
          <el-select v-model="filters.review_status" placeholder="全部" clearable class="status-filter" @change="loadRelations">
            <el-option label="已验证" value="verified" />
            <el-option label="未验证" value="unverified" />
            <el-option label="已批准" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索中英文表名/字段/条件" clearable class="keyword-filter" @keyup.enter="loadRelations" @clear="loadRelations" />
        </el-form-item>
        <el-form-item>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header><div class="review-header"><span>关系清单（{{ total }}）</span><div><el-button v-perms="'asset.relation.review'" size="small" type="success" :disabled="!selectedRelations.length" @click="batchReview('approve')">批量批准</el-button><el-button v-perms="'asset.relation.review'" size="small" type="danger" :disabled="!selectedRelations.length" @click="batchReview('reject')">批量驳回</el-button></div></div></template>
      <el-table :data="relations" v-loading="loading" size="small" @selection-change="selectedRelations = $event">
        <el-table-column type="selection" width="44" />
        <el-table-column label="来源表" width="220" show-overflow-tooltip><template #default="{ row }"><div>{{ row.from_table_name_cn || row.from_table }}</div><small v-if="row.from_table_name_cn">{{ row.from_table }}</small></template></el-table-column>
        <el-table-column prop="from_columns" label="来源字段" width="150" show-overflow-tooltip />
        <el-table-column label="目标表" width="220" show-overflow-tooltip><template #default="{ row }"><div>{{ row.to_table_name_cn || row.to_table }}</div><small v-if="row.to_table_name_cn">{{ row.to_table }}</small></template></el-table-column>
        <el-table-column prop="to_columns" label="目标字段" width="150" show-overflow-tooltip />
        <el-table-column prop="join_condition" label="关联条件" width="200" show-overflow-tooltip />
        <el-table-column prop="confidence" label="置信度" width="80">
          <template #default="{ row }">
            <el-tag :type="getConfidenceType(row.confidence)" size="small">{{ row.confidence }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="validation_status" label="验证状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.validation_status === 'verified' ? 'success' : 'warning'" size="small">{{ row.validation_status || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="150" show-overflow-tooltip />
        <el-table-column prop="relation_class" label="关系类别" width="120" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button v-perms="'asset.relation.review'" size="small" text type="success" @click="handleApprove(row.id)">批准</el-button>
            <el-button v-perms="'asset.relation.review'" size="small" text type="danger" @click="handleReject(row.id)">驳回</el-button>
            <el-button size="small" text @click="showMappings(row.id)">字段映射</el-button>
            <el-button v-perms="'asset.relation.review'" size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text @click="openAudit(row)">审计</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[30, 50, 100, 200]" layout="total, sizes, prev, pager, next" class="pager" @current-change="loadRelations" @size-change="loadRelations" />
    </el-card>

    <el-dialog v-model="dialogVisible" title="编辑关系" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="来源表"><el-input v-model="form.from_table" /></el-form-item>
        <el-form-item label="来源字段"><el-input v-model="form.from_columns" /></el-form-item>
        <el-form-item label="目标表"><el-input v-model="form.to_table" /></el-form-item>
        <el-form-item label="目标字段"><el-input v-model="form.to_columns" /></el-form-item>
        <el-form-item label="关联条件"><el-input v-model="form.join_condition" type="textarea" /></el-form-item>
        <el-form-item label="基数"><el-input v-model="form.cardinality" placeholder="1:1/1:N/N:M" /></el-form-item>
        <el-form-item label="置信度">
          <el-select v-model="form.confidence" class="full-width">
            <el-option label="A - 高" value="A" />
            <el-option label="B - 中" value="B" />
            <el-option label="C - 低" value="C" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button v-perms="'asset.relation.review'" type="primary" @click="saveRelation">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="mappingsDrawerVisible" title="字段映射" size="600px">
      <template #header>
        <span>字段映射</span>
        <span v-if="currentMappingRel" class="mapping-subtitle">
          {{ currentMappingRel.from_table }} &rarr; {{ currentMappingRel.to_table }}
        </span>
      </template>
      <el-table v-loading="mappingsLoading" :data="mappings" size="small">
        <el-table-column prop="from_column" label="来源字段" width="200" show-overflow-tooltip />
        <el-table-column prop="to_column" label="目标字段" width="200" show-overflow-tooltip />
        <el-table-column prop="match_type" label="匹配类型" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.match_type" size="small">{{ row.match_type }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="!mappingsLoading && mappings.length === 0" description="暂无字段映射数据" />
    </el-drawer>
  </div>
</template>


<style scoped>
.relation-review-page {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}

.filter-card,
.review-card {
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-md);
  box-shadow: var(--re-shadow-sm);
}

.filter-card {
  margin-bottom: 16px;
}
.relation-tabs { margin-bottom: 12px; }
.review-header { display: flex; align-items: center; justify-content: space-between; }
.pager { justify-content: flex-end; margin-top: 16px; }

.mapping-subtitle {
  margin-left: 12px;
  color: var(--re-text-secondary);
  font-size: 13px;
}

.system-filter { width: 160px; }
.confidence-filter { width: 100px; }
.status-filter { width: 130px; }
.keyword-filter { width: 220px; }
.full-width { width: 100%; }
</style>
