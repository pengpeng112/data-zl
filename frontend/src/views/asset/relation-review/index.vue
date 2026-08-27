<script setup lang="ts">
import { ref, reactive, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  approveRelationReview,
  batchReviewRelations,
  getRelationFieldMappings,
  getRelationFieldMappingsFor,
  getRelationListCounts,
  getRelationReviews,
  getRelationsList,
  legacyReviewRelation,
  listSystems,
  rejectRelationReview,
  updateRelation
} from "@/api/asset";
import { usePagedList } from "@/composables/usePagedList";
import { ElMessage } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import {
  RELATION_CLASS_TABS,
  normalizeRelationClass,
  relationClassQuery,
  relationEvidenceKind,
  relationEvidenceLabel,
  displayRelationColumns
} from "@/views/asset/relation-review/relationReviewTabs";

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
  evidence_kind?: string;
  inferred_columns?: string;
  review_status?: string;
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
// F6：分页五件套收敛到 usePagedList（含请求序号守卫与 catch 提示）；
// items 别名为 relations 保持模板引用不变。
const {
  items: relations,
  total,
  page,
  pageSize,
  loading,
  loadData: loadRelations,
  doSearch
} = usePagedList<Relation, any>({
  pageSize: 30,
  errorText: "关系列表加载失败",
  extraParams: () => {
    const extra: Record<string, string> = {};
    if (filters.system_code) extra.system_code = filters.system_code;
    if (filters.confidence) extra.confidence = filters.confidence;
    if (filters.review_status) extra.review_status = filters.review_status;
    if (filters.keyword) extra.keyword = filters.keyword;
    if (relationClass.value && relationClass.value !== "all") extra.relation_class = relationClass.value;
    return extra as any;
  },
  fetcher: async query => {
    const res = await getRelationsList(query as Record<string, string | number>);
    void loadTabCounts();
    void loadRecentReviews();
    return {
      items: (res.data?.items || []) as unknown as Relation[],
      total: res.data?.total || 0
    };
  }
});
const dialogVisible = ref(false);
const isEdit = ref(false);
const editId = ref(0);
const form = ref({ from_table: "", from_columns: "", to_table: "", to_columns: "", join_condition: "", cardinality: "", confidence: "", note: "" });

const systemOptions = ref<SystemOption[]>([]);
const filters = reactive({ system_code: "", confidence: "", review_status: "", keyword: "" });
const relationClass = ref(normalizeRelationClass(route.query.class as string));
const selectedRelations = ref<Relation[]>([]);
const classTabs = RELATION_CLASS_TABS;
const tabCounts = ref<Record<string, number>>({});
interface RecentReview {
  id: number;
  from_table?: string;
  from_columns?: string;
  to_table?: string;
  to_columns?: string;
  reviewer?: string;
  review_status?: string;
  review_note?: string;
  relation_desc_cn?: string;
  reviewed_at?: string;
}

const recentReviews = ref<RecentReview[]>([]);

const mappingsDrawerVisible = ref(false);
const mappings = ref<FieldMapping[]>([]);
const mappingsLoading = ref(false);
const currentMappingRel = ref<Relation | null>(null);

async function loadSystemOptions() {
  try {
    const res = await listSystems();
    systemOptions.value = res.data || [];
  } catch { /* ignore */ }
}

function resetFilters() {
  filters.system_code = "";
  filters.confidence = "";
  filters.review_status = "";
  filters.keyword = "";
  relationClass.value = "pending";
  page.value = 1;
  if (route.query.class) router.replace({ path: "/asset/relation-review", query: {} });
  loadRelations();
}


async function loadRecentReviews() {
  if (relationClass.value !== "confirmed" && relationClass.value !== "rejected") {
    recentReviews.value = [];
    return;
  }
  try {
    const status = relationClass.value === "rejected" ? "rejected" : "approved";
    const res = await getRelationReviews({ review_status: status, page: 1, page_size: 50 });
    recentReviews.value = (res.data?.items || []) as unknown as RecentReview[];
  } catch {
    recentReviews.value = [];
  }
}

function changeClass(name?: string | number) {
  const next = normalizeRelationClass(name ?? relationClass.value);
  if (relationClass.value !== next) relationClass.value = next;
  page.value = 1;
  const query = relationClassQuery(next);
  if (String(route.query.class || "pending") !== String(query.class || "pending")) {
    router.replace({ path: "/asset/relation-review", query });
  }
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
      await updateRelation(editId.value, form.value);
      ElMessage.success("修改成功");
    }
    dialogVisible.value = false;
    loadRelations();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "保存失败"));
  }
}

