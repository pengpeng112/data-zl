<template>
  <div class="quality-issues-page">
    <RePageHeader :title="pageTitle" subtitle="问题能分派到科室和人员、整改、复测、关闭并留痕的治理闭环。">
      <template #actions>
        <el-button @click="loadList">刷新</el-button>
        <el-button v-perms="'quality.issue.create'" type="primary" @click="openCreate">
          手工登记问题
        </el-button>
        <el-button v-perms="'quality.issue.export'" @click="doExport">导出 CSV</el-button>
        <el-button
          v-perms="'quality.issue.assign'"
          :disabled="!selectedRows.length"
          @click="openBatchAssign"
        >
          批量分派{{ selectedRows.length ? `（${selectedRows.length}）` : "" }}
        </el-button>
        <el-button @click="openCoverage">覆盖看板</el-button>
        <el-button v-perms="'quality.run.read'" @click="openRuns">最近运行</el-button>
        <el-button v-perms="'quality.notification.read'" @click="openTodo">
          <el-badge :value="todoUnread" :hidden="!todoUnread">我的待办</el-badge>
        </el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <div class="scope-row">
        <el-radio-group v-model="activeScope" @change="onScopeChange">
          <el-radio-button value="mine">我的任务</el-radio-button>
          <el-radio-button value="department">科室任务</el-radio-button>
          <el-radio-button value="all">全院总览</el-radio-button>
        </el-radio-group>
        <span class="scope-hint">{{ scopeHint }}</span>
      </div>

      <div class="filter-row">
        <el-select v-model="filters.status" placeholder="状态" clearable class="f-item f-slim">
          <el-option v-for="s in STATUSES" :key="s" :label="statusLabel(s)" :value="s" />
        </el-select>
        <el-select v-model="filters.severity" placeholder="严重度" clearable class="f-item f-slim">
          <el-option v-for="s in SEVERITIES" :key="s" :label="severityLabel(s)" :value="s" />
        </el-select>
        <el-select v-model="filters.priority" placeholder="优先级" clearable class="f-item f-slim">
          <el-option v-for="p in PRIORITIES" :key="p" :label="p" :value="p" />
        </el-select>
        <el-select
          v-model="filters.primary_vendor_code"
          placeholder="厂商"
          clearable
          filterable
          class="f-item f-slim"
        >
          <el-option v-for="v in vendorOptions" :key="v.vendor_code" :label="v.vendor_name" :value="v.vendor_code" />
        </el-select>
        <el-input
          v-model="filters.primary_system_code"
          placeholder="系统（如 HIS）"
          clearable
          class="f-item"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.keyword"
          placeholder="问题编号/标题关键字"
          clearable
          class="f-item f-wide"
          @keyup.enter="applyFilter"
        />
        <el-checkbox v-model="filters.overdue" label="仅逾期" @change="onOverdueToggle" />
        <el-button type="primary" @click="applyFilter">筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>

      <div class="chip-row">
        <span class="muted">快捷：</span>
        <el-tag
          v-for="chip in QUICK_CHIPS"
          :key="chip.key"
          class="chip"
          :effect="activeChip === chip.key ? 'dark' : 'plain'"
          :type="activeChip === chip.key ? 'primary' : 'info'"
          @click="applyQuickChip(chip.key)"
        >
          {{ chip.label }}
        </el-tag>
      </div>

      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="displayItems"
        stripe
        row-key="id"
        @row-click="onRowClick"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="42" />
        <el-table-column prop="issue_code" label="问题编号" width="150" show-overflow-tooltip />
        <el-table-column label="问题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.title }}</span>
            <el-tag v-if="row.recurrence_no > 0" size="small" type="danger" class="ml4">
              复发{{ row.recurrence_no }}
            </el-tag>
            <el-tag v-if="row.issue_type === 'monitoring_gap'" size="small" type="warning" class="ml4">
              监测缺口
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="系统/对象" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.primary_system_code || "-" }}</div>
            <div class="muted">{{ row.object_name_snapshot || row.control_code || "" }}</div>
          </template>
        </el-table-column>
        <el-table-column label="最新指标" width="120">
          <template #default="{ row }">
            <span :class="row.latest_result_status === 'fail' ? 'metric-bad' : 'metric-ok'">
              {{ row.latest_metric_value ?? "-" }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="严重度" width="82" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="sevTagType(row.severity)">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="76" align="center" />
        <el-table-column label="责任" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.responsible_dept_name_snapshot || row.responsible_dept_code || "-" }}</div>
            <div class="muted">
              {{ row.responsible_person_name_snapshot || row.responsible_person_code || "" }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name_snapshot" label="经办人" width="90" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.assignee_name_snapshot || row.assignee_user_identifier || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="到期" width="120">
          <template #default="{ row }">
            <span :class="{ overdue: row.overdue }">
              {{ row.due_at || "-" }}
              <template v-if="row.overdue">（逾期）</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近观测" width="140">
          <template #default="{ row }">
            {{ formatTime(row.last_seen_at) }}
          </template>
        </el-table-column>
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

    <el-dialog
      v-model="createVisible"
      title="手工登记问题"
      width="640px"
      @closed="resetCreateForm"
    >
      <el-form label-width="96px">
        <el-form-item label="问题标题" required>
          <el-input v-model="createForm.title" maxlength="256" placeholder="例如：XX 表 XX 字段缺失" />
        </el-form-item>
        <el-form-item label="问题描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="主责系统">
          <el-input v-model="createForm.primary_system_code" placeholder="如 HIS / LIS / DOCARE" />
        </el-form-item>
        <el-form-item label="对象说明">
          <el-input v-model="createForm.object_name_snapshot" placeholder="如 MEDREC.PAT_VISIT.DISCHARGE_DISPOSITION" />
        </el-form-item>
        <el-form-item label="严重度">
          <el-select v-model="createForm.severity" class="w160">
            <el-option v-for="s in SEVERITIES" :key="s" :label="severityLabel(s)" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="createForm.priority" class="w160">
            <el-option v-for="p in PRIORITIES" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="主责科室">
          <el-select
            v-model="createForm.responsible_dept_code"
            filterable
            clearable
            placeholder="选择科室"
            class="w-full"
            @change="onCreateDeptChange"
          >
            <el-option
              v-for="d in departments"
              :key="d.dept_code"
              :label="`${d.dept_name_cn}（${d.dept_code}）`"
              :value="d.dept_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="责任人">
          <el-select
            v-model="createForm.responsible_person_code"
            filterable
            clearable
            placeholder="选择责任人"
            class="w-full"
          >
            <el-option
              v-for="p in persons"
              :key="p.person_code"
              :label="`${p.person_name_cn || p.person_code}（${p.person_code}）`"
              :value="p.person_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="计划完成日">
          <el-date-picker v-model="createForm.due_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="证据来源">
          <el-input v-model="createForm.evidence_ref" placeholder="如 会议纪要/工单号（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreate">登记</el-button>
      </template>
    </el-dialog>

    <!-- B3：批量分派 -->
    <el-dialog v-model="batchVisible" :title="`批量分派（已选 ${selectedRows.length} 条）`" width="620px">
      <el-form label-width="90px">
        <el-form-item label="主责科室">
          <el-select
            v-model="batchForm.responsible_dept_code"
            filterable
            clearable
            class="w-full"
            @change="onBatchDeptChange"
          >
            <el-option
              v-for="d in departments"
              :key="d.dept_code"
              :label="`${d.dept_name_cn}（${d.dept_code}）`"
              :value="d.dept_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="责任人">
          <el-select
            v-model="batchForm.responsible_person_code"
            filterable
            clearable
            class="w-full"
          >
            <el-option v-for="p in persons" :key="p.person_code" :label="personLabel(p)" :value="p.person_code" />
          </el-select>
        </el-form-item>
        <el-form-item label="经办人">
          <el-select
            v-model="batchForm.assignee_user_identifier"
            filterable
            clearable
            class="w-full"
            placeholder="接收站内待办的人员"
          >
            <el-option v-for="p in persons" :key="`a-${p.person_code}`" :label="personLabel(p)" :value="p.person_code" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="batchAssigneeNoLogin">
          <el-alert
            type="warning"
            :closable="false"
            show-icon
            title="该人员无登录账号，将无法接收站内待办（可先登记主责代办）"
          />
        </el-form-item>
        <el-form-item label="分派理由" required>
          <el-input v-model="batchForm.reason" type="textarea" :rows="2" placeholder="批量分派理由（入审计）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitBatchAssign">确认批量分派</el-button>
      </template>
    </el-dialog>

    <!-- B3：批量分派结果 -->
    <el-dialog v-model="batchResultVisible" title="批量分派结果" width="720px" @closed="onBatchResultClosed">
      <template v-if="batchResult">
        <el-alert
          :type="batchResult.failed ? 'warning' : 'success'"
          :closable="false"
          class="mb8"
          :title="`成功 ${batchResult.ok} 条 / 失败 ${batchResult.failed} 条（共 ${batchResult.total} 条）`"
        />
        <el-table :data="batchResult.items" stripe size="small" max-height="360">
          <el-table-column label="问题" width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.issue_code || `#${row.issue_id}` }}</template>
          </el-table-column>
          <el-table-column label="结果" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.ok ? 'success' : 'danger'">{{ row.ok ? "成功" : "失败" }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="原因" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ row.error || "-" }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-dialog>

    <!-- B3：覆盖看板 -->
    <el-drawer v-model="coverageVisible" size="720px" title="覆盖看板" @open="loadCoverage">
      <div v-loading="coverageLoading">
        <template v-if="coverage">
          <el-descriptions :column="3" border size="small" class="mb8">
            <el-descriptions-item label="适用检查实例">{{ coverage.applicable_instances }}</el-descriptions-item>
            <el-descriptions-item label="有效检测实例">{{ coverage.effective_instances }}</el-descriptions-item>
            <el-descriptions-item label="可执行覆盖率">{{ pctText(coverage.executable_coverage_pct) }}</el-descriptions-item>
            <el-descriptions-item label="数据通过率">{{ pctText(coverage.data_pass_rate_pct) }}</el-descriptions-item>
            <el-descriptions-item label="活动问题">{{ coverage.issues.active }}</el-descriptions-item>
            <el-descriptions-item label="已解决">{{ coverage.issues.resolved }}</el-descriptions-item>
            <el-descriptions-item label="复发数">{{ coverage.issues.recurrence }}</el-descriptions-item>
            <el-descriptions-item label="复发率">{{ pctText(coverage.issues.recurrence_rate_pct) }}</el-descriptions-item>
            <el-descriptions-item label="整改通过率">{{ pctText(coverage.issues.remediation_pass_rate_pct) }}</el-descriptions-item>
            <el-descriptions-item label="统计时点" :span="3">{{ formatTime(coverage.statistics_time) }}</el-descriptions-item>
          </el-descriptions>
          <div class="status-tags mb8">
            <el-tag
              v-for="st in COVERAGE_STATUS_TAGS"
              :key="st.key"
              :type="st.type"
              :effect="st.effect"
              class="mr4"
            >
              {{ st.label }} {{ coverage.latest_status_counts[st.key] ?? 0 }}
            </el-tag>
          </div>
          <div class="block-title">未覆盖清单（{{ coverage.uncovered_total }}）</div>
          <el-table :data="coverage.uncovered" stripe size="small" max-height="320">
            <el-table-column prop="control_code" label="清单编码" width="150" show-overflow-tooltip />
            <el-table-column prop="detector" label="检测器" min-width="150" show-overflow-tooltip />
            <el-table-column prop="reason" label="原因" min-width="200" show-overflow-tooltip />
            <el-table-column label="最近观测" width="150">
              <template #default="{ row }">{{ formatTime(row.last_observed_at) }}</template>
            </el-table-column>
          </el-table>
          <el-alert
            v-if="coverage.note"
            type="info"
            :closable="false"
            class="note-block"
            :title="coverage.note"
          />
        </template>
      </div>
    </el-drawer>

    <!-- B3：我的待办 -->
    <el-drawer v-model="todoVisible" size="640px" title="我的待办" @open="loadTodo">
      <div class="todo-toolbar mb8">
        <span class="muted">未读 {{ todoUnread }} / 共 {{ todoTotal }} 条</span>
        <el-button size="small" :disabled="!todoUnread" @click="doReadAllTodo">全部已读</el-button>
      </div>
      <div v-loading="todoLoading">
        <div v-for="n in todoItems" :key="n.id" class="todo-item" :class="{ unread: !n.read_at }">
          <div class="todo-line1">
            <el-tag size="small" :type="todoTagType(n.notify_type)">{{ notifyTypeLabel(n.notify_type) }}</el-tag>
            <el-link v-if="n.payload.issue_code" type="primary" @click="gotoIssueById(n.issue_id)">
              {{ n.payload.issue_code }}
            </el-link>
            <span class="muted">{{ formatTime(n.created_at) }}</span>
          </div>
          <div class="todo-line2">
            <span class="muted">{{ n.read_at ? "已读" : "未读" }}</span>
            <el-button v-if="!n.read_at" size="small" link type="primary" @click="doReadTodo(n.id)">
              标记已读
            </el-button>
          </div>
        </div>
        <el-empty v-if="!todoItems.length && !todoLoading" description="暂无待办" :image-size="60" />
      </div>
      <div class="pager-row">
        <el-pagination
          v-model:current-page="todoPage"
          small
          layout="prev, pager, next"
          :total="todoTotal"
          :page-size="todoPageSize"
          @current-change="loadTodo"
        />
      </div>
    </el-drawer>

    <!-- U04：最近运行（统一主入口三要素之「运行」；操作仍收敛在质控清单页） -->
    <el-drawer v-model="runsVisible" size="780px" title="最近运行" @open="loadRuns">
      <div class="todo-toolbar mb8">
        <span class="muted">运行单状态中文对照同质控清单页；取消/重试请到质控清单详情操作。</span>
      </div>
      <div v-loading="runsLoading">
        <el-table :data="runItems" stripe size="small">
          <el-table-column prop="run_code" label="运行单" width="170" />
          <el-table-column label="用途" width="76">
            <template #default="{ row }">{{ runPurposeLabel(row.purpose) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="86">
            <template #default="{ row }">
              <el-tag size="small" :type="runStatusTag(row.status)">{{ runStatusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="结论/错误" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.result_summary">{{ runSummaryText(row.result_summary) }}</span>
              <span v-else-if="row.error_message_sanitized" class="muted">{{ row.error_message_sanitized }}</span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="150">
            <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!runItems.length && !runsLoading" description="暂无运行" :image-size="60" />
      </div>
      <div class="pager-row">
        <el-pagination
          v-model:current-page="runsPage"
          small
          layout="prev, pager, next"
          :total="runsTotal"
          :page-size="runsPageSize"
          @current-change="loadRuns"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  batchAssignQualityIssues,
  createQualityIssue,
  exportQualityIssues,
  getQualityCoverage,
  listAssignmentDepartments,
  listQualityRuns,
  listAssignmentPersons,
  listQualityIssues,
  listQualityNotifications,
  listQualityVendors,
  readAllQualityNotifications,
  readQualityNotification,
  type AssignmentDepartment,
  type AssignmentPerson,
  type QualityBatchAssignResult,
  type QualityCoverage,
  type QualityRunItem,
  type QualityIssueListItem,
  type QualityNotificationItem,
  type QualityVendorItem
} from "@/api/quality";
import { extractErrorDetail } from "@/utils/errorMessage";
import { formatTime } from "@/utils/format";

defineOptions({ name: "QualityIssues" });

const STATUSES = [
  "new",
  "acknowledged",
  "assigned",
  "in_progress",
  "waiting_external",
  "waiting_verify",
  "resolved",
  "accepted_risk",
  "false_positive",
  "duplicate",
  "cancelled"
];
const SEVERITIES = ["critical", "high", "medium", "low", "info"];
const PRIORITIES = ["P1", "P2", "P3", "P4"];

/** 207 B1：快捷筛选 chips（复发/复测受阻为前端过滤，其余落服务端筛选）。 */
type QuickChipKey = "new" | "waiting_verify" | "waiting_external" | "overdue" | "recurrence" | "recheck_blocked";
const QUICK_CHIPS: { key: QuickChipKey; label: string }[] = [
  { key: "new", label: "待分派" },
  { key: "waiting_verify", label: "待复测" },
  { key: "waiting_external", label: "等厂商" },
  { key: "overdue", label: "逾期" },
  { key: "recurrence", label: "复发" },
  { key: "recheck_blocked", label: "复测受阻" }
];

/** 207 B3：待办类型中文映射。 */
const NOTIFY_TYPE_MAP: Record<string, string> = {
  recheck_failed: "复测未通过",
  recheck_passed: "复测通过待确认",
  remind_due: "临期提醒",
  overdue: "已逾期",
  escalate: "升级督办",
  vendor_overdue: "厂商逾期",
  reminded: "催办"
};

/** 207 B3：覆盖看板六态标签（pass绿/fail红/no_data灰/error橙/blocked棕/skipped灰，棕以 danger plain 代替）。 */
const COVERAGE_STATUS_TAGS: {
  key: "pass" | "fail" | "no_data" | "error" | "blocked" | "skipped";
  label: string;
  type: "success" | "danger" | "info" | "warning";
  effect: "light" | "plain";
}[] = [
  { key: "pass", label: "通过", type: "success", effect: "light" },
  { key: "fail", label: "未通过", type: "danger", effect: "light" },
  { key: "no_data", label: "无数据", type: "info", effect: "light" },
  { key: "error", label: "错误", type: "warning", effect: "light" },
  { key: "blocked", label: "受阻", type: "danger", effect: "plain" },
  { key: "skipped", label: "跳过", type: "info", effect: "plain" }
];

const STATUS_LABELS: Record<string, string> = {
  new: "新建",
  acknowledged: "已确认",
  assigned: "已分派",
  in_progress: "整改中",
  waiting_external: "等外部",
  waiting_verify: "待复测",
  resolved: "已解决",
  accepted_risk: "风险接受",
  false_positive: "误报",
  duplicate: "重复",
  cancelled: "已取消"
};
const SEVERITY_LABELS: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低",
  info: "提示"
};

