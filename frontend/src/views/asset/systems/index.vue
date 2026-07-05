<script setup lang="ts">
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
const typeOptions = ["HIS", "EMR", "LIS", "PACS", "NURSING", "ODS", "OTHER"];

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
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>系统总览</span>
          <el-button type="primary" @click="openCreate">新增系统</el-button>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col v-for="s in systems" :key="s.id" :span="6" style="margin-bottom:16px">
          <el-card shadow="hover" :body-style="{ padding: '16px' }">
            <div style="display:flex;justify-content:space-between;align-items:flex-start">
              <div>
                <h4 style="margin:0 0 8px">{{ s.system_name_cn }}</h4>
                <p style="margin:0 0 4px;color:#909399;font-size:13px">{{ s.system_code }}</p>
                <el-tag v-if="s.system_type" :type="getTypeColor(s.system_type)" size="small">{{ s.system_type }}</el-tag>
                <el-tag :type="s.status === 'active' ? 'success' : 'info'" size="small" style="margin-left:4px">{{ s.status === 'active' ? '启用' : '禁用' }}</el-tag>
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
          <el-select v-model="form.system_type" clearable style="width:100%">
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
