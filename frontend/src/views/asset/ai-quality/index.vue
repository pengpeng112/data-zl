<template>
  <div class="ai-quality-page">
    <RePageHeader title="AI 质控分析" subtitle="用院内模型解读平台里的质控规则和问题。只读平台库汇总，不连 HIS/ODS/嘉和业务库。">
      <template #actions>
        <el-tag :type="hospitalReady ? 'success' : 'warning'">{{ hospitalReady ? `院内 ${modelName}` : "未接通" }}</el-tag>
      </template>
    </RePageHeader>

    <section class="toolbar">
      <div class="toolbar-meta">
        <el-tag :type="statusTone(statusText)" size="small">{{ statusText }}</el-tag>
        <span>模型 {{ modelName }}</span>
        <span class="quiet">只传平台规则/问题/关系，不传患者明细</span>
      </div>
      <div class="toolbar-actions">
        <el-button v-perms="'asset.quality.ai.connection_test'" size="small" @click="testConnection" :loading="connectionTesting">测试连接</el-button>
        <el-button v-perms="'asset.quality.ai.analyze'" size="small" @click="makeGovernanceReport" :loading="reportLoading">生成总览报告</el-button>
      </div>
    </section>

    <section class="engine-banner">
      <div><span class="status-dot" :class="{ ready: hospitalReady }" /><strong>院内模型引擎</strong></div>
      <span>{{ modelName }}</span><span>{{ aiStatus?.hospital_llm?.host || "地址未配置" }}</span>
      <span>本会话成功 {{ aiStatus?.success_count ?? 0 }} 次</span>
      <span class="quiet">只传平台规则、聚合指标和脱敏元数据</span>
    </section>
    <el-segmented v-model="activeView" class="view-switch" :options="[{ label: '问题分析', value: 'analysis' }, { label: 'AI 巡查演示', value: 'patrol' }]" />

    <div v-if="activeView === 'analysis'" class="workspace">
      <el-card class="panel" shadow="never">
        <template #header>
          <div class="card-title">
            <span>待分析问题</span>
            <el-tag size="small">已选 {{ selectedFindingIds.length }}</el-tag>
          </div>
        </template>
        <div class="filters">
          <el-select v-model="findingStatus" clearable placeholder="状态" @change="() => { findingsPage = 1; loadFindings(); }">
            <el-option label="待处理" value="open" />
            <el-option label="已分派" value="assigned" />
            <el-option label="已确认" value="acknowledged" />
          </el-select>
          <el-select v-model="findingSeverity" clearable placeholder="程度" @change="() => { findingsPage = 1; loadFindings(); }">
            <el-option label="严重" value="critical" />
            <el-option label="重要" value="major" />
            <el-option label="一般" value="minor" />
          </el-select>
          <el-button @click="() => { findingsPage = 1; loadFindings(); }">刷新</el-button>
        </div>
        <el-table v-loading="findingsLoading" :data="findings" row-key="id" size="small" height="380" @selection-change="onSelectionChange">
          <el-table-column type="selection" width="44" :selectable="rowSelectable" reserve-selection />
          <el-table-column label="问题是什么" min-width="240">
            <template #default="{ row }">
              <div class="problem">{{ row.problem || row.rule_name || "质量问题" }}</div>
              <small class="quiet">{{ row.rule_description || "目录/关系级检查，不一定有单表字段" }}</small>
            </template>
          </el-table-column>
          <el-table-column label="规则" width="170">
            <template #default="{ row }">
              <div>{{ row.rule_name || row.rule_code || "-" }}</div>
              <small class="quiet">{{ row.rule_code }}</small>
            </template>
          </el-table-column>
          <el-table-column label="库 / 表 / 字段" min-width="200">
            <template #default="{ row }">
              <div>{{ objectText(row) }}</div>
              <small class="quiet">{{ row.system_name_cn || row.system_code || "未归属系统" }}</small>
            </template>
          </el-table-column>
          <el-table-column label="程度" width="72">
            <template #default="{ row }">{{ severityLabel(row.severity) }}</template>
          </el-table-column>
        </el-table>
        <!-- 146 E3（R5）：待分析问题服务端分页；勾选经 reserve-selection 跨页保留 -->
        <el-pagination
          v-model:current-page="findingsPage"
          class="pager"
          :page-size="findingsPageSize"
          :total="findingsTotal"
          layout="total, prev, pager, next"
          @current-change="loadFindings"
        />
        <div class="analyze-bar">
          <el-button v-perms="'asset.quality.ai.analyze'" type="primary" :disabled="!selectedFindingIds.length" :loading="submitting || previewLoading" @click="analyzeSelected">
            分析所选问题
          </el-button>
          <span class="quiet">{{ selectedFindingIds.length ? `将把 ${selectedFindingIds.length} 条问题的规则说明和对象传给院内模型` : "先勾选问题" }}</span>
        </div>
      </el-card>

      <el-card class="panel report-panel" shadow="never">
        <template #header>
          <div class="card-title">
            <span>分析结果</span>
            <div v-if="selectedResult" class="result-heading">
              <el-tag :type="riskTone(selectedResult.risk_level)" size="small">{{ riskLabel(selectedResult.risk_level) }}</el-tag>
              <el-tag size="small">{{ reviewLabel(selectedResult.review_status) }}</el-tag>
            </div>
          </div>
        </template>
        <div v-if="analyzing || (interruptedText && !selectedResult)" class="report-body">
          <div class="live-head">
            <el-tag :type="interruptedText && !analyzing ? 'danger' : 'warning'" size="small">
              {{ interruptedText && !analyzing ? "分析未完成，以下是已生成内容" : (livePhase === "thinking" ? "模型思考中" : "正在生成") }}
            </el-tag>
            <span class="quiet">{{ interruptedText && !analyzing ? "可直接阅读，或重新点分析" : "右侧会边出字边更新，不用重复点" }}</span>
          </div>
          <div class="selected-box">
            <div v-for="row in selectedRows" :key="row.id">{{ row.problem || row.rule_name }} · {{ objectText(row) }}</div>
          </div>
          <div class="report-actions">
        <el-button size="small" @click="copyReport">复制报告</el-button>
      </div>
      <div class="live-text markdown" v-html="renderReportHtml(liveDisplayText(interruptedText || liveText))" />
        </div>
        <div v-else-if="selectedResult" class="report-body">
          <section class="fact">
            <h4>结论</h4>
            <p>{{ selectedResult.summary }}</p>
          </section>
          <section v-for="item in selectedResult.structured_result.root_causes || []" :key="item.title" class="fact">
            <h4>{{ item.title }}</h4>
            <p>{{ item.reason }}</p>
          </section>
          <section class="fact">
            <h4>是不是噪音</h4>
            <p>{{ noiseText }}</p>
          </section>
          <section class="fact">
            <h4>建议动作</h4>
            <el-checkbox-group v-model="acceptedRecommendationIndexes">
              <el-checkbox v-for="(item, index) in selectedResult.structured_result.recommendations || []" :key="item.title" :label="index">
                {{ item.title }}<span v-if="item.reason">：{{ item.reason }}</span>
              </el-checkbox>
            </el-checkbox-group>
          </section>
          <div class="review-actions">
            <el-input v-model="reviewNote" placeholder="复核备注" clearable />
            <el-button v-perms="'asset.quality.ai.review'" type="success" @click="reviewJob('accepted')">接受</el-button>
            <el-button v-perms="'asset.quality.ai.review'" type="warning" @click="reviewJob('partial')">部分接受</el-button>
            <el-button v-perms="'asset.quality.ai.review'" type="danger" @click="reviewJob('rejected')">拒绝</el-button>
          </div>
        </div>
        <el-empty v-else description="勾选问题后点“分析所选问题”" />
      </el-card>
    </div>

    <el-card v-if="activeView === 'analysis'" class="panel" shadow="never">
      <template #header><span>最近分析</span></template>
      <el-table v-loading="jobsLoading" :data="jobs" size="small" @row-click="selectJob">
        <el-table-column prop="id" label="任务" width="70" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">{{ row.task_type === "run_summary" ? "总览报告" : "问题分析" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">{{ aiQualityJobStatusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="对象" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ (row.finding_ids || []).length ? `问题 ${row.finding_ids.join("、")}` : "平台规则/关系总览" }}</template>
        </el-table-column>
        <el-table-column width="90">
          <template #default="{ row }">
            <el-button v-if="row.result || row.status === 'succeeded'" size="small" @click.stop="selectJob(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <!-- 146 E3（R5）：任务列表服务端分页（后端 /jobs 已支持 page/page_size/total） -->
      <el-pagination
        v-model:current-page="jobsPage"
        class="pager"
        :page-size="jobsPageSize"
        :total="jobsTotal"
        layout="total, prev, pager, next"
        @current-change="loadJobs"
      />
    </el-card>

    <div v-else class="patrol-view">
      <div class="patrol-grid">
        <el-card class="plan-card" shadow="never">
          <div class="eyebrow">巡查计划</div>
          <h3>每日 02:00</h3>
          <el-tag type="info">演示形态（未启用调度）</el-tag>
          <p>定时执行未启用，当前通过一键巡查手动演示。</p>
          <el-button v-perms="'asset.quality.ai.analyze'" type="primary" class="demo-button" :loading="patrolRunning" @click="startPatrol">一键巡查</el-button>
          <el-button class="sql-link" @click="$router.push('/asset/ai-sql')">去 AI 写 SQL</el-button>
        </el-card>
        <el-card class="targets-card" shadow="never">
          <template #header><div class="card-title"><span>固定巡查目标</span><el-tag>{{ patrolTargets.length }} 张表</el-tag></div></template>
          <div v-for="target in patrolTargets" :key="`${target.source_code}.${target.schema_name}.${target.table_name}`" class="target-row">
            <div><strong>{{ target.name_cn }}</strong><small>{{ target.system_code }} / {{ target.schema_name }}.{{ target.table_name }}</small></div>
            <div class="target-evidence"><el-tag type="warning" size="small">{{ target.issue_label }}</el-tag><small>证据 {{ target.evidence.rule_id }} · #{{ target.evidence.finding_id }} · 截至 {{ formatTime(target.evidence.data_as_of) }}</small></div>
          </div>
        </el-card>
      </div>
      <el-alert v-if="offlineReplay" title="离线回放" type="warning" :description="`引擎当前不可用，展示最近成功巡查；最后成功 ${formatTime(aiStatus?.last_success_at)}`" show-icon :closable="false" />
      <el-card class="panel patrol-results" shadow="never">
        <template #header><div class="card-title"><span>巡查进度与结论</span><span class="quiet">{{ patrolProgressText }}</span></div></template>
        <el-timeline v-if="patrolJobs.length">
          <el-timeline-item v-for="item in patrolJobs" :key="item.id" :type="item.status === 'succeeded' ? 'success' : item.status === 'failed' ? 'danger' : 'primary'" :timestamp="item.table">
            <strong>{{ aiQualityJobStatusLabel(item.status) }}</strong>
            <div v-if="item.result" class="patrol-conclusion">{{ item.result.summary }}</div>
            <div v-else-if="item.partial_text" class="patrol-conclusion markdown" v-html="renderReportHtml(item.partial_text)" />
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="尚无巡查记录，点一键巡查试试" />
      </el-card>
      <el-card class="panel" shadow="never">
        <template #header><span>巡查历史</span></template>
        <el-table :data="patrolRuns" size="small">
          <el-table-column prop="patrol_run_id" label="批次" min-width="230" />
          <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.started_at) }}</template></el-table-column>
          <el-table-column prop="summary" label="结果" />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  getQualityFindings, getAiQualityStatus, testAiQualityConnection,
  previewAiQuality, createAiQualityJob, createGovernanceReport, getAiQualityJobs, getAiQualityJob,
  reviewAiQualityResult,
  getAiPatrolTargets, getAiPatrolRuns, runAiPatrol,
  type AiQualityJob, type AiQualityStatus, type AiQualityResultItem, type QualityFindingItem,
  type AiPatrolTarget, type AiPatrolRun
} from "@/api/asset";
import { aiQualityErrorLabel, aiQualityJobStatusLabel, aiQualityStatusLabel, canSubmitAiQuality, limitFindingIds, usesHospitalLlm } from "./contracts";
import { liveDisplayText, objectText, renderReportHtml, severityLabel } from "./reportMarkdown";