const router = useRouter();
const loading = ref(false);
const acting = ref(false);
const items = ref<QualityIssueListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const activeScope = ref<"mine" | "department" | "all">("all");
const scopeHint = ref("");
const scopeForbidden = ref(false);
const skipNextActivated = ref(true);

const pageTitle = computed(() => {
  if (activeScope.value === "department") return "科室任务";
  if (activeScope.value === "mine") return "我的任务";
  return "质量台账";
});

const filters = reactive({
  status: "",
  severity: "",
  priority: "",
  primary_system_code: "",
  primary_vendor_code: "",
  keyword: "",
  overdue: false
});

/** 207 B1/B3：快捷 chips、批量分派、覆盖看板、我的待办状态。 */
const activeChip = ref<QuickChipKey | "">("");
const vendorOptions = ref<QualityVendorItem[]>([]);
const selectedRows = ref<QualityIssueListItem[]>([]);
const tableRef = ref();

const batchVisible = ref(false);
const batchForm = reactive({
  responsible_dept_code: "",
  responsible_person_code: "",
  assignee_user_identifier: "",
  reason: ""
});
const batchResultVisible = ref(false);
const batchResult = ref<QualityBatchAssignResult | null>(null);

const coverageVisible = ref(false);
const coverageLoading = ref(false);
const coverage = ref<QualityCoverage | null>(null);
// U04：最近运行 drawer（统一主入口三要素之「运行」）
const runsVisible = ref(false);
const runsLoading = ref(false);
const runItems = ref<QualityRunItem[]>([]);
const runsTotal = ref(0);
const runsPage = ref(1);
const runsPageSize = 10;

