<template>
  <div class="quality-issue-detail-page">
    <RePageHeader :title="detail?.title || '问题详情'" :subtitle="detail?.issue_code || ''">
      <template #actions>
        <el-button @click="loadAll">刷新</el-button>
        <el-button @click="goBack">返回台账</el-button>
      </template>
    </RePageHeader>

    <el-card v-loading="loading" shadow="never" class="main-card">
      <template v-if="detail">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="问题编号">{{ detail.issue_code }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusTagType(detail.status)">
              {{ statusLabel(detail.status) }}
            </el-tag>
            <el-tag v-if="detail.recurrence_no > 0" size="small" type="danger" class="ml4">
              复发 {{ detail.recurrence_no }} 次
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="问题类型">
            {{ issueTypeLabel(detail.issue_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="主责系统">{{ detail.primary_system_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="对象" :span="2">
            {{ detail.object_name_snapshot || detail.scope_key || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="质控清单">
            {{ detail.control_code || "-" }}
            <span v-if="detail.control_code" class="muted">（v{{ detail.opened_control_version || "?" }} 开单）</span>
          </el-descriptions-item>
          <el-descriptions-item label="严重度">
            <el-tag size="small" :type="sevTagType(detail.severity)">
              {{ severityLabel(detail.severity) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">{{ detail.priority || "-" }}</el-descriptions-item>
          <el-descriptions-item label="主责科室">
            {{ detail.responsible_dept_name_snapshot || detail.responsible_dept_code || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="责任人">
            {{ detail.responsible_person_name_snapshot || detail.responsible_person_code || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="经办人">
            {{ detail.assignee_name_snapshot || detail.assignee_user_identifier || "-" }}
          </el-descriptions-item>
          <el-descriptions-item label="最新指标">
            <span :class="detail.latest_result_status === 'fail' ? 'metric-bad' : 'metric-ok'">
              {{ detail.latest_metric_value ?? "-" }}（{{ detail.latest_result_status || "-" }}）
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="计划完成日">
            <span :class="{ overdue: detail.overdue }">
              {{ detail.due_at || "-" }}
              <template v-if="detail.overdue">（逾期）</template>
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="首次/最近发现">
            {{ formatTime(detail.first_seen_at) }} / {{ formatTime(detail.last_seen_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.wait_kind" label="外部依赖" :span="3">
            {{ detail.wait_kind }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.description" label="描述" :span="3">
            {{ detail.description }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.action_plan" label="整改措施" :span="3">
            {{ detail.action_plan }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.resolution_summary" label="关闭说明" :span="3">
            {{ detail.resolution_summary }}（{{ detail.resolved_by }} @ {{ formatTime(detail.resolved_at) }}）
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.risk_reason" label="风险接受" :span="3">
            {{ detail.risk_reason }}｜批准人：{{ detail.risk_approver }}｜复审：{{ detail.risk_review_at || "-" }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.recurrence_of_issue_id" label="复发自" :span="3">
            <el-link type="primary" @click="gotoIssue(detail.recurrence_of_issue_id!)">
              上一轮问题 #{{ detail.recurrence_of_issue_id }}
            </el-link>
          </el-descriptions-item>
        </el-descriptions>

        <div class="section-gap">
          <span class="muted">可用操作由后端 allowed_actions 下发（前端只渲染，不越权）：</span>
          <el-button
            v-if="can('acknowledge')"
            v-perms="'quality.issue.handle'"
            size="small"
            @click="openTransition('acknowledged', '确认问题有效')"
          >
            确认
          </el-button>
          <el-button
            v-if="can('start')"
            v-perms="'quality.issue.handle'"
            size="small"
            type="primary"
            @click="openTransition('in_progress', '开始整改')"
          >
            开始整改
          </el-button>
          <el-button
            v-if="can('assign')"
            v-perms="'quality.issue.assign'"
            size="small"
            type="primary"
            @click="onOpenAssign"
          >
            分派
          </el-button>
          <el-button
            v-if="can('wait_external')"
            v-perms="'quality.issue.handle'"
            size="small"
            type="warning"
            @click="externalDialogVisible = true"
          >
            等外部
          </el-button>
          <el-button
            v-if="can('request_verification')"
            v-perms="'quality.issue.handle'"
            size="small"
            type="success"
            @click="verifyDialogVisible = true"
          >
            提交待复测
          </el-button>
          <el-button
            v-if="can('verify')"
            v-perms="'quality.issue.verify'"
            size="small"
            type="success"
            @click="verifyResultVisible = true"
          >
            复测验证
          </el-button>
          <el-button
            v-if="can('accept_risk')"
            v-perms="'quality.issue.accept_risk'"
            size="small"
            type="warning"
            @click="riskDialogVisible = true"
          >
            风险接受
          </el-button>
          <el-button
            v-if="can('mark_false_positive')"
            v-perms="'quality.issue.handle'"
            size="small"
            @click="fpDialogVisible = true"
          >
            误报
          </el-button>
          <el-button
            v-if="can('cancel')"
            v-perms="'quality.issue.handle'"
            size="small"
            @click="openTransition('cancelled', '登记错误或对象退役')"
          >
            取消
          </el-button>
          <el-button
            v-if="can('reopen')"
            v-perms="'quality.control.manage'"
            size="small"
            @click="openTransition('acknowledged', '管理员重开（复发/复审到期）')"
          >
            重开
          </el-button>
          <el-button v-if="can('edit')" v-perms="'quality.issue.handle'" size="small" @click="onOpenEdit">
            编辑字段
          </el-button>
        </div>

        <el-tabs v-model="tab" class="section-gap">
          <el-tab-pane label="业务时间线" name="timeline">
            <el-timeline v-if="events.length">
              <el-timeline-item
                v-for="ev in events"
                :key="ev.id"
                :timestamp="formatTime(ev.occurred_at)"
                :type="eventTagType(ev.event_type)"
              >
                <b>{{ eventLabel(ev.event_type) }}</b>
                <span v-if="ev.from_status && ev.to_status" class="muted ml4">
                  {{ statusLabel(ev.from_status) }} → {{ statusLabel(ev.to_status) }}
                </span>
                <div v-if="ev.reason" class="ev-reason">{{ ev.reason }}</div>
                <div class="muted">{{ ev.actor_user_identifier || "-" }}</div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无事件" :image-size="60" />
          </el-tab-pane>
          <el-tab-pane label="关联观测" name="observations">
            <el-table :data="observations" stripe size="small">
              <el-table-column prop="observed_at" label="观测时间" width="150">
                <template #default="{ row }">{{ formatTime(row.observed_at) }}</template>
              </el-table-column>
              <el-table-column prop="result_status" label="结果" width="80" align="center">
                <template #default="{ row }">
                  <el-tag size="small" :type="obsTagType(row.result_status)">
                    {{ row.result_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="metric_value" label="指标" width="100" />
              <el-table-column prop="window_start" label="窗口" width="180">
                <template #default="{ row }">{{ row.window_start || "-" }} ~ {{ row.window_end || "-" }}</template>
              </el-table-column>
              <el-table-column label="来源" width="160">
                <template #default="{ row }">
                  <el-link
                    v-if="parseProbeFindingRef(row.source_record_ref)"
                    type="primary"
                    @click="goProbeFinding(parseProbeFindingRef(row.source_record_ref)!.id)"
                  >{{ row.source_kind }}</el-link>
                  <span v-else>{{ row.source_kind || "-" }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="run_key" label="run_key" min-width="180" show-overflow-tooltip />
            </el-table>
            <el-empty v-if="!observations.length" description="暂无观测" :image-size="60" />
          </el-tab-pane>
        </el-tabs>
      </template>
      <el-empty v-else-if="!loading" description="问题不存在或无权访问" />
    </el-card>

    <!-- 通用流转对话框 -->
    <el-dialog v-model="transitionVisible" :title="`流转到 ${transitionTitle}`" width="520px">
      <el-input
        v-model="transitionReason"
        type="textarea"
        :rows="3"
        placeholder="流转理由（必填，入审计）"
      />
      <template #footer>
        <el-button @click="transitionVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitTransition">确认</el-button>
      </template>
    </el-dialog>

    <!-- 分派 -->
    <el-dialog v-model="assignVisible" title="分派科室/人员" width="560px">
      <el-form label-width="80px">
        <el-form-item label="主责科室">
          <el-select
            v-model="assignForm.responsible_dept_code"
            filterable
            clearable
            class="w-full"
            @change="onAssignDeptChange"
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
          <el-select v-model="assignForm.responsible_person_code" filterable clearable class="w-full">
            <el-option
              v-for="p in persons"
              :key="p.person_code"
              :label="`${p.person_name_cn || p.person_code}（${p.person_code}）`"
              :value="p.person_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="分派说明">
          <el-input v-model="assignForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitAssign">确认分派</el-button>
      </template>
    </el-dialog>

    <!-- 等外部 -->
    <el-dialog v-model="externalDialogVisible" title="等待外部依赖" width="520px">
      <el-form label-width="90px">
        <el-form-item label="依赖类型" required>
          <el-select v-model="externalForm.wait_kind" class="w-full">
            <el-option label="等厂商" value="vendor" />
            <el-option label="等上游系统" value="upstream" />
            <el-option label="等接口开放" value="interface" />
            <el-option label="等外部审批" value="approval" />
          </el-select>
        </el-form-item>
        <el-form-item label="外部工单">
          <el-input v-model="externalForm.external_ticket_ref" placeholder="工单号（可选）" />
        </el-form-item>
        <el-form-item label="说明" required>
          <el-input v-model="externalForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="externalDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitExternal">确认</el-button>
      </template>
    </el-dialog>

    <!-- 提交待复测 -->
    <el-dialog v-model="verifyDialogVisible" title="提交待复测" width="520px">
      <el-alert type="info" :closable="false" class="mb8" title="提交后需由另一位有验证权限的人员复测通过才能关闭。" />
      <el-form label-width="90px">
        <el-form-item label="整改措施" required>
          <el-input v-model="verifyRequestForm.action_plan" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="完成说明" required>
          <el-input v-model="verifyRequestForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="verifyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitVerifyRequest">提交</el-button>
      </template>
    </el-dialog>

    <!-- 复测验证 -->
    <el-dialog v-model="verifyResultVisible" title="复测验证" width="520px">
      <el-alert
        type="warning"
        :closable="false"
        class="mb8"
        title="验证人不能是最后提交待复测的同一经办人（管理员豁免除外）。"
      />
      <el-form label-width="90px">
        <el-form-item label="验证结论" required>
          <el-radio-group v-model="verifyResultForm.passed">
            <el-radio :value="true">通过（关闭问题）</el-radio>
            <el-radio :value="false">不通过（退回整改）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="结论说明" required>
          <el-input v-model="verifyResultForm.reason" type="textarea" :rows="3" placeholder="如：复测指标回落至阈值内" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="verifyResultVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitVerifyResult">确认验证</el-button>
      </template>
    </el-dialog>

    <!-- 风险接受 -->
    <el-dialog v-model="riskDialogVisible" title="风险接受" width="520px">
      <el-form label-width="90px">
        <el-form-item label="风险原因" required>
          <el-input v-model="riskForm.risk_reason" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="批准人" required>
          <el-input v-model="riskForm.risk_approver" placeholder="如 质量委员会/科主任" />
        </el-form-item>
        <el-form-item label="复审日期" required>
          <el-date-picker v-model="riskForm.risk_review_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="riskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitRisk">确认接受</el-button>
      </template>
    </el-dialog>

    <!-- 误报 -->
    <el-dialog v-model="fpDialogVisible" title="标记误报（限时抑制）" width="520px">
      <el-alert
        type="info"
        :closable="false"
        class="mb8"
        title="抑制只作用于当前规则版本+范围，到期或版本变化后自动恢复判定。"
      />
      <el-form label-width="90px">
        <el-form-item label="误报原因" required>
          <el-input v-model="fpForm.false_positive_reason" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="抑制至" required>
          <el-date-picker v-model="fpForm.suppressed_until" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="备注" required>
          <el-input v-model="fpForm.reason" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fpDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitFalsePositive">确认</el-button>
      </template>
    </el-dialog>

    <!-- 编辑字段 -->
    <el-dialog v-model="editVisible" title="编辑非状态字段" width="560px">
      <el-form label-width="90px">
        <el-form-item label="整改措施">
          <el-input v-model="editForm.action_plan" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="计划完成日">
          <el-date-picker v-model="editForm.due_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editForm.priority" class="w160">
            <el-option v-for="p in PRIORITIES" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  acceptQualityIssueRisk,
  assignQualityIssue,
  getQualityIssue,
  listAssignmentDepartments,
  listAssignmentPersons,
  listQualityIssueEvents,
  listQualityIssueObservations,
  markQualityIssueFalsePositive,
  patchQualityIssue,
  requestQualityIssueVerification,
  transitionQualityIssue,
  verifyQualityIssue,
  type AssignmentDepartment,
  type AssignmentPerson,
  type QualityIssueDetail,
  type QualityIssueEvent,
  type QualityObservationItem
} from "@/api/quality";
import { extractErrorDetail } from "@/utils/errorMessage";
import { formatTime } from "@/utils/format";
import { parseProbeFindingRef, probeFindingLink } from "@/views/quality/sourceRef";

defineOptions({ name: "QualityIssueDetail" });

const PRIORITIES = ["P1", "P2", "P3", "P4"];

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
const EVENT_LABELS: Record<string, string> = {
  created: "建单",
  acknowledged: "确认",
  assigned: "分派",
  status_changed: "状态变更",
  action_plan_updated: "措施更新",
  fields_updated: "字段更新",
  comment_added: "评论",
  observation_linked: "观测挂接",
  verification_requested: "提交待复测",
  verification_passed: "复测通过",
  verification_failed: "复测不通过",
  reopened: "重开",
  resolved: "关闭",
  risk_accepted: "风险接受",
  suppression_set: "误报抑制",
  duplicate_marked: "标记重复"
};

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const acting = ref(false);
const detail = ref<QualityIssueDetail | null>(null);
const events = ref<QualityIssueEvent[]>([]);
const observations = ref<QualityObservationItem[]>([]);
const tab = ref("timeline");

const departments = ref<AssignmentDepartment[]>([]);
const persons = ref<AssignmentPerson[]>([]);

const transitionVisible = ref(false);
const transitionTo = ref("");
const transitionTitle = ref("");
const transitionReason = ref("");

const assignVisible = ref(false);
const assignForm = reactive({
  responsible_dept_code: "",
  responsible_person_code: "",
  reason: ""
});

const externalDialogVisible = ref(false);
const externalForm = reactive({ wait_kind: "vendor", external_ticket_ref: "", reason: "" });

const verifyDialogVisible = ref(false);
const verifyRequestForm = reactive({ action_plan: "", reason: "" });

const verifyResultVisible = ref(false);
const verifyResultForm = reactive({ passed: true, reason: "" });

const riskDialogVisible = ref(false);
const riskForm = reactive({ risk_reason: "", risk_approver: "", risk_review_at: "" });

const fpDialogVisible = ref(false);
const fpForm = reactive({ false_positive_reason: "", suppressed_until: "", reason: "" });

const editVisible = ref(false);
const editForm = reactive({ action_plan: "", due_at: "", priority: "" });

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

function severityLabel(severity: string | null): string {
  return SEVERITY_LABELS[severity || ""] || severity || "-";
}

function issueTypeLabel(issueType: string): string {
  return { data_defect: "数据缺陷", monitoring_gap: "监测缺口", manual: "手工问题" }[issueType] || issueType;
}

function eventLabel(eventType: string): string {
  return EVENT_LABELS[eventType] || eventType;
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

function eventTagType(eventType: string): "primary" | "success" | "warning" | "danger" {
  return (
    ({
      created: "danger",
      verification_passed: "success",
      resolved: "success",
      verification_failed: "warning",
      verification_requested: "primary",
      reopened: "warning"
    }) as Record<string, "primary" | "success" | "warning" | "danger">
  )[eventType] || "primary";
}

function obsTagType(result: string): "success" | "danger" | "warning" | "info" {
  return (
    { pass: "success", fail: "danger", blocked: "warning", no_data: "warning" } as Record<
      string,
      "success" | "danger" | "warning" | "info"
    >
  )[result] || "info";
}

function can(action: string): boolean {
  return !!detail.value?.allowed_actions?.includes(action);
}

function goBack() {
  router.push("/quality/issues");
}

function gotoIssue(id: number) {
  router.push(`/quality/issues/${id}`);
}

/** 178 R4①：观测来源为探查发现时，正向跳转发现页并按 finding_id 定位 */
function goProbeFinding(id: number) {
  router.push(probeFindingLink({ type: "probe_finding", id }));
}

async function loadAll() {
  const id = Number(route.params.id);
  if (!Number.isFinite(id)) return;
  loading.value = true;
  try {
    const [d, e, o] = await Promise.all([
      getQualityIssue(id),
      listQualityIssueEvents(id),
      listQualityIssueObservations(id)
    ]);
    detail.value = d;
    events.value = e.items;
    observations.value = o.items;
  } catch (error: any) {
    detail.value = null;
    ElMessage.error(extractErrorDetail(error, "问题详情加载失败（可能无权访问）"));
  } finally {
    loading.value = false;
  }
}

/** 409 冲突统一提示并刷新（174 S7：乐观锁冲突刷新） */
async function runAction(fn: () => Promise<QualityIssueDetail>, successText: string) {
  if (!detail.value) return;
  acting.value = true;
  try {
    detail.value = await fn();
    ElMessage.success(successText);
    await loadAll();
  } catch (error: any) {
    const detail409 = extractErrorDetail(error, "操作失败");
    if (/lock_version|409|冲突/.test(detail409)) {
      ElMessage.warning("数据已被他人修改（409），已刷新为最新版本，请重试");
      await loadAll();
    } else {
      ElMessage.error(detail409);
    }
  } finally {
    acting.value = false;
  }
}

function openTransition(toStatus: string, hint: string) {
  transitionTo.value = toStatus;
  transitionTitle.value = statusLabel(toStatus);
  transitionReason.value = "";
  transitionVisible.value = true;
}

function submitTransition() {
  if (!detail.value || !transitionReason.value.trim()) {
    ElMessage.warning("流转理由必填");
    return;
  }
  transitionVisible.value = false;
  runAction(
    () =>
      transitionQualityIssue(detail.value!.id, {
        to_status: transitionTo.value,
        expected_lock_version: detail.value!.lock_version,
        reason: transitionReason.value
      }),
    "流转完成"
  );
}

async function onOpenAssign() {
  assignForm.responsible_dept_code = detail.value?.responsible_dept_code || "";
  assignForm.responsible_person_code = detail.value?.responsible_person_code || "";
  assignForm.reason = "";
  assignVisible.value = true;
  if (!departments.value.length) {
    try {
      const res = await listAssignmentDepartments();
      departments.value = res.items;
    } catch (error: any) {
      ElMessage.error(extractErrorDetail(error, "科室选项加载失败"));
    }
  }
  if (assignForm.responsible_dept_code && !persons.value.length) {
    await onAssignDeptChange(assignForm.responsible_dept_code);
  }
}

async function onAssignDeptChange(deptCode: string) {
  persons.value = [];
  assignForm.responsible_person_code = "";
  if (!deptCode) return;
  try {
    const res = await listAssignmentPersons({ department_code: deptCode });
    persons.value = res.items;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "人员选项加载失败"));
  }
}

function submitAssign() {
  if (!detail.value) return;
  assignVisible.value = false;
  runAction(
    () =>
      assignQualityIssue(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        responsible_dept_code: assignForm.responsible_dept_code || undefined,
        responsible_person_code: assignForm.responsible_person_code || undefined,
        reason: assignForm.reason || "分派"
      }),
    "分派完成"
  );
}

function submitExternal() {
  if (!detail.value || !externalForm.reason.trim()) {
    ElMessage.warning("等待外部必须填写说明");
    return;
  }
  externalDialogVisible.value = false;
  runAction(
    () =>
      transitionQualityIssue(detail.value!.id, {
        to_status: "waiting_external",
        expected_lock_version: detail.value!.lock_version,
        reason: externalForm.reason,
        wait_kind: externalForm.wait_kind,
        wait_note: externalForm.reason,
        external_ticket_ref: externalForm.external_ticket_ref || undefined
      }),
    "已转等待外部"
  );
}

function submitVerifyRequest() {
  if (!detail.value || !verifyRequestForm.reason.trim() || !verifyRequestForm.action_plan.trim()) {
    ElMessage.warning("整改措施与完成说明必填");
    return;
  }
  verifyDialogVisible.value = false;
  runAction(
    () =>
      requestQualityIssueVerification(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        reason: verifyRequestForm.reason,
        action_plan: verifyRequestForm.action_plan
      }),
    "已提交待复测"
  );
}

function submitVerifyResult() {
  if (!detail.value || !verifyResultForm.reason.trim()) {
    ElMessage.warning("验证结论说明必填");
    return;
  }
  verifyResultVisible.value = false;
  runAction(
    () =>
      verifyQualityIssue(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        passed: verifyResultForm.passed,
        reason: verifyResultForm.reason
      }),
    verifyResultForm.passed ? "复测通过，问题已关闭" : "复测不通过，已退回整改"
  );
}

function submitRisk() {
  if (!detail.value || !riskForm.risk_reason.trim() || !riskForm.risk_approver.trim() || !riskForm.risk_review_at) {
    ElMessage.warning("风险原因、批准人、复审日期均必填");
    return;
  }
  riskDialogVisible.value = false;
  runAction(
    () =>
      acceptQualityIssueRisk(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        risk_reason: riskForm.risk_reason,
        risk_approver: riskForm.risk_approver,
        risk_review_at: riskForm.risk_review_at
      }),
    "已接受风险"
  );
}

function submitFalsePositive() {
  if (
    !detail.value ||
    !fpForm.false_positive_reason.trim() ||
    !fpForm.suppressed_until ||
    !fpForm.reason.trim()
  ) {
    ElMessage.warning("误报原因、抑制期限与备注均必填（禁止永久抑制）");
    return;
  }
  fpDialogVisible.value = false;
  runAction(
    () =>
      markQualityIssueFalsePositive(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        false_positive_reason: fpForm.false_positive_reason,
        suppressed_until: fpForm.suppressed_until,
        reason: fpForm.reason
      }),
    "已标记误报（限时抑制）"
  );
}

function onOpenEdit() {
  editForm.action_plan = detail.value?.action_plan || "";
  editForm.due_at = detail.value?.due_at || "";
  editForm.priority = detail.value?.priority || "";
  editVisible.value = true;
}

function submitEdit() {
  if (!detail.value) return;
  const fields: Record<string, unknown> = {};
  if (editForm.action_plan) fields.action_plan = editForm.action_plan;
  if (editForm.due_at) fields.due_at = editForm.due_at;
  if (editForm.priority) fields.priority = editForm.priority;
  if (!Object.keys(fields).length) {
    editVisible.value = false;
    return;
  }
  editVisible.value = false;
  runAction(
    () =>
      patchQualityIssue(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        fields
      }),
    "字段已更新"
  );
}

onMounted(loadAll);
</script>

<style scoped>
.quality-issue-detail-page {
  min-height: calc(100vh - 84px);
}

.main-card {
  margin: 12px 16px;
}

.section-gap {
  margin-top: 16px;
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

.overdue {
  color: #f56c6c;
  font-weight: 600;
}

.ev-reason {
  margin: 4px 0;
  white-space: pre-wrap;
}

.mb8 {
  margin-bottom: 8px;
}

.w160 {
  width: 160px;
}

.w-full {
  width: 100%;
}
</style>
