<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { ref, onMounted } from "vue";
import { http } from "@/utils/http";
import { ElMessage } from "element-plus";

interface System {
  id: number;
  system_code: string;
  system_name_cn: string;
  system_type: string;
  status: string;
  created_at: string;
}

const systems = ref<System[]>([]);
const loading = ref(false);
const dialogVisible = ref(false);
const dialogTitle = ref("新增系统");
const form = ref({ system_code: "", system_name_cn: "", system_type: "", description_cn: "", status: "active" });
const typeOptions = ["ODS", "HIS", "EMR", "LIS", "PACS", "NURSING", "HRP", "OTHER"];

async function loadSystems() {
  loading.value = true;
  try {
    const res = await http.request<any>("get", "/api/v1/systems");
    systems.value = res.data || [];
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  dialogTitle.value = "新增系统";
  form.value = { system_code: "", system_name_cn: "", system_type: "", description_cn: "", status: "active" };
  dialogVisible.value = true;
}

function openEdit(row: System) {
  dialogTitle.value = "编辑系统";
  form.value = {
    system_code: row.system_code,
    system_name_cn: row.system_name_cn,
    system_type: row.system_type || "",
    description_cn: "",
    status: row.status || "active"
  };
  dialogVisible.value = true;
}

async function saveSystem() {
  if (!form.value.system_code || !form.value.system_name_cn) {
    ElMessage.warning("系统编码和名称为必填");
    return;
  }
  try {
    await http.request("put", "/api/v1/systems", { data: form.value });
    ElMessage.success("保存成功");
    dialogVisible.value = false;
    loadSystems();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  }
}

async function deleteSystem(code: string) {
  try {
    await http.request("delete", `/api/v1/systems/${code}`);
    ElMessage.success("已删除");
    loadSystems();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  }
}

function getTypeColor(type: string): any {
  const map: Record<string, string> = { HIS: "", EMR: "success", LIS: "warning", PACS: "danger", NURSING: "info", ODS: "", OTHER: "info" };
  return map[type] || "";
}

onMounted(loadSystems);
</script>

<template>
  <div class="systems-page">
    <RePageHeader
      title="系统总览"
      subtitle="维护系统编码与类型；表目录五层导航的「系统大类」由此映射（ODS / HIS 源端 / 周边业务 / HRP / 平台）。"
    >
      <template #actions>
        <el-button type="primary" @click="openCreate">新增系统</el-button>
      </template>
    </RePageHeader>

    <el-card class="systems-card">
      <el-row :gutter="16">
        <el-col v-for="s in systems" :key="s.id" :xs="24" :sm="12" :lg="6">
          <el-card shadow="hover" class="system-tile">
            <div class="system-tile-main">
              <div>
                <h4 class="system-title">{{ s.system_name_cn }}</h4>
                <p class="system-code">{{ s.system_code }}</p>
                <el-tag v-if="s.system_type" :type="getTypeColor(s.system_type)" size="small">{{ s.system_type }}</el-tag>
                <el-tag :type="s.status === 'active' ? 'success' : 'info'" size="small" class="status-tag">{{ s.status === 'active' ? '启用' : '禁用' }}</el-tag>
              </div>
              <div>
                <el-button size="small" text @click="openEdit(s)">编辑</el-button>
                <el-button size="small" text type="danger" @click="deleteSystem(s.system_code)">删除</el-button>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-empty v-if="!loading && systems.length === 0" description="暂无系统" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="系统编码" required>
          <el-input v-model="form.system_code" :disabled="dialogTitle === '编辑系统'" />
        </el-form-item>
        <el-form-item label="系统名称" required>
          <el-input v-model="form.system_name_cn" />
        </el-form-item>
        <el-form-item label="系统类型">
          <el-select v-model="form.system_type" clearable class="full-width">
            <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="active">启用</el-radio>
            <el-radio value="inactive">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description_cn" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSystem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.systems-page {
  padding: 4px;
}
.systems-card {
  border-color: var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
}
.systems-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.system-tile :deep(.el-card__body) {
  padding: 16px;
}
.system-tile-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.system-title {
  margin: 0 0 8px;
  font-size: 15px;
  color: var(--text-primary);
}
.system-code {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--text-secondary);
}
.status-tag {
  margin-left: 4px;
}
@media (max-width: 1200px) {
  .systems-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .systems-grid { grid-template-columns: 1fr; }
}

.full-width { width: 100%; }
</style>
