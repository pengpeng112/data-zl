<template>
  <el-drawer :model-value="modelValue" title="关系证据详情" size="600px" @update:model-value="emit('update:modelValue', $event)">
    <el-alert
      v-if="edge && isDeferredEdge(edge)"
      type="warning"
      show-icon
      :closable="false"
      :title="deferredRelationVerificationText()"
      class="drawer-alert"
    />
    <el-descriptions v-if="edge" :column="1" border size="small">
      <el-descriptions-item label="来源系统">{{ edge.from_system_code || '-' }}</el-descriptions-item>
      <el-descriptions-item label="来源数据源">{{ edge.from_source_code || '-' }}</el-descriptions-item>
      <el-descriptions-item label="来源 Schema">{{ edge.from_schema_name || '-' }}</el-descriptions-item>
      <el-descriptions-item label="来源表">{{ edge.from_table_name || edge.source }}</el-descriptions-item>
      <el-descriptions-item label="来源表中文名">{{ edge.from_table_name_cn || '-' }}</el-descriptions-item>
      <el-descriptions-item label="来源表角色">{{ edge.from_table_role || '-' }}</el-descriptions-item>
      <el-descriptions-item label="来源纳入状态">{{ edge.from_include_status || '-' }}</el-descriptions-item>
      <el-descriptions-item label="来源字段">{{ edge.from_columns || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标系统">{{ edge.to_system_code || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标数据源">{{ edge.to_source_code || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标 Schema">{{ edge.to_schema_name || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标表">{{ edge.to_table_name || edge.target }}</el-descriptions-item>
      <el-descriptions-item label="目标表中文名">{{ edge.to_table_name_cn || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标表角色">{{ edge.to_table_role || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标纳入状态">{{ edge.to_include_status || '-' }}</el-descriptions-item>
      <el-descriptions-item label="目标字段">{{ edge.to_columns || '-' }}</el-descriptions-item>
      <el-descriptions-item label="字段映射">{{ fieldMappingSummary(edge) }}</el-descriptions-item>
      <el-descriptions-item v-if="fieldMappingRows.length" label="关系字段">
        <el-table :data="fieldMappingRows" size="small" border class="field-map-table">
          <el-table-column prop="from_column" label="来源字段" min-width="120" />
          <el-table-column prop="from_column_name_cn" label="来源字段中文名" min-width="140" />
          <el-table-column prop="to_column" label="目标字段" min-width="120" />
          <el-table-column prop="to_column_name_cn" label="目标字段中文名" min-width="140" />
        </el-table>
      </el-descriptions-item>
      <el-descriptions-item label="关系类型">{{ relationTypeLabel(edge.relation_type) }}</el-descriptions-item>
      <el-descriptions-item label="关系业务域">{{ edge.business_domain || '-' }}</el-descriptions-item>
      <el-descriptions-item label="关系等级">{{ edge.confidence || '-' }}</el-descriptions-item>
      <el-descriptions-item label="D 类/延后标记">
        <el-tag v-if="isDeferredEdge(edge)" size="small" type="warning" effect="plain">待分析层</el-tag>
        <span v-else>-</span>
      </el-descriptions-item>
      <el-descriptions-item label="验证状态">
        <el-tag size="small" :type="statusTagType(edge.validation_status)">{{ statusLabel(edge.validation_status || '') }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="验证等级">{{ edge.validation_level || '-' }}</el-descriptions-item>
      <el-descriptions-item label="关联条件">{{ edge.join_condition || '-' }}</el-descriptions-item>
      <el-descriptions-item label="覆盖/孤儿指标">
        <el-table v-if="metricRows.length" :data="metricRows" size="small" border class="metric-table">
          <el-table-column prop="label" label="指标" min-width="130" />
          <el-table-column prop="value" label="值" min-width="160" />
        </el-table>
        <span v-else>{{ rawEvidenceMetrics(edge) }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="来源文档/依据">{{ evidenceSourceText(edge) }}</el-descriptions-item>
      <el-descriptions-item v-if="isDeferredEdge(edge)" label="待验证范围">{{ deferredRelationVerificationText() }}</el-descriptions-item>
      <el-descriptions-item label="延后原因">{{ edge.deferred_reason || edge.validation_note || edge.note || '-' }}</el-descriptions-item>
      <el-descriptions-item label="风险说明">{{ edge.validation_note || '-' }}</el-descriptions-item>
    </el-descriptions>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { GraphEdge } from "@/api/asset";
import { buildEvidenceMetricRows, buildFieldMappingRows, deferredRelationVerificationText, evidenceSourceText, fieldMappingSummary, rawEvidenceMetrics } from "@/views/asset/graph/graphEvidence";

const props = defineProps<{
  modelValue: boolean;
  edge: GraphEdge | null;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: boolean];
}>();

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

const fieldMappingRows = computed(() => props.edge ? buildFieldMappingRows(props.edge) : []);
const metricRows = computed(() => props.edge ? buildEvidenceMetricRows(props.edge) : []);
</script>

<style scoped>
.drawer-alert { margin-bottom: 12px; }
.field-map-table, .metric-table { width: 100%; }
</style>
