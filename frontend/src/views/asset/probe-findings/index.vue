<template>
  <div class="probe-findings-page">
    <RePageHeader
      title="探查发现"
      subtitle="夜间探查执行器产出的数据问题：观测、复发与人工终态流转。"
    >
      <template #actions>
        <el-button @click="loadAll">刷新</el-button>
        <el-button v-perms="'probe.finding.read'" @click="doExport">导出 CSV</el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <div class="filter-row">
        <el-select v-model="filters.probe_type" placeholder="探查类型" clearable class="f-item">
          <el-option v-for="t in PROBE_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
        <el-input
          v-model="filters.system_pair"
          placeholder="系统对（如 HIS↔JHEMR）"
          clearable
          class="f-item f-wide"
          @keyup.enter="applyFilter"
        />
        <el-select v-model="filters.severity" placeholder="严重度" clearable class="f-item f-slim">
          <el-option label="P1" value="P1" />
          <el-option label="P2" value="P2" />
          <el-option label="P3" value="P3" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable class="f-item f-slim">
          <el-option v-for="s in STATUSES" :key="s" :label="statusLabel(s)" :value="s" />
        </el-select>
        <el-input
          v-model="filters.window_start_from"
          placeholder="窗起（YYYY-MM-DD）"
          clearable
          class="f-item f-date"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.window_start_to"
          placeholder="窗止（YYYY-MM-DD）"
          clearable
          class="f-item f-date"
          @keyup.enter="applyFilter"
        />
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
        <el-table-column prop="probe_type" label="类型" width="86" align="center" />
        <el-table-column prop="system_pair" label="系统对" width="130" show-overflow-tooltip />
        <el-table-column prop="object_desc" label="对象" min-width="220" show-overflow-tooltip />
        <el-table-column label="指标" min-width="200">
          <template #default="{ row }">
            <span class="metric-name">{{ row.metric_name }}</span>
            <span class="metric-value">
              {{ row.metric_value }}{{ row.metric_unit }} / 阈 {{ row.threshold }}{{ row.metric_unit }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="严重度" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="sevTagType(row.severity)">{{ row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
            <el-badge
              v-if="row.relapse_count > 0"
              :value="`复发${row.relapse_count}`"
              type="danger"
              class="relapse-badge"
            />
          </template>
        </el-table-column>
        <el-table-column label="观测窗" width="180">
          <template #default="{ row }">
            {{ row.window_start }} ~ {{ row.window_end }}
          </template>
        </el-table-column>
        <el-table-column prop="last_seen_run" label="最近 run" width="170" show-overflow-tooltip />
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

    <el-drawer v-model="drawerVisible" size="760px" title="发现详情" @closed="onDrawerClosed">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="对象" :span="2">
            {{ detail.object_desc }}
          </el-descriptions-item>
          <el-descriptions-item label="探查类型">{{ detail.probe_type }}</el-descriptions-item>
          <el-descriptions-item label="系统对">{{ detail.system_pair }}</el-descriptions-item>
          <el-descriptions-item label="指标" :span="2">
            {{ detail.metric_name }} = {{ detail.metric_value }}{{ detail.metric_unit }}（阈值
            {{ detail.threshold }}{{ detail.metric_unit }}）
          </el-descriptions-item>
          <el-descriptions-item label="观测窗" :span="2">
            {{ detail.window_start }} ~ {{ detail.window_end }}
          </el-descriptions-item>
          <el-descriptions-item label="首次发现">
            {{ detail.first_seen_run }}
          </el-descriptions-item>
          <el-descriptions-item label="最近观测">
            {{ detail.last_seen_run }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTagType(detail.status)">
              {{ statusLabel(detail.status) }}
            </el-tag>
            <el-tag v-if="detail.relapse_count > 0" size="small" type="danger" class="relapse-badge">
              复发 {{ detail.relapse_count }} 次
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.resolved_by" label="终态操作">
            {{ detail.resolved_by }} @ {{ detail.resolved_at }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.note" label="备注" :span="2">
            {{ detail.note }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="drawer-actions section-gap">
          <el-button
            v-perms="'probe.finding.manage'"
            type="primary"
            size="small"
            :disabled="detail.status === 'confirmed'"
            @click="openTransition('confirm')"
          >
            确认
          </el-button>
          <el-button
            v-perms="'probe.finding.manage'"
            type="warning"
            size="small"
            :disabled="detail.status === 'false_positive'"
            @click="openTransition('false_positive')"
          >
            误报
          </el-button>
          <el-button
            v-perms="'probe.finding.manage'"
            type="success"
            size="small"
            :disabled="detail.status === 'resolved'"
            @click="openTransition('resolve')"
          >
            解决
          </el-button>
          <el-dropdown trigger="click" @command="onMoreCommand">
            <el-button v-perms="'probe.finding.manage'" size="small">
              更多<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="reopen">重开（回到 open）</el-dropdown-item>
                <el-dropdown-item command="reclassify_confirmed">改判为已确认</el-dropdown-item>
                <el-dropdown-item command="reclassify_false_positive">改判为误报</el-dropdown-item>
                <el-dropdown-item command="reclassify_resolved">改判为已解决</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <el-tabs v-model="drawerTab" class="section-gap">
          <el-tab-pane label="证据 SQL" name="evidence">
            <div class="evidence-head">
              <span class="muted">模板参数化文本（无患者字面量）；渲染前已过脱敏管道。</span>
              <el-button size="small" @click="copyEvidence">复制</el-button>
            </div>
            <pre class="evidence-code"><code>{{ sanitizedEvidenceSql }}</code></pre>
            <div v-if="detail.evidence_digest" class="digest-line">
              digest: {{ detail.evidence_digest }}
            </div>
          </el-tab-pane>
          <el-tab-pane label="探查 runs" name="runs">
            <el-table :data="runs" stripe size="small">
              <el-table-column prop="run_id" label="run" width="180" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="80" align="center" />
              <el-table-column prop="finding_new" label="新增" width="60" align="center" />
              <el-table-column prop="finding_updated" label="更新" width="60" align="center" />
              <el-table-column prop="relapse_count" label="复发" width="60" align="center" />
              <el-table-column label="错误摘要（已脱敏）" min-width="220">
                <template #default="{ row }">
                  {{ sanitizeEvidenceText(row.error_summary, 300) }}
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>

    <el-dialog v-model="transitionDialogVisible" :title="transitionTitle" width="520px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="状态迁移说明"
        class="dialog-gap"
      >
        <template #default>
          <div>人工四值互转与重开全允许（open / confirmed / false_positive / resolved）；同态原地转将被拒绝（422）。</div>
          <div>本次迁移：<b>{{ detail?.status }}</b> → <b>{{ pendingToStatus }}</b></div>
        </template>
      </el-alert>
      <el-input
        v-model="transitionReason"
        type="textarea"
        :rows="3"
        placeholder="流转理由（必填，入审计）"
      />
      <template #footer>
        <el-button @click="transitionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitTransition">确认迁移</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { ArrowDown } from "@element-plus/icons-vue";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  exportProbeFindings,
  getProbeFinding,
  listProbeFindings,
  listProbeRuns,
  transitionProbeFinding,
  type ProbeFindingDetail,
  type ProbeFindingListItem,
  type ProbeRun
} from "@/api/probe";
import { extractErrorDetail } from "@/utils/errorMessage";
import { sanitizeEvidenceText } from "@/views/asset/probe-findings/sanitize";

const PROBE_TYPES = ["R-REF", "R-CNT", "R-KEY", "R-XSYS", "R-DOM"];
const STATUSES = ["open", "confirmed", "false_positive", "resolved"];

const loading = ref(false);
const items = ref<ProbeFindingListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const filters = reactive({
  probe_type: "",
  system_pair: "",
  severity: "",
  status: "",
  window_start_from: "",
  window_start_to: ""
});

const drawerVisible = ref(false);
const drawerTab = ref<"evidence" | "runs">("evidence");
const detail = ref<ProbeFindingDetail | null>(null);
const runs = ref<ProbeRun[]>([]);

const acting = ref(false);
const transitionDialogVisible = ref(false);
const transitionAction = ref("");
const pendingToStatus = ref("");
const transitionReason = ref("");

const sanitizedEvidenceSql = computed(() => sanitizeEvidenceText(detail.value?.evidence_sql));

const transitionTitle = computed(() => {
  const map: Record<string, string> = {
    confirm: "确认为真实问题",
    false_positive: "标记为误报",
    resolve: "标记为已解决",
    reopen: "重开（回到 open）"
  };
  return map[transitionAction.value] || "改判";
});

function statusLabel(status: string): string {
  return (
    { open: "待处理", confirmed: "已确认", false_positive: "误报", resolved: "已解决" }[status] ||
    status
  );
}

function statusTagType(status: string): "primary" | "success" | "warning" | "danger" | "info" {
  return (
    ({ open: "warning", confirmed: "primary", false_positive: "info", resolved: "success" } as Record<
      string,
      "primary" | "success" | "warning" | "danger" | "info"
    >)[status] || "info"
  );
}

function sevTagType(severity: string | null): "danger" | "warning" | "info" {
  return ({ P1: "danger", P2: "warning", P3: "info" } as Record<string, "danger" | "warning" | "info">)[
    severity || ""
  ] || "info";
}

async function loadList() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    const res = await listProbeFindings(params as any);
    items.value = res.items;
    total.value = res.total;
  } catch (error: any) {
    // B2：无 mock 开关——空态+引导文案
    items.value = [];
    total.value = 0;
    ElMessage.error(extractErrorDetail(error, "探查发现加载失败，请确认平台服务可用（探查执行器夜间写入）"));
  } finally {
    loading.value = false;
  }
}

function loadAll() {
  loadList();
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

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

async function openDetail(row: ProbeFindingListItem) {
  drawerTab.value = "evidence";
  drawerVisible.value = true;
  detail.value = null;
  runs.value = [];
  try {
    const [dRes, rRes] = await Promise.all([
      getProbeFinding(row.id),
      listProbeRuns({ page: 1, page_size: 10 })
    ]);
    detail.value = dRes;
    runs.value = rRes.items;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "发现详情加载失败"));
  }
}

function onDrawerClosed() {
  detail.value = null;
  runs.value = [];
}

function copyEvidence() {
  const text = sanitizedEvidenceSql.value;
  if (!text) return;
  navigator.clipboard
    ?.writeText(text)
    .then(() => ElMessage.success("已复制（脱敏后文本）"))
    .catch(() => ElMessage.warning("复制失败，请手动选择复制"));
}

/** F5 流转入口：三按钮 + 更多菜单（重开/改判） */
function openTransition(action: string, toStatus?: string) {
  transitionAction.value = action;
  pendingToStatus.value = toStatus || "";
  transitionReason.value = "";
  transitionDialogVisible.value = true;
}

function onMoreCommand(command: string) {
  if (command === "reopen") {
    openTransition("reopen", "open");
  } else if (command.startsWith("reclassify_")) {
    openTransition("reclassify", command.replace("reclassify_", ""));
  }
}

function submitTransition() {
  if (!detail.value) return;
  if (!transitionReason.value.trim()) {
    ElMessage.warning("流转理由必填（入审计）");
    return;
  }
  acting.value = true;
  transitionProbeFinding(detail.value.id, {
    action: transitionAction.value,
    reason: transitionReason.value.trim(),
    to_status: pendingToStatus.value || undefined
  })
    .then(async () => {
      ElMessage.success("状态已流转");
      transitionDialogVisible.value = false;
      try {
        detail.value = await getProbeFinding(detail.value!.id);
      } catch {
        // 详情刷新失败不阻塞列表
      }
      loadList();
    })
    .catch(error => {
      ElMessage.error(extractErrorDetail(error, "流转失败（可能缺少 probe.finding.manage 权限或迁移非法）"));
    })
    .finally(() => {
      acting.value = false;
    });
}

async function doExport() {
  try {
    const body: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(filters)) {
      if (value) body[key] = value;
    }
    const blob = (await exportProbeFindings(body as any)) as unknown as Blob;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `probe-findings-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "导出失败"));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.probe-findings-page {
  min-height: calc(100vh - 84px);
  padding: 20px;
  background: var(--re-page-bg);
}

.main-card {
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-md);
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.f-item {
  width: 150px;
}

.f-wide {
  width: 200px;
}

.f-slim {
  width: 100px;
}

.f-date {
  width: 170px;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.metric-name {
  display: block;
  font-family: monospace;
  font-size: 12px;
}

.metric-value {
  color: var(--re-text-secondary);
  font-size: 12px;
}

.relapse-badge {
  margin-left: 4px;
}

.section-gap {
  margin-top: 14px;
}

.drawer-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.evidence-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.evidence-code {
  padding: 12px;
  margin: 0;
  overflow-x: auto;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--re-page-bg);
  border: 1px solid var(--re-border-color);
  border-radius: var(--re-radius-sm);
}

.digest-line {
  margin-top: 6px;
  color: var(--re-text-secondary);
  font-family: monospace;
  font-size: 11px;
}

.dialog-gap {
  margin-bottom: 10px;
}

.muted {
  color: var(--re-text-secondary);
  font-size: 12px;
}
</style>
