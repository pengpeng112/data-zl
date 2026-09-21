<template>
  <div class="accuracy-page">
    <el-card shadow="never" class="mb-4">
      <template #header>
        <div class="card-header">
          <span>准确性看板（只统计已审核反馈与黄金用例）</span>
          <el-button size="small" @click="loadDashboard">刷新</el-button>
        </div>
      </template>
      <el-row v-if="dash" :gutter="12">
        <el-col :span="6">
          <el-statistic title="已审核反馈" :value="dash.audited_feedback_total" />
          <div class="sub">未评价 {{ dash.unevaluated_feedback }} 条（不计入准确率）</div>
        </el-col>
        <el-col :span="6">
          <el-statistic title="黄金用例通过" :value="dash.golden_pass" />
          <div class="sub">失败 {{ dash.golden_fail }} · 错误 {{ dash.golden_error }}</div>
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="黄金用例通过率"
            :value="dash.golden_pass_rate ?? 0"
            :precision="dash.golden_pass_rate == null ? 0 : 4"
          />
          <div class="sub">窗口：{{ dash.golden_case_runs_window }}</div>
        </el-col>
        <el-col :span="6">
          <div class="rating-list">
            <div v-for="(count, rating) in dash.feedback_rating_distribution" :key="rating" class="rating-row">
              <el-tag size="small" :type="ratingTone(String(rating))">{{ ratingLabel(String(rating)) }}</el-tag>
              <span>{{ count }}</span>
            </div>
          </div>
        </el-col>
      </el-row>
      <el-alert
        v-if="dash"
        :title="dash.notes"
        type="info"
        :closable="false"
        class="mt-2"
      />
    </el-card>

    <el-card shadow="never" class="mb-4">
      <template #header><span>提交准确性反馈</span></template>
      <!-- 186 P1-1：结果 → 反馈上下文提示（URL 只带定位 ID；上下文以接口回读为准） -->
      <el-alert
        v-if="linkAlert"
        :type="linkAlert.type"
        :title="linkAlert.text"
        :closable="false"
        class="mb-2"
      />
      <el-form :model="form" label-width="120px" size="small">
        <el-form-item label="问题摘要" required>
          <el-input v-model="form.question" placeholder="例：2026年7月住院次均费用" />
        </el-form-item>
        <el-form-item label="结论评价" required>
          <el-select v-model="form.rating" style="width: 260px">
            <el-option v-for="opt in RATINGS" :key="opt.v" :label="opt.label" :value="opt.v" />
          </el-select>
        </el-form-item>
        <el-form-item label="错误类型">
          <el-select v-model="form.errorTypes" multiple collapse-tags style="width: 100%">
            <el-option v-for="et in ERROR_TYPES" :key="et.v" :label="et.label" :value="et.v" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明（脱敏）">
          <el-input v-model="form.comment" type="textarea" :rows="2" placeholder="不写入患者信息/凭据" />
        </el-form-item>
        <el-form-item>
          <el-button v-perms="'feedback.create'" type="primary" size="small" :loading="submitting" @click="submit">
            登记回答并提交反馈
          </el-button>
        </el-form-item>
      </el-form>
      <!-- 186 P1-1：提交成功显示反馈编号与「查看我的反馈」锚点链接 -->
      <el-alert v-if="lastFeedback" type="success" :closable="false" class="mt-2">
        <template #title>
          反馈 #{{ lastFeedback.feedback_id }} 已提交（状态：{{ lastFeedback.status }}）
          <el-link type="primary" :underline="false" class="ml-2" @click="goMyFeedback">查看我的反馈</el-link>
        </template>
      </el-alert>
    </el-card>

    <!-- 186 Q2：我的反馈 / 审核队列（§4.4 列表契约消费） -->
    <el-card id="feedback-records" shadow="never" class="mb-4">
      <template #header>
        <div class="card-header">
          <span>反馈记录</span>
          <el-radio-group v-model="feedbackScope" size="small" @change="loadFeedback(1)">
            <el-radio-button value="mine">我的反馈</el-radio-button>
            <el-radio-button value="queue">审核队列</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table v-loading="feedbackLoading" :data="feedbackItems" size="small" stripe>
        <el-table-column prop="feedback_id" label="ID" width="70" />
        <el-table-column prop="rating" label="评价" width="130" />
        <el-table-column prop="status" label="状态" width="140">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'resolved' ? 'success' : row.status === 'rejected' ? 'info' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象" min-width="200">
          <template #default="{ row }">
            {{ row.query_code ? `${row.query_code}@v${row.query_version}` : row.metric_code ? `${row.metric_code}@v${row.metric_version}` : row.product_code || "-" }}
          </template>
        </el-table-column>
        <el-table-column prop="run_id" label="run" width="80">
          <template #default="{ row }">{{ row.run_id ?? "-" }}</template>
        </el-table-column>
        <el-table-column label="错误类型" min-width="160">
          <template #default="{ row }">{{ (row.error_types || []).join(", ") || "-" }}</template>
        </el-table-column>
        <el-table-column prop="submitted_at" label="提交时间" min-width="150">
          <template #default="{ row }">{{ formatTime(row.submitted_at) }}</template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="feedbackTotal > feedbackPageSize"
        layout="total, prev, pager, next"
        :total="feedbackTotal"
        :page-size="feedbackPageSize"
        :current-page="feedbackPage"
        size="small"
        class="mt-3"
        @current-change="loadFeedback"
      />
      <el-alert v-if="feedbackError" type="error" :title="feedbackError" :closable="false" class="mt-3" />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>回归评测</span>
          <el-button v-perms="'evaluation.run'" size="small" type="primary" :loading="running" @click="runEval">
            回放全部黄金用例
          </el-button>
        </div>
      </template>
      <el-descriptions v-if="evalSummary" :column="4" size="small" border>
        <el-descriptions-item label="总数">{{ evalSummary.total }}</el-descriptions-item>
        <el-descriptions-item label="通过">{{ evalSummary.passed }}</el-descriptions-item>
        <el-descriptions-item label="失败">{{ evalSummary.failed }}</el-descriptions-item>
        <el-descriptions-item label="错误">{{ evalSummary.errors }}</el-descriptions-item>
      </el-descriptions>
      <el-table v-if="evalSummary?.cases?.length" :data="evalSummary.cases" size="small" class="mt-2">
        <el-table-column prop="case_code" label="用例" width="160" />
        <el-table-column prop="status" label="结果" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'pass' ? 'success' : row.status === 'fail' ? 'danger' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="run_id" label="运行 ID" />
      </el-table>
      <el-empty v-else description="尚无评测结果" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import {
  fetchAccuracyDashboard,
  fetchMetricDetail,
  fetchQueryRunDetail,
  listAiFeedback,
  registerAnswerEvent,
  runEvaluation,
  submitFeedback,
  type AccuracyDashboard,
  type EvaluationRunSummary,
  type QueryRun
} from "@/api/query-center";

