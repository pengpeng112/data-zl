<script setup lang="ts">
import { ref, onMounted } from "vue";
import { http } from "@/utils/http";
import { ElMessage } from "element-plus";

interface DataSource {
  id: number;
  system_code: string;
  source_code: string;
  source_name_cn: string;
  db_type: string;
  environment: string;
  collect_mode: string;
  enabled: boolean;
  last_check_status: string;
}

interface TreeNode {
  source_code: string;
  source_name_cn: string;
  system_code: string;
  schemas: { namespace: string; tables: any[]; table_count: number }[];
  table_count: number;
}

interface Snapshot {
  snapshot_id: number;
  label: string;
  created_at: string;
  table_count: number;
  column_count: number;
}

interface CollectResult {
  snapshot_id: number;
  table_count: number;
  column_count: number;
}

const sources = ref<DataSource[]>([]);
const tree = ref<TreeNode[]>([]);
const dialogVisible = ref(false);
const dialogTitle = ref("新增数据源");
const form = ref({ system_code: "", source_code: "", source_name_cn: "", db_type: "", host_masked: "", port: 1521, connection_mode: "direct", environment: "prod", collect_mode: "metadata_only", enabled: true, description_cn: "" });
const dbTypes = ["oracle", "postgresql", "mysql", "sqlserver"];
const connModes = ["direct", "jump_host", "dblink", "manual_import"];

const collectingSource = ref<string | null>(null);
const collectResult = ref<CollectResult | null>(null);
const snapshots = ref<Snapshot[]>([]);
const selectedSource = ref<DataSource | null>(null);
const snapshotsLoading = ref(false);

async function loadSources() {
  const res = await http.request<any>("get", "/api/v1/sources");
  sources.value = res.data || [];
}

async function loadTree() {
  const res = await http.request<any>("get", "/api/v1/assets/tree");
  tree.value = res.data || [];
}

function openCreate() {
  dialogTitle.value = "新增数据源";
  form.value = { system_code: "", source_code: "", source_name_cn: "", db_type: "", host_masked: "", port: 1521, connection_mode: "direct", environment: "prod", collect_mode: "metadata_only", enabled: true, description_cn: "" };
  dialogVisible.value = true;
}

async function saveSource() {
  if (!form.value.system_code || !form.value.source_code) {
    ElMessage.warning("系统编码和数据源编码为必填");
    return;
  }
  try {
    await http.request("put", "/api/v1/sources", { data: form.value });
    ElMessage.success("保存成功");
    dialogVisible.value = false;
    loadSources();
    loadTree();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  }
}

async function checkSource(code: string) {
  ElMessage.info("正在检测...");
  try {
    const res = await http.request<any>("post", `/api/v1/sources/${code}/check`);
    ElMessage.success(res.data?.message || "检测完成");
    loadSources();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "检测失败");
  }
}

async function deleteSource(code: string) {
  try {
    await http.request("delete", `/api/v1/sources/${code}`);
    ElMessage.success("已删除");
    loadSources();
    loadTree();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  }
}

function selectSource(row: DataSource) {
  selectedSource.value = row;
  collectResult.value = null;
  loadSnapshots(row.source_code);
}

async function loadSnapshots(sourceCode: string) {
  snapshotsLoading.value = true;
  try {
    const res = await http.request<any>("get", `/api/v1/sources/${sourceCode}/snapshots`);
    snapshots.value = res.data || [];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "获取快照失败");
    snapshots.value = [];
  } finally {
    snapshotsLoading.value = false;
  }
}

async function handleCollect(sourceCode: string) {
  collectingSource.value = sourceCode;
  collectResult.value = null;
  try {
    const res = await http.request<any>("post", `/api/v1/sources/${sourceCode}/collect-metadata`);
    collectResult.value = res.data || null;
    ElMessage.success(`采集完成：快照ID ${res.data?.snapshot_id}，${res.data?.table_count} 表，${res.data?.column_count} 字段`);
    loadSources();
    if (selectedSource.value && selectedSource.value.source_code === sourceCode) {
      loadSnapshots(sourceCode);
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "采集失败：数据源未注册或连接不可用");
  } finally {
    collectingSource.value = null;
  }
}