const aiStatus = ref<AiQualityStatus | null>(null);
const connectionTesting = ref(false);
const findings = ref<QualityFindingItem[]>([]);
const findingsLoading = ref(false);
// 146 E3（R5）：待分析问题服务端分页状态；勾选跨页保留（reserve-selection + row-key）。
const findingsPage = ref(1);
const findingsPageSize = 50;
const findingsTotal = ref(0);
const findingStatus = ref("open");
const findingSeverity = ref("");
const selectedFindingIds = ref<number[]>([]);
const previewLoading = ref(false);
const submitting = ref(false);
const reportLoading = ref(false);
const jobs = ref<AiQualityJob[]>([]);
const jobsLoading = ref(false);
const jobsPage = ref(1);
const jobsPageSize = 20;
const jobsTotal = ref(0);
const selectedResult = ref<AiQualityResultItem | null>(null);
const acceptedRecommendationIndexes = ref<number[]>([]);
const reviewNote = ref("");
const analyzing = ref(false);
const liveText = ref("");
const livePhase = ref("");
const interruptedText = ref("");
let pollTimer: number | undefined;
const activeView = ref<"analysis" | "patrol">("analysis");
const patrolTargets = ref<AiPatrolTarget[]>([]);
const patrolRuns = ref<AiPatrolRun[]>([]);
const patrolJobs = ref<Array<AiQualityJob & { table: string }>>([]);
const patrolRunning = ref(false);
const offlineReplay = ref(false);