const todoVisible = ref(false);
const todoLoading = ref(false);
const todoItems = ref<QualityNotificationItem[]>([]);
const todoTotal = ref(0);
const todoUnread = ref(0);
const todoPage = ref(1);
const todoPageSize = ref(20);

/** 复发/复测受阻为当前页前端过滤（服务端筛选结果之上）。 */
const displayItems = computed(() => {
  if (activeChip.value === "recurrence") return items.value.filter(row => row.recurrence_no > 0);
  if (activeChip.value === "recheck_blocked") {
    return items.value.filter(row => (row as QualityIssueListItem).recheck_substatus === "blocked");
  }
  return items.value;
});

const batchAssigneeNoLogin = computed(() => {
  const person = persons.value.find(p => p.person_code === batchForm.assignee_user_identifier);
  return !!person && !person.has_login;
});

const createVisible = ref(false);
const departments = ref<AssignmentDepartment[]>([]);
const persons = ref<AssignmentPerson[]>([]);
const createForm = reactive({
  title: "",
  description: "",
  primary_system_code: "",
  object_name_snapshot: "",
  severity: "medium",
  priority: "P3",
  responsible_dept_code: "",
  responsible_person_code: "",
  due_at: "",
  evidence_ref: ""
});

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

function severityLabel(severity: string | null): string {
  return SEVERITY_LABELS[severity || ""] || severity || "-";
}

