<template>
  <div class="ai-quality-page">
    <RePageHeader title="AI 质控分析" subtitle="手动组包、人工复核的质量分析工作台">
      <template #actions><el-tag type="warning">AI建议，仅供质控复核</el-tag></template>
    </RePageHeader>

    <el-alert class="notice" type="info" :closable="false" show-icon>
      Dify 只接收脱敏后的质量摘要，不接收患者级样本、凭据或自由文本；接受建议不会修改质量问题或执行 SQL。
    </el-alert>

    <el-card class="section" shadow="never">
      <template #header><div class="card-title"><span>连接状态</span><el-button v-perms="'asset.quality.ai.connection_test'" size="small" @click="testConnection" :loading="connectionTesting">测试连接</el-button></div></template>
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="状态"><el-tag :type="statusTone(statusText)">{{ statusText }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="Workflow">{{ aiStatus?.workflow_name || aiStatus?.workflow || '未配置' }}</el-descriptions-item>
        <el-descriptions-item label="Prompt / Schema">{{ aiStatus?.prompt_version || '-' }} / {{ aiStatus?.schema_version || '-' }}</el-descriptions-item>
        <el-descriptions-item label="最近成功">{{ aiStatus?.last_success_at || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="aiStatus?.message" class="inner-alert" :type="aiStatus.enabled ? 'warning' : 'info'" :closable="false" :title="aiStatus.message" />
    </el-card>

    <el-card class="section" shadow="never">
      <template #header><div class="card-title"><span>待分析问题</span><el-tag size="small">最多 50 条同域问题</el-tag></div></template>
      <div class="filters">
        <el-select v-model="findingStatus" clearable placeholder="状态" @change="loadFindings"><el-option label="待处理" value="open" /><el-option label="已分派" value="assigned" /><el-option label="已确认" value="acknowledged" /></el-select>
        <el-select v-model="findingSeverity" clearable placeholder="严重程度" @change="loadFindings"><el-option label="严重" value="critical" /><el-option label="重要" value="major" /><el-option label="一般" value="minor" /></el-select>
        <el-button @click="loadFindings">刷新问题</el-button>
        <span class="selection-note">已选 {{ selectedFindingIds.length }} / 50</span>
      </div>
      <el-table v-loading="findingsLoading" :data="findings" row-key="id" size="small" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="48" :selectable="rowSelectable" />
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="rule_code" label="规则" width="160" show-overflow-tooltip />
        <el-table-column prop="table_name" label="表" min-width="160" show-overflow-tooltip />
        <el-table-column prop="column_name" label="字段" min-width="120" show-overflow-tooltip />
        <el-table-column prop="system_code" label="系统" width="120" />
        <el-table-column prop="severity" label="严重程度" width="100" />
        <el-table-column prop="status" label="状态" width="100" />
      </el-table>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header><span>安全预览（提交前必做）</span></template>
      <div class="preview-actions">
        <el-select v-model="taskType" style="width: 180px" @change="preview = null"><el-option label="问题批量分析" value="finding_batch" /><el-option label="单问题分析" value="finding" /><el-option label="质控批次摘要" value="run_summary" /></el-select>
        <el-select v-if="taskType === 'run_summary'" v-model="selectedRunId" style="width: 220px" placeholder="选择质量检查 run" @change="preview = null"><el-option v-for="run in runs" :key="run.id" :label="`#${run.id} · ${run.status || '-'} · ${run.total_findings ?? 0} 个问题`" :value="run.id" /></el-select>
        <el-button v-perms="'asset.quality.ai.analyze'" type="primary" :disabled="(taskType === 'run_summary' ? !selectedRunId : !selectedFindingIds.length) || previewLoading" :loading="previewLoading" @click="makePreview">生成安全预览</el-button>
        <el-button v-if="preview" v-perms="'asset.quality.ai.analyze'" type="success" :disabled="!canSubmit" :loading="submitting" @click="submitJob">提交分析</el-button>
      </div>
      <el-alert v-if="!aiStatus?.enabled || !aiStatus?.configured" class="inner-alert" type="info" :closable="false" title="AI 质控当前未配置或处于关闭态，可查看问题但不能提交分析。" />
      <el-descriptions v-if="preview" class="preview-grid" :column="3" border size="small">
        <el-descriptions-item label="实际字段"><span v-for="field in preview.fields || []" :key="field" class="field-chip">{{ field }}</span><span v-if="!preview.fields?.length">由服务端白名单组包</span></el-descriptions-item>
        <el-descriptions-item label="条数 / 字节">{{ preview.item_count ?? preview.finding_ids?.length ?? (preview.run_id ? 1 : 0) }} / {{ preview.payload_bytes ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="input_digest"><code>{{ preview.input_digest }}</code></el-descriptions-item>
        <el-descriptions-item label="脱敏剔除数">{{ preview.redacted_count ?? 0 }} / {{ preview.dropped_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="请求号">{{ preview.request_id }}</el-descriptions-item>
        <el-descriptions-item label="安全告警">{{ preview.warnings?.join('；') || '无' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="section" shadow="never">
      <template #header><span>分析任务与结构化结果</span></template>
      <el-table v-loading="jobsLoading" :data="jobs" row-key="id" size="small" @row-click="selectJob">
        <el-table-column prop="id" label="任务" width="90" /><el-table-column prop="task_type" label="类型" width="130" /><el-table-column prop="status" label="状态" width="110" /><el-table-column prop="finding_ids" label="问题/Run" width="120" show-overflow-tooltip /><el-table-column prop="input_digest" label="digest" min-width="190" show-overflow-tooltip /><el-table-column prop="error_class" label="错误分类" width="120" />
        <el-table-column label="操作" width="180" fixed="right"><template #default="{ row }"><el-button v-if="['failed','unknown'].includes(row.status)" v-perms="'asset.quality.ai.analyze'" size="small" @click.stop="retryJob(row)">重试</el-button><el-button v-if="row.result" size="small" @click.stop="selectJob(row)">查看结果</el-button></template></el-table-column>
      </el-table>
      <div v-if="selectedResult" class="result-panel">
        <div class="result-heading"><span>结果摘要</span><el-tag :type="riskTone(selectedResult.risk_level)">{{ selectedResult.risk_level || 'unknown' }}</el-tag><el-tag>{{ selectedResult.review_status }}</el-tag></div>
        <p>{{ selectedResult.summary }}</p>
        <h4>可能根因</h4><ul><li v-for="item in selectedResult.structured_result.root_causes || []" :key="item.title">{{ item.title }}<span v-if="item.reason">：{{ item.reason }}</span></li></ul>
        <h4>建议动作</h4><el-checkbox-group v-model="acceptedRecommendationIndexes"><el-checkbox v-for="(item, index) in selectedResult.structured_result.recommendations || []" :key="item.title" :label="index">{{ item.title }}<span v-if="item.reason">：{{ item.reason }}</span></el-checkbox></el-checkbox-group>
        <div class="review-actions"><el-input v-model="reviewNote" placeholder="复核备注（可选）" clearable /><el-button v-perms="'asset.quality.ai.review'" type="success" @click="reviewJob('accepted')">接受</el-button><el-button v-perms="'asset.quality.ai.review'" type="warning" @click="reviewJob('partial')">部分接受</el-button><el-button v-perms="'asset.quality.ai.review'" type="danger" @click="reviewJob('rejected')">拒绝</el-button><el-button v-perms="'asset.quality.ai.review'" :disabled="!acceptedRecommendationIndexes.length" @click="attachJob">挂接已接受建议</el-button></div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { getQualityFindings, getQualityCheckRuns, getAiQualityStatus, testAiQualityConnection, previewAiQuality, createAiQualityJob, getAiQualityJobs, getAiQualityJob, retryAiQualityJob, reviewAiQualityResult, attachAiQualityResult, type AiQualityJob, type AiQualityPreview, type AiQualityStatus, type AiQualityResultItem, type QualityFindingItem, type QualityCheckRunItem } from "@/api/asset";
import { aiQualityStatusLabel, canSubmitAiQuality, limitFindingIds, sameFindingDomain } from "./contracts";

type Finding = QualityFindingItem & { table_name?: string; column_name?: string; system_code?: string; source_code?: string; schema_name?: string; error_cnt?: number; domain?: string };
const route = useRoute();
const aiStatus = ref<AiQualityStatus | null>(null); const connectionTesting = ref(false);
const findings = ref<Finding[]>([]); const findingsLoading = ref(false); const findingStatus = ref("open"); const findingSeverity = ref("");
const selectedFindingIds = ref<number[]>([]); const taskType = ref<"finding" | "finding_batch" | "run_summary">("finding_batch");
const runs = ref<QualityCheckRunItem[]>([]); const selectedRunId = ref<number | undefined>();
const preview = ref<AiQualityPreview | null>(null); const previewLoading = ref(false); const submitting = ref(false);
const jobs = ref<AiQualityJob[]>([]); const jobsLoading = ref(false); const selectedJob = ref<AiQualityJob | null>(null); const selectedResult = ref<AiQualityResultItem | null>(null); const acceptedRecommendationIndexes = ref<number[]>([]); const reviewNote = ref("");
const statusText = computed(() => aiQualityStatusLabel(aiStatus.value));
const canSubmit = computed(() => canSubmitAiQuality(aiStatus.value, preview.value));

async function loadStatus() { try { aiStatus.value = (await getAiQualityStatus()).data; } catch { aiStatus.value = { enabled: false, configured: false, message: "状态接口不可用" }; } }
async function testConnection() { connectionTesting.value = true; try { aiStatus.value = (await testAiQualityConnection()).data; ElMessage.success("连接测试完成"); } catch { ElMessage.error("连接测试失败"); } finally { connectionTesting.value = false; } }
async function loadFindings() { findingsLoading.value = true; try { const data = (await getQualityFindings({ page: 1, page_size: 50, status: findingStatus.value || undefined, severity: findingSeverity.value || undefined })).data; findings.value = (data.items || []) as Finding[]; } finally { findingsLoading.value = false; } }
async function loadRuns() { try { runs.value = ((await getQualityCheckRuns({ page: 1, page_size: 50 })).data.items || []); } catch { runs.value = []; } }
async function loadJobs() { jobsLoading.value = true; try { jobs.value = ((await getAiQualityJobs({ page: 1, page_size: 30 })).data.items || []); } finally { jobsLoading.value = false; } }
function rowSelectable(row: Finding) { return selectedFindingIds.value.length < 50 || selectedFindingIds.value.includes(row.id); }
function onSelectionChange(rows: Finding[]) { if (rows.length > 50) ElMessage.warning("最多选择 50 条同域问题"); const limited = rows.slice(0, 50); if (!sameFindingDomain(limited)) { ElMessage.warning("所选问题必须属于同一业务系统+数据连接，且不能缺少物理归属"); selectedFindingIds.value = []; preview.value = null; return; } selectedFindingIds.value = limitFindingIds(limited.map(row => row.id)); preview.value = null; }
async function makePreview() { if (taskType.value === "run_summary" && !selectedRunId.value) { ElMessage.warning("请选择质量检查 run"); return; } if (taskType.value !== "run_summary" && !selectedFindingIds.value.length) { ElMessage.warning("请选择问题"); return; } if (taskType.value === "finding" && selectedFindingIds.value.length !== 1) { ElMessage.warning("单问题分析只能选择 1 条问题"); return; } if (taskType.value === "finding_batch" && selectedFindingIds.value.length < 2) { ElMessage.warning("批量分析至少选择 2 条同域问题"); return; } previewLoading.value = true; try { preview.value = (await previewAiQuality({ task_type: taskType.value, finding_ids: taskType.value === "run_summary" ? [] : selectedFindingIds.value, run_id: taskType.value === "run_summary" ? selectedRunId.value : undefined })).data; } catch { preview.value = null; ElMessage.error("安全预览失败"); } finally { previewLoading.value = false; } }
async function submitJob() { if (!preview.value || !canSubmit.value || submitting.value) return; submitting.value = true; try { const result = (await createAiQualityJob({ task_type: preview.value.task_type, finding_ids: preview.value.finding_ids, run_id: preview.value.run_id ?? undefined, input_digest: preview.value.input_digest, request_id: preview.value.request_id })).data; jobs.value = [result, ...jobs.value.filter(item => item.id !== result.id)]; selectedJob.value = result; selectedResult.value = result.result || null; ElMessage.success("分析任务已提交"); } catch { ElMessage.error("提交失败或已有相同任务在处理中"); } finally { submitting.value = false; } }
async function selectJob(job: AiQualityJob) { selectedJob.value = job; acceptedRecommendationIndexes.value = []; selectedResult.value = job.result || null; if (!selectedResult.value) { try { const detail = (await getAiQualityJob(job.id)).data; selectedJob.value = detail; selectedResult.value = detail.result || null; } catch { ElMessage.error("任务详情加载失败"); } } }
async function retryJob(job: AiQualityJob) { try { const result = (await retryAiQualityJob(job.id)).data; jobs.value = jobs.value.map(item => item.id === job.id ? result : item); ElMessage.success("已提交重试"); } catch { ElMessage.error("当前任务不可重试"); } }
async function reviewJob(status: "accepted" | "rejected" | "partial") { if (!selectedResult.value) return; try { selectedResult.value = (await reviewAiQualityResult(selectedResult.value.id, { status, note: reviewNote.value, accepted_recommendations: acceptedRecommendationIndexes.value })).data; ElMessage.success("复核状态已保存"); } catch { ElMessage.error("复核失败"); } }
async function attachJob() { if (!selectedResult.value || !acceptedRecommendationIndexes.value.length) return; try { selectedResult.value = (await attachAiQualityResult(selectedResult.value.id, { recommendation_indexes: acceptedRecommendationIndexes.value, note: reviewNote.value })).data; ElMessage.success("已挂接已接受建议"); } catch { ElMessage.error("挂接失败"); } }
function statusTone(status: string) { return status === "可用" ? "success" : status === "连接失败" ? "danger" : "warning"; }
function riskTone(level?: string) { return level === "critical" || level === "high" ? "danger" : level === "medium" ? "warning" : "success"; }
onMounted(async () => { await loadStatus(); await Promise.all([loadFindings(), loadRuns(), loadJobs()]); const id = Number(route.query.finding_id); if (id && findings.value.some(item => item.id === id)) selectedFindingIds.value = [id]; });
</script>

<style scoped>
.ai-quality-page { padding: 4px; }.notice { margin-bottom: 14px; }.section { margin-bottom: 14px; border-color: var(--border-light); }.card-title,.preview-actions,.result-heading,.review-actions { display:flex; align-items:center; gap:10px; justify-content:space-between; }.filters { display:flex; gap:10px; align-items:center; margin-bottom:10px; }.selection-note { color:var(--text-secondary); }.inner-alert { margin-top:12px; }.preview-grid { margin-top:12px; }.field-chip { display:inline-block; margin:2px 4px 2px 0; padding:2px 6px; border-radius:4px; background:#f0f7ec; color:#38552c; }.result-panel { margin-top:16px; padding:16px; background:var(--bg-elevated); border-radius:8px; }.result-heading { justify-content:flex-start; }.result-panel li { margin:5px 0; }.review-actions { justify-content:flex-start; margin-top:15px; }.review-actions .el-input { max-width:320px; }code { font-size:11px; word-break:break-all; }@media(max-width:760px){.filters,.preview-actions,.review-actions{flex-wrap:wrap}.review-actions .el-input{max-width:none;width:100%}}
</style>