const statusText = computed(() => aiQualityStatusLabel(aiStatus.value));
const hospitalReady = computed(() => usesHospitalLlm(aiStatus.value) && Boolean(aiStatus.value?.configured));
const modelName = computed(() => aiStatus.value?.hospital_llm?.model || "未配置");
const selectedRows = computed(() => selectedFindingRows.value);
const patrolProgressText = computed(() => patrolJobs.value.length ? `${patrolJobs.value.filter(item => item.status === "succeeded").length}/${patrolJobs.value.length} 完成` : "等待演示");
const noiseText = computed(() => {
  const flag = selectedResult.value?.structured_result?.false_positive;
  if (!flag) return "需人工判断";
  return flag.possible ? `更像噪音。${flag.reason || ""}` : `需要处理。${flag.reason || ""}`;
});

async function loadStatus() {
  try { aiStatus.value = (await getAiQualityStatus()).data; }
  catch { aiStatus.value = { enabled: false, configured: false, message: "状态接口不可用" }; }
}
async function loadFindings() {
  findingsLoading.value = true;
  try {
    const data = (await getQualityFindings({
      page: findingsPage.value,
      page_size: findingsPageSize,
      status: findingStatus.value || undefined,
      severity: findingSeverity.value || undefined
    })).data;
    findings.value = data.items || [];
    findingsTotal.value = data.total || 0;
  } finally { findingsLoading.value = false; }
}
async function loadJobs() {
  jobsLoading.value = true;
  try {
    const data = (await getAiQualityJobs({ page: jobsPage.value, page_size: jobsPageSize })).data;
    jobs.value = data.items || [];
    jobsTotal.value = data.total || 0;
  } finally { jobsLoading.value = false; }
}
async function loadPatrol() {
  try {
    const [targets, runs] = await Promise.all([getAiPatrolTargets(), getAiPatrolRuns({ page: 1, page_size: 10 })]);
    patrolTargets.value = targets.data.targets || [];
    patrolRuns.value = runs.data.items || [];
  } catch { ElMessage.warning("巡查演示配置暂不可用"); }
}
async function refreshPatrolJobs() {
  patrolJobs.value = await Promise.all(patrolJobs.value.map(async item => {
    try { return { ...(await getAiQualityJob(item.id)).data, table: item.table } as AiQualityJob & { table: string }; }
    catch { return item; }
  }));
}
async function startPatrol() {
  patrolRunning.value = true;
  offlineReplay.value = false;
  try {
    const data = (await runAiPatrol()).data;
    patrolJobs.value = data.jobs.map(item => ({ id: item.job_id, job_id: item.job_id, table: item.table, task_type: "finding_batch", status: "queued" } as AiQualityJob & { table: string }));
    await refreshPatrolJobs();
    await loadPatrol();
    ElMessage.success(data.errors.length ? "巡查已提交，个别目标失败" : "巡查已提交");
  } catch {
    offlineReplay.value = Boolean(patrolRuns.value.length);
    ElMessage.error(offlineReplay.value ? "模型不可达，已切换最近成功回放" : "巡查提交失败");
  } finally { patrolRunning.value = false; }
}
function formatTime(value?: string | null) { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-"; }
function rowSelectable(row: QualityFindingItem) {
  return selectedFindingIds.value.length < 50 || selectedFindingIds.value.includes(row.id);
}
// 146 E3（R5）：selection-change 携带保留选择+当前页全量勾选行，跨页累计不丢行。
const selectedFindingRows = ref<QualityFindingItem[]>([]);
function onSelectionChange(rows: QualityFindingItem[]) {
  selectedFindingRows.value = rows;
  selectedFindingIds.value = limitFindingIds(rows.map(row => row.id));
}
async function testConnection() {
  connectionTesting.value = true;
  try {
    aiStatus.value = (await testAiQualityConnection()).data;
    ElMessage.success("院内模型已接通");
  } catch { ElMessage.error("连接失败"); }
  finally { connectionTesting.value = false; }
}
function stopWatch() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = undefined;
  }
}
async function watchJob(jobId: number | string) {
  analyzing.value = true;
  selectedResult.value = null;
  liveText.value = "";
  livePhase.value = "thinking";
  interruptedText.value = "";
  stopWatch();
  // 146 E3：轮询 10 分钟上限，指数退避 0.8s→10s，卸载即停止
  const POLL_TIMEOUT_MS = 10 * 60 * 1000;
  const startedAt = Date.now();
  let interval = 800;
  const tick = async () => {
    if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
      analyzing.value = false;
      interruptedText.value = liveText.value;
      ElMessage.error("分析超时（10 分钟），已停止轮询，可稍后刷新查看结果");
      return;
    }
    try {
      const detail = (await getAiQualityJob(jobId)).data;
      liveText.value = detail.partial_text || liveText.value;
      livePhase.value = detail.phase || livePhase.value;
      jobs.value = [detail, ...jobs.value.filter(item => item.id !== detail.id)];
      if (detail.status === "succeeded" && detail.result) {
        selectedResult.value = detail.result;
        analyzing.value = false;
        ElMessage.success("分析完成");
        return;
      }
      if (["failed", "blocked", "unknown"].includes(detail.status)) {
        interruptedText.value = detail.partial_text || liveText.value;
        analyzing.value = false;
        ElMessage.error(aiQualityErrorLabel(detail.error_class));
        return;
      }
      interval = 800; // 成功轮询后重置退避
    } catch {
      interval = Math.min(interval * 2, 10000); // 瞬时失败退避，最多 10s
    }
    pollTimer = window.setTimeout(tick, interval);
  };
  await tick();
}
async function copyReport() {
  const result = selectedResult.value as any;
  const text = result?.structured_result?.summary || result?.summary || liveText.value || "";
  if (!text) {
    ElMessage.warning("暂无可复制的报告内容");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success("报告已复制");
  } catch {
    ElMessage.warning("剪贴板不可用，请手动选择复制");
  }
}