function statusTagType(status: string): "primary" | "success" | "warning" | "danger" | "info" {
  return (
    ({
      new: "danger",
      acknowledged: "warning",
      assigned: "primary",
      in_progress: "primary",
      waiting_external: "warning",
      waiting_verify: "warning",
      resolved: "success",
      accepted_risk: "info",
      false_positive: "info",
      duplicate: "info",
      cancelled: "info"
    }) as Record<string, "primary" | "success" | "warning" | "danger" | "info">
  )[status] || "info";
}

function sevTagType(severity: string | null): "danger" | "warning" | "info" {
  return (
    { critical: "danger", high: "danger", medium: "warning", low: "info", info: "info" } as Record<
      string,
      "danger" | "warning" | "info"
    >
  )[severity || ""] || "info";
}

/** 路由进入默认范围：台账=/quality/issues→all；我的/科室走独立 path。KeepAlive 必须随路由刷新。 */
function initScopeFromRoute() {
  const path = router.currentRoute.value.path.replace(/\/$/, "");
  if (path.endsWith("/department")) activeScope.value = "department";
  else if (path.endsWith("/mine")) activeScope.value = "mine";
  else activeScope.value = "all";
}

function onScopeChange() {
  page.value = 1;
  loadList();
}

async function loadList() {
  loading.value = true;
  scopeForbidden.value = false;
  try {
    const params: Record<string, unknown> = {
      scope: activeScope.value,
      page: page.value,
      page_size: pageSize.value
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    const res = await listQualityIssues(params as any);
    items.value = res.items;
    total.value = res.total;
    scopeHint.value =
      res.scope === "all" ? "全院总览（需全院总览权限）" : "";
  } catch (error: any) {
    items.value = [];
    total.value = 0;
    const detail = extractErrorDetail(error, "台账加载失败");
    if (/read_all|403/i.test(detail)) {
      scopeForbidden.value = true;
      scopeHint.value = "无全院查看权限，已回退本人范围";
      activeScope.value = "mine";
      if (page.value === 1) {
        try {
          const res = await listQualityIssues({ scope: "mine", page: 1, page_size: pageSize.value });
          items.value = res.items;
          total.value = res.total;
        } catch {
          ElMessage.error(detail);
        }
      }
    } else {
      ElMessage.error(detail);
    }
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  loadList();
}

function resetFilter() {
  for (const key of Object.keys(filters) as (keyof typeof filters)[]) {
    (filters as any)[key] = key === "overdue" ? false : "";
  }
  activeChip.value = "";
  page.value = 1;
  loadList();
}

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

/** 点击选择框不触发详情跳转。 */
function onRowClick(row: QualityIssueListItem, column?: { type?: string }) {
  if (column && column.type === "selection") return;
  router.push(`/quality/issues/${row.id}`);
}

function onSelectionChange(rows: QualityIssueListItem[]) {
  selectedRows.value = rows;
}

/** B1：快捷 chips——状态/逾期落服务端筛选，复发/复测受阻为前端过滤。 */
function applyQuickChip(key: QuickChipKey) {
  const statusChips: QuickChipKey[] = ["new", "waiting_verify", "waiting_external"];
  if (activeChip.value === key) {
    activeChip.value = "";
    if (statusChips.includes(key)) filters.status = "";
    if (key === "overdue") filters.overdue = false;
  } else {
    activeChip.value = key;
    if (statusChips.includes(key)) {
      filters.status = key;
      filters.overdue = false;
    } else if (key === "overdue") {
      filters.overdue = true;
      filters.status = "";
    }
  }
  applyFilter();
}

/** 手动切换逾期勾选时同步清除快捷 chip 冲突。 */
function onOverdueToggle() {
  if (filters.overdue && activeChip.value && activeChip.value !== "overdue") {
    if (["new", "waiting_verify", "waiting_external"].includes(activeChip.value)) {
      activeChip.value = "";
    }
  }
  applyFilter();
}

async function loadVendorOptions() {
  try {
    const res = await listQualityVendors({ status: "active", page: 1, page_size: 100 });
    vendorOptions.value = res.items;
  } catch {
    // 静默：厂商选项加载失败不阻塞台账本身
  }
}

function notifyTypeLabel(notifyType: string): string {
  return NOTIFY_TYPE_MAP[notifyType] || notifyType;
}

function todoTagType(notifyType: string): "success" | "warning" | "danger" | "info" {
  return (
    {
      recheck_failed: "danger",
      overdue: "danger",
      escalate: "warning",
      vendor_overdue: "warning",
      remind_due: "warning",
      reminded: "warning",
      recheck_passed: "success"
    } as Record<string, "success" | "warning" | "danger" | "info">
  )[notifyType] || "info";
}

function pctText(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${value}%`;
}

function personLabel(person: AssignmentPerson): string {
  const base = `${person.person_name_cn || person.person_code}（${person.person_code}）`;
  return person.has_login ? base : `${base} · 无登录`;
}

// ─────────────────────────── B3：批量分派 ───────────────────────────

async function openBatchAssign() {
  if (!selectedRows.value.length) {
    ElMessage.warning("请先勾选要分派的问题");
    return;
  }
  batchForm.responsible_dept_code = "";
  batchForm.responsible_person_code = "";
  batchForm.assignee_user_identifier = "";
  batchForm.reason = "";
  batchVisible.value = true;
  if (!departments.value.length) {
    try {
      const res = await listAssignmentDepartments();
      departments.value = res.items;
    } catch (error: any) {
      ElMessage.error(extractErrorDetail(error, "科室选项加载失败"));
    }
  }
}

async function onBatchDeptChange(deptCode: string) {
  batchForm.responsible_person_code = "";
  batchForm.assignee_user_identifier = "";
  persons.value = [];
  if (!deptCode) return;
  try {
    const res = await listAssignmentPersons({ department_code: deptCode });
    persons.value = res.items;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "人员选项加载失败"));
  }
}

async function submitBatchAssign() {
  if (!selectedRows.value.length) {
    batchVisible.value = false;
    return;
  }
  if (!batchForm.responsible_dept_code && !batchForm.responsible_person_code) {
    ElMessage.warning("请至少选择主责科室或责任人");
    return;
  }
  if (!batchForm.reason.trim()) {
    ElMessage.warning("分派理由必填");
    return;
  }
  acting.value = true;
  try {
    const res = await batchAssignQualityIssues({
      items: selectedRows.value.map(row => ({
        issue_id: row.id,
        expected_lock_version: row.lock_version
      })),
      responsible_dept_code: batchForm.responsible_dept_code || undefined,
      responsible_person_code: batchForm.responsible_person_code || undefined,
      assignee_user_identifier: batchForm.assignee_user_identifier || undefined,
      reason: batchForm.reason.trim()
    });
    batchResult.value = res;
    batchVisible.value = false;
    batchResultVisible.value = true;
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "批量分派失败"));
  } finally {
    acting.value = false;
  }
}

function onBatchResultClosed() {
  selectedRows.value = [];
  tableRef.value?.clearSelection();
}

// ─────────────────────────── B3：覆盖看板 ───────────────────────────

function openCoverage() {
  coverageVisible.value = true;
}

async function loadCoverage() {
  coverageLoading.value = true;
  try {
    coverage.value = await getQualityCoverage();
  } catch (error: any) {
    coverage.value = null;
    ElMessage.error(extractErrorDetail(error, "覆盖看板加载失败"));
  } finally {
    coverageLoading.value = false;
  }
}

// ─────────────────────────── U04：最近运行 ───────────────────────────

const RUN_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  waiting_window: "等待窗口",
  running: "运行中",
  succeeded: "成功",
  partial: "部分通过",
  failed: "失败",
  cancelled: "已取消",
  blocked: "受阻"
};

function runStatusLabel(status: string): string {
  return RUN_STATUS_LABELS[status] ?? status;
}

function runStatusTag(status: string): "success" | "warning" | "danger" | "info" {
  if (status === "succeeded") return "success";
  if (status === "running" || status === "queued" || status === "waiting_window") return "warning";
  if (status === "failed" || status === "blocked") return "danger";
  return "info";
}

function runPurposeLabel(purpose: string): string {
  return { check: "检查", recheck: "复测" }[purpose] ?? purpose;
}

function runSummaryText(summary: string): string {
  try {
    const parsed = JSON.parse(summary) as Record<string, unknown>;
    const status = typeof parsed.status === "string" ? runStatusLabel(String(parsed.status)) : "";
    const metric = parsed.metric_value !== undefined && parsed.metric_value !== null ? ` ${parsed.metric_value}${parsed.metric_unit ?? ""}` : "";
    return `${status}${metric}`.trim() || summary;
  } catch {
    return summary;
  }
}

function openRuns() {
  runsPage.value = 1;
  runsVisible.value = true;
}

async function loadRuns() {
  runsLoading.value = true;
  try {
    const res = await listQualityRuns({ page: runsPage.value, page_size: runsPageSize });
    runItems.value = res.items ?? [];
    runsTotal.value = res.total ?? 0;
  } catch (error: any) {
    runItems.value = [];
    runsTotal.value = 0;
    ElMessage.error(extractErrorDetail(error, "最近运行加载失败"));
  } finally {
    runsLoading.value = false;
  }
}

// ─────────────────────────── B3：我的待办 ───────────────────────────

function openTodo() {
  todoPage.value = 1;
  todoVisible.value = true;
}

async function loadTodo() {
  todoLoading.value = true;
  try {
    const res = await listQualityNotifications({
      page: todoPage.value,
      page_size: todoPageSize.value
    });
    todoItems.value = res.items;
    todoTotal.value = res.total;
    todoUnread.value = res.unread ?? 0;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "待办加载失败"));
  } finally {
    todoLoading.value = false;
  }
}

async function loadTodoBadge() {
  try {
    const res = await listQualityNotifications({ page: 1, page_size: 1 });
    todoUnread.value = res.unread ?? 0;
  } catch {
    // 静默：无权限或失败时不显示徽标
  }
}

async function doReadTodo(id: number) {
  try {
    await readQualityNotification(id);
    loadTodo();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "标记已读失败"));
  }
}

async function doReadAllTodo() {
  try {
    await readAllQualityNotifications();
    ElMessage.success("已全部标记为已读");
    loadTodo();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "全部已读失败"));
  }
}

function gotoIssueById(issueId: number | null) {
  if (issueId) router.push(`/quality/issues/${issueId}`);
}

async function doExport() {
  try {
    const body: Record<string, unknown> = { scope: activeScope.value };
    for (const [key, value] of Object.entries(filters)) {
      if (value) body[key] = value;
    }
    const blob = (await exportQualityIssues(body as any)) as unknown as Blob;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `quality-issues-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "导出失败（上限 5000 行，请缩小范围）"));
  }
}