defineOptions({ name: "QueryAccuracy" });

const route = useRoute();

const RATINGS = [
  { v: "correct", label: "正确" },
  { v: "partially_correct", label: "部分正确" },
  { v: "incorrect", label: "错误" },
  { v: "insufficient_evidence", label: "证据不足" },
  { v: "ambiguous", label: "问题歧义" }
];

const ERROR_TYPES = [
  { v: "metadata_stale", label: "元数据过期" },
  { v: "wrong_source", label: "来源错误" },
  { v: "wrong_field", label: "字段错误" },
  { v: "join_error", label: "JOIN 错误" },
  { v: "fanout", label: "fanout 膨胀" },
  { v: "filter_error", label: "过滤错误" },
  { v: "time_semantics", label: "时间口径" },
  { v: "dedup", label: "去重" },
  { v: "numerator", label: "分子" },
  { v: "denominator", label: "分母" },
  { v: "formula", label: "公式" },
  { v: "dimension", label: "维度" },
  { v: "parameter", label: "参数" },
  { v: "source_data_quality", label: "数据源质量" },
  { v: "result_stale", label: "结果过期" },
  { v: "permission_or_masking", label: "权限/脱敏" },
  { v: "performance", label: "性能" },
  { v: "answer_phrasing", label: "回答表述" }
];