async function makeGovernanceReport() {
  reportLoading.value = true;
  try {
    const result = (await createGovernanceReport()).data;
    jobs.value = [result, ...jobs.value.filter(item => item.id !== result.id)];
    if (result.status === "succeeded" && result.result) selectedResult.value = result.result;
    else await watchJob(result.id);
  } catch { ElMessage.error("生成报告失败"); }
  finally { reportLoading.value = false; }
}
async function analyzeSelected() {
  if (!selectedFindingIds.value.length) {
    ElMessage.warning("请先勾选问题");
    return;
  }
  submitting.value = true;
  previewLoading.value = true;
  analyzing.value = true;
  selectedResult.value = null;
  liveText.value = "正在提交所选问题…";
  try {
    const taskType = selectedFindingIds.value.length === 1 ? "finding" : "finding_batch";
    const preview = (await previewAiQuality({
      task_type: taskType,
      finding_ids: selectedFindingIds.value
    })).data;
    if (!canSubmitAiQuality(aiStatus.value, preview)) {
      ElMessage.error("当前不能提交分析");
      analyzing.value = false;
      return;
    }
    const result = (await createAiQualityJob({
      task_type: preview.task_type,
      finding_ids: preview.finding_ids,
      input_digest: preview.input_digest,
      request_id: preview.request_id
    })).data;
    jobs.value = [result, ...jobs.value.filter(item => item.id !== result.id)];
    if (result.status === "succeeded" && result.result) {
      selectedResult.value = result.result;
      analyzing.value = false;
      ElMessage.success("分析完成");
    } else {
      await watchJob(result.id);
    }
  } catch { ElMessage.error("提交失败"); analyzing.value = false; }
  finally {
    submitting.value = false;
    previewLoading.value = false;
  }
}
async function selectJob(job: AiQualityJob) {
  acceptedRecommendationIndexes.value = [];
  selectedResult.value = job.result || null;
  if (!selectedResult.value) {
    try { selectedResult.value = (await getAiQualityJob(job.id)).data.result || null; }
    catch { ElMessage.error("加载失败"); }
  }
}
async function reviewJob(status: "accepted" | "rejected" | "partial") {
  if (!selectedResult.value) return;
  try {
    selectedResult.value = (await reviewAiQualityResult(selectedResult.value.id, {
      status, note: reviewNote.value, accepted_recommendations: acceptedRecommendationIndexes.value
    })).data;
    ElMessage.success("复核已保存");
  } catch { ElMessage.error("复核失败"); }
}
function statusTone(status: string) { return status === "可用" ? "success" : status === "连接失败" ? "danger" : "warning"; }
function riskTone(level?: string) { return level === "critical" || level === "high" ? "danger" : level === "medium" ? "warning" : "success"; }
function riskLabel(level?: string) {
  return ({ critical: "严重", high: "偏高", medium: "中等", low: "较低", unknown: "待判断" } as Record<string, string>)[level || ""] || "待判断";
}
function reviewLabel(status?: string) {
  return ({ pending: "待复核", accepted: "已接受", rejected: "已拒绝", partial: "部分接受" } as Record<string, string>)[status || ""] || "待复核";
}
onMounted(async () => {
  await loadStatus();
  await Promise.all([loadFindings(), loadJobs(), loadPatrol()]);
});
onUnmounted(() => stopWatch());
</script>

