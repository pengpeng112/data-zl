<template>
  <div class="run-provenance">
    <template v-if="run">
      <el-descriptions :column="2" size="small" border>
        <el-descriptions-item label="运行 ID">{{ run.id }}</el-descriptions-item>
        <el-descriptions-item label="查询版本">
          {{ run.query_code }}@{{ run.version }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTone(run.status)" size="small">{{ run.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="行数">{{ run.row_count ?? "—" }}</el-descriptions-item>
        <el-descriptions-item label="截断">
          <el-tag :type="run.truncated ? 'warning' : 'success'" size="small">
            {{ run.truncated ? "已截断" : "未截断" }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="耗时">{{ run.duration_ms ?? "—" }} ms</el-descriptions-item>
        <el-descriptions-item label="数据截至 (data_as_of)" :span="2">
          {{ run.data_as_of ?? "unknown" }}
          <el-tag v-if="asOfUnknown" type="warning" size="small" style="margin-left: 6px">
            来源未声明，非运行时间
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="结果 digest" :span="2">
          <code class="digest">{{ run.result_digest ?? "—" }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="schema digest" :span="2">
          <code class="digest">{{ run.schema_digest ?? "—" }}</code>
        </el-descriptions-item>
        <el-descriptions-item v-if="run.run_batch" label="批次">{{ run.run_batch }}</el-descriptions-item>
        <el-descriptions-item label="correlation_id">
          {{ run.correlation_id ?? "—" }}
        </el-descriptions-item>
        <el-descriptions-item v-if="run.error_class" label="错误分类" :span="2">
          <el-tag type="danger" size="small">{{ run.error_class }}</el-tag>
          {{ run.error_message ?? "" }}
        </el-descriptions-item>
        <el-descriptions-item label="参数摘要" :span="2">
          <code class="digest">{{ safeParamsJson }}</code>
        </el-descriptions-item>
      </el-descriptions>
    </template>
    <el-empty v-else description="暂无运行信息" :image-size="60" />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { QueryRun } from "@/api/query-center";

const props = defineProps<{ run?: QueryRun | null }>();

const asOfUnknown = computed(() => !props.run?.data_as_of);

const safeParamsJson = computed(() => {
  const summary = props.run?.safe_parameters_summary ?? props.run?.parameters_hash ?? {};
  return typeof summary === "string" ? summary : JSON.stringify(summary);
});

function statusTone(status?: string): "success" | "warning" | "danger" | "info" {
  if (status === "success") return "success";
  if (status === "partial") return "warning";
  if (status === "failed" || status === "unavailable") return "danger";
  return "info";
}
</script>

<style scoped>
.digest {
  font-family: monospace;
  font-size: 11px;
  word-break: break-all;
}
</style>
