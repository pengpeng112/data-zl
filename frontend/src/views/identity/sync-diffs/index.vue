<template>
  <div class="identity-sync-diffs">
    <RePageHeader title="人员同步差异" subtitle="采集 HIS/HRP 等来源人员与科室数据，生成差异并进行人工处理；默认 HIS dry-run 不写入。">
      <template #icon><DiffIcon /></template>
      <template #actions>
        <!-- 146 E6（R5）：按钮收敛——保留主动作“生成差异”，其余同步动作收进下拉 -->
        <el-button v-perms="'identity.sync.run'" type="primary" :loading="syncLoading" :icon="DiffIcon" @click="doSync">生成差异</el-button>
        <el-dropdown v-perms="'identity.sync.run'" trigger="click" @command="(cmd: string) => runSyncAction(cmd)">
          <el-button :icon="MoreIcon">
            更多同步动作<el-icon class="el-icon--right"><arrow-down /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="collect" :disabled="collectLoading">采集来源</el-dropdown-item>
              <el-dropdown-item command="his_sync" :disabled="hisSyncLoading">HIS 预同步（默认 dry-run）</el-dropdown-item>
              <el-dropdown-item command="review" :disabled="reviewLoading">生成复核差异</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </RePageHeader>

    <section class="diff-stats">
      <ReStatCard label="当前页差异" :value="items.length" tone="primary" helper="按筛选条件展示">
        <template #icon><DiffIcon /></template>
      </ReStatCard>
      <ReStatCard label="未处理" :value="openCount" tone="warning" helper="当前页统计">
        <template #icon><OpenIcon /></template>
      </ReStatCard>
      <ReStatCard label="已解决" :value="resolvedCount" tone="accent" helper="当前页统计">
        <template #icon><CheckIcon /></template>
      </ReStatCard>
      <ReStatCard label="忽略" :value="ignoredCount" tone="info" helper="当前页统计">
        <template #icon><IgnoreIcon /></template>
      </ReStatCard>
    </section>

    <el-card shadow="never" class="diff-card">
      <ReToolbar title="同步参数" class="diff-toolbar">
        <div class="action-bar">
          <!-- 146 E6（R5）：来源改动态加载（数据连接接口驱动），不再手输 source_code -->
          <el-select
            v-model="collectForm.source_code"
            filterable
            placeholder="选择来源数据连接"
            :loading="sourceOptionsLoading"
            class="control source"
          >
            <el-option
              v-for="item in sourceOptions"
              :key="item.source_code"
              :label="item.source_name_cn ? `${item.source_name_cn}（${item.source_code}）` : item.source_code"
              :value="item.source_code"
            />
          </el-select>
          <el-select v-model="collectForm.entity_type" class="control entity">
            <el-option label="科室" value="identity_department" />
            <el-option label="人员" value="identity_person" />
            <el-option label="全部" value="identity_all" />
          </el-select>
          <el-input-number v-model="collectForm.max_rows" :min="1" :max="50000" :step="100" class="rows" />
          <el-checkbox v-model="hisSyncForm.dry_run">HIS dry-run</el-checkbox>
        </div>
      </ReToolbar>

      <ReToolbar title="差异筛选" class="diff-toolbar" dense>
        <el-select v-model="params.status" placeholder="处理状态" clearable class="control status" @change="doSearch">
          <el-option label="未处理" value="open" />
          <el-option label="已解决" value="resolved" />
          <el-option label="已忽略" value="ignored" />
        </el-select>
        <el-select v-model="params.diff_type" placeholder="差异类型" clearable class="control diff-type" @change="doSearch">
          <el-option label="多源冲突" value="multi_source_conflict" />
          <el-option label="工号仅源有" value="staff_only_supplement" />
          <el-option label="字段不一致" value="field_mismatch" />
          <el-option label="源未匹配" value="source_unmatched" />
          <el-option label="主档缺人员" value="missing_master_person" />
          <el-option label="主档缺科室" value="missing_master_department" />
        </el-select>
      </ReToolbar>

      <el-alert v-if="lastResult" :type="lastResult.dry_run ? 'warning' : 'success'" :closable="false" class="result-alert">
        <template #title>{{ resultTitle }}</template>
      </el-alert>

      <div class="batch-bar">
        <span class="batch-hint">已选 {{ selectedDiffs.length }} 条（批量最多 50）</span>
        <el-button
          size="small"
          type="danger"
          :disabled="!selectedDiffs.length"
          :loading="batchLoading"
          v-perms="'identity.sync.run'"
          @click="batchPropose"
        >
          批量提出主档变更
        </el-button>
        <el-button
          size="small"
          type="success"
          :disabled="!selectedDiffs.length"
          :loading="batchLoading"
          v-perms="'identity.sync.run'"
          @click="batchSetStatus('resolved')"
        >
          批量解决
        </el-button>
        <el-button
          size="small"
          type="info"
          :disabled="!selectedDiffs.length"
          :loading="batchLoading"
          v-perms="'identity.sync.run'"
          @click="batchSetStatus('ignored')"
        >
          批量忽略
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        stripe
        class="medical-data-table"
        row-key="id"
        @selection-change="onDiffSelectionChange"
      >
        <el-table-column type="selection" width="48" reserve-selection />
        <el-table-column prop="diff_type" label="差异类型" width="160">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ diffTypeLabel(row.diff_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_system" label="来源系统" width="140" />
        <el-table-column prop="target_system" label="目标系统" width="120" />
        <el-table-column prop="entity_type" label="实体类型" width="120">
          <template #default="{ row }">{{ entityTypeLabel(row.entity_type) }}</template>
        </el-table-column>
        <el-table-column prop="entity_code" label="实体编码" min-width="120" show-overflow-tooltip />
        <el-table-column label="合并建议" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.merge_suggestion?.note || row.merge_suggestion?.action || "—" }}
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重度" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="severityTag(row.severity)">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'open' && (row.entity_type === 'identity_person' || row.entity_type === 'identity_department')"
              link
              type="danger"
              :loading="proposingId === row.id"
              v-perms="'identity.sync.run'"
              @click="doProposeMaster(row)"
            >
              提出主档变更
            </el-button>
            <el-button v-perms="'identity.sync.run'" v-if="row.status !== 'resolved'" link type="success" :loading="updatingId === row.id" @click="updateStatus(row, 'resolved')">解决</el-button>
            <el-button v-perms="'identity.sync.run'" v-if="row.status !== 'ignored'" link type="info" :loading="updatingId === row.id" @click="updateStatus(row, 'ignored')">忽略</el-button>
            <el-button v-perms="'identity.sync.run'" v-if="row.status !== 'open'" link type="warning" :loading="updatingId === row.id" @click="updateStatus(row, 'open')">重开</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-drawer v-model="detailVisible" title="差异详情（不自动覆盖主数据）" size="48%">
        <template v-if="detailRow">
          <p><b>类型</b>：{{ diffTypeLabel(detailRow.diff_type) }}</p>
          <p><b>编码</b>：{{ detailRow.entity_code }}</p>
          <p><b>建议</b>：{{ detailRow.merge_suggestion?.note || "—" }}</p>
          <p><b>prefer</b>：{{ detailRow.merge_suggestion?.prefer_source_table || "—" }}</p>
          <el-divider />
          <!-- 146 E6（R5）：字段级 diff（差异前 → 差异后，仅展示不一致字段） -->
          <p class="muted">字段差异（before → after）</p>
          <el-table v-if="detailFieldDiff.length" :data="detailFieldDiff" size="small" border max-height="260">
            <el-table-column prop="field" label="字段" min-width="140" show-overflow-tooltip />
            <el-table-column prop="before" label="差异前" min-width="150" show-overflow-tooltip />
            <el-table-column prop="after" label="差异后" min-width="150" show-overflow-tooltip />
            <el-table-column label="是否变化" width="90" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.changed ? 'warning' : 'info'">{{ row.changed ? "不一致" : "一致" }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <p v-else class="muted">无可比对的字段数据（before/after 为空）。</p>
          <el-divider />
          <p class="muted">before_data 原始 JSON</p>
          <pre class="json-box">{{ formatJson(detailRow.before_data) }}</pre>
          <p class="muted">after_data 原始 JSON</p>
          <pre class="json-box">{{ formatJson(detailRow.after_data) }}</pre>
          <div
            v-if="detailRow.status === 'open' && (detailRow.entity_type === 'identity_person' || detailRow.entity_type === 'identity_department')"
            class="drawer-actions"
          >
            <el-button v-perms="'identity.sync.run'" type="primary" :loading="proposingId === detailRow.id" @click="doProposeMaster(detailRow)">
              按源优先提出主档变更（L16）
            </el-button>
            <p class="muted">仅创建变更请求，需另一人审批后执行才会写主档（人员/科室）。</p>
          </div>
        </template>
      </el-drawer>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        class="pager"
        @current-change="loadData"
        @size-change="onPageSizeChange"
      />
    </el-card>

    <el-card shadow="never" class="diff-card cr-card">
      <ReToolbar title="L16 主档变更请求（审批后执行）" class="diff-toolbar">
        <el-button size="small" :loading="crLoading" @click="loadChangeRequests">刷新</el-button>
        <el-button
          v-perms="'identity.sync.run'"
          size="small"
          type="success"
          :disabled="!selectedCrs.length"
          :loading="batchLoading"
          @click="batchApproveCrs"
        >
          批量审批（{{ selectedCrs.length }}）
        </el-button>
        <el-button
          size="small"
          type="danger"
          :disabled="!selectedCrs.length"
          :loading="batchLoading"
          v-perms="'identity.sync.run'"
          @click="batchExecuteCrs"
        >
          批量执行写主档
        </el-button>
      </ReToolbar>
      <el-table
        v-loading="crLoading"
        :data="changeRequests"
        stripe
        size="small"
        class="medical-data-table"
        row-key="id"
        @selection-change="onCrSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="entity_ref" label="人员编码" min-width="120" show-overflow-tooltip />
        <el-table-column prop="request_type" label="类型" width="160" />
        <el-table-column prop="approval_status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="crStatusTag(row.approval_status)">{{ crStatusLabel(row.approval_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="requested_by" label="申请人" width="120" />
        <el-table-column prop="approved_by" label="审批人" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-perms="'identity.sync.run'"
              v-if="row.approval_status === 'pending' || row.approval_status === 'draft'"
              link
              type="success"
              :loading="crActingId === row.id"
              @click="doApproveCr(row)"
            >
              审批
            </el-button>
            <el-button
              v-perms="'identity.sync.run'"
              v-if="row.approval_status === 'approved'"
              link
              type="danger"
              :loading="crActingId === row.id"
              @click="doExecuteCr(row)"
            >
              执行写主档
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import ReStatCard from "@/components/ReStatCard/index.vue";
import ReToolbar from "@/components/ReToolbar/index.vue";
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import {
  approveIdentityChangeRequest,
  batchApproveIdentityChangeRequests,
  batchExecuteIdentityChangeRequests,
  batchProposeMasterFromDiffs,
  batchUpdateSyncDiffStatus,
  collectSources,
  executeIdentityChangeRequest,
  generateIdentityReview,
  getSyncDiffs,
  listIdentityChangeRequests,
  proposeMasterFromDiff,
  runIdentitySync,
  syncHisIdentity,
  updateIdentitySyncDiff
} from "@/api/identity";
import { listSources } from "@/api/asset";
import { usePagedList } from "@/composables/usePagedList";
import {
  buildSyncDiffFieldDiff,
  syncSeverityLabel,
  syncSeverityTag,
  syncDiffStatusLabel,
  syncDiffStatusTag
} from "@/composables/useSyncDiffPanel";
import { extractErrorDetail } from "@/utils/errorMessage";
import DiffIcon from "~icons/ri/git-branch-line";
import MoreIcon from "~icons/ri/more-line";
import CheckIcon from "~icons/ri/checkbox-circle-line";
import IgnoreIcon from "~icons/ri/forbid-2-line";
import OpenIcon from "~icons/ri/error-warning-line";

