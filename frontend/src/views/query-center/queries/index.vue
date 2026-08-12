<template>
  <div class="query-center">
    <RePageHeader
      title="查询与指标中心"
      subtitle="查询 SQL / 统计指标 / 数据产品闭环（126 P1–P4）。结果默认不保存；自动门禁通过后成为现行版本；产品目录禁止任意 SQL。"
    />

    <el-alert
      class="mb16"
      type="info"
      :closable="false"
      title="本地固定工作区：F:\\python\\数据资产\\取数。queryctl init/validate/submit；指标可引用 query_code 版本。"
    />

    <el-tabs v-model="tab" @tab-change="onTab">
      <el-tab-pane label="查询资产" name="list">
        <el-card>
          <div class="toolbar">
            <el-input v-model="keyword" clearable placeholder="编码/标题/用途" style="width: 240px" @keyup.enter="loadList" />
            <el-button type="primary" @click="loadList">查询</el-button>
            <el-button @click="openIngest">提交 SQL</el-button>
          </div>
          <el-table v-loading="loading" :data="items" stripe size="small" @row-click="openDetail">
            <el-table-column prop="query_code" label="编码" width="200" />
            <el-table-column prop="title" label="名称" min-width="160" />
            <el-table-column prop="system_code" label="系统" width="120" />
            <el-table-column prop="source_code" label="连接" width="140" />
            <el-table-column label="现行版本" width="100">
              <template #default="{ row }">
                {{ row.active_version?.version ?? "-" }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.active_version?.status || row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="mt12"
            layout="total, prev, pager, next"
            :total="total"
            v-model:current-page="page"
            :page-size="pageSize"
            @current-change="loadList"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="运行记录" name="runs">
        <el-card>
          <el-button size="small" @click="loadRuns">刷新</el-button>
          <el-table v-loading="runsLoading" :data="runs" stripe size="small" class="mt12">
            <el-table-column prop="id" label="Run" width="80" />
            <el-table-column prop="query_code" label="编码" width="180" />
            <el-table-column prop="version" label="版本" width="70" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="row_count" label="行数" width="80" />
            <el-table-column prop="result_storage" label="结果策略" width="100" />
            <el-table-column prop="correlation_id" label="关联ID" width="120" />
            <el-table-column prop="error_message" label="错误" min-width="160" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="统计指标" name="metrics">
        <el-card>
          <div class="toolbar">
            <el-input v-model="metricKeyword" clearable placeholder="指标编码/名称" style="width: 240px" @keyup.enter="loadMetrics" />
            <el-button type="primary" @click="loadMetrics">查询</el-button>
            <el-button @click="openMetricIngest">登记指标</el-button>
          </div>
          <el-table v-loading="metricLoading" :data="metricItems" stripe size="small" @row-click="openMetricDetail">
            <el-table-column prop="metric_code" label="编码" width="180" />
            <el-table-column prop="title" label="名称" min-width="140" />
            <el-table-column prop="unit" label="单位" width="70" />
            <el-table-column label="现行版本" width="90">
              <template #default="{ row }">{{ row.active_version?.version ?? "-" }}</template>
            </el-table-column>
            <el-table-column label="查询引用" min-width="160">
              <template #default="{ row }">
                {{ row.active_version?.query_code || row.active_version?.numerator_query_code || "-" }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.active_version?.status || row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="数据产品" name="products">
        <el-card>
          <el-alert
            class="mb12"
            type="warning"
            :closable="false"
            title="数据产品只允许执行已发布目录项，禁止任意 SQL。调度默认可选关闭。"
          />
          <div class="toolbar">
            <el-input v-model="productKeyword" clearable placeholder="产品编码/名称" style="width: 240px" @keyup.enter="loadProducts" />
            <el-button type="primary" @click="loadProducts">查询</el-button>
            <el-button :loading="publishLoading" @click="publishCoreProducts">发布 CORE 产品</el-button>
          </div>
          <el-table v-loading="productLoading" :data="productItems" stripe size="small">
            <el-table-column prop="product_code" label="产品编码" width="220" />
            <el-table-column prop="title" label="名称" min-width="160" />
            <el-table-column prop="product_type" label="类型" width="90" />
            <el-table-column prop="query_code" label="查询" width="180" />
            <el-table-column prop="metric_code" label="指标" width="160" />
            <el-table-column prop="max_rows" label="限行" width="70" />
            <el-table-column label="启用" width="70">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="executeProduct(row)">试执行</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="mt12"
            layout="total, prev, pager, next"
            :total="productTotal"
            v-model:current-page="productPage"
            :page-size="20"
            @current-change="loadProducts"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="指标看板" name="board">
        <el-card>
          <div class="toolbar">
            <el-input v-model="boardFrom" clearable placeholder="起始月 YYYY-MM" style="width: 140px" />
            <el-input v-model="boardTo" clearable placeholder="结束月 YYYY-MM" style="width: 140px" />
            <el-button type="primary" :loading="boardLoading" @click="loadBoard">刷新看板</el-button>
            <el-button @click="exportBoardCsv">导出 CSV</el-button>
            <span class="muted">结果格数：{{ boardTotal }}</span>
          </div>
          <div class="board-wrap">
            <el-table v-loading="boardLoading" :data="boardRows" stripe size="small" border height="520">
              <el-table-column prop="metric_code" label="编码" width="120" fixed />
              <el-table-column prop="title" label="指标" min-width="180" fixed show-overflow-tooltip />
              <el-table-column prop="has_active" label="可执行" width="70">
                <template #default="{ row }">
                  <el-tag size="small" :type="row.has_active ? 'success' : 'info'">{{ row.has_active ? "是" : "否" }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column
                v-for="p in boardPeriods"
                :key="p"
                :prop="p"
                :label="p"
                min-width="100"
                show-overflow-tooltip
              />
            </el-table>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="调度与多源" name="ops">
        <el-card class="mb16">
          <template #header>查询调度（单条默认关闭；全局还需 APP_QUERY_SCHEDULE_ENABLED）</template>
          <div class="toolbar">
            <el-button type="primary" :loading="scheduleLoading" @click="loadSchedules">刷新</el-button>
            <el-button :loading="seedLoading" @click="seedSchedules">种子 CORE 调度</el-button>
          </div>
          <el-table v-loading="scheduleLoading" :data="scheduleItems" stripe size="small">
            <el-table-column prop="query_code" label="查询编码" width="200" />
            <el-table-column prop="schedule_cron" label="Cron" width="140" />
            <el-table-column prop="source_code" label="连接" width="160" />
            <el-table-column label="启用" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_status" label="上次状态" width="100" />
            <el-table-column prop="last_run_at" label="上次运行" min-width="160" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="toggleSchedule(row)">
                  {{ row.enabled ? "关闭" : "启用" }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card>
          <template #header>多源连接能力</template>
          <el-button size="small" class="mb12" :loading="sourceLoading" @click="loadSources">刷新</el-button>
          <el-table v-loading="sourceLoading" :data="sourceItems" stripe size="small">
            <el-table-column prop="source_code" label="连接编码" width="180" />
            <el-table-column prop="title" label="名称" min-width="140" />
            <el-table-column prop="system_code" label="系统" width="140" />
            <el-table-column prop="db_type" label="类型" width="100" />
            <el-table-column prop="write_policy" label="写策略" width="100" />
            <el-table-column label="查询适配" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.query_runner_supported ? 'success' : 'warning'">
                  {{ row.query_runner_supported ? "支持" : "待扩" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="credential_status" label="凭据状态" width="120" />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="ingestVisible" title="摄取查询 SQL" width="720px">
      <el-form label-width="100px">
        <el-form-item label="编码"><el-input v-model="form.query_code" /></el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="系统"><el-input v-model="form.system_code" placeholder="DATA_CENTER / HIS_SOURCE" /></el-form-item>
        <el-form-item label="连接"><el-input v-model="form.source_code" placeholder="ods_8_216" /></el-form-item>
        <el-form-item label="方言"><el-input v-model="form.dialect" /></el-form-item>
        <el-form-item label="用途"><el-input v-model="form.purpose" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="SQL">
          <el-input v-model="form.sql_text" type="textarea" :rows="10" placeholder="仅 SELECT / WITH" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="previewGate">门禁试算</el-button>
        <el-button type="primary" :loading="saving" @click="submitIngest">提交（自动门禁）</el-button>
      </template>
      <el-alert v-if="gateResult" class="mt12" :type="gateResult.status === 'blocked' ? 'error' : 'success'" :closable="false">
        门禁: {{ gateResult.status }}；自动激活: {{ gateResult.auto_activate }}；
        错误: {{ (gateResult.errors || []).join("; ") || "无" }}
      </el-alert>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="50%" title="查询详情">
      <template v-if="detail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="编码">{{ detail.definition?.query_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detail.definition?.title }}</el-descriptions-item>
          <el-descriptions-item label="用途">{{ detail.definition?.purpose }}</el-descriptions-item>
          <el-descriptions-item label="现行版本">{{ detail.active_version?.version }}</el-descriptions-item>
          <el-descriptions-item label="SQL 哈希">{{ detail.active_version?.sql_sha256 }}</el-descriptions-item>
        </el-descriptions>
        <h4 class="mt16">现行 SQL</h4>
        <pre class="sql-box">{{ detail.active_version?.sql_text }}</pre>
        <h4 class="mt16">版本列表</h4>
        <el-table :data="detail.versions || []" size="small">
          <el-table-column prop="version" label="版本" width="70" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="is_active" label="现行" width="70" />
          <el-table-column prop="revision_reason" label="修订原因" />
        </el-table>
      </template>
    </el-drawer>

    <el-dialog v-model="metricIngestVisible" title="登记统计指标" width="720px">
      <el-form label-width="110px">
        <el-form-item label="指标编码"><el-input v-model="metricForm.metric_code" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="metricForm.title" /></el-form-item>
        <el-form-item label="含义/口径"><el-input v-model="metricForm.definition_text" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="分子说明"><el-input v-model="metricForm.numerator_desc" /></el-form-item>
        <el-form-item label="分母说明"><el-input v-model="metricForm.denominator_desc" /></el-form-item>
        <el-form-item label="公式"><el-input v-model="metricForm.formula" /></el-form-item>
        <el-form-item label="关联查询"><el-input v-model="metricForm.query_code" placeholder="query_code" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="metricForm.unit" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="metricSaving" @click="submitMetric">提交</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="metricDetailVisible" size="50%" title="指标详情">
      <template v-if="metricDetail">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="编码">{{ metricDetail.definition?.metric_code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ metricDetail.definition?.title }}</el-descriptions-item>
          <el-descriptions-item label="口径">{{ metricDetail.active_version?.definition_text }}</el-descriptions-item>
          <el-descriptions-item label="分子">{{ metricDetail.active_version?.numerator_desc }}</el-descriptions-item>
          <el-descriptions-item label="分母">{{ metricDetail.active_version?.denominator_desc }}</el-descriptions-item>
          <el-descriptions-item label="公式">{{ metricDetail.active_version?.formula }}</el-descriptions-item>
          <el-descriptions-item label="查询">
            {{ metricDetail.active_version?.query_code }} @ {{ metricDetail.active_version?.query_version }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { http } from "@/utils/http";

const tab = ref("list");
const loading = ref(false);
const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const keyword = ref("");

const runsLoading = ref(false);
const runs = ref<any[]>([]);

const ingestVisible = ref(false);
const saving = ref(false);
const gateResult = ref<any>(null);
const form = reactive({
  query_code: "",
  title: "",
  system_code: "DATA_CENTER",
  source_code: "ods_8_216",
  dialect: "oracle",
  purpose: "",
  sql_text: "SELECT PATIENT_ID FROM HIS.PAT_VISIT WHERE ROWNUM <= 10"
});

const detailVisible = ref(false);
const detail = ref<any>(null);

const metricLoading = ref(false);
const metricItems = ref<any[]>([]);
const metricKeyword = ref("");
const metricIngestVisible = ref(false);
const metricSaving = ref(false);
const metricDetailVisible = ref(false);
const metricDetail = ref<any>(null);
const metricForm = reactive({
  metric_code: "",
  title: "",
  definition_text: "",
  numerator_desc: "",
  denominator_desc: "",
  formula: "",
  query_code: "",
  unit: "%"
});

const productLoading = ref(false);
const productItems = ref<any[]>([]);
const productTotal = ref(0);
const productPage = ref(1);
const productKeyword = ref("");
const publishLoading = ref(false);

const boardLoading = ref(false);
const boardFrom = ref("");
const boardTo = ref("");
const boardPeriods = ref<string[]>([]);
const boardRows = ref<any[]>([]);
const boardTotal = ref(0);
const boardCells = ref<Record<string, Record<string, any>>>({});

const scheduleLoading = ref(false);
const seedLoading = ref(false);
const scheduleItems = ref<any[]>([]);
const sourceLoading = ref(false);
const sourceItems = ref<any[]>([]);

function onTab(name: string | number) {
  if (name === "metrics") loadMetrics();
  if (name === "runs") loadRuns();
  if (name === "products") loadProducts();
  if (name === "board") loadBoard();
  if (name === "ops") {
    loadSchedules();
    loadSources();
  }
}

async function loadList() {
  loading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/queries", {
      params: { page: page.value, page_size: pageSize, keyword: keyword.value || undefined }
    });
    items.value = res.data?.items || [];
    total.value = res.data?.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载查询列表失败");
  } finally {
    loading.value = false;
  }
}

async function loadRuns() {
  runsLoading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/queries/runs/list", {
      params: { page: 1, page_size: 50 }
    });
    runs.value = res.data?.items || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载运行记录失败");
  } finally {
    runsLoading.value = false;
  }
}

function openIngest() {
  gateResult.value = null;
  ingestVisible.value = true;
}

async function previewGate() {
  try {
    const res = await http.request<any>("post", "/api/v1/queries/gate", {
      data: { sql_text: form.sql_text, dialect: form.dialect, source_code: form.source_code }
    });
    gateResult.value = res.data;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "门禁失败");
  }
}

