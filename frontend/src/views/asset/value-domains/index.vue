<template>
  <div class="value-domains-page">
    <RePageHeader
      title="值域知识库"
      subtitle="字段值域全量视图：候选、冲突裁决与版本时间线（149 端点族活化）。"
    >
      <template #actions>
        <el-badge
          :value="pendingTotal"
          :hidden="pendingTotal === 0"
          type="warning"
          class="pending-badge"
        >
          <el-button @click="loadAll">刷新</el-button>
        </el-badge>
        <el-button v-perms="'value_domain.read'" @click="doExport">导出 CSV</el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane name="conflicted">
          <template #label>
            冲突
            <el-badge
              :value="conflictedTotal"
              :hidden="conflictedTotal === 0"
              type="danger"
              class="tab-badge"
            />
          </template>
        </el-tab-pane>
      </el-tabs>

      <div class="filter-row">
        <el-input
          v-model="filters.system_code"
          placeholder="系统编码"
          clearable
          class="f-item"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.schema_name"
          placeholder="Schema"
          clearable
          class="f-item"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.table_name"
          placeholder="表名"
          clearable
          class="f-item"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.column_name"
          placeholder="字段名"
          clearable
          class="f-item"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.code"
          placeholder="值码"
          clearable
          class="f-item f-code"
          @keyup.enter="applyFilter"
        />
        <el-select
          v-model="filters.domain_kind"
          placeholder="值域类型"
          clearable
          class="f-item"
        >
          <el-option label="枚举" value="enum" />
          <el-option label="阈值" value="threshold" />
          <el-option label="字面量" value="literal" />
          <el-option label="陷阱" value="trap" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable class="f-item">
          <el-option label="待确认" value="pending" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="已废弃" value="deprecated" />
        </el-select>
        <el-button type="primary" @click="applyFilter">筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        stripe
        row-key="id"
        @row-click="openDetail"
      >
        <el-table-column prop="system_code" label="系统" width="110" show-overflow-tooltip />
        <el-table-column prop="schema_name" label="Schema" width="110" show-overflow-tooltip />
        <el-table-column prop="table_name" label="表" min-width="140" show-overflow-tooltip />
        <el-table-column prop="column_name" label="字段" min-width="130" show-overflow-tooltip />
        <el-table-column prop="code" label="值码" width="90" show-overflow-tooltip />
        <el-table-column prop="meaning" label="含义" min-width="180" show-overflow-tooltip />
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="kindTagType(row.domain_kind)">
              {{ kindLabel(row.domain_kind) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="冲突" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.conflict_status === 'conflicted'" type="danger" size="small">
              未裁决
            </el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="version_no" label="版本" width="70" align="center" />
        <el-table-column prop="evidence_count" label="证据" width="70" align="center" />
        <el-table-column prop="updated_at" label="更新时间" width="170" show-overflow-tooltip />
      </el-table>

      <div class="pager-row">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadList"
          @size-change="onPageSizeChange"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawerVisible" size="720px" title="值域详情" @closed="onDrawerClosed">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="定位键" :span="2">
            {{ detail.system_code }} / {{ detail.schema_name }}.{{ detail.table_name }}.{{
              detail.column_name
            }}
          </el-descriptions-item>
          <el-descriptions-item label="值码">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ kindLabel(detail.domain_kind) }}
          </el-descriptions-item>
          <el-descriptions-item label="含义" :span="2">
            {{ detail.meaning }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.scope_condition" label="适用条件" :span="2">
            {{ detail.scope_condition }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTagType(detail.status)">
              {{ statusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="版本">
            v{{ detail.version_no }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.confirmed_by" label="确认人" :span="2">
            {{ detail.confirmed_by }} @ {{ detail.confirmed_at }}
          </el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="detail.conflict_status === 'conflicted'"
          type="warning"
          :closable="false"
          show-icon
          title="该值码存在未裁决的含义冲突"
          description="两侧来源观测到不同含义；须先人工裁决（采纳其一或改写），解除冲突后才能确认。"
          class="section-gap"
        />

        <div class="drawer-actions section-gap">
          <el-tooltip
            :disabled="detail.conflict_status !== 'conflicted'"
            content="存在未裁决冲突：请先完成冲突裁决，再执行确认"
            placement="top"
          >
            <span>
              <el-button
                v-perms="'value_domain.confirm'"
                type="primary"
                size="small"
                @click="onClickConfirm"
              >
                确认
              </el-button>
            </span>
          </el-tooltip>
          <el-button
            v-if="detail.conflict_status === 'conflicted'"
            v-perms="'value_domain.confirm'"
            type="warning"
            size="small"
            @click="openResolveDialog"
          >
            裁决冲突
          </el-button>
          <el-button
            v-perms="'value_domain.confirm'"
            type="danger"
            size="small"
            plain
            @click="deprecateDialogVisible = true"
          >
            废弃
          </el-button>
        </div>

        <el-tabs v-model="drawerTab" class="section-gap">
          <el-tab-pane label="证据链" name="evidences">
            <el-table :data="detail.evidences || []" stripe size="small">
              <el-table-column prop="source_type" label="来源类型" width="110" />
              <el-table-column prop="source_system" label="来源系统" width="100" />
              <el-table-column
                prop="observed_meaning"
                label="观测含义（竞争口径在此呈现）"
                min-width="180"
                show-overflow-tooltip
              />
              <el-table-column prop="method" label="方法" min-width="140" show-overflow-tooltip />
              <el-table-column prop="sample_count" label="样本" width="70" align="center" />
              <el-table-column prop="snippet_ref" label="原文引用" width="110" show-overflow-tooltip />
            </el-table>
          </el-tab-pane>
          <el-tab-pane label="版本历史" name="versions">
            <el-table :data="versions" stripe size="small">
              <el-table-column prop="version_no" label="版本" width="70" align="center" />
              <el-table-column prop="change_reason" label="变更" width="140" />
              <el-table-column prop="evidence_ref" label="依据" min-width="140" show-overflow-tooltip />
              <el-table-column prop="actor" label="操作人" width="120" show-overflow-tooltip />
              <el-table-column prop="created_at" label="时间" width="170" />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>

    <el-dialog v-model="confirmDialogVisible" title="确认值域" width="480px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="影响说明"
        description="确认后该值域进入 AI 上下文注入链路（system-context / 值域知识库导出），下游 AI 取数将引用该口径。"
        class="dialog-gap"
      />
      <el-input
        v-model="confirmReason"
        type="textarea"
        :rows="2"
        placeholder="确认依据（可选）"
      />
      <template #footer>
        <el-button @click="confirmDialogVisible = false">取消</el-button>
        <el-button v-perms="'value_domain.confirm'" type="primary" :loading="acting" @click="submitConfirm">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resolveDialogVisible" title="裁决冲突" width="520px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="影响说明"
        description="裁决将覆盖当前含义并解除冲突状态；确认入口随之开放。请核对两侧证据后采纳正确口径。"
        class="dialog-gap"
      />
      <div v-if="detail" class="competing-box">
        <div class="competing-title">竞争口径</div>
        <div class="competing-item">现行含义：{{ detail.meaning }}</div>
        <div
          v-for="ev in competingEvidences"
          :key="ev.id"
          class="competing-item"
        >
          {{ ev.source_type }}<template v-if="ev.source_system">（{{ ev.source_system }}）</template>：{{ ev.observed_meaning }}
        </div>
      </div>
      <el-input
        v-model="resolveForm.meaning"
        placeholder="采纳的含义（必填）"
        class="dialog-gap"
      />
      <el-input
        v-model="resolveForm.reason"
        placeholder="裁决理由（必填）"
        class="dialog-gap"
      />
      <el-input
        v-model="resolveForm.note"
        type="textarea"
        :rows="2"
        placeholder="备注（可选）"
      />
      <template #footer>
        <el-button @click="resolveDialogVisible = false">取消</el-button>
        <el-button type="warning" :loading="acting" @click="submitResolve">采纳并解除冲突</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deprecateDialogVisible" title="废弃值域" width="480px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="影响说明"
        description="废弃后该值域退出 AI 注入链路，不再出现在上下文与导出中；历史版本保留可追溯。"
        class="dialog-gap"
      />
      <el-input
        v-model="deprecateReason"
        type="textarea"
        :rows="2"
        placeholder="废弃理由（必填）"
      />
      <template #footer>
        <el-button @click="deprecateDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="acting" @click="submitDeprecate">废弃</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  confirmValueDomain,
  deprecateValueDomain,
  exportValueDomains,
  getValueDomainDetail,
  getValueDomainVersions,
  listValueDomains,
  resolveValueDomainConflict,
  type ValueDomainDetail,
  type ValueDomainItem,
  type ValueDomainVersion
} from "@/api/asset";
import { extractErrorDetail } from "@/utils/errorMessage";

const activeTab = ref<"all" | "conflicted">("all");
const loading = ref(false);
const items = ref<ValueDomainItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const pendingTotal = ref(0);
const conflictedTotal = ref(0);

const filters = reactive({
  system_code: "",
  schema_name: "",
  table_name: "",
  column_name: "",
  code: "",
  domain_kind: "",
  status: ""
});

const drawerVisible = ref(false);
const drawerTab = ref<"evidences" | "versions">("evidences");
const detail = ref<ValueDomainDetail | null>(null);
const versions = ref<ValueDomainVersion[]>([]);

const acting = ref(false);
const confirmDialogVisible = ref(false);
const confirmReason = ref("");
const resolveDialogVisible = ref(false);
const resolveForm = reactive({ meaning: "", reason: "", note: "" });
const deprecateDialogVisible = ref(false);
const deprecateReason = ref("");

const competingEvidences = computed(() =>
  (detail.value?.evidences || []).filter(
    ev => ev.observed_meaning && ev.observed_meaning !== detail.value?.meaning
  )
);

type TagType = "primary" | "success" | "warning" | "danger" | "info";

function kindLabel(kind: string): string {
  return { enum: "枚举", threshold: "阈值", literal: "字面量", trap: "陷阱" }[kind] || kind;
}

function kindTagType(kind: string): TagType {
  return ({ enum: "primary", threshold: "success", literal: "info", trap: "danger" }[
    kind
  ] as TagType) || "info";
}

function statusLabel(status: string): string {
  return { pending: "待确认", confirmed: "已确认", deprecated: "已废弃" }[status] || status;
}

function statusTagType(status: string): TagType {
  return ({ pending: "warning", confirmed: "success", deprecated: "info" }[
    status
  ] as TagType) || "info";
}

function buildParams(extra: Record<string, unknown> = {}) {
  const params: Record<string, unknown> = {
    page: page.value,
    page_size: pageSize.value,
    ...(activeTab.value === "conflicted" ? { conflicted: true } : {})
  };
  for (const [key, value] of Object.entries(filters)) {
    if (value) params[key] = value;
  }
  return { ...params, ...extra };
}

async function loadList() {
  loading.value = true;
  try {
    const res = await listValueDomains(buildParams() as any);
    items.value = res.data.items;
    total.value = res.data.total;
  } catch (error: any) {
    // B2：无 mock 开关——空态+引导文案，不显示假 0
    items.value = [];
    total.value = 0;
    ElMessage.error(extractErrorDetail(error, "值域列表加载失败，请确认平台服务可用"));
  } finally {
    loading.value = false;
  }
}

async function loadCounters() {
  try {
    const [pending, conflicted] = await Promise.all([
      listValueDomains({ status: "pending", page: 1, page_size: 1 } as any),
      listValueDomains({ conflicted: true, page: 1, page_size: 1 } as any)
    ]);
    pendingTotal.value = pending.data.total;
    conflictedTotal.value = conflicted.data.total;
  } catch {
    pendingTotal.value = 0;
    conflictedTotal.value = 0;
  }
}

function loadAll() {
  loadList();
  loadCounters();
}

function applyFilter() {
  page.value = 1;
  loadList();
}

function resetFilter() {
  for (const key of Object.keys(filters) as (keyof typeof filters)[]) {
    filters[key] = "";
  }
  page.value = 1;
  loadList();
}

function onTabChange() {
  page.value = 1;
  loadList();
}

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

async function openDetail(row: ValueDomainItem) {
  drawerTab.value = "evidences";
  drawerVisible.value = true;
  detail.value = null;
  versions.value = [];
  try {
    const [dRes, vRes] = await Promise.all([
      getValueDomainDetail(row.id),
      getValueDomainVersions(row.id)
    ]);
    detail.value = dRes.data;
    versions.value = vRes.data.items;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "值域详情加载失败"));
  }
}

function onDrawerClosed() {
  detail.value = null;
  versions.value = [];
}

/** F3：conflicted 行点击确认 → 引导先裁决（B4：confirm 必 409 的死胡同前置拦截） */
function onClickConfirm() {
  if (detail.value?.conflict_status === "conflicted") {
    ElMessage.warning("存在未裁决冲突，请先完成冲突裁决");
    openResolveDialog();
    return;
  }
  confirmReason.value = "";
  confirmDialogVisible.value = true;
}

function openResolveDialog() {
  resolveForm.meaning = "";
  resolveForm.reason = "";
  resolveForm.note = "";
  resolveDialogVisible.value = true;
}

async function afterAction(message: string) {
  ElMessage.success(message);
  confirmDialogVisible.value = false;
  resolveDialogVisible.value = false;
  deprecateDialogVisible.value = false;
  if (detail.value) {
    const id = detail.value.id;
    try {
      const [dRes, vRes] = await Promise.all([
        getValueDomainDetail(id),
        getValueDomainVersions(id)
      ]);
      detail.value = dRes.data;
      versions.value = vRes.data.items;
    } catch {
      // 详情刷新失败不阻塞列表刷新
    }
  }
  loadList();
  loadCounters();
}

function submitConfirm() {
  if (!detail.value) return;
  acting.value = true;
  confirmValueDomain(detail.value.id, confirmReason.value || undefined)
    .then(() => afterAction("已确认，进入 AI 注入链路"))
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "确认失败（可能缺少 value_domain.confirm 权限）"));
    })
    .finally(() => {
      acting.value = false;
    });
}