<style scoped>
.ai-quality-page { padding: 4px 4px 24px; }
.toolbar, .card-title, .analyze-bar, .review-actions, .toolbar-actions, .toolbar-meta, .result-heading {
  display: flex; align-items: center; gap: 10px;
}
.toolbar { justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; }
.engine-banner { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-bottom: 12px; padding: 14px 18px; border-radius: 12px; color: var(--el-text-color-primary); background: linear-gradient(120deg, var(--el-color-primary-light-9), var(--el-fill-color-light)); border: 1px solid var(--el-color-primary-light-7); }
.status-dot { display: inline-block; width: 9px; height: 9px; margin-right: 8px; border-radius: 50%; background: var(--el-color-warning); }
.status-dot.ready { background: var(--el-color-success); box-shadow: 0 0 0 5px rgba(103, 194, 58, .12); }
.view-switch { margin-bottom: 14px; }
.toolbar-meta { color: var(--el-text-color-regular); }
.quiet { color: var(--el-text-color-secondary); font-size: 12px; }
.workspace { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr); gap: 12px; margin-bottom: 12px; }
.panel { border-color: var(--border-light); }
.card-title { justify-content: space-between; }
.filters { display: flex; gap: 8px; margin-bottom: 10px; }
.problem { font-weight: 600; }
.analyze-bar { margin-top: 12px; }
.report-body { min-height: 360px; }
.fact { margin-bottom: 14px; }
.fact h4 { margin: 0 0 6px; font-size: 13px; color: var(--el-text-color-secondary); }
.fact p { margin: 0; line-height: 1.7; }
.live-head, .selected-box { margin-bottom: 10px; }
.live-text {
  white-space: pre-wrap;
  min-height: 180px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
  line-height: 1.65;
}
.review-actions { margin-top: 14px; }
.review-actions .el-input { max-width: 240px; }
@media (max-width: 1200px) {
  .workspace, .split { grid-template-columns: 1fr; }
}
.report-actions { display: flex; gap: 8px; margin-bottom: 8px; }
.pager { display: flex; justify-content: flex-end; margin-top: 10px; }
.patrol-grid { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 12px; margin-bottom: 12px; }
.plan-card h3 { margin: 8px 0; font-size: 26px; }
.plan-card p { color: var(--el-text-color-secondary); line-height: 1.6; }
.eyebrow { color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.demo-button { width: 100%; margin-top: 12px; background: linear-gradient(110deg, var(--el-color-primary), #7357ff); border: 0; }
.sql-link { width: 100%; margin: 8px 0 0; }
.target-row { display: grid; grid-template-columns: minmax(200px, .7fr) minmax(0, 1.3fr); gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.target-row:last-child { border-bottom: 0; }
.target-row small, .target-evidence small { display: block; margin-top: 5px; color: var(--el-text-color-secondary); }
.target-evidence .el-tag { max-width: 100%; }
.patrol-results { margin: 12px 0; }
.patrol-conclusion { margin-top: 8px; padding: 10px 12px; border-radius: 8px; background: var(--el-fill-color-light); line-height: 1.65; }
@media (max-width: 1280px) { .patrol-grid, .target-row { grid-template-columns: 1fr; } }
</style>
