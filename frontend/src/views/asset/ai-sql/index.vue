<template>
  <div class="ai-sql-page">
    <RePageHeader title="AI 写 SQL" subtitle="让院内模型依据已验证表关系生成 Oracle 只读 SQL；只生成、永不执行。">
      <template #actions><el-button @click="$router.push('/asset/ai-quality')">返回 AI 巡查</el-button></template>
    </RePageHeader>
    <section class="safety-banner"><strong>Oracle · DATA_CENTER</strong><span>只读 SELECT / CTE</span><span>正式关系证据</span><span>生成 SQL 永不执行</span></section>
    <div class="workbench">
      <el-card class="request-panel" shadow="never">
        <template #header><div class="title"><span>1. 描述取数需求</span><el-tag>{{ selectedTables.length }}/20 表</el-tag></div></template>
        <el-input v-model="question" type="textarea" :rows="6" maxlength="2000" show-word-limit placeholder="例如：按月统计住院人次，并关联出院方式；结果限制 100 行" />
        <div class="section-label">2. 选择已登记表</div>
        <el-select v-model="selectedTables" multiple filterable remote reserve-keyword :remote-method="searchTables" :loading="tableLoading" placeholder="输入中文名、Schema 或表名搜索" class="table-select">
          <el-option v-for="row in tableOptions" :key="tableKey(row)" :label="`${row.table_name_cn || row.table_name} · ${row.schema_name}.${row.table_name}`" :value="`${row.schema_name}.${row.table_name}`" />
        </el-select>
        <div class="chips"><el-tag v-for="table in selectedTables" :key="table" closable @close="selectedTables = selectedTables.filter(item => item !== table)">{{ table }}</el-tag></div>
        <el-button v-perms="'ai.context.read'" type="primary" class="generate" :loading="generating" :disabled="question.trim().length < 2 || !selectedTables.length" @click="generate">3. 生成只读 SQL</el-button>
        <p class="hint">模型只收到脱敏需求、表字段、正式 JOIN 三要素和相关已确认值域，不接触患者明细。</p>
      </el-card>
      <el-card class="result-panel" shadow="never">
        <template #header><div class="title"><span>生成结果</span><div><el-tag v-if="result" :type="riskBlocked ? 'danger' : 'success'">{{ riskBlocked ? '风险拦截' : '只读检查通过' }}</el-tag><el-button v-if="result" size="small" @click="copySql">复制 SQL</el-button></div></div></template>
        <template v-if="result">
          <pre class="sql-code"><code>{{ result.sql }}</code></pre>
          <div class="digest"><span>表 {{ result.context_digest.tables }}</span><span>关系 {{ result.context_digest.relations }}</span><span>值域 {{ result.context_digest.value_domains }}</span><span>{{ result.context_digest.payload_bytes }} bytes</span></div>
          <el-alert v-if="Object.keys(result.risk).length" title="风险扫描提示" type="warning" :description="JSON.stringify(result.risk)" show-icon :closable="false" />
        </template>
        <el-empty v-else description="描述你的取数需求试试" />
      </el-card>
    </div>
    <el-card shadow="never">
      <template #header><span>我的生成历史</span></template>
      <el-table :data="history" size="small">
        <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.called_at) }}</template></el-table-column>
        <el-table-column label="需求（脱敏摘要）" min-width="280"><template #default="{ row }">{{ row.request.question_summary }}</template></el-table-column>
        <el-table-column label="选表" min-width="240"><template #default="{ row }">{{ row.request.selected_tables.join('、') }}</template></el-table-column>
        <el-table-column prop="response_summary" label="结果" min-width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { generateAiSql, getAiSqlHistory, getTables, type AiSqlGenerateResult, type AiSqlHistoryItem, type TableBrief } from "@/api/asset";
import { extractErrorDetail } from "@/utils/errorMessage";

const question = ref("");
const selectedTables = ref<string[]>([]);
const tableOptions = ref<TableBrief[]>([]);
const tableLoading = ref(false);
const generating = ref(false);
const result = ref<AiSqlGenerateResult | null>(null);
const history = ref<AiSqlHistoryItem[]>([]);
const riskBlocked = computed(() => Boolean(result.value?.risk?.blocked));
const tableKey = (row: TableBrief) => `${row.system_code}|${row.source_code}|${row.schema_name}|${row.table_name}`;

async function searchTables(keyword: string) {
  tableLoading.value = true;
  try { tableOptions.value = (await getTables({ keyword, system_code: "DATA_CENTER", page: 1, page_size: 30 })).data.items || []; }
  catch (error) { ElMessage.error(extractErrorDetail(error, "表目录加载失败，请稍后重试")); }
  finally { tableLoading.value = false; }
}
async function loadHistory() {
  try { history.value = (await getAiSqlHistory({ page: 1, page_size: 20 })).data.items || []; }
  catch (error) { ElMessage.error(extractErrorDetail(error, "生成历史加载失败")); }
}
async function generate() {
  generating.value = true;
  try {
    result.value = (await generateAiSql({ question: question.value, system_code: "DATA_CENTER", selected_tables: selectedTables.value })).data;
    await loadHistory();
    ElMessage.success("SQL 已生成，尚未执行");
  } catch (error) { ElMessage.error(extractErrorDetail(error, "生成失败，请检查模型状态与所选表")); }
  finally { generating.value = false; }
}
async function copySql() {
  if (!result.value) return;
  try { await navigator.clipboard.writeText(result.value.sql); ElMessage.success("SQL 已复制"); }
  catch { ElMessage.warning("剪贴板不可用，请手动复制"); }
}
function formatTime(value?: string | null) { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "-"; }
onMounted(async () => { await Promise.all([searchTables(""), loadHistory()]); });
</script>

<style scoped>
.ai-sql-page { padding: 4px 4px 24px; }
.safety-banner, .title, .digest { display: flex; align-items: center; gap: 12px; }
.safety-banner { margin-bottom: 14px; padding: 14px 18px; border: 1px solid var(--el-color-primary-light-7); border-radius: 12px; background: linear-gradient(120deg, var(--el-color-primary-light-9), var(--el-fill-color-light)); }
.safety-banner span { padding: 4px 9px; border-radius: 999px; background: var(--el-bg-color); color: var(--el-text-color-regular); font-size: 12px; }
.workbench { display: grid; grid-template-columns: minmax(360px, .9fr) minmax(0, 1.1fr); gap: 14px; margin-bottom: 14px; }
.title { justify-content: space-between; }
.title > div { display: flex; align-items: center; gap: 8px; }
.section-label { margin: 18px 0 8px; font-weight: 600; }
.table-select { width: 100%; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; min-height: 30px; margin: 10px 0; }
.generate { width: 100%; margin-top: 8px; background: linear-gradient(110deg, var(--el-color-primary), #7357ff); border: 0; }
.hint { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
.sql-code { min-height: 310px; max-height: 520px; overflow: auto; margin: 0 0 12px; padding: 18px; border-radius: 10px; background: #101827; color: #d8e6ff; line-height: 1.7; white-space: pre-wrap; }
.digest { flex-wrap: wrap; margin-bottom: 12px; color: var(--el-text-color-secondary); font-size: 12px; }
@media (max-width: 1280px) { .workbench { grid-template-columns: 1fr; } }
</style>
