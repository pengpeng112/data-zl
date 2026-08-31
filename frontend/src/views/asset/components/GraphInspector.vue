<template>
  <aside v-if="open" class="inspector" aria-label="图谱 Inspector">
    <header><strong>Inspector</strong><el-button text @click="emit('close')">收起 ›</el-button></header>
    <el-tabs v-model="tab">
      <el-tab-pane label="节点" name="node" :disabled="!node">
        <el-descriptions v-if="node" :column="1" border size="small">
          <el-descriptions-item label="五段物理键">{{ node.id }}</el-descriptions-item>
          <el-descriptions-item label="中文名">{{ displayName }}</el-descriptions-item>
          <el-descriptions-item label="技术名">{{ node.technical_name || node.display_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="入度 / 出度">{{ node.in_degree ?? 0 }} / {{ node.out_degree ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="业务域">{{ node.business_domain || node.domain || '-' }}</el-descriptions-item>
          <el-descriptions-item label="字段数">{{ node.column_count ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="值域摘要">{{ valueDomainSummary }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="node" class="actions"><el-button size="small" @click="emit('open-table', node)">打开表详情</el-button></div>
      </el-tab-pane>
      <el-tab-pane label="关系" name="edge" :disabled="!edge">
        <div v-if="edge" v-loading="loading">
          <el-alert v-if="detailError" type="warning" :closable="false" :title="detailError" class="detail-error" />
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="起点">{{ edge.display_source || edge.source }}</el-descriptions-item>
            <el-descriptions-item label="终点">{{ edge.display_target || edge.target }}</el-descriptions-item>
            <el-descriptions-item label="类型 / 置信度">{{ edge.relation_type || '-' }} / {{ edge.confidence || '-' }}</el-descriptions-item>
            <el-descriptions-item label="字段">{{ edge.from_columns || '-' }} → {{ edge.to_columns || '-' }}</el-descriptions-item>
            <el-descriptions-item label="SQL Hash"><code>{{ edge.sql_hash || '-' }}</code></el-descriptions-item>
            <el-descriptions-item label="SQL 摘要"><code>{{ edge.sql_snippet || '-' }}</code></el-descriptions-item>
          </el-descriptions>
        </div>
      </el-tab-pane>
    </el-tabs>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { getGraphEdgeDetail, type GraphEdge, type GraphNode } from "@/api/asset";
const props = defineProps<{ open: boolean; node: GraphNode | null; edge: GraphEdge | null }>();
const emit = defineEmits<{ close: []; "open-table": [node: GraphNode] }>();
const tab = ref<"node" | "edge">("node");
const detail = ref<GraphEdge | null>(null);
const loading = ref(false);
const detailError = ref("");
const edge = computed(() => detail.value || props.edge);
const valueDomainSummary = computed(() => props.node?.note ? String(props.node.note).slice(0, 160) : "按需查看表详情（当前未加载值域）");
// 169 G5 顺手修：label 可能是 G6 标签配置对象（{formatter: ...}）而非字符串，
// 直接插值会渲染整段 JSON——取 formatter 文本，对象则兜底 display_id。
const displayName = computed(() => {
  const node: any = props.node || {};
  if (node.table_name_cn) return String(node.table_name_cn);
  const label = node.label;
  if (typeof label === "string" && label) return label;
  if (label && typeof label === "object" && typeof label.formatter === "string") return label.formatter;
  return node.display_id || "-";
});
watch(() => props.node, value => { if (value) tab.value = "node"; });
watch(() => props.edge, async value => {
  if (!value) return;
  tab.value = "edge";
  detail.value = null;
  detailError.value = "";
  loading.value = true;
  try { detail.value = (await getGraphEdgeDetail(value.id)).data; }
  catch { detailError.value = "证据详情加载失败，已保留当前关系摘要"; }
  finally { loading.value = false; }
});
</script>

<style scoped>
.inspector { width:340px; min-width:340px; border:1px solid #d8e0ec; border-radius:10px; background:#fff; padding:10px; overflow:auto; }
header { display:flex; justify-content:space-between; align-items:center; }
.actions { margin-top:12px; }
.detail-error { margin-bottom:10px; }
code { white-space:pre-wrap; overflow-wrap:anywhere; }
</style>