async function submitIngest() {
  saving.value = true;
  try {
    const res = await http.request<any>("post", "/api/v1/queries/ingest", { data: { ...form } });
    const d = res.data;
    ElMessage.success(
      d.idempotent
        ? `幂等：已有版本 v${d.version?.version}`
        : `已摄取 v${d.version?.version} 状态=${d.version?.status}`
    );
    ingestVisible.value = false;
    await loadList();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "摄取失败");
  } finally {
    saving.value = false;
  }
}

async function openDetail(row: any) {
  try {
    const res = await http.request<any>("get", `/api/v1/queries/${encodeURIComponent(row.query_code)}`);
    detail.value = res.data;
    detailVisible.value = true;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "详情失败");
  }
}

async function loadMetrics() {
  metricLoading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/metrics", {
      params: { page: 1, page_size: 50, keyword: metricKeyword.value || undefined }
    });
    metricItems.value = res.data?.items || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载指标失败");
  } finally {
    metricLoading.value = false;
  }
}

function openMetricIngest() {
  metricIngestVisible.value = true;
}

async function submitMetric() {
  metricSaving.value = true;
  try {
    const res = await http.request<any>("post", "/api/v1/metrics/ingest", { data: { ...metricForm } });
    ElMessage.success(`指标 v${res.data?.version?.version} 状态=${res.data?.version?.status}`);
    metricIngestVisible.value = false;
    await loadMetrics();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "指标提交失败");
  } finally {
    metricSaving.value = false;
  }
}

