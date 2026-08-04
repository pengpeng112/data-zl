<script setup lang="ts">
import { ref, reactive } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile } from "element-plus";
import {
  uploadDiagnosisMapping,
  getImportRun,
  getImportRows,
  reviewImportRows,
  mergeImportRun
} from "@/api/dict";
import type { ImportRunInfo, ImportRowItem } from "@/api/dict";

const step = ref(1);
const uploading = ref(false);
const runInfo = ref<ImportRunInfo | null>(null);
const rows = ref<ImportRowItem[]>([]);
const rowsTotal = ref(0);
const rowsPage = ref(1);
const loading = ref(false);
const onlyAnomalies = ref(false);
const selectedIds = ref<number[]>([]);
const merging = ref(false);

async function handleUpload(uploadFile: UploadFile) {
  if (!uploadFile.raw) return;
  uploading.value = true;
  try {
    const res = await uploadDiagnosisMapping(uploadFile.raw);
    const data = res.data;
    ElMessage.success(`解析完成：${data.row_count} 行，工作表 ${data.sheet}`);
    runInfo.value = await loadRunInfo(data.import_run_id);
    step.value = 2;
    await loadRows(data.import_run_id);
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "上传失败");
  } finally {
    uploading.value = false;
  }
}

async function loadRunInfo(runId: number): Promise<ImportRunInfo> {
  const res = await getImportRun(runId);
  return res.data;
}

async function loadRows(runId?: number) {
  const id = runId || runInfo.value?.id;
  if (!id) return;
  loading.value = true;
  try {
    const res = await getImportRows(id, {
      page: rowsPage.value,
      page_size: 50,
      only_anomalies: onlyAnomalies.value
    });
    rows.value = res.data.items;
    rowsTotal.value = res.data.total;
  } finally {
    loading.value = false;
  }
}

function onSelectionChange(selection: ImportRowItem[]) {
  selectedIds.value = selection.map(r => r.id);
}

async function batchReview(action: "approve" | "reject") {
  if (!runInfo.value || selectedIds.value.length === 0) return;
  const label = action === "approve" ? "批准" : "驳回";
  await ElMessageBox.confirm(`确认${label} ${selectedIds.value.length} 行？`, "审核确认");
  try {
    const res = await reviewImportRows(runInfo.value.id, {
      row_ids: selectedIds.value,
      action
    });
    ElMessage.success(`已${label} ${res.data.reviewed} 行${res.data.blocked ? `，${res.data.blocked} 行被阻断` : ""}`);
    await loadRows();
    runInfo.value = await loadRunInfo(runInfo.value.id);
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "审核失败");
  }
}

async function doMerge() {
  if (!runInfo.value) return;
  await ElMessageBox.confirm("确认将已批准行合并到正式字典？此操作不可撤销。", "正式合并");
  merging.value = true;
  try {
    const res = await mergeImportRun(runInfo.value.id);
    ElMessage.success(`合并完成：新增 ${res.data.items_created} 项，映射 ${res.data.mappings_created} 条`);
    step.value = 4;
    runInfo.value = await loadRunInfo(runInfo.value.id);
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : "合并失败");
  } finally {
    merging.value = false;
  }
}

type TagType = "primary" | "success" | "warning" | "danger" | "info";
function statusTag(status: string): TagType {
  const map: Record<string, TagType> = {
    valid: "success",
    warning: "warning",
    error: "danger",
    pending: "info",
    approved: "success",
    rejected: "danger"
  };
  return map[status] || "info";
}
</script>