// 146 E6（R5）：来源选项动态加载（数据连接接口驱动）
const sourceOptions = ref<Array<{ source_code: string; source_name_cn?: string | null }>>([]);
const sourceOptionsLoading = ref(false);
async function loadSourceOptions() {
  sourceOptionsLoading.value = true;
  try {
    const res = await listSources();
    sourceOptions.value = (res.data || []).map(item => ({
      source_code: item.source_code,
      source_name_cn: item.source_name_cn
    }));
    if (sourceOptions.value.length && !sourceOptions.value.some(item => item.source_code === collectForm.source_code)) {
      collectForm.source_code = sourceOptions.value[0].source_code;
    }
  } catch {
    // 来源选项加载失败时保留当前默认值，动作发起时由后端校验
    sourceOptions.value = [];
  } finally {
    sourceOptionsLoading.value = false;
  }
}

// 146 E6（R5）：按钮收敛后的统一动作分发
function runSyncAction(command: string) {
  if (command === "collect") void doCollect();
  else if (command === "his_sync") void doHisSync();
  else if (command === "review") void doReview();
}

const collectLoading = ref(false);
const syncLoading = ref(false);
const hisSyncLoading = ref(false);
const reviewLoading = ref(false);
const updatingId = ref<number | null>(null);
const proposingId = ref<number | null>(null);
const lastResult = ref<any>(null);
const detailVisible = ref(false);
const detailRow = ref<any>(null);
// 146 E6（R5）：详情抽屉字段级 diff（共享 composable 提供）
const detailFieldDiff = computed(() => buildSyncDiffFieldDiff(detailRow.value?.before_data, detailRow.value?.after_data));
const changeRequests = ref<any[]>([]);
const crLoading = ref(false);
const crActingId = ref<number | null>(null);
const selectedDiffs = ref<any[]>([]);
const selectedCrs = ref<any[]>([]);
const batchLoading = ref(false);