onMounted(() => { loadSources(); loadTree(); });
</script>

<template>
  <div>
    <el-card style="margin-bottom:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>数据源管理</span>
          <el-button type="primary" @click="openCreate">新增数据源</el-button>
        </div>
      </template>
      <el-table :data="sources" v-loading="false" size="small" highlight-current-row @row-click="selectSource">
        <el-table-column prop="source_code" label="数据源编码" width="160" />
        <el-table-column prop="source_name_cn" label="名称" width="140" />
        <el-table-column prop="system_code" label="所属系统" width="120" />
        <el-table-column prop="db_type" label="数据库类型" width="100" />
        <el-table-column prop="environment" label="环境" width="70" />
        <el-table-column prop="last_check_status" label="最近检测" width="90">
          <template #default="{ row }">
            <el-tag :type="row.last_check_status === 'connected' ? 'success' : 'info'" size="small">{{ row.last_check_status || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="70">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'danger'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button size="small" text @click="checkSource(row.source_code)">检测</el-button>
            <el-button size="small" text type="primary" :loading="collectingSource === row.source_code" @click.stop="handleCollect(row.source_code)">采集元数据</el-button>
            <el-button size="small" text type="danger" @click.stop="deleteSource(row.source_code)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-bottom:16px">
      <template #header><span>资产树（系统→数据源→Schema→表）</span></template>
      <div v-for="node in tree" :key="node.source_code" style="margin-bottom:16px">
        <h4 style="margin:0 0 8px">{{ node.source_name_cn }} <el-tag size="small">{{ node.system_code }}</el-tag> <span style="color:#909399;font-size:13px">{{ node.table_count }} 张表</span></h4>
        <div v-for="s in node.schemas" :key="s.namespace" style="margin-left:16px;margin-bottom:8px">
          <p style="margin:0;color:#409EFF">{{ s.namespace || '(default)' }} <span style="color:#909399;font-size:12px">({{ s.table_count }} 表)</span></p>
        </div>
      </div>
      <el-empty v-if="tree.length === 0" description="暂无资产树数据" />
    </el-card>

    <el-card v-if="selectedSource">
      <template #header>
        <span>快照记录 - {{ selectedSource.source_name_cn }}</span>
      </template>
      <div v-if="collectResult" style="margin-bottom:12px">
        <el-alert type="success" :closable="false" show-icon>
          <template #title>
            最近采集结果：快照ID #{{ collectResult.snapshot_id }}，{{ collectResult.table_count }} 张表，{{ collectResult.column_count }} 个字段
          </template>
        </el-alert>
      </div>
      <el-table v-loading="snapshotsLoading" :data="snapshots" size="small">
        <el-table-column prop="snapshot_id" label="快照ID" width="100" />
        <el-table-column prop="label" label="标签" width="160" show-overflow-tooltip />
        <el-table-column prop="created_at" label="采集时间" width="180" />
        <el-table-column prop="table_count" label="表数" width="80" />
        <el-table-column prop="column_count" label="字段数" width="80" />
      </el-table>
      <el-empty v-if="!snapshotsLoading && snapshots.length === 0" description="暂无快照记录" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="系统编码" required>
          <el-input v-model="form.system_code" placeholder="如 DATA_CENTER" />
        </el-form-item>
        <el-form-item label="数据源编码" required>
          <el-input v-model="form.source_code" placeholder="如 ods_8_216" />
        </el-form-item>
        <el-form-item label="数据源名称">
          <el-input v-model="form.source_name_cn" />
        </el-form-item>
        <el-form-item label="数据库类型">
          <el-select v-model="form.db_type" clearable style="width:100%">
            <el-option v-for="t in dbTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机">
          <el-input v-model="form.host_masked" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="连接模式">
          <el-select v-model="form.connection_mode" style="width:100%">
            <el-option v-for="m in connModes" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="环境">
          <el-radio-group v-model="form.environment">
            <el-radio value="prod">生产</el-radio>
            <el-radio value="test">测试</el-radio>
            <el-radio value="dev">开发</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSource">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