async function openCreate() {
  createVisible.value = true;
  if (!departments.value.length) {
    try {
      const res = await listAssignmentDepartments();
      departments.value = res.items;
    } catch (error: any) {
      ElMessage.error(extractErrorDetail(error, "科室选项加载失败"));
    }
  }
}

async function onCreateDeptChange(deptCode: string) {
  persons.value = [];
  createForm.responsible_person_code = "";
  if (!deptCode) return;
  try {
    const res = await listAssignmentPersons({ department_code: deptCode });
    persons.value = res.items;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "人员选项加载失败"));
  }
}

function resetCreateForm() {
  for (const key of Object.keys(createForm) as (keyof typeof createForm)[]) {
    (createForm as any)[key] = "";
  }
  createForm.severity = "medium";
  createForm.priority = "P3";
}

async function submitCreate() {
  if (!createForm.title.trim()) {
    ElMessage.warning("问题标题必填");
    return;
  }
  acting.value = true;
  try {
    await createQualityIssue({ ...createForm });
    ElMessage.success("问题已登记（new）");
    createVisible.value = false;
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "登记失败"));
  } finally {
    acting.value = false;
  }
}

initScopeFromRoute();
onMounted(() => {
  loadList();
  loadVendorOptions();
  loadTodoBadge();
});
onActivated(() => {
  if (skipNextActivated.value) {
    skipNextActivated.value = false;
    return;
  }
  initScopeFromRoute();
  loadList();
});
watch(
  () => router.currentRoute.value.path,
  (to, from) => {
    if (to === from) return;
    initScopeFromRoute();
    page.value = 1;
    loadList();
  }
);
</script>

