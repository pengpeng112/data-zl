<template>
  <div class="quality-controls-page">
    <RePageHeader title="质控清单" subtitle="版本化的质控规则清单：稳定编码 + 口径版本，绑定检测来源。">
      <template #actions>
        <el-button @click="loadList">刷新</el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <div class="filter-row">
        <el-select v-model="filters.lifecycle_status" placeholder="状态" clearable class="f-item">
          <el-option label="草稿" value="draft" />
          <el-option label="激活" value="active" />
          <el-option label="阻塞" value="blocked" />
          <el-option label="废弃" value="deprecated" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="编码/名称关键字"
          clearable
          class="f-item f-wide"
          @keyup.enter="applyFilter"
        />
        <el-button type="primary" @click="applyFilter">筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column prop="control_code" label="清单编码" width="170" show-overflow-tooltip />
        <el-table-column label="名称" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.title }}
            <el-tag size="small" class="ml4">v{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="86" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="lifeTagType(row.lifecycle_status)">
              {{ lifeLabel(row.lifecycle_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="86" align="center" />
        <el-table-column prop="dimension" label="维度" width="110" show-overflow-tooltip />
        <el-table-column prop="primary_system_code" label="主责系统" width="90" align="center" />
        <el-table-column label="指标/阈值" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.metric_name">
              {{ row.metric_name }} {{ row.comparator || "" }} {{ row.threshold_value ?? "-" }}{{ row.metric_unit || "" }}
            </template>
            <span v-else class="muted">手工清单</span>
          </template>
        </el-table-column>
        <el-table-column label="检测器" min-width="180">
          <template #default="{ row }">
            <div v-for="d in row.detectors" :key="d.id" class="detector-line">
              <el-tag size="small" :type="detectorTagType(d.status)" class="mr4">{{ d.status }}</el-tag>
              <span class="muted">{{ d.detector_kind }}:{{ d.detector_ref }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.lifecycle_status !== 'active'"
              v-perms="'quality.control.manage'"
              size="small"
              type="primary"
              link
              @click="doActivate(row)"
            >
              激活
            </el-button>
            <el-button
              v-if="row.lifecycle_status === 'active'"
              v-perms="'quality.control.run'"
              size="small"
              type="success"
              link
              @click="doRun(row)"
            >
              执行
            </el-button>
            <el-button
              v-if="row.lifecycle_status === 'active'"
              v-perms="'quality.control.manage'"
              size="small"
              type="warning"
              link
              @click="doDeprecate(row)"
            >
              废弃
            </el-button>
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
import { ElMessage, ElMessageBox } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  activateQualityControl,
  deprecateQualityControl,
  listQualityControls,
  runQualityControl,
  type QualityControlItem
} from "@/api/quality";
import { extractErrorDetail } from "@/utils/errorMessage";

defineOptions({ name: "QualityControls" });

const loading = ref(false);
const items = ref<QualityControlItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const filters = reactive({ lifecycle_status: "", keyword: "" });

function lifeLabel(status: string): string {
  return { draft: "草稿", active: "激活", blocked: "阻塞", deprecated: "废弃" }[status] || status;
}

function lifeTagType(status: string): "success" | "warning" | "info" | "danger" {
  return (
    { draft: "info", active: "success", blocked: "danger", deprecated: "warning" } as Record<
      string,
      "success" | "warning" | "info" | "danger"
    >
  )[status] || "info";
}

function detectorTagType(status: string): "success" | "warning" | "info" | "danger" {
  return (
    { active: "success", blocked: "danger", draft: "info", disabled: "warning" } as Record<
      string,
      "success" | "warning" | "info" | "danger"
    >
  )[status] || "info";
}

async function loadList() {
  loading.value = true;
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    const res = await listQualityControls(params as any);
    items.value = res.items;
    total.value = res.total;
  } catch (error: any) {
    items.value = [];
    total.value = 0;
    ElMessage.error(extractErrorDetail(error, "质控清单加载失败"));
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  loadList();
}

function resetFilter() {
  filters.lifecycle_status = "";
  filters.keyword = "";
  page.value = 1;
  loadList();
}

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

async function doActivate(row: QualityControlItem) {
  try {
    await activateQualityControl(row.id);
    ElMessage.success(`已激活 ${row.control_code}`);
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "激活失败（自动规则需至少一个 active 检测器）"));
  }
}

async function doDeprecate(row: QualityControlItem) {
  try {
    await ElMessageBox.confirm(`确认废弃清单 ${row.control_code}？`, "废弃确认", { type: "warning" });
  } catch {
    return;
  }
  try {
    await deprecateQualityControl(row.id);
    ElMessage.success(`已废弃 ${row.control_code}`);
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "废弃失败"));
  }
}

async function doRun(row: QualityControlItem) {
  try {
    const res: any = await runQualityControl(row.id);
    const runnable = (res?.runnable_detectors || []).join(", ") || "无";
    ElMessage.info(`已受理（runnable: ${runnable}）；探查模板由夜间执行器执行，本入口不伪造结果`);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "执行请求失败（清单需为激活状态）"));
  }
}

onMounted(loadList);
</script>

<style scoped>
.quality-controls-page {
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

.mr4 {
  margin-right: 4px;
}

.detector-line {
  line-height: 1.6;
}

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
