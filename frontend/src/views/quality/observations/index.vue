<template>
  <div class="quality-observations-page">
    <RePageHeader title="观测记录" subtitle="不可变观测流水：每次执行在一个窗口、一个范围的固化结果。">
      <template #actions>
        <el-button @click="loadList">刷新</el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <div class="filter-row">
        <el-select v-model="filters.result_status" placeholder="结果" clearable class="f-item">
          <el-option v-for="r in RESULTS" :key="r" :label="r" :value="r" />
        </el-select>
        <el-select v-model="filters.source_kind" placeholder="来源" clearable class="f-item">
          <el-option v-for="s in SOURCES" :key="s" :label="s" :value="s" />
        </el-select>
        <el-input
          v-model="filters.control_id"
          placeholder="清单 ID"
          clearable
          class="f-item f-slim"
          @keyup.enter="applyFilter"
        />
        <el-button type="primary" @click="applyFilter">筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column prop="id" label="#" width="70" align="center" />
        <el-table-column prop="control_id" label="清单" width="70" align="center" />
        <el-table-column prop="control_version" label="版本" width="60" align="center" />
        <el-table-column label="结果" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="obsTagType(row.result_status)">
              {{ row.result_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="指标" width="110">
          <template #default="{ row }">
            {{ row.metric_value ?? "-" }}{{ row.metric_unit || "" }}
          </template>
        </el-table-column>
        <el-table-column prop="scope_key" label="范围" min-width="200" show-overflow-tooltip />
        <el-table-column label="窗口" width="180">
          <template #default="{ row }">
            {{ row.window_start || "-" }} ~ {{ row.window_end || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="来源" width="130">
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
        <el-table-column label="观测时间" width="150">
          <template #default="{ row }">
            {{ formatTime(row.observed_at) }}
          </template>
        </el-table-column>
        <el-table-column label="精度" width="130" align="center">
          <template #default="{ row }">
            <span class="muted">{{ precisionLabel(row.historical_precision) }}</span>
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import { listQualityObservations, type QualityObservationItem } from "@/api/quality";
import { extractErrorDetail } from "@/utils/errorMessage";
import { formatTime } from "@/utils/format";
import { parseProbeFindingRef, probeFindingLink } from "@/views/quality/sourceRef";

defineOptions({ name: "QualityObservations" });

const router = useRouter();

const RESULTS = ["pass", "fail", "error", "blocked", "skipped", "no_data"];
const SOURCES = ["probe_finding", "probe_run", "quality_finding", "manual", "external"];

const loading = ref(false);
const items = ref<QualityObservationItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const filters = reactive({ result_status: "", source_kind: "", control_id: "" });

function obsTagType(result: string): "success" | "danger" | "warning" | "info" {
  return (
    { pass: "success", fail: "danger", blocked: "warning", no_data: "warning" } as Record<
      string,
      "success" | "danger" | "warning" | "info"
    >
  )[result] || "info";
}

/** 178 R4①：观测来源为探查发现时，正向跳转发现页并按 finding_id 定位 */
function goProbeFinding(id: number) {
  router.push(probeFindingLink({ type: "probe_finding", id }));
}

function precisionLabel(precision: string): string {
  return (
    {
      exact: "精确",
      latest_snapshot: "最新快照",
      summary_backfill: "汇总回填"
    } as Record<string, string>
  )[precision] || precision;
}

async function loadList() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = key === "control_id" ? Number(value) : value;
    }
    const res = await listQualityObservations(params as any);
    items.value = res.items;
    total.value = res.total;
  } catch (error: any) {
    items.value = [];
    total.value = 0;
    ElMessage.error(extractErrorDetail(error, "观测记录加载失败"));
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  loadList();
}

function resetFilter() {
  filters.result_status = "";
  filters.source_kind = "";
  filters.control_id = "";
  page.value = 1;
  loadList();
}

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

onMounted(loadList);
</script>

<style scoped>
.quality-observations-page {
  min-height: calc(100vh - 84px);
}

.main-card {
  margin: 12px 16px;
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
  width: 110px;
}

.muted {
  color: #909399;
  font-size: 12px;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
