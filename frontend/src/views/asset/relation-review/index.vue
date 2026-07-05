<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { useRouter } from "vue-router";
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
const relations = ref<Relation[]>([]);
const allRelations = ref<Relation[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const isEdit = ref(false);
const editId = ref(0);
const form = ref({ from_table: "", from_columns: "", to_table: "", to_columns: "", join_condition: "", cardinality: "", confidence: "", note: "" });

const systemOptions = ref<SystemOption[]>([]);
const filters = reactive({ system_code: "", confidence: "", validation_status: "", keyword: "" });

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

function applyFilters() {
  let result = [...allRelations.value];
  if (filters.system_code) {
    result = result.filter(r => r.system_code === filters.system_code);
  }
  if (filters.confidence) {
    result = result.filter(r => r.confidence === filters.confidence);
  }
  if (filters.validation_status) {
    result = result.filter(r => r.validation_status === filters.validation_status);
  }
  if (filters.keyword) {
    const kw = filters.keyword.toLowerCase();
    result = result.filter(r =>
      (r.from_table && r.from_table.toLowerCase().includes(kw)) ||
      (r.to_table && r.to_table.toLowerCase().includes(kw)) ||
      (r.join_condition && r.join_condition.toLowerCase().includes(kw)) ||
      (r.note && r.note.toLowerCase().includes(kw))
    );
  }
  relations.value = result;
}

function resetFilters() {
  filters.system_code = "";
  filters.confidence = "";
  filters.validation_status = "";
  filters.keyword = "";
  relations.value = [...allRelations.value];
}

async function loadRelations() {
  loading.value = true;
  try {
    const params: Record<string, string> = {};
    if (filters.system_code) params.system_code = filters.system_code;
    if (filters.confidence) params.confidence = filters.confidence;
    if (filters.validation_status) params.validation_status = filters.validation_status;
    if (filters.keyword) params.keyword = filters.keyword;
    const res = await http.request<any>("get", "/api/v1/relations/list", { params });
    allRelations.value = res.data || [];
    relations.value = [...allRelations.value];
  } finally {
    loading.value = false;
  }
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
  <div>
    <el-card style="margin-bottom:16px">
      <el-form :inline="true" :model="filters" size="small">
        <el-form-item label="所属系统">
          <el-select v-model="filters.system_code" placeholder="全部" clearable style="width:160px" @change="applyFilters">
            <el-option v-for="s in systemOptions" :key="s.system_code" :label="s.system_name_cn || s.system_code" :value="s.system_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="置信度">
          <el-select v-model="filters.confidence" placeholder="全部" clearable style="width:100px" @change="applyFilters">
            <el-option label="A - 高" value="A" />
            <el-option label="B - 中" value="B" />
            <el-option label="C - 低" value="C" />
          </el-select>
        </el-form-item>
        <el-form-item label="验证状态">
          <el-select v-model="filters.validation_status" placeholder="全部" clearable style="width:130px" @change="applyFilters">
            <el-option label="已验证" value="verified" />
            <el-option label="未验证" value="unverified" />
            <el-option label="已批准" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索表名/字段/条件" clearable style="width:220px" @input="applyFilters" @clear="applyFilters" />
        </el-form-item>
        <el-form-item>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header><span>关系复核工作台</span></template>
      <el-table :data="relations" v-loading="loading" size="small">
        <el-table-column prop="from_table" label="来源表" width="180" show-overflow-tooltip />
        <el-table-column prop="from_columns" label="来源字段" width="150" show-overflow-tooltip />
        <el-table-column prop="to_table" label="目标表" width="180" show-overflow-tooltip />
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
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="success" @click="handleApprove(row.id)">批准</el-button>
            <el-button size="small" text type="danger" @click="handleReject(row.id)">驳回</el-button>
            <el-button size="small" text @click="showMappings(row.id)">字段映射</el-button>
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text @click="openAudit(row)">审计</el-button>
          </template>
        </el-table-column>
      </el-table>
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
          <el-select v-model="form.confidence" style="width:100%">
            <el-option label="A - 高" value="A" />
            <el-option label="B - 中" value="B" />
            <el-option label="C - 低" value="C" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRelation">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="mappingsDrawerVisible" title="字段映射" size="600px">
      <template #header>
        <span>字段映射</span>
        <span v-if="currentMappingRel" style="color:#909399;font-size:13px;margin-left:12px">
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