async function openMetricDetail(row: any) {
  try {
    const res = await http.request<any>("get", `/api/v1/metrics/${encodeURIComponent(row.metric_code)}`);
    metricDetail.value = res.data;
    metricDetailVisible.value = true;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "指标详情失败");
  }
}

async function loadProducts() {
  productLoading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/data-products", {
      params: {
        page: productPage.value,
        page_size: 20,
        keyword: productKeyword.value || undefined,
        enabled: true
      }
    });
    productItems.value = res.data?.items || [];
    productTotal.value = res.data?.total || 0;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载数据产品失败");
  } finally {
    productLoading.value = false;
  }
}

async function publishCoreProducts() {
  publishLoading.value = true;
  try {
    const res = await http.request<any>("post", "/api/v1/data-products/publish-core");
    ElMessage.success(`已发布 ${res.data?.count ?? 0} 个 CORE 数据产品`);
    await loadProducts();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "发布失败");
  } finally {
    publishLoading.value = false;
  }
}

async function executeProduct(row: any) {
  try {
    const res = await http.request<any>(
      "post",
      `/api/v1/data-products/${encodeURIComponent(row.product_code)}/execute`,
      { data: { parameters: {}, execute_sql: row.product_type === "query" } }
    );
    const d = res.data || {};
    if (d.mode === "metric_result" || d.results) {
      ElMessage.success(
        d.mode === "metric_result"
          ? `指标结果条数: ${(d.results || []).length}`
          : `执行成功 行数=${d.row_count ?? "-"}`
      );
    } else {
      ElMessage.success(JSON.stringify(d).slice(0, 200));
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "执行失败");
  }
}

