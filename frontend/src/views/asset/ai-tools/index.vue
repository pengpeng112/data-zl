<template>
  <div class="ai-tools-page">
    <RePageHeader title="AI 工具与协作" subtitle="集中管理 AI 可调工具、系统上下文、SQL 草稿审核和调用审计。" />

    <el-card class="mb20">
      <template #header>
        <span>系统上下文</span>
      </template>
      <div class="context-filter">
        <span>选择系统：</span>
        <el-select
          v-model="systemCode"
          placeholder="请选择系统"
          clearable
          class="system-select"
          @change="loadSystemContext"
        >
          <el-option
            v-for="sys in systemOptions"
            :key="sys.system_code"
            :label="sys.system_code"
            :value="sys.system_code"
          />
        </el-select>
      </div>
      <section v-if="systemContext" class="context-stat-grid">
        <ReStatCard label="总表数" :value="systemContext.total_tables" tone="primary" />
        <ReStatCard label="总字段数" :value="systemContext.total_columns" tone="accent" />
        <ReStatCard label="总关系数" :value="systemContext.total_relations" tone="info" />
      </section>
      <el-empty v-if="!systemContext" description="选择系统后显示上下文摘要" :image-size="60" />
    </el-card>

    <el-card class="mb20">
      <template #header>
        <span>可调用工具（{{ tools.length }}）</span>
        <el-tag type="info" size="small" class="header-tag"
          >Dify / MCP / 外部 AI</el-tag
        >
      </template>
      <div class="policy-note">{{ policy }}</div>
      <el-table :data="tools" stripe size="small" class="tools-table">
        <el-table-column prop="name" label="工具名" width="200" />
        <el-table-column prop="description" label="说明" min-width="250" />
        <el-table-column label="参数" min-width="200">
          <template #default="{ row }">
            <el-tag
              v-for="(_, key) in row.parameters"
              :key="key"
              size="small"
              class="mr5"
              >{{ key }}</el-tag
            >
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="mb20">
      <template #header>
        <span>SQL/视图草稿</span>
        <el-select
          v-model="draftStatusFilter"
          placeholder="状态"
          clearable
          size="small"
          class="draft-status-filter"
          @change="loadDrafts"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="已通过" value="approved" />
          <el-option label="已拒绝" value="rejected" />
        </el-select>
      </template>
      <el-table v-loading="draftsLoading" :data="drafts" stripe size="small">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="标题" width="180" />
        <el-table-column label="SQL" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.sql_text }}</span>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.risk_flags?.blocked" type="danger" size="small"
              >已拦截</el-tag
            >
            <el-tag
              v-else-if="row.risk_flags?.big_table_warning"
              type="warning"
              size="small"
              >大表警告</el-tag
            >
            <el-tag v-else type="success" size="small">安全</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="draftStatusTag(row.status)" size="small">{{
              draftStatusLabel(row.status)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'draft'">
              <el-button type="success" size="small" @click="approveDraft(row)"
                >通过</el-button
              >
              <el-button type="danger" size="small" @click="rejectDraft(row)"
                >拒绝</el-button
              >
            </template>
            <el-tag v-else type="info" size="small">已审核</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>AI 调用审计</template>
      <el-table v-loading="auditLoading" :data="auditItems" stripe size="small">
        <el-table-column
          prop="session_key"
          label="会话"
          width="120"
          show-overflow-tooltip
        />
        <el-table-column prop="tool_name" label="工具" width="150" />
        <el-table-column label="请求" width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ JSON.stringify(row.request || {}) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="response_summary"
          label="响应摘要"
          min-width="150"
          show-overflow-tooltip
        />
        <el-table-column prop="called_at" label="时间" width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import { ref, onMounted } from "vue";
import { http } from "@/utils/http";
import { getAiTools, getDrafts, getToolCalls, reviewDraft } from "@/api/asset";
import type { AiToolDef, ViewDraftItem, AiToolCallItem } from "@/api/asset";
import { ElMessage } from "element-plus";

interface SystemOption {
  system_code: string;
}

interface SystemContext {
  total_tables: number;
  total_columns: number;
  total_relations: number;
}

const systemCode = ref("");
const systemOptions = ref<SystemOption[]>([]);
const systemContext = ref<SystemContext | null>(null);

const tools = ref<AiToolDef[]>([]);
const policy = ref("");

const drafts = ref<ViewDraftItem[]>([]);
const draftsLoading = ref(false);
const draftStatusFilter = ref("draft");

const auditItems = ref<AiToolCallItem[]>([]);
const auditLoading = ref(false);

function draftStatusLabel(s: string | null) {
  const m: Record<string, string> = {
    draft: "草稿",
    approved: "已通过",
    rejected: "已拒绝"
  };
  return m[s ?? ""] || s || "";
}

function draftStatusTag(s: string | null): any {
  const m: Record<string, string> = {
    draft: "warning",
    approved: "success",
    rejected: "danger"
  };
  return m[s ?? ""] || "";
}

function loadSystems() {
  http
    .request("get", "/api/v1/systems")
    .then((d: any) => {
      systemOptions.value = d.data || [];
    })
    .catch(() => {});
}

function loadSystemContext() {
  if (!systemCode.value) {
    systemContext.value = null;
    return;
  }
  http
    .request("get", "/api/v1/ai/system-context", {
      params: { system_code: systemCode.value }
    })
    .then((d: any) => {
      systemContext.value = d.data;
    })
    .catch(() => {
      systemContext.value = null;
    });
}

function loadAll() {
  getAiTools().then(({ data }) => {
    tools.value = data.tools;
    policy.value = data.policy;
  });
  loadDrafts();
  loadAudit();
  loadSystems();
}

function loadDrafts() {
  draftsLoading.value = true;
  getDrafts({ status: draftStatusFilter.value || undefined })
    .then(({ data }) => {
      drafts.value = data.items;
    })
    .finally(() => {
      draftsLoading.value = false;
    });
}

function loadAudit() {
  auditLoading.value = true;
  getToolCalls({ page_size: 30 })
    .then(({ data }) => {
      auditItems.value = data.items;
    })
    .finally(() => {
      auditLoading.value = false;
    });
}

function approveDraft(row: ViewDraftItem) {
  reviewDraft(row.id, { status: "approved", reviewed_by: "manual" })
    .then(() => {
      ElMessage.success("已通过");
      loadDrafts();
    })
    .catch(() => {});
}

function rejectDraft(row: ViewDraftItem) {
  reviewDraft(row.id, { status: "rejected", reviewed_by: "manual" })
    .then(() => {
      ElMessage.success("已拒绝");
      loadDrafts();
    })
    .catch(() => {});
}

onMounted(loadAll);
</script>

<style scoped>
.mb20 {
  margin-bottom: 20px;
}
.mr5 {
  margin-right: 5px;
}
.mono {
  font-family: "Courier New", monospace;
  font-size: 12px;
}
.policy-note {
  color: var(--text-secondary);
  font-size: 13px;
  padding: 4px 0;
}
.ai-tools-page {
  padding: 4px;
}
.context-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
@media (max-width: 760px) {
  .context-stat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