const params = reactive({ status: "open", diff_type: "" as string });
// F6：分页五件套收敛到 usePagedList（含请求序号守卫与 catch 提示，E8/E7 语义）。
const { items, total, page, pageSize, loading, loadData, doSearch } = usePagedList<
  any,
  { page: number; page_size: number; status?: string; diff_type?: string }
>({
  pageSize: 20,
  errorText: "人员同步差异加载失败",
  extraParams: () => ({
    status: params.status || undefined,
    diff_type: params.diff_type || undefined
  }),
  fetcher: async query => {
    const res = await getSyncDiffs(query);
    return { items: res.data.items ?? [], total: res.data.total ?? 0 };
  }
});
const collectForm = reactive({
  source_code: "his_source_10_10_10_15",
  source_system: "HIS",
  entity_type: "identity_all",
  max_rows: 5000
});
const hisSyncForm = reactive({ dry_run: true });
const openCount = computed(() => items.value.filter(item => item.status === "open").length);
const resolvedCount = computed(() => items.value.filter(item => item.status === "resolved").length);
const ignoredCount = computed(() => items.value.filter(item => item.status === "ignored").length);

const resultTitle = computed(() => {
  if (Array.isArray(lastResult.value?.runs)) {
    const scanned = lastResult.value.runs.reduce((sum: number, item: any) => sum + (item.scanned ?? 0), 0);
    const diffs = lastResult.value.runs.reduce((sum: number, item: any) => sum + (item.diffs_created ?? 0), 0);
    return `采集完成：扫描 ${scanned}，生成差异 ${diffs}`;
  }
  if (lastResult.value?.prepared) {
    const prepared = lastResult.value.prepared;
    const bridge = lastResult.value.bridge || {};
    return `${lastResult.value.mode}: 人员 ${prepared.persons ?? 0}，科室 ${prepared.departments ?? 0}，桥接 ${bridge.bridge_hits ?? 0}/${bridge.sys_employee_rows ?? 0}`;
  }
  return `${lastResult.value.status}: 扫描 ${lastResult.value.scanned ?? 0}，变更 ${lastResult.value.diffs_created ?? lastResult.value.inserted ?? 0}`;
});

