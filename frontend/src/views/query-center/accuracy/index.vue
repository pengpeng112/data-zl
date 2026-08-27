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
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  fetchAccuracyDashboard,
  registerAnswerEvent,
  runEvaluation,
  submitFeedback,
  type AccuracyDashboard,
  type EvaluationRunSummary
} from "@/api/query-center";

defineOptions({ name: "QueryAccuracy" });

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
const evalSummary = ref<EvaluationRunSummary | null>(null);
const submitting = ref(false);
const running = ref(false);

const form = reactive({
  question: "",
  rating: "correct",
  errorTypes: [] as string[],
  comment: ""
});

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
      caller_id: "web-console"
    });
    await submitFeedback({
      answer_event_id: answer.data.answer_event_id,
      rating: form.rating,
      error_types: form.errorTypes,
      comment: form.comment
    });
    ElMessage.success("反馈已提交，等待审核（不自动发布任何资产）");
    form.comment = "";
    await loadDashboard();
  } catch {
    ElMessage.error("提交失败：请检查权限与输入");
  } finally {
    submitting.value = false;
  }
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

onMounted(loadDashboard);
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