<style scoped>
.quality-issues-page {
  min-height: calc(100vh - 84px);
}

.main-card {
  margin: 12px 16px;
}

.scope-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.scope-hint {
  color: #909399;
  font-size: 12px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.f-item {
  width: 160px;
}

.f-slim {
  width: 120px;
}

.f-wide {
  width: 220px;
}

.muted {
  color: #909399;
  font-size: 12px;
}

.ml4 {
  margin-left: 4px;
}

.metric-bad {
  color: #f56c6c;
  font-weight: 600;
}

.metric-ok {
  color: #67c23a;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 12px;
}

.chip {
  cursor: pointer;
}

.status-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mr4 {
  margin-right: 4px;
}

.block-title {
  margin: 12px 0 8px;
  font-weight: 600;
}

.note-block {
  margin-top: 12px;
}

.todo-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.todo-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 4px;
  border-bottom: 1px solid #ebeef5;
}

.todo-item.unread {
  background: #ecf5ff;
}

.todo-line1 {
  display: flex;
  align-items: center;
  gap: 8px;
}

.todo-line2 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: 2px;
}

.mb8 {
  margin-bottom: 8px;
}

.overdue {
  color: #f56c6c;
  font-weight: 600;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.w160 {
  width: 160px;
}

.w-full {
  width: 100%;
}
</style>
