<template>
  <div class="quality-issues-page">
    <RePageHeader :title="pageTitle" subtitle="问题能分派到科室和人员、整改、复测、关闭并留痕的治理闭环。">
      <template #actions>
        <el-button @click="loadList">刷新</el-button>
        <el-button v-perms="'quality.issue.create'" type="primary" @click="openCreate">
          手工登记问题
        </el-button>
        <el-button v-perms="'quality.issue.export'" @click="doExport">导出 CSV</el-button>
      </template>
    </RePageHeader>

    <el-card shadow="never" class="main-card">
      <div class="scope-row">
        <el-radio-group v-model="activeScope" @change="onScopeChange">
          <el-radio-button value="mine">我的任务</el-radio-button>
          <el-radio-button value="department">科室任务</el-radio-button>
          <el-radio-button value="all">全院总览</el-radio-button>
        </el-radio-group>
        <span class="scope-hint">{{ scopeHint }}</span>
      </div>

      <div class="filter-row">
        <el-select v-model="filters.status" placeholder="状态" clearable class="f-item f-slim">
          <el-option v-for="s in STATUSES" :key="s" :label="statusLabel(s)" :value="s" />
        </el-select>
        <el-select v-model="filters.severity" placeholder="严重度" clearable class="f-item f-slim">
          <el-option v-for="s in SEVERITIES" :key="s" :label="severityLabel(s)" :value="s" />
        </el-select>
        <el-select v-model="filters.priority" placeholder="优先级" clearable class="f-item f-slim">
          <el-option v-for="p in PRIORITIES" :key="p" :label="p" :value="p" />
        </el-select>
        <el-input
          v-model="filters.primary_system_code"
          placeholder="系统（如 HIS）"
          clearable
          class="f-item"
          @keyup.enter="applyFilter"
        />
        <el-input
          v-model="filters.keyword"
          placeholder="问题编号/标题关键字"
          clearable
          class="f-item f-wide"
          @keyup.enter="applyFilter"
        />
        <el-checkbox v-model="filters.overdue" label="仅逾期" @change="applyFilter" />
        <el-button type="primary" @click="applyFilter">筛选</el-button>
        <el-button @click="resetFilter">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="items" stripe row-key="id" @row-click="openDetail">
        <el-table-column prop="issue_code" label="问题编号" width="150" show-overflow-tooltip />
        <el-table-column label="问题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.title }}</span>
            <el-tag v-if="row.recurrence_no > 0" size="small" type="danger" class="ml4">
              复发{{ row.recurrence_no }}
            </el-tag>
            <el-tag v-if="row.issue_type === 'monitoring_gap'" size="small" type="warning" class="ml4">
              监测缺口
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="系统/对象" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.primary_system_code || "-" }}</div>
            <div class="muted">{{ row.object_name_snapshot || row.control_code || "" }}</div>
          </template>
        </el-table-column>
        <el-table-column label="最新指标" width="120">
          <template #default="{ row }">
            <span :class="row.latest_result_status === 'fail' ? 'metric-bad' : 'metric-ok'">
              {{ row.latest_metric_value ?? "-" }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="严重度" width="82" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="sevTagType(row.severity)">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="76" align="center" />
        <el-table-column label="责任" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ row.responsible_dept_name_snapshot || row.responsible_dept_code || "-" }}</div>
            <div class="muted">
              {{ row.responsible_person_name_snapshot || row.responsible_person_code || "" }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="assignee_name_snapshot" label="经办人" width="90" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.assignee_name_snapshot || row.assignee_user_identifier || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTagType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="到期" width="120">
          <template #default="{ row }">
            <span :class="{ overdue: row.overdue }">
              {{ row.due_at || "-" }}
              <template v-if="row.overdue">（逾期）</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近观测" width="140">
          <template #default="{ row }">
            {{ formatTime(row.last_seen_at) }}
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

    <el-dialog
      v-model="createVisible"
      title="手工登记问题"
      width="640px"
      @closed="resetCreateForm"
    >
      <el-form label-width="96px">
        <el-form-item label="问题标题" required>
          <el-input v-model="createForm.title" maxlength="256" placeholder="例如：XX 表 XX 字段缺失" />
        </el-form-item>
        <el-form-item label="问题描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="主责系统">
          <el-input v-model="createForm.primary_system_code" placeholder="如 HIS / LIS / DOCARE" />
        </el-form-item>
        <el-form-item label="对象说明">
          <el-input v-model="createForm.object_name_snapshot" placeholder="如 MEDREC.PAT_VISIT.DISCHARGE_DISPOSITION" />
        </el-form-item>
        <el-form-item label="严重度">
          <el-select v-model="createForm.severity" class="w160">
            <el-option v-for="s in SEVERITIES" :key="s" :label="severityLabel(s)" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="createForm.priority" class="w160">
            <el-option v-for="p in PRIORITIES" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="主责科室">
          <el-select
            v-model="createForm.responsible_dept_code"
            filterable
            clearable
            placeholder="选择科室"
            class="w-full"
            @change="onCreateDeptChange"
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
          <el-select
            v-model="createForm.responsible_person_code"
            filterable
            clearable
            placeholder="选择责任人"
            class="w-full"
          >
            <el-option
              v-for="p in persons"
              :key="p.person_code"
              :label="`${p.person_name_cn || p.person_code}（${p.person_code}）`"
              :value="p.person_code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="计划完成日">
          <el-date-picker v-model="createForm.due_at" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="证据来源">
          <el-input v-model="createForm.evidence_ref" placeholder="如 会议纪要/工单号（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="acting" @click="submitCreate">登记</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import RePageHeader from "@/components/RePageHeader/index.vue";
import {
  createQualityIssue,
  exportQualityIssues,
  listAssignmentDepartments,
  listAssignmentPersons,
  listQualityIssues,
  type AssignmentDepartment,
  type AssignmentPerson,
  type QualityIssueListItem
} from "@/api/quality";
import { extractErrorDetail } from "@/utils/errorMessage";
import { formatTime } from "@/utils/format";

defineOptions({ name: "QualityIssues" });

const STATUSES = [
  "new",
  "acknowledged",
  "assigned",
  "in_progress",
  "waiting_external",
  "waiting_verify",
  "resolved",
  "accepted_risk",
  "false_positive",
  "duplicate",
  "cancelled"
];
const SEVERITIES = ["critical", "high", "medium", "low", "info"];
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

const router = useRouter();
const loading = ref(false);
const acting = ref(false);
const items = ref<QualityIssueListItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const activeScope = ref<"mine" | "department" | "all">("all");
const scopeHint = ref("");
const scopeForbidden = ref(false);
const skipNextActivated = ref(true);

const pageTitle = computed(() => {
  if (activeScope.value === "department") return "科室任务";
  if (activeScope.value === "mine") return "我的任务";
  return "质量台账";
});

const filters = reactive({
  status: "",
  severity: "",
  priority: "",
  primary_system_code: "",
  keyword: "",
  overdue: false
});

const createVisible = ref(false);
const departments = ref<AssignmentDepartment[]>([]);
const persons = ref<AssignmentPerson[]>([]);
const createForm = reactive({
  title: "",
  description: "",
  primary_system_code: "",
  object_name_snapshot: "",
  severity: "medium",
  priority: "P3",
  responsible_dept_code: "",
  responsible_person_code: "",
  due_at: "",
  evidence_ref: ""
});

function statusLabel(status: string): string {
  return STATUS_LABELS[status] || status;
}

function severityLabel(severity: string | null): string {
  return SEVERITY_LABELS[severity || ""] || severity || "-";
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

/** 路由进入默认范围：台账=/quality/issues→all；我的/科室走独立 path。KeepAlive 必须随路由刷新。 */
function initScopeFromRoute() {
  const path = router.currentRoute.value.path.replace(/\/$/, "");
  if (path.endsWith("/department")) activeScope.value = "department";
  else if (path.endsWith("/mine")) activeScope.value = "mine";
  else activeScope.value = "all";
}

function onScopeChange() {
  page.value = 1;
  loadList();
}

async function loadList() {
  loading.value = true;
  scopeForbidden.value = false;
  try {
    const params: Record<string, unknown> = {
      scope: activeScope.value,
      page: page.value,
      page_size: pageSize.value
    };
    for (const [key, value] of Object.entries(filters)) {
      if (value) params[key] = value;
    }
    const res = await listQualityIssues(params as any);
    items.value = res.items;
    total.value = res.total;
    scopeHint.value =
      res.scope === "all" ? "全院总览（需 quality.issue.read_all 权限）" : "";
  } catch (error: any) {
    items.value = [];
    total.value = 0;
    const detail = extractErrorDetail(error, "台账加载失败");
    if (/read_all|403/i.test(detail)) {
      scopeForbidden.value = true;
      scopeHint.value = "无全院查看权限（quality.issue.read_all），已回退本人范围";
      activeScope.value = "mine";
      if (page.value === 1) {
        try {
          const res = await listQualityIssues({ scope: "mine", page: 1, page_size: pageSize.value });
          items.value = res.items;
          total.value = res.total;
        } catch {
          ElMessage.error(detail);
        }
      }
    } else {
      ElMessage.error(detail);
    }
  } finally {
    loading.value = false;
  }
}

function applyFilter() {
  page.value = 1;
  loadList();
}

function resetFilter() {
  for (const key of Object.keys(filters) as (keyof typeof filters)[]) {
    (filters as any)[key] = key === "overdue" ? false : "";
  }
  page.value = 1;
  loadList();
}

function onPageSizeChange() {
  page.value = 1;
  loadList();
}

function openDetail(row: QualityIssueListItem) {
  router.push(`/quality/issues/${row.id}`);
}

async function doExport() {
  try {
    const body: Record<string, unknown> = { scope: activeScope.value };
    for (const [key, value] of Object.entries(filters)) {
      if (value) body[key] = value;
    }
    const blob = (await exportQualityIssues(body as any)) as unknown as Blob;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `quality-issues-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "导出失败（上限 5000 行，请缩小范围）"));
  }
}

async function openCreate() {
  createVisible.value = true;
  if (!departments.value.length) {
    try {
      const res = await listAssignmentDepartments();
      departments.value = res.items;
    } catch (error: any) {
      ElMessage.error(extractErrorDetail(error, "科室选项加载失败"));
    }
  }
}

async function onCreateDeptChange(deptCode: string) {
  persons.value = [];
  createForm.responsible_person_code = "";
  if (!deptCode) return;
  try {
    const res = await listAssignmentPersons({ department_code: deptCode });
    persons.value = res.items;
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "人员选项加载失败"));
  }
}

function resetCreateForm() {
  for (const key of Object.keys(createForm) as (keyof typeof createForm)[]) {
    (createForm as any)[key] = "";
  }
  createForm.severity = "medium";
  createForm.priority = "P3";
}

async function submitCreate() {
  if (!createForm.title.trim()) {
    ElMessage.warning("问题标题必填");
    return;
  }
  acting.value = true;
  try {
    await createQualityIssue({ ...createForm });
    ElMessage.success("问题已登记（new）");
    createVisible.value = false;
    loadList();
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "登记失败"));
  } finally {
    acting.value = false;
  }
}

initScopeFromRoute();
onMounted(loadList);
onActivated(() => {
  if (skipNextActivated.value) {
    skipNextActivated.value = false;
    return;
  }
  initScopeFromRoute();
  loadList();
});
watch(
  () => router.currentRoute.value.path,
  (to, from) => {
    if (to === from) return;
    initScopeFromRoute();
    page.value = 1;
    loadList();
  }
);
</script>

<style scoped>
.quality-issues-page {
  min-height: calc(100vh - 84px);
}

.main-card {
  margin: 12px 16px;
}

.scope-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.scope-hint {
  color: #909399;
  font-size: 12px;
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
  width: 120px;
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

.pager-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.w160 {
  width: 160px;
}

.w-full {
  width: 100%;
}
</style>