async function updateField(relId: number, field: string, value: string) {
  try {
    await updateRelation(relId, { [field]: value });
    ElMessage.success("已更新");
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "更新失败"));
  }
}

async function loadTabCounts() {
  try {
    const res = await getRelationListCounts();
    tabCounts.value = res.data || {};
  } catch {
    tabCounts.value = {};
  }
}

function tabLabel(tab: { value: string; label: string }) {
  const count = tabCounts.value[tab.value];
  return count == null ? tab.label : `${tab.label} ${count}`;
}

function columnText(row: Relation, side: "from" | "to") {
  const raw = side === "from" ? row.from_columns : row.to_columns;
  return displayRelationColumns(raw, row.inferred_columns);
}

function evidenceOf(row: Relation) {
  return relationEvidenceKind(row.note, row.from_columns, row.to_columns);
}

function statusText(value?: string) {
  const map: Record<string, string> = {
    verified: "已验证",
    approved: "已确认",
    manual_reviewed: "人工确认",
    candidate: "候选",
    not_tested: "未验证",
    bounded: "有边界",
    needs_split: "需拆分",
    sample_pass: "抽样通过",
    sample_verified: "抽样验证",
    rejected: "已拒绝",
    user_confirmed_sync: "已确认镜像",
    verified_dependency: "已确认依赖"
  };
  return map[value || ""] || value || "-";
}

function getConfidenceType(c: string) {
  if (c === "A") return "success";
  if (c === "B") return "warning";
  if (c === "C") return "danger";
  return "info";
}

async function handleApprove(relId: number) {
  try {
    // Prefer relation-reviews approve (links formal, no candidate promote)
    try {
      const res = await approveRelationReview(relId);
      const action = res.data?.action || "approved";
      ElMessage.success(`已批准（${action}）`);
    } catch (primaryError: any) {
      // E9：仅主端点 404（草稿不在 relation-reviews）时回退 legacy；其余错误原样上抛。
      if (primaryError?.response?.status !== 404) {
        throw primaryError;
      }
      await legacyReviewRelation(relId, "approve");
      ElMessage.success("已批准");
    }
    loadRelations();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "操作失败"));
  }
}

async function handleReject(relId: number) {
  try {
    try {
      await rejectRelationReview(relId);
      ElMessage.success("已驳回（草稿保留证据）");
    } catch (primaryError: any) {
      // E9：仅主端点 404 时回退 legacy。
      if (primaryError?.response?.status !== 404) {
        throw primaryError;
      }
      await legacyReviewRelation(relId, "reject");
      ElMessage.success("已驳回");
    }
    loadRelations();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "操作失败"));
  }
}

async function batchReview(action: "approve" | "reject") {
  if (!selectedRelations.value.length) {
    ElMessage.warning("请先选择关系");
    return;
  }
  try {
    await batchReviewRelations({
      relation_ids: selectedRelations.value.map(row => row.id),
      action
    });
    ElMessage.success(`已批量${action === "approve" ? "批准" : "驳回"} ${selectedRelations.value.length} 条关系`);
    selectedRelations.value = [];
    loadRelations();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "批量处理失败"));
  }
}

async function showMappings(relId: number) {
  currentMappingRel.value = relations.value.find(r => r.id === relId) || null;
  mappingsDrawerVisible.value = true;
  mappingsLoading.value = true;
  mappings.value = [];
  try {
    try {
      const res = await getRelationFieldMappingsFor(relId);
      mappings.value = Array.isArray(res.data) ? res.data : res.data?.items || [];
      return;
    } catch {
      /* fall through to relations API */
    }
    const res = await getRelationFieldMappings(relId);
    const payload = res.data;
    mappings.value = Array.isArray(payload) ? payload : payload?.items || [];
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "获取字段映射失败"));
  } finally {
    mappingsLoading.value = false;
  }
}

function openAudit(row: Relation) {
  router.push({ path: "/ops/audit", query: { entity_ref: `relation:${row.id}` } });
}

watch(() => String(route.query.class || "pending"), value => {
  const next = normalizeRelationClass(value);
  if (next === relationClass.value) return;
  relationClass.value = next;
  page.value = 1;
  loadRelations();
});

onMounted(() => {
  loadSystemOptions();
  loadRelations();
});
</script>