function severityTag(severity: string): "danger" | "warning" | "info" {
  return syncSeverityTag(severity);
}
function severityLabel(value: string) {
  return syncSeverityLabel(value);
}
function statusTag(status: string): "success" | "warning" | "info" {
  return syncDiffStatusTag(status);
}
function statusLabel(value: string) {
  return syncDiffStatusLabel(value);
}
function entityTypeLabel(value: string) {
  const map: Record<string, string> = { identity_department: "科室", identity_person: "人员", identity_all: "全部" };
  return map[value] || value || "-";
}
function diffTypeLabel(value: string) {
  const map: Record<string, string> = {
    multi_source_conflict: "多源冲突",
    staff_only_supplement: "工号仅源有",
    field_mismatch: "字段不一致",
    source_unmatched: "源未匹配",
    missing_master_person: "主档缺人员",
    missing_master_department: "主档缺科室"
  };
  return map[value] || value || "-";
}
function crStatusLabel(value: string) {
  const map: Record<string, string> = {
    draft: "草稿",
    pending: "待审批",
    approved: "已审批",
    executed: "已执行",
    rejected: "已驳回"
  };
  return map[value] || value || "-";
}
function crStatusTag(value: string): "success" | "warning" | "info" | "danger" {
  if (value === "executed") return "success";
  if (value === "approved") return "warning";
  if (value === "pending" || value === "draft") return "danger";
  return "info";
}