<template>
  <div class="import-wizard">
    <el-steps :active="step - 1" finish-status="success" class="wizard-steps">
      <el-step title="上传文件" />
      <el-step title="解析校验" />
      <el-step title="差异审核" />
      <el-step title="合并结果" />
    </el-steps>

    <!-- Step 1: Upload -->
    <div v-if="step === 1" class="step-content">
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".xlsx,.xls"
        :on-change="handleUpload"
      >
        <el-icon class="el-icon--upload"><i class="ep:upload-filled" /></el-icon>
        <div class="el-upload__text">拖拽 Excel 到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">仅支持 .xlsx/.xls，工作表需包含"诊断字典映射"</div>
        </template>
      </el-upload>
      <el-button v-if="uploading" loading disabled class="mt-4">解析中...</el-button>
    </div>

    <!-- Step 2: Validation Summary -->
    <div v-if="step === 2 && runInfo" class="step-content">
      <el-descriptions :column="3" border size="small" class="mb-4">
        <el-descriptions-item label="批次">{{ runInfo.batch_code }}</el-descriptions-item>
        <el-descriptions-item label="文件">{{ runInfo.file_name }}</el-descriptions-item>
        <el-descriptions-item label="SHA256">{{ runInfo.file_sha256?.slice(0, 16) }}...</el-descriptions-item>
      </el-descriptions>
      <el-row :gutter="12" class="mb-4">
        <el-col :span="4"><el-statistic title="待审核" :value="runInfo.row_stats?.pending || 0" /></el-col>
        <el-col :span="4"><el-statistic title="校验通过" :value="runInfo.row_stats?.validation_valid || 0" /></el-col>
        <el-col :span="4"><el-statistic title="警告" :value="runInfo.row_stats?.validation_warning || 0" /></el-col>
        <el-col :span="4"><el-statistic title="错误" :value="runInfo.row_stats?.validation_error || 0" /></el-col>
        <el-col :span="4"><el-statistic title="已批准" :value="runInfo.row_stats?.approved || 0" /></el-col>
        <el-col :span="4"><el-statistic title="已驳回" :value="runInfo.row_stats?.rejected || 0" /></el-col>
      </el-row>
      <el-button type="primary" @click="step = 3">进入审核</el-button>
    </div>

    <!-- Step 3: Review -->
    <div v-if="step === 3 && runInfo" class="step-content">
      <div class="toolbar mb-2">
        <el-checkbox v-model="onlyAnomalies" @change="loadRows()">只看异常</el-checkbox>
        <el-button type="success" size="small" :disabled="selectedIds.length === 0" @click="batchReview('approve')">
          批量批准 ({{ selectedIds.length }})
        </el-button>
        <el-button type="danger" size="small" :disabled="selectedIds.length === 0" @click="batchReview('reject')">
          批量驳回
        </el-button>
        <el-button type="primary" size="small" @click="doMerge()" :loading="merging">
          合并已批准行
        </el-button>
      </div>
      <el-table
        v-loading="loading"
        :data="rows"
        stripe
        size="small"
        @selection-change="onSelectionChange"
        max-height="480"
      >
        <el-table-column type="selection" width="40" />
        <el-table-column prop="row_no" label="行号" width="60" />
        <el-table-column prop="hospital_code" label="院内编码" width="120" fixed />
        <el-table-column prop="hospital_name" label="院内名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="national_clinical_code" label="国临编码" width="120" />
        <el-table-column prop="insurance_code" label="医保编码" width="120" />
        <el-table-column label="医保状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.insurance_mapping_status === 'grey' ? 'warning' : 'info'" size="small">
              {{ row.insurance_mapping_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="校验" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.validation_status)" size="small">{{ row.validation_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.review_status)" size="small">{{ row.review_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="diff_type" label="差异" width="100" />
      </el-table>
      <el-pagination
        v-if="rowsTotal > 50"
        v-model:current-page="rowsPage"
        :total="rowsTotal"
        :page-size="50"
        layout="total, prev, pager, next"
        class="mt-2"
        @change="loadRows()"
      />
    </div>

    <!-- Step 4: Result -->
    <div v-if="step === 4 && runInfo" class="step-content">
      <el-result icon="success" title="合并完成" :sub-title="`批次 ${runInfo.batch_code} 已合并到正式字典`">
        <template #extra>
          <el-button @click="step = 1; runInfo = null">导入新文件</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<style scoped>
.import-wizard { padding: 16px 0; }
.wizard-steps { margin-bottom: 24px; }
.step-content { min-height: 300px; }
.toolbar { display: flex; align-items: center; gap: 12px; }
</style>