<template>
  <div class="relation-review-page">
    <RePageHeader
      title="关系复核中心"
      subtitle="审的是“表和表怎么关联”。批准后进入正式关系图谱；视图解析出来、没有 JOIN 字段的只能当线索，不能直接当外键。"
    />

    <el-alert
      class="review-hint"
      type="info"
      show-icon
      :closable="false"
      title="待复核是还没点头的关系。已经批准的在「已确认」，不会留在待复核里。最近人工复核的记录会单独列在已确认顶部。"
    />

    <el-tabs v-model="relationClass" class="relation-tabs" @tab-change="changeClass">
      <el-tab-pane v-for="tab in classTabs" :key="tab.value" :label="tabLabel(tab)" :name="tab.value" />
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

    <el-card v-if="recentReviews.length" class="recent-review-card" shadow="never">
      <template #header>
        <span>{{ relationClass === "rejected" ? "最近驳回的复核记录" : "最近人工复核记录" }}（{{ recentReviews.length }}）</span>
      </template>
      <el-table :data="recentReviews" size="small">
        <el-table-column label="来源表" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.from_table }}</template>
        </el-table-column>
        <el-table-column label="来源字段" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.from_columns || "未解析" }}</template>
        </el-table-column>
        <el-table-column label="目标表" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.to_table }}</template>
        </el-table-column>
        <el-table-column label="目标字段" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.to_columns || "未解析" }}</template>
        </el-table-column>
        <el-table-column label="复核人" width="130">
          <template #default="{ row }">{{ row.reviewer || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.review_status === 'approved' ? 'success' : 'info'">
              {{ row.review_status === "approved" ? "已确认" : "已拒绝" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="复核时间" width="170">
          <template #default="{ row }">{{ row.reviewed_at || "-" }}</template>
        </el-table-column>
        <el-table-column label="说明" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.review_note || row.relation_desc_cn || "-" }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header><div class="review-header"><span>关系清单（{{ total }}）</span><div><el-button v-perms="'asset.relation.review'" size="small" type="success" :disabled="!selectedRelations.length" @click="batchReview('approve')">批量批准</el-button><el-button v-perms="'asset.relation.review'" size="small" type="danger" :disabled="!selectedRelations.length" @click="batchReview('reject')">批量驳回</el-button></div></div></template>
      <el-table :data="relations" v-loading="loading" size="small" @selection-change="selectedRelations = $event">
        <el-table-column type="selection" width="44" />
        <el-table-column label="来源表" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.from_table_name_cn || row.from_table }}</div>
            <small class="tech-name">{{ row.from_table }}</small>
          </template>
        </el-table-column>
        <el-table-column label="来源字段" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'muted-col': !row.from_columns }">{{ columnText(row, "from").text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="目标表" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.to_table_name_cn || row.to_table }}</div>
            <small class="tech-name">{{ row.to_table }}</small>
          </template>
        </el-table-column>
        <el-table-column label="目标字段" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'muted-col': !row.to_columns }">{{ columnText(row, "to").text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="证据来源" width="150">
          <template #default="{ row }">
            <el-tag size="small" :type="evidenceOf(row) === 'view_ddl' ? 'info' : 'success'" effect="plain">
              {{ relationEvidenceLabel(row.evidence_kind || evidenceOf(row)) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="join_condition" label="关联条件" min-width="160" show-overflow-tooltip />
        <el-table-column prop="confidence" label="置信度" width="80">
          <template #default="{ row }">
            <el-tag :type="getConfidenceType(row.confidence)" size="small">{{ row.confidence || "-" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.validation_status === 'verified' ? 'success' : 'warning'" size="small">
              {{ statusText(row.validation_status) }}
            </el-tag>
          </template>
        </el-table-column>
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
      <el-empty
        v-if="!loading && !relations.length"
        :description="relationClass === 'pending' ? '当前没有带关联字段的待审关系。无字段的视图推断在「视图推断」页签。' : '当前页签没有数据'"
      />
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

.filter-card,
.recent-review-card {
  margin-bottom: 16px;
}

.recent-review-card {
  border: 1px solid var(--el-color-success-light-5, #b3e19d);
}
.review-hint { margin-bottom: 12px; }
.relation-tabs { margin-bottom: 12px; }
.tech-name { color: var(--text-secondary, #64748b); font-size: 12px; }
.muted-col { color: var(--text-secondary, #94a3b8); }
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