async function loadChangeRequests() {
  crLoading.value = true;
  try {
    const res = await listIdentityChangeRequests({ page: 1, page_size: 30 });
    changeRequests.value = res.data.items ?? [];
  } catch {
    changeRequests.value = [];
  } finally {
    crLoading.value = false;
  }
}
function onPageSizeChange() {
  loadData(1);
}
async function doCollect() {
  collectLoading.value = true;
  try {
    const res = await collectSources({ ...collectForm });
    lastResult.value = res.data;
    ElMessage.success("来源采集完成");
    loadData();
  } catch (error) {
    // 161 P2-2（round-2 P11）：动作 catch 与列表加载对称，走 extractErrorDetail。
    ElMessage.error(extractErrorDetail(error, "来源采集失败"));
  } finally {
    collectLoading.value = false;
  }
}
async function doSync() {
  syncLoading.value = true;
  try {
    const entityTypes = collectForm.entity_type === "identity_all" ? ["identity_department", "identity_person"] : [collectForm.entity_type];
    const runs = [];
    for (const entityType of entityTypes) {
      const res = await runIdentitySync({ source_system: collectForm.source_system, target_system: "asset", entity_type: entityType });
      runs.push(res.data);
    }
    lastResult.value = runs.length === 1 ? runs[0] : { runs };
    ElMessage.success("差异生成完成");
    loadData();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "差异生成失败"));
  } finally {
    syncLoading.value = false;
  }
}
async function doHisSync() {
  hisSyncLoading.value = true;
  try {
    const res = await syncHisIdentity({ dry_run: hisSyncForm.dry_run, max_rows: collectForm.max_rows, operator: "frontend" });
    lastResult.value = res.data;
    ElMessage.success(hisSyncForm.dry_run ? "HIS dry-run 完成" : "HIS 同步完成");
    if (!hisSyncForm.dry_run) loadData();
  } catch {
    ElMessage.error("HIS 同步失败");
  } finally {
    hisSyncLoading.value = false;
  }
}
async function doReview() {
  reviewLoading.value = true;
  try {
    const res = await generateIdentityReview({ source_system: collectForm.source_system });
    lastResult.value = res.data;
    ElMessage.success(`复核差异已生成：${res.data?.diffs_created ?? 0} 条（不自动覆盖）`);
    loadData();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "生成复核差异失败"));
  } finally {
    reviewLoading.value = false;
  }
}
function openDetail(row: any) {
  detailRow.value = row;
  detailVisible.value = true;
}
function formatJson(v: unknown) {
  try {
    return JSON.stringify(v ?? {}, null, 2);
  } catch {
    return String(v);
  }
}
async function updateStatus(row: any, status: "open" | "resolved" | "ignored") {
  updatingId.value = row.id;
  try {
    await updateIdentitySyncDiff(row.id, { status, handled_by: "frontend", note: "manual status update" });
    ElMessage.success("状态已更新");
    loadData();
  } catch {
    ElMessage.error("状态更新失败");
  } finally {
    updatingId.value = null;
  }
}

async function doProposeMaster(row: any) {
  proposingId.value = row.id;
  try {
    const res = await proposeMasterFromDiff(row.id, { use_prefer_source: true });
    ElMessage.success(`已创建变更请求 #${res.data?.change_request_id}（待另一人审批）`);
    await loadChangeRequests();
  } catch {
    ElMessage.error("提出主档变更失败（需人员差异且有可合并字段）");
  } finally {
    proposingId.value = null;
  }
}

function onDiffSelectionChange(rows: any[]) {
  selectedDiffs.value = rows;
}
function onCrSelectionChange(rows: any[]) {
  selectedCrs.value = rows;
}

async function batchPropose() {
  const ids = selectedDiffs.value
    .filter(
      r =>
        r.status === "open" &&
        (r.entity_type === "identity_person" || r.entity_type === "identity_department")
    )
    .map(r => r.id)
    .slice(0, 50);
  if (!ids.length) {
    ElMessage.warning("请勾选 open 状态的人员/科室差异（最多 50）");
    return;
  }
  batchLoading.value = true;
  try {
    const res = await batchProposeMasterFromDiffs({ diff_ids: ids, use_prefer_source: true });
    const d = res.data || {};
    ElMessage.success(`批量提出：成功 ${d.created ?? 0}，失败 ${d.failed ?? 0}`);
    await loadChangeRequests();
  } catch {
    ElMessage.error("批量提出失败");
  } finally {
    batchLoading.value = false;
  }
}