const dash = ref<AccuracyDashboard | null>(null);

// 186 Q2：反馈记录（mine=本人历史；queue 需 feedback:review，403 时提示）
const feedbackScope = ref<"mine" | "queue">("mine");
const feedbackItems = ref<any[]>([]);
const feedbackTotal = ref(0);
const feedbackPage = ref(1);
const feedbackPageSize = 20;
const feedbackLoading = ref(false);
const feedbackError = ref<string | null>(null);

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-";
}

async function loadFeedback(page = 1) {
  feedbackLoading.value = true;
  feedbackError.value = null;
  try {
    const { data } = await listAiFeedback({
      scope: feedbackScope.value,
      page,
      page_size: feedbackPageSize
    });
    feedbackItems.value = data.items || [];
    feedbackTotal.value = data.total ?? 0;
    feedbackPage.value = page;
  } catch (e: any) {
    feedbackItems.value = [];
    feedbackTotal.value = 0;
    const status = e?.response?.status;
    feedbackError.value =
      status === 403
        ? feedbackScope.value === "queue"
          ? "审核队列需要 feedback:review 权限"
          : "缺少反馈读取权限（feedback:create / feedback:review）"
        : e?.response?.data?.detail || e?.message || "反馈列表加载失败";
  } finally {
    feedbackLoading.value = false;
  }
}
const evalSummary = ref<EvaluationRunSummary | null>(null);
const submitting = ref(false);
const running = ref(false);

const form = reactive({
  question: "",
  rating: "correct",
  errorTypes: [] as string[],
  comment: ""
});

// 186 P1-1：结果 → 反馈链上下文。URL 只带非敏感定位 ID（run_id/metric_code），
// query_code/version/digest 等一律以运行/指标详情接口回读为准，不信任 URL 传值；
// 回读失败（404/403 等）不伪造上下文，提示可提交通用意见。
type LinkState = "none" | "loading" | "linked" | "missing";
const linkState = ref<LinkState>("none");
const linkMissingText = ref("未找到运行记录，可提交通用意见（不会伪造上下文）");
const linkedRun = ref<Pick<QueryRun, "id" | "query_code" | "version" | "result_digest"> | null>(null);
const linkedMetric = ref<{ metric_code: string; metric_version: number | null } | null>(null);

const linkAlert = computed<{ type: "info" | "success" | "warning"; text: string } | null>(() => {
  if (linkState.value === "loading") {
    return { type: "info", text: "正在回读关联运行/指标记录…" };
  }
  if (linkState.value === "linked" && linkedRun.value) {
    const run = linkedRun.value;
    return {
      type: "success",
      text: `已关联运行记录：${run.query_code}@v${run.version ?? "?"} · run #${run.id}（上下文来自运行详情回读，问题摘要请自行填写）`
    };
  }
  if (linkState.value === "linked" && linkedMetric.value) {
    const metric = linkedMetric.value;
    return {
      type: "success",
      text: `已关联指标记录：${metric.metric_code}${metric.metric_version != null ? `@v${metric.metric_version}` : ""}（上下文来自指标详情回读，问题摘要请自行填写）`
    };
  }
  if (linkState.value === "missing") {
    return { type: "warning", text: linkMissingText.value };
  }
  return null;
});

