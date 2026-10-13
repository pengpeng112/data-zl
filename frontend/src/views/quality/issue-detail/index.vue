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
            <span v-if="detail.wait_note" class="muted">（{{ detail.wait_note }}）</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.escalation_level > 0" label="督办">
            <el-tag size="small" type="warning">已升级督办</el-tag>
            <span class="muted ml4">L{{ detail.escalation_level }}</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.primary_vendor_code" label="责任厂商">
            {{ detail.primary_vendor_code }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.supervisor_user_identifier" label="督办人">
            {{ detail.supervisor_user_identifier }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.vendor_promised_at" label="厂商承诺日">
            {{ formatTime(detail.vendor_promised_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.next_followup_at" label="下次跟进">
            {{ formatTime(detail.next_followup_at) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.original_due_at" label="原截止日">
            {{ formatTime(detail.original_due_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="复测状态">
            <el-tag size="small" :type="recheckTagType(detail.recheck_substatus)">
              {{ recheckLabel(detail.recheck_substatus) }}
            </el-tag>
            <span v-if="detail.recheck_pass_streak" class="muted ml4">
              连续通过 {{ detail.recheck_pass_streak }}
            </span>
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
          <!-- 208 A4：waiting_verify 取回继续整改（后端 resume 已下发，前端原缺入口） -->
          <el-button
            v-if="can('resume')"
            v-perms="'quality.issue.handle'"
            size="small"
            @click="openTransition('in_progress', '取回继续整改')"
          >
            取回整改
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
            @click="openVerifyResult"
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
          <el-button v-perms="'quality.issue.handle'" size="small" type="primary" @click="openFollowup">
            厂商跟进
          </el-button>
          <el-button v-perms="'quality.issue.assign'" size="small" type="warning" @click="doRemind">
            催办
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

    <!-- U05：复测与整改验证卡片 -->
    <el-card v-if="detail" shadow="never" class="main-card recheck-card">
      <template #header>
        <span>复测与整改验证</span>
        <el-tag size="small" :type="recheckTagType(detail.recheck_substatus)" class="ml4">
          {{ recheckLabel(detail.recheck_substatus) }}
        </el-tag>
        <span v-if="detail.recheck_pass_streak" class="muted ml4">
          连续通过 {{ detail.recheck_pass_streak }}
        </span>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="整改提交时间">
          {{ formatTime(detail.remediation_submitted_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="复测运行">
          <el-button
            v-if="detail.last_verification_run_id"
            v-perms="'quality.run.read'"
            size="small"
            type="primary"
            link
            @click="openRunDrawer(detail.last_verification_run_id!)"
          >
            查看复测运行 #{{ detail.last_verification_run_id }}
          </el-button>
          <span v-else class="muted">暂无</span>
        </el-descriptions-item>
        <el-descriptions-item label="督办状态">
          {{ detail.escalation_level > 0 ? `已升级督办 L${detail.escalation_level}` : "未升级" }}
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.recheck_note" label="复测说明" :span="3">
          {{ detail.recheck_note }}
        </el-descriptions-item>
      </el-descriptions>
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
        <el-form-item label="整改证据">
          <el-input v-model="verifyRequestForm.remediation_evidence_ref" placeholder="证据引用（复测运行/截图/工单号，可选）" />
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
        <el-form-item v-if="verifyResultForm.passed" label="复测运行">
          <el-input-number
            v-model="verifyResultForm.verification_run_id"
            :min="1"
            controls-position="right"
            placeholder="关联自动复测运行 ID（手工清单可留空）"
            class="w-full"
          />
        </el-form-item>
        <el-form-item v-if="verifyResultForm.passed && !verifyResultForm.verification_run_id" label="手工证据" required>
          <el-input
            v-model="verifyResultForm.manual_evidence_note"
            type="textarea"
            :rows="2"
            placeholder="未关联复测运行时必填（人工验证证据说明）"
          />
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

    <!-- U03：厂商跟进 -->
    <el-dialog v-model="followupVisible" title="厂商跟进" width="640px">
      <el-form label-width="100px">
        <el-form-item label="跟进类型" required>
          <el-select v-model="followupForm.kind" class="w160">
            <el-option label="进展" value="progress" />
            <el-option label="厂商工单" value="ticket" />
            <el-option label="厂商承诺" value="commitment" />
            <el-option label="催办记录" value="remind" />
          </el-select>
        </el-form-item>
        <el-form-item label="跟进说明" required>
          <el-input v-model="followupForm.note" type="textarea" :rows="3" placeholder="跟进内容（必填，入时间线）" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-select
            v-model="followupForm.vendor_code"
            filterable
            clearable
            placeholder="选择厂商（可搜索）"
            class="w-full"
          >
            <el-option
              v-for="v in vendors"
              :key="v.vendor_code"
              :label="`${v.vendor_name}（${v.vendor_code}）`"
              :value="v.vendor_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="外部工单号">
          <el-input v-model="followupForm.external_ticket_ref" placeholder="厂商工单号（可选）" />
        </el-form-item>
        <el-form-item label="厂商承诺日">
          <el-date-picker v-model="followupForm.vendor_promised_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="下次跟进日">
          <el-date-picker v-model="followupForm.next_followup_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="延期至">
          <el-date-picker v-model="followupForm.change_due_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item v-if="followupForm.change_due_at" label="延期原因" required>
          <el-input
            v-model="followupForm.change_due_reason"
            type="textarea"
            :rows="2"
            placeholder="填写延期至后必填；延期将保留原截止日期（记录为 original_due_at）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="followupVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitFollowup">登记跟进</el-button>
      </template>
    </el-dialog>

    <!-- U05：复测运行详情抽屉 -->
    <el-drawer
      v-model="runDrawerVisible"
      size="760px"
      :title="runDetail ? `复测运行 ${runDetail.run_code}` : '复测运行'"
    >
      <div v-loading="runDrawerLoading" class="run-drawer-body">
        <template v-if="runDetail">
          <el-descriptions :column="2" border size="small" class="mb8">
            <el-descriptions-item label="状态">
              <el-tag size="small" :type="runStatusTagType(runDetail.status)">
                {{ RUN_STATUS_MAP[runDetail.status] || runDetail.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="目的">
              {{ runDetail.purpose === "recheck" ? "复测" : runDetail.purpose }}
            </el-descriptions-item>
            <el-descriptions-item label="检测器">
              <template v-if="runDetail.detector_kind">
                {{ DETECTOR_KIND_LABELS[runDetail.detector_kind] || runDetail.detector_kind }}：{{ runDetail.detector_ref || "-" }}
              </template>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="触发">{{ runDetail.trigger_kind || "-" }}</el-descriptions-item>
            <el-descriptions-item label="开始 / 结束">
              {{ formatTime(runDetail.started_at) }} ~ {{ formatTime(runDetail.finished_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="尝试">
              {{ runDetail.attempt ?? "-" }} / {{ runDetail.max_attempts ?? "-" }}
            </el-descriptions-item>
            <el-descriptions-item v-if="runDetail.result_summary" label="结果摘要" :span="2">
              {{ runDetail.result_summary }}
            </el-descriptions-item>
            <el-descriptions-item v-if="runDetail.error_message_sanitized" label="错误" :span="2">
              <span class="err-text">{{ runDetail.error_code ? `[${runDetail.error_code}] ` : "" }}{{ runDetail.error_message_sanitized }}</span>
            </el-descriptions-item>
          </el-descriptions>
          <template v-if="runDetail.children && runDetail.children.length">
            <div class="block-title">子运行</div>
            <el-table :data="runDetail.children" stripe size="small" class="mb8">
              <el-table-column prop="run_code" label="运行单" width="150" show-overflow-tooltip />
              <el-table-column label="检测器" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ DETECTOR_KIND_LABELS[row.detector_kind] || row.detector_kind }}：{{ row.detector_ref }}
                </template>
              </el-table-column>
              <el-table-column label="状态" width="86" align="center">
                <template #default="{ row }">{{ RUN_STATUS_MAP[row.status] || row.status }}</template>
              </el-table-column>
            </el-table>
          </template>
          <div class="block-title">观测明细</div>
          <el-table :data="runDetail.observations" stripe size="small">
            <el-table-column label="结果" width="110" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="obsTagType(row.result_status)">
                  {{ RESULT_STATUS_LABELS[row.result_status] || row.result_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="metric_value" label="指标" width="90">
              <template #default="{ row }">{{ row.metric_value ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="分子" width="80" align="right">
              <template #default="{ row }">{{ row.numerator ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="分母" width="80" align="right">
              <template #default="{ row }">{{ row.denominator ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="错误" min-width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.error || "-" }}</template>
            </el-table-column>
            <el-table-column label="观测时间" width="150">
              <template #default="{ row }">{{ formatTime(row.observed_at) }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!runDetail.observations.length" description="暂无观测" :image-size="60" />
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  acceptQualityIssueRisk,
  assignQualityIssue,
  followupQualityIssue,
  getQualityIssue,
  getQualityRun,
  listAssignmentDepartments,
  listAssignmentPersons,
  listQualityIssueEvents,
  listQualityIssueObservations,
  listQualityVendors,
  markQualityIssueFalsePositive,
  patchQualityIssue,
  remindQualityIssue,
  requestQualityIssueVerification,
  transitionQualityIssue,
  verifyQualityIssue,
  type AssignmentDepartment,
  type AssignmentPerson,
  type QualityIssueDetail,
  type QualityIssueEvent,
  type QualityObservationItem,
  type QualityRunDetail,
  type QualityVendorItem
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
  duplicate_marked: "标记重复",
  // 207：厂商跟进 / 催办 / 复测 / 运行挂接
  followup_added: "厂商跟进",
  reminded: "催办",
  recheck_passed: "自动复测通过",
  recheck_failed: "复测未通过",
  recheck_blocked: "复测受阻",
  run_linked: "运行挂接"
};
/** 207 U02：复测子状态 / 运行状态 / 检测器类型 / 观测六态中文映射。 */
const RECHECK_STATUS_MAP: Record<string, string> = {
  none: "未复测",
  pending: "复测中",
  passed: "自动复测通过",
  failed: "复测未通过",
  blocked: "复测受阻"
};
const RUN_STATUS_MAP: Record<string, string> = {
  queued: "排队中",
  waiting_window: "等待窗口",
  running: "执行中",
  succeeded: "成功",
  partial: "部分成功",
  failed: "失败",
  cancelled: "已取消",
  blocked: "受阻"
};
const DETECTOR_KIND_LABELS: Record<string, string> = {
  probe_template: "探查模板",
  quality_rule: "质量规则",
  manual: "人工",
  external: "外部"
};
const RESULT_STATUS_LABELS: Record<string, string> = {
  pass: "通过",
  fail: "未通过",
  no_data: "无数据",
  error: "错误",
  blocked: "受阻",
  skipped: "跳过"
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
const verifyRequestForm = reactive({
  action_plan: "",
  reason: "",
  remediation_evidence_ref: ""
});

const verifyResultVisible = ref(false);
const verifyResultForm = reactive({
  passed: true,
  reason: "",
  verification_run_id: null as number | null,
  manual_evidence_note: ""
});

const riskDialogVisible = ref(false);
const riskForm = reactive({ risk_reason: "", risk_approver: "", risk_review_at: "" });

const fpDialogVisible = ref(false);
const fpForm = reactive({ false_positive_reason: "", suppressed_until: "", reason: "" });

const editVisible = ref(false);
const editForm = reactive({ action_plan: "", due_at: "", priority: "" });

/** 207 U03：厂商跟进 */
const followupVisible = ref(false);
const vendors = ref<QualityVendorItem[]>([]);
const followupForm = reactive({
  kind: "progress",
  note: "",
  vendor_code: "",
  external_ticket_ref: "",
  vendor_promised_at: "",
  next_followup_at: "",
  change_due_at: "",
  change_due_reason: ""
});

/** 207 U05：复测运行抽屉 */
const runDrawerVisible = ref(false);
const runDrawerLoading = ref(false);
const runDetail = ref<QualityRunDetail | null>(null);

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
      reopened: "warning",
      followup_added: "primary",
      reminded: "warning",
      recheck_passed: "success",
      recheck_failed: "danger",
      recheck_blocked: "warning"
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

function recheckLabel(substatus: string | null | undefined): string {
  return RECHECK_STATUS_MAP[substatus || "none"] || substatus || "未复测";
}

function recheckTagType(
  substatus: string | null | undefined
): "success" | "danger" | "warning" | "info" {
  return (
    { passed: "success", failed: "danger", blocked: "warning", pending: "warning", none: "info" } as Record<
      string,
      "success" | "danger" | "warning" | "info"
    >
  )[substatus || "none"] || "info";
}

function runStatusTagType(
  status: string
): "success" | "warning" | "info" | "danger" | "primary" {
  return (
    {
      queued: "info",
      waiting_window: "warning",
      running: "primary",
      succeeded: "success",
      partial: "warning",
      failed: "danger",
      cancelled: "info",
      blocked: "danger"
    } as Record<string, "success" | "warning" | "info" | "danger" | "primary">
  )[status] || "info";
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

async function submitVerifyRequest() {
  if (!detail.value || !verifyRequestForm.reason.trim() || !verifyRequestForm.action_plan.trim()) {
    ElMessage.warning("整改措施与完成说明必填");
    return;
  }
  verifyDialogVisible.value = false;
  acting.value = true;
  try {
    const res = await requestQualityIssueVerification(detail.value.id, {
      expected_lock_version: detail.value.lock_version,
      reason: verifyRequestForm.reason,
      action_plan: verifyRequestForm.action_plan,
      remediation_evidence_ref: verifyRequestForm.remediation_evidence_ref.trim() || undefined
    });
    detail.value = res;
    showRecheckHint(res);
    await loadAll();
  } catch (error: any) {
    const detailText = extractErrorDetail(error, "操作失败");
    if (/lock_version|409|冲突/.test(detailText)) {
      ElMessage.warning("数据已被他人修改（409），已刷新为最新版本，请重试");
      await loadAll();
    } else {
      ElMessage.error(detailText);
    }
  } finally {
    acting.value = false;
  }
}

/** U05：按提交响应的复测排队结果提示（自动排队 / 手工清单 / 受阻）。 */
function showRecheckHint(res: QualityIssueDetail) {
  const recheck = (
    res as QualityIssueDetail & {
      recheck?: {
        mode?: string;
        run_id?: number | null;
        manual_required?: boolean;
        blocked_reasons?: string[];
      };
    }
  ).recheck;
  if (recheck?.mode === "auto" && recheck.run_id) {
    ElMessage.success(`自动复测已排队（运行 #${recheck.run_id}）`);
  } else if (recheck?.manual_required) {
    ElMessage.warning("手工清单：复测走人工验证路径");
  } else if (recheck?.blocked_reasons?.length) {
    ElMessage.error(`复测排队受阻：${recheck.blocked_reasons.join("；")}`);
  } else if (res.last_verification_run_id) {
    ElMessage.success(`自动复测已排队（运行 #${res.last_verification_run_id}）`);
  } else if (res.recheck_substatus === "blocked") {
    ElMessage.warning(`复测受阻：${res.recheck_note || "详见复测卡片"}`);
  } else {
    ElMessage.success("已提交待复测");
  }
}

/** 复测验证：默认关联最近一次复测运行；未关联运行（手工清单）时人工证据必填。 */
function openVerifyResult() {
  verifyResultForm.passed = true;
  verifyResultForm.reason = "";
  verifyResultForm.verification_run_id = detail.value?.last_verification_run_id ?? null;
  verifyResultForm.manual_evidence_note = "";
  verifyResultVisible.value = true;
}

function submitVerifyResult() {
  if (!detail.value || !verifyResultForm.reason.trim()) {
    ElMessage.warning("验证结论说明必填");
    return;
  }
  if (
    verifyResultForm.passed &&
    !verifyResultForm.verification_run_id &&
    !verifyResultForm.manual_evidence_note.trim()
  ) {
    ElMessage.warning("手工清单验证需填写人工证据说明（或关联复测运行）");
    return;
  }
  verifyResultVisible.value = false;
  runAction(
    () =>
      verifyQualityIssue(detail.value!.id, {
        expected_lock_version: detail.value!.lock_version,
        passed: verifyResultForm.passed,
        reason: verifyResultForm.reason,
        ...(verifyResultForm.passed && verifyResultForm.verification_run_id
          ? { verification_run_id: verifyResultForm.verification_run_id }
          : {}),
        ...(verifyResultForm.passed && verifyResultForm.manual_evidence_note.trim()
          ? { manual_evidence_note: verifyResultForm.manual_evidence_note.trim() }
          : {})
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

/** 207 U03：厂商跟进（进展/工单/承诺/催办留痕，可附承诺日与延期）。 */
async function openFollowup() {
  for (const key of Object.keys(followupForm) as (keyof typeof followupForm)[]) {
    (followupForm as any)[key] = "";
  }
  followupForm.kind = "progress";
  followupForm.vendor_code = detail.value?.primary_vendor_code || "";
  followupVisible.value = true;
  if (!vendors.value.length) {
    try {
      const res = await listQualityVendors({ status: "active", page: 1, page_size: 100 });
      vendors.value = res.items;
    } catch (error: any) {
      ElMessage.error(extractErrorDetail(error, "厂商选项加载失败"));
    }
  }
}

function submitFollowup() {
  if (!detail.value) return;
  if (!followupForm.note.trim()) {
    ElMessage.warning("跟进说明必填");
    return;
  }
  if (followupForm.change_due_at && !followupForm.change_due_reason.trim()) {
    ElMessage.warning("填写延期时必须填写延期原因（延期将保留原截止日期）");
    return;
  }
  followupVisible.value = false;
  runAction(
    () =>
      followupQualityIssue(detail.value!.id, {
        kind: followupForm.kind,
        note: followupForm.note.trim(),
        vendor_code: followupForm.vendor_code || undefined,
        external_ticket_ref: followupForm.external_ticket_ref.trim() || undefined,
        vendor_promised_at: followupForm.vendor_promised_at || undefined,
        next_followup_at: followupForm.next_followup_at || undefined,
        change_due_at: followupForm.change_due_at || undefined,
        change_due_reason: followupForm.change_due_reason.trim() || undefined
      }),
    "已登记厂商跟进"
  );
}

/** 207 U03：催办（同日不重复产生站内待办）。 */
async function doRemind() {
  if (!detail.value) return;
  let reason = "";
  try {
    const { value } = await ElMessageBox.prompt("催办理由（必填，入审计）", `催办 ${detail.value.issue_code}`, {
      inputValidator: (input: string) => (input && input.trim() ? true : "催办理由必填")
    });
    reason = value.trim();
  } catch {
    return;
  }
  acting.value = true;
  try {
    const res = await remindQualityIssue(detail.value.id, { reason });
    if (res.notification_created) {
      ElMessage.success("已催办并产生站内待办");
    } else {
      ElMessage.info("今日已催办，不重复产生站内待办");
    }
    await loadAll();
  } catch (error: any) {
    const detailText = extractErrorDetail(error, "催办失败");
    if (/lock_version|409|冲突/.test(detailText)) {
      ElMessage.warning("数据已被他人修改（409），已刷新为最新版本，请重试");
      await loadAll();
    } else {
      ElMessage.error(detailText);
    }
  } finally {
    acting.value = false;
  }
}

/** 207 U05：查看复测运行（状态 + 子运行 + 观测明细）。 */
async function openRunDrawer(runId: number) {
  runDetail.value = null;
  runDrawerLoading.value = true;
  runDrawerVisible.value = true;
  try {
    runDetail.value = await getQualityRun(runId);
  } catch (error: any) {
    runDrawerVisible.value = false;
    ElMessage.error(extractErrorDetail(error, "复测运行加载失败"));
  } finally {
    runDrawerLoading.value = false;
  }
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

.recheck-card {
  margin-top: 0;
}

.run-drawer-body {
  min-height: 80px;
}

.block-title {
  margin: 12px 0 8px;
  font-weight: 600;
}

.err-text {
  color: #f56c6c;
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