async function batchSetStatus(status: "resolved" | "ignored") {
  const ids = selectedDiffs.value.map(r => r.id).slice(0, 100);
  if (!ids.length) return;
  batchLoading.value = true;
  try {
    const res = await batchUpdateSyncDiffStatus({
      diff_ids: ids,
      status,
      note: "batch status update"
    });
    ElMessage.success(`已更新 ${res.data?.updated ?? 0} 条为 ${status}`);
    await loadData();
  } catch {
    ElMessage.error("批量更新状态失败");
  } finally {
    batchLoading.value = false;
  }
}

async function batchApproveCrs() {
  const ids = selectedCrs.value
    .filter(r => r.approval_status === "pending" || r.approval_status === "draft")
    .map(r => r.id)
    .slice(0, 50);
  if (!ids.length) {
    ElMessage.warning("请勾选待审批请求（须与申请人不同账号）");
    return;
  }
  batchLoading.value = true;
  try {
    const res = await batchApproveIdentityChangeRequests({ ids, note: "batch approve" });
    ElMessage.success(`批量审批：成功 ${res.data?.approved ?? 0}，失败 ${res.data?.failed ?? 0}`);
    await loadChangeRequests();
  } catch {
    ElMessage.error("批量审批失败");
  } finally {
    batchLoading.value = false;
  }
}

async function batchExecuteCrs() {
  const ids = selectedCrs.value
    .filter(r => r.approval_status === "approved")
    .map(r => r.id)
    .slice(0, 50);
  if (!ids.length) {
    ElMessage.warning("请勾选已审批、待执行的请求");
    return;
  }
  batchLoading.value = true;
  try {
    const res = await batchExecuteIdentityChangeRequests({ ids });
    ElMessage.success(`批量执行：成功 ${res.data?.executed ?? 0}，失败 ${res.data?.failed ?? 0}`);
    await loadChangeRequests();
    await loadData();
  } catch {
    ElMessage.error("批量执行失败");
  } finally {
    batchLoading.value = false;
  }
}

async function doApproveCr(row: any) {
  crActingId.value = row.id;
  try {
    await approveIdentityChangeRequest(row.id, { note: "frontend approve" });
    ElMessage.success("审批通过（审批人须与申请人不同）");
    await loadChangeRequests();
  } catch {
    ElMessage.error("审批失败：需另一账号，且状态为 pending");
  } finally {
    crActingId.value = null;
  }
}

async function doExecuteCr(row: any) {
  crActingId.value = row.id;
  try {
    await executeIdentityChangeRequest(row.id);
    ElMessage.success("已执行写主档，关联差异将标记为已解决");
    await loadChangeRequests();
    await loadData();
  } catch {
    ElMessage.error("执行失败：需已审批通过");
  } finally {
    crActingId.value = null;
  }
}

onMounted(() => {
  void loadSourceOptions();
  loadData();
  loadChangeRequests();
});
</script>

<style scoped lang="scss">
.identity-sync-diffs {
  padding: 4px;
}

.diff-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.diff-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);

  :deep(.el-card__body) {
    display: grid;
    gap: 12px;
  }
}

.cr-card {
  margin-top: 16px;
}

.batch-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.batch-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-right: 4px;
}

.drawer-actions {
  margin-top: 12px;
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  width: 100%;
}

.control.source {
  width: 260px;
}

.json-box {
  max-height: 240px;
  overflow: auto;
  padding: 8px;
  background: var(--el-fill-color-light, #f5f7fa);
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
}
.muted {
  color: var(--el-text-color-secondary);
  margin: 8px 0 4px;
}
.control.entity {
  width: 180px;
}

.control.status {
  width: 160px;
}

.control.diff-type {
  width: 180px;
}

.rows {
  width: 150px;
}

.medical-data-table {
  --el-table-header-bg-color: var(--bg-elevated);
  --el-table-row-hover-bg-color: rgb(14 165 233 / 6%);
  --el-table-border-color: var(--border-light);
  font-size: 13px;
}

.pager {
  justify-content: flex-end;
  margin-top: 4px;
}

@media (max-width: 1180px) {
  .diff-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .diff-stats {
    grid-template-columns: 1fr;
  }

  .control.source,
  .control.entity,
  .control.status,
  .rows {
    width: 100%;
  }
}
</style>