async function loadLinkedContext() {
  const metricCode = route.query.metric_code;
  const runIdRaw = route.query.run_id;
  const wantMetric = typeof metricCode === "string" && metricCode.trim() !== "";
  const wantRun = runIdRaw != null && String(runIdRaw).trim() !== "";
  if (!wantMetric && !wantRun) return;
  const missingText = wantMetric
    ? "未找到指标记录，可提交通用意见（不会伪造上下文）"
    : "未找到运行记录，可提交通用意见（不会伪造上下文）";
  linkState.value = "loading";
  try {
    if (wantMetric) {
      const res = await fetchMetricDetail(metricCode as string);
      const data = res.data as {
        definition?: { metric_code?: string };
        active_version?: { version?: number | null };
      } | null;
      const code = data?.definition?.metric_code;
      if (!code) {
        linkMissingText.value = missingText;
        linkState.value = "missing";
        return;
      }
      linkedMetric.value = { metric_code: code, metric_version: data?.active_version?.version ?? null };
      linkState.value = "linked";
      return;
    }
    const runId = Number(runIdRaw);
    if (!Number.isInteger(runId) || runId <= 0) {
      linkMissingText.value = missingText;
      linkState.value = "missing";
      return;
    }
    const res = await fetchQueryRunDetail(runId);
    const run = res.data;
    if (!run?.id || !run?.query_code) {
      linkMissingText.value = missingText;
      linkState.value = "missing";
      return;
    }
    linkedRun.value = run;
    linkState.value = "linked";
  } catch {
    linkedRun.value = null;
    linkedMetric.value = null;
    linkMissingText.value = missingText;
    linkState.value = "missing";
  }
}

function ratingLabel(rating: string): string {
  return RATINGS.find((r) => r.v === rating)?.label ?? rating;
}

function ratingTone(rating: string): "success" | "warning" | "danger" | "info" {
  if (rating === "correct") return "success";
  if (rating === "partially_correct") return "warning";
  if (rating === "incorrect") return "danger";
  return "info";
}

async function loadDashboard() {
  try {
    const res = await fetchAccuracyDashboard();
    dash.value = res.data;
  } catch {
    ElMessage.error("看板加载失败");
  }
}

async function submit() {
  if (!form.question.trim()) {
    ElMessage.warning("请填写问题摘要");
    return;
  }
  submitting.value = true;
  try {
    const answer = await registerAnswerEvent({
      question_summary: form.question,
      caller_id: "web-console",
      // 186 P1-1：携带回读得到的运行/指标上下文；未关联时不带，不伪造
      ...(linkedRun.value
        ? {
            query_code: linkedRun.value.query_code,
            query_version: linkedRun.value.version ?? undefined,
            run_id: linkedRun.value.id,
            ...(linkedRun.value.result_digest
              ? { result_digest: linkedRun.value.result_digest }
              : {})
          }
        : {}),
      ...(linkedMetric.value
        ? {
            metric_code: linkedMetric.value.metric_code,
            ...(linkedMetric.value.metric_version != null
              ? { metric_version: linkedMetric.value.metric_version }
              : {})
          }
        : {})
    });
    const feedback = await submitFeedback({
      answer_event_id: answer.data.answer_event_id,
      rating: form.rating,
      error_types: form.errorTypes,
      comment: form.comment
    });
    lastFeedback.value = {
      feedback_id: feedback.data?.feedback_id,
      status: feedback.data?.status || "pending"
    };
    ElMessage.success("反馈已提交，等待审核（不自动发布任何资产）");
    form.comment = "";
    await Promise.all([loadDashboard(), loadFeedback(1)]);
  } catch {
    ElMessage.error("提交失败：请检查权限与输入");
  } finally {
    submitting.value = false;
  }
}

// 186 P1-1：反馈成功后「查看我的反馈」锚点（页内反馈记录卡）
const lastFeedback = ref<{ feedback_id?: number; status: string } | null>(null);

function goMyFeedback() {
  feedbackScope.value = "mine";
  loadFeedback(1);
  document.getElementById("feedback-records")?.scrollIntoView?.({ behavior: "smooth" });
}

async function runEval() {
  running.value = true;
  try {
    const res = await runEvaluation({});
    evalSummary.value = res.data;
    ElMessage.success(`评测完成：${res.data.passed}/${res.data.total} 通过`);
  } catch {
    ElMessage.error("评测运行失败（需 evaluation.run 权限）");
  } finally {
    running.value = false;
  }
}

onMounted(() => {
  loadDashboard();
  loadFeedback(1);
  // 186 P1-1：检测 run_id/metric_code 参数并回读上下文
  loadLinkedContext();
});
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.rating-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 4px;
}
.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