async function loadBoard() {
  boardLoading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/metrics/board/overview", {
      params: {
        period_from: boardFrom.value || undefined,
        period_to: boardTo.value || undefined
      }
    });
    const d = res.data || {};
    boardPeriods.value = d.periods || [];
    boardCells.value = d.cells || {};
    boardTotal.value = d.total_results || 0;
    boardRows.value = (d.metrics || []).map((m: any) => {
      const row: any = {
        metric_code: m.metric_code,
        title: m.title,
        has_active: m.has_active
      };
      for (const p of boardPeriods.value) {
        const cell = boardCells.value[m.metric_code]?.[p];
        row[p] = cell?.metric_value || cell?.status || (cell ? `${cell.numerator_value || ""}/${cell.denominator_value || ""}` : "-");
      }
      return row;
    });
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载看板失败");
  } finally {
    boardLoading.value = false;
  }
}

function exportBoardCsv() {
  if (!boardRows.value.length) {
    ElMessage.warning("无看板数据");
    return;
  }
  const headers = ["metric_code", "title", "has_active", ...boardPeriods.value];
  const lines = [headers.join(",")];
  for (const r of boardRows.value) {
    lines.push(
      headers
        .map(h => {
          const v = r[h] ?? "";
          const s = String(v).replace(/"/g, '""');
          return `"${s}"`;
        })
        .join(",")
    );
  }
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `metric_board_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function loadSchedules() {
  scheduleLoading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/queries/schedules/list");
    scheduleItems.value = res.data || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载调度失败");
  } finally {
    scheduleLoading.value = false;
  }
}

async function seedSchedules() {
  seedLoading.value = true;
  try {
    const res = await http.request<any>("post", "/api/v1/queries/schedules/seed-core");
    ElMessage.success(`已种子 ${res.data?.count ?? 0} 条（默认关闭）`);
    await loadSchedules();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "种子失败");
  } finally {
    seedLoading.value = false;
  }
}

async function toggleSchedule(row: any) {
  try {
    await http.request<any>("post", "/api/v1/queries/schedules", {
      data: {
        query_code: row.query_code,
        schedule_cron: row.schedule_cron || "0 3 * * *",
        source_code: row.source_code,
        enabled: !row.enabled,
        result_storage: "none"
      }
    });
    ElMessage.success(row.enabled ? "已关闭" : "已启用（仍依赖全局开关）");
    await loadSchedules();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "更新失败");
  }
}

async function loadSources() {
  sourceLoading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/queries/sources/capabilities");
    sourceItems.value = res.data?.items || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "加载多源能力失败");
  } finally {
    sourceLoading.value = false;
  }
}

onMounted(() => {
  loadList();
  loadRuns();
});
</script>

<style scoped>
.query-center {
  padding: 4px;
}
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.mb16 {
  margin-bottom: 16px;
}
.mt12 {
  margin-top: 12px;
}
.mt16 {
  margin-top: 16px;
}
.sql-box {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
}
.muted {
  color: #64748b;
  font-size: 13px;
  align-self: center;
}
.board-wrap {
  overflow: auto;
}
.mb12 {
  margin-bottom: 12px;
}
</style>
