<template>
  <el-drawer :model-value="modelValue" title="关系证据详情" size="620px" @update:model-value="emit('update:modelValue', $event)">
    <div v-loading="loadingDetail" class="evidence-loading">
      <template v-if="detailEdge">
        <el-alert
          v-if="isDeferredEdge(detailEdge)"
          type="warning"
          show-icon
          :closable="false"
          :title="deferredRelationVerificationText()"
          class="drawer-alert"
        />
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="来源系统">{{ detailEdge.from_system_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源数据源">{{ detailEdge.from_source_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源 Schema">{{ detailEdge.from_schema_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源表">{{ detailEdge.display_source || detailEdge.from_table_name || detailEdge.source }}</el-descriptions-item>
          <el-descriptions-item label="来源表中文名">{{ detailEdge.from_table_name_cn || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源表角色">{{ detailEdge.from_table_role || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源纳入状态">{{ detailEdge.from_include_status || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源字段">{{ detailEdge.from_columns || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标系统">{{ detailEdge.to_system_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标数据源">{{ detailEdge.to_source_code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标 Schema">{{ detailEdge.to_schema_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标表">{{ detailEdge.display_target || detailEdge.to_table_name || detailEdge.target }}</el-descriptions-item>
          <el-descriptions-item label="目标表中文名">{{ detailEdge.to_table_name_cn || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标表角色">{{ detailEdge.to_table_role || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标纳入状态">{{ detailEdge.to_include_status || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标字段">{{ detailEdge.to_columns || '-' }}</el-descriptions-item>
          <el-descriptions-item label="字段映射">{{ fieldMappingSummary(detailEdge) }}</el-descriptions-item>
          <el-descriptions-item v-if="fieldMappingRows.length" label="关系字段">
            <el-table :data="fieldMappingRows" size="small" border class="field-map-table">
              <el-table-column prop="from_column" label="来源字段" min-width="120" />
              <el-table-column prop="from_column_name_cn" label="来源字段中文名" min-width="140" />
              <el-table-column prop="to_column" label="目标字段" min-width="120" />
              <el-table-column prop="to_column_name_cn" label="目标字段中文名" min-width="140" />
            </el-table>
          </el-descriptions-item>
          <el-descriptions-item label="关系类型">{{ relationTypeLabel(detailEdge.relation_type) }}</el-descriptions-item>
          <el-descriptions-item label="关系业务域">{{ detailEdge.business_domain || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关系等级">{{ detailEdge.confidence || '-' }}</el-descriptions-item>
          <el-descriptions-item label="D 类/延后标记">
            <el-tag v-if="isDeferredEdge(detailEdge)" size="small" type="warning" effect="plain">待分析层</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="验证状态">
            <el-tag size="small" :type="statusTagType(detailEdge.validation_status)">{{ statusLabel(detailEdge.validation_status || '') }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="验证等级">{{ detailEdge.validation_level || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联条件">{{ detailEdge.join_condition || '-' }}</el-descriptions-item>
          <el-descriptions-item label="覆盖/孤儿指标">
            <el-table v-if="metricRows.length" :data="metricRows" size="small" border class="metric-table">
              <el-table-column prop="label" label="指标" min-width="130" />
              <el-table-column prop="value" label="值" min-width="160" />
            </el-table>
            <span v-else>{{ rawEvidenceMetrics(detailEdge) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="来源文档/依据">{{ evidenceSourceText(detailEdge) }}</el-descriptions-item>
          <el-descriptions-item v-if="isDeferredEdge(detailEdge)" label="待验证范围">{{ deferredRelationVerificationText() }}</el-descriptions-item>
          <el-descriptions-item label="延后原因">{{ detailEdge.deferred_reason || detailEdge.validation_note || detailEdge.note || '-' }}</el-descriptions-item>
          <el-descriptions-item label="风险说明">{{ detailEdge.validation_note || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <el-alert v-else-if="!loadingDetail" type="error" show-icon :closable="false" title="证据详情加载失败，请稍后重试" />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import type { GraphEdge } from "@/api/asset";
import { getGraphEdgeDetail } from "@/api/asset";
import { buildEvidenceMetricRows, buildFieldMappingRows, deferredRelationVerificationText, evidenceSourceText, fieldMappingSummary, rawEvidenceMetrics } from "@/views/asset/graph/graphEvidence";

const props = defineProps<{
  modelValue: boolean;
  edge: GraphEdge | null;
  edgeKey?: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
}>();

const loadingDetail = ref(false);
const detailEdge = ref<GraphEdge | null>(null);

function statusLabel(status: string) {
  const map: Record<string, string> = {
    sample_pass: "样本通过",
    verified: "已验证",
    manual_reviewed: "人工复核",
    bounded: "有边界",
    needs_split: "需拆分",
    not_tested: "未验证",
    rejected: "已拒绝"
  };
  return map[status] || status || "-";
}

function relationTypeLabel(type?: string | null) {
  const map: Record<string, string> = {
    formal: "正式关系",
    candidate: "候选/待分析",
    dependency: "视图依赖"
  };
  return map[type || "formal"] || type || "-";
}

function isDeferredEdge(edge?: GraphEdge | null) {
  if (!edge) return false;
  return Boolean(edge.is_deferred) || (edge.confidence || "").toUpperCase() === "D" || edge.relation_type === "candidate";
}

function statusTagType(status?: string | null) {
  if (["sample_pass", "verified"].includes(status || "")) return "success";
  if (["bounded", "manual_reviewed"].includes(status || "")) return "warning";
  if (["needs_split", "rejected"].includes(status || "")) return "danger";
  return "info";
}

const fieldMappingRows = computed(() => detailEdge.value ? buildFieldMappingRows(detailEdge.value) : []);
const metricRows = computed(() => detailEdge.value ? buildEvidenceMetricRows(detailEdge.value) : []);

async function loadDetail(edgeKey: string) {
  loadingDetail.value = true;
  detailEdge.value = null;
  try {
    const res = await getGraphEdgeDetail(edgeKey);
    if (!res.data) throw new Error("empty edge detail");
    detailEdge.value = res.data as GraphEdge;
  } catch (err) {
    // 证据详情失败不影响主图；展示摘要边作为回退
    if (props.edge) detailEdge.value = props.edge;
    ElMessage.warning("边证据详情加载失败，已展示摘要信息");
  } finally {
    loadingDetail.value = false;
  }
}

watch(
  () => [props.modelValue, props.edgeKey, props.edge],
  ([open, edgeKey, edge]: [boolean, string | undefined, GraphEdge | null]) => {
    if (!open) return;
    const key = String(edgeKey || "");
    if (key && key !== "rel:") {
      void loadDetail(key);
    } else if (edge) {
      detailEdge.value = edge;
    }
  },
  { immediate: true, deep: false }
);
</script>

<style scoped>
.drawer-alert { margin-bottom: 12px; }
.field-map-table, .metric-table { width: 100%; }
</style>