function submitResolve() {
  if (!detail.value) return;
  if (!resolveForm.meaning.trim() || !resolveForm.reason.trim()) {
    ElMessage.warning("采纳含义与裁决理由均为必填");
    return;
  }
  acting.value = true;
  resolveValueDomainConflict(detail.value.id, {
    meaning: resolveForm.meaning.trim(),
    reason: resolveForm.reason.trim(),
    note: resolveForm.note.trim() || undefined
  })
    .then(() => afterAction("冲突已裁决并解除"))
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "裁决失败"));
    })
    .finally(() => {
      acting.value = false;
    });
}

function submitDeprecate() {
  if (!detail.value) return;
  if (!deprecateReason.value.trim()) {
    ElMessage.warning("废弃理由必填");
    return;
  }
  acting.value = true;
  deprecateValueDomain(detail.value.id, deprecateReason.value.trim())
    .then(() => afterAction("已废弃，退出注入链路"))
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "废弃失败"));
    })
    .finally(() => {
      acting.value = false;
    });
}

/** F6：值域 CSV 导出（按当前筛选；默认排除 conflicted——外发防未裁决口径扩散） */
async function doExport() {
  try {
    const params: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    if (activeTab.value === "conflicted") params.include_conflicted = true;
    const blob = (await exportValueDomains(params as any)) as unknown as Blob;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    const statusTag = filters.status ? `-status-${filters.status}` : "";
    link.download = `value-domains-${new Date().toISOString().slice(0, 10)}${statusTag}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "导出失败"));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.value-domains-page {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}

.main-card {
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-md);
}

.pending-badge {
  margin-right: 12px;
}

.tab-badge {
  margin-left: 4px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.f-item {
  width: 130px;
}

.f-code {
  width: 90px;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.section-gap {
  margin-top: 14px;
}

.drawer-actions {
  display: flex;
  gap: 8px;
}

.dialog-gap {
  margin-bottom: 10px;
}

.competing-box {
  padding: 8px 10px;
  margin-bottom: 10px;
  border: 1px solid var(--el-color-warning-light-7);
  border-radius: var(--re-radius-sm);
  background: var(--el-color-warning-light-9);
  font-size: 13px;
}

.competing-title {
  margin-bottom: 4px;
  font-weight: 600;
}

.competing-item {
  color: var(--re-text-secondary);
}

.muted {
  color: var(--re-text-secondary);
}
</style>
