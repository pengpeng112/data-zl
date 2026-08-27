<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { ref, onMounted, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { extractErrorDetail } from "@/utils/errorMessage";
import {
  getAssetTree,
  listSystems,
  getSystemDetail,
  listSources,
  listConnections,
  listDbTypes,
  createSystemWithConnections,
  upsertSystem,
  addSystemConnection,
  checkSource,
  testSavedConnection,
  testConnectionDraft,
  updateSourceCredential,
  clearSourceCredential,
  patchSource,
  disableSource,
  softDisableSystem,
  type AssetTreeNode,
  type AssetSystemItem,
  type AssetSourceItem,
  type DbTypeMeta
} from "@/api/asset";
import { collectMetadata } from "@/api/metadata";
import {
  buildSystemTypeOptions,
  filterAndPaginateConnections,
  systemDetailToForm,
  validateWizardStep
} from "./contracts";

const route = useRoute();
const router = useRouter();
const activeTab = ref("overview");
const systems = ref<AssetSystemItem[]>([]);
const sources = ref<AssetSourceItem[]>([]);
const resourceTree = ref<AssetTreeNode[]>([]);
const dbTypes = ref<DbTypeMeta[]>([]);
const loading = ref(false);
const sourcesLoading = ref(false);
const systemsError = ref("");
const sourcesError = ref("");
const resourceTreeError = ref("");

// wizard
const drawerVisible = ref(false);
const wizardStep = ref(0);
const editorMode = ref<"create" | "edit">("create");
const editorLoading = ref(false);
const editorSaving = ref(false);
const form = ref({
  system_code: "",
  system_name_cn: "",
  system_type: "business",
  target_host: "",
  description_cn: "",
  status: "active"
});
const connectionForm = ref(emptyConnection());
const connections = ref<ReturnType<typeof emptyConnection>[]>([]);
const credForm = ref({ username: "", password: "" });
const checkResult = ref<string>("");

// credential rotate dialog (readonly | write)
const credDialog = ref(false);
const credTarget = ref<AssetSourceItem | null>(null);
const credRotate = ref({
  username: "",
  password: "",
  purpose: "readonly" as "readonly" | "write",
  write_policy: "medical_dict_push"
});

// add connection to existing system
const addConnDialog = ref(false);
const addConnSystem = ref("");
const addConnForm = ref(emptyConnection());
const addConnCred = ref({ username: "", password: "" });
const connectionEditMode = ref(false);
const connectionFilters = ref({ system_code: "", db_type: "" });
const connectionPage = ref(1);
const connectionPageSize = ref(20);

function emptyConnection() {
  return {
    source_code: "",
    source_name_cn: "",
    db_type: "oracle",
    target_host: "",
    port: 1521 as number | null,
    service_mode: "service_name",
    service_name: "",
    database_name: "",
    default_schema: "",
    environment: "prod",
    connection_mode: "direct",
    collect_mode: "metadata_only",
    write_policy: "readonly",
    username: "",
    password: ""
  };
}

const selectedDbMeta = computed(() =>
  dbTypes.value.find(d => d.db_type === connectionForm.value.db_type)
);

const systemTypeOptions = computed(() =>
  buildSystemTypeOptions(systems.value, form.value.system_type)
);
const pagedConnections = computed(() =>
  filterAndPaginateConnections(
    sources.value,
    connectionFilters.value,
    connectionPage.value,
    connectionPageSize.value
  )
);

watch(connectionFilters, () => {
  connectionPage.value = 1;
}, { deep: true });

watch(activeTab, tab => {
  const query = { ...route.query };
  if (tab === "overview") delete query.tab;
  else query.tab = tab;
  void router.replace({ query });
});

watch(
  () => connectionForm.value.db_type,
  code => {
    const meta = dbTypes.value.find(d => d.db_type === code);
    if (meta) {
      connectionForm.value.port = meta.default_port;
      connectionForm.value.service_mode = meta.service_modes[0] || "database";
    }
  }
);

async function loadSystems() {
  loading.value = true;
  systemsError.value = "";
  try {
    const res = await listSystems();
    // 不再硬编码过滤 HIS/HRP/DATA_CENTER；展示后端返回的非 merged 系统
    systems.value = res.data || [];
  } catch (error: any) {
    systemsError.value = error?.response?.data?.detail || "系统列表加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadSources() {
  sourcesLoading.value = true;
  sourcesError.value = "";
  try {
    // physical connections with aliases folded (plan 76)
    const res = await listConnections({ include_aliases: false });
    sources.value = (res.data || []) as AssetSourceItem[];
  } catch {
    try {
      const res = await listSources();
      sources.value = res.data || [];
    } catch (error: any) {
      sources.value = [];
      sourcesError.value = error?.response?.data?.detail || "数据连接加载失败";
    }
  } finally {
    sourcesLoading.value = false;
  }
}

async function loadResourceTree() {
  resourceTreeError.value = "";
  try {
    const res = await getAssetTree({ include_tables: false });
    resourceTree.value = res.data || [];
  } catch (error: any) {
    resourceTree.value = [];
    resourceTreeError.value = error?.response?.data?.detail || "数据资源树加载失败";
  }
}

async function loadDbTypes() {
  try {
    const res = await listDbTypes();
    dbTypes.value = res.data || [];
  } catch {
    dbTypes.value = [
      { db_type: "oracle", label: "Oracle", default_port: 1521, service_modes: ["service_name", "sid"], requires_database_name: false, requires_service_or_sid: true },
      { db_type: "mysql", label: "MySQL", default_port: 3306, service_modes: ["database"], requires_database_name: true, requires_service_or_sid: false },
      { db_type: "sqlserver", label: "SQL Server", default_port: 1433, service_modes: ["database"], requires_database_name: true, requires_service_or_sid: false },
      { db_type: "vastbase", label: "海量数据库（Vastbase）", default_port: 5432, service_modes: ["database"], requires_database_name: true, requires_service_or_sid: false },
      { db_type: "postgresql", label: "PostgreSQL", default_port: 5432, service_modes: ["database"], requires_database_name: true, requires_service_or_sid: false }
    ];
  }
}

function openCreate() {
  editorMode.value = "create";
  wizardStep.value = 0;
  form.value = { system_code: "", system_name_cn: "", system_type: "business", target_host: "", description_cn: "", status: "active" };
  connections.value = [];
  connectionForm.value = emptyConnection();
  credForm.value = { username: "", password: "" };
  checkResult.value = "";
  drawerVisible.value = true;
}

async function openEdit(row: AssetSystemItem) {
  editorMode.value = "edit";
  wizardStep.value = 0;
  drawerVisible.value = true;
  editorLoading.value = true;
  try {
    const res = await getSystemDetail(row.system_code);
    form.value = systemDetailToForm(res.data);
  } catch (error: any) {
    drawerVisible.value = false;
    ElMessage.error(extractErrorDetail(error, "系统详情加载失败，未进入编辑"));
  } finally {
    editorLoading.value = false;
  }
}

async function saveSystemEdit() {
  const error = validateWizardStep(0, form.value, []);
  if (error) {
    ElMessage.warning(error);
    return;
  }
  editorSaving.value = true;
  try {
    await upsertSystem({ ...form.value });
    ElMessage.success("系统信息已更新");
    drawerVisible.value = false;
    await Promise.all([loadSystems(), loadResourceTree()]);
  } catch (error: any) {
    ElMessage.error(extractErrorDetail(error, "系统更新失败"));
  } finally {
    editorSaving.value = false;
  }
}

function nextWizardStep() {
  const error = validateWizardStep(wizardStep.value, form.value, connections.value);
  if (error) {
    ElMessage.warning(error);
    return;
  }
  wizardStep.value += 1;
}

function addConnectionToList() {
  const c = { ...connectionForm.value };
  if (!c.source_code || !c.source_name_cn || !c.target_host) {
    ElMessage.warning("请填写连接编码、名称和目标地址");
    return;
  }
  if (credForm.value.username) {
    c.username = credForm.value.username;
    c.password = credForm.value.password;
  }
  connections.value.push(c);
  connectionForm.value = emptyConnection();
  credForm.value = { username: "", password: "" };
  ElMessage.success("已加入连接列表");
}

async function saveWizard() {
  if (!form.value.system_code || !form.value.system_name_cn) {
    ElMessage.warning("系统编码和名称为必填");
    return;
  }
  try {
    const payload = {
      ...form.value,
      connections: connections.value.map(c => ({
        source_code: c.source_code,
        source_name_cn: c.source_name_cn,
        db_type: c.db_type,
        target_host: c.target_host,
        port: c.port,
        service_mode: c.service_mode,
        service_name: c.service_name || null,
        database_name: c.database_name || null,
        default_schema: c.default_schema || null,
        environment: c.environment,
        connection_mode: c.connection_mode,
        collect_mode: c.collect_mode,
        write_policy: "readonly",
        username: c.username || undefined,
        password: c.password || undefined
      }))
    };
    await createSystemWithConnections(payload);
    ElMessage.success("系统与连接已保存");
    drawerVisible.value = false;
    await Promise.all([loadSystems(), loadSources(), loadResourceTree()]);
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "保存失败"));
  }
}

function connectionStatusLabel(status?: string | null) {
  const labels: Record<string, string> = {
    connected: "已连通",
    success: "成功",
    failed: "失败",
    timeout: "超时",
    pending: "待检测"
  };
  return status ? labels[status.toLowerCase()] || status : "未检测";
}

async function onCheck(sourceCode: string) {
  try {
    const row = sources.value.find(s => s.source_code === sourceCode);
    if (row?.id) {
      const res = await testSavedConnection(row.id);
      const d = res.data || {};
      ElMessage[d.success ? "success" : "warning"](
        `${sourceCode}: ${d.success ? "connected" : d.error_masked || "failed"} (${d.latency_ms || 0}ms)`
      );
    } else {
      const res = await checkSource(sourceCode);
      const d = res.data || {};
      ElMessage[d.status === "connected" ? "success" : "warning"](
        `${sourceCode}: ${d.status} ${d.message || ""} (${d.elapsed_ms || 0}ms)`
      );
    }
    loadSources();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "检测失败"));
  }
}

async function onTestDraftForm() {
  try {
    const res = await testConnectionDraft({
      db_type: connectionForm.value.db_type,
      target_host: connectionForm.value.target_host,
      port: connectionForm.value.port,
      service_mode: connectionForm.value.service_mode,
      service_name: connectionForm.value.service_name,
      database_name: connectionForm.value.database_name,
      username: credForm.value.username || undefined,
      password: credForm.value.password || undefined
    });
    const d = res.data || {};
    checkResult.value = d.success ? `连通成功 ${d.latency_ms}ms` : `失败: ${d.error_masked}`;
    ElMessage[d.success ? "success" : "warning"](checkResult.value);
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "draft 测试失败"));
  }
}

async function onCollectMetadata(sourceCode: string) {
  try {
    await ElMessageBox.confirm(
      `对 ${sourceCode} 触发只读元数据采集？不会写入业务源库。`,
      "采集元数据",
      { type: "info" }
    );
    const res = await collectMetadata(sourceCode, { mode: "live_source", label: `manual-${sourceCode}` });
    ElMessage.success(`采集已触发：${JSON.stringify(res.data || {}).slice(0, 120)}`);
  } catch (e: any) {
    if (e === "cancel" || e === "close") return;
    ElMessage.error(extractErrorDetail(e, "采集失败"));
  }
}

function openCredRotate(row: AssetSourceItem, purpose: "readonly" | "write" = "readonly") {
  credTarget.value = row;
  credRotate.value = {
    username: "",
    password: "",
    purpose,
    write_policy: row.write_policy === "platform_controlled" ? "platform_controlled" : "medical_dict_push"
  };
  credDialog.value = true;
}

async function saveCredRotate() {
  if (!credTarget.value) return;
  if (!credRotate.value.username || !credRotate.value.password) {
    ElMessage.warning("用户名和密码必填");
    return;
  }
  try {
    const payload: {
      username: string;
      password: string;
      purpose: "readonly" | "write";
      write_policy?: string;
    } = {
      username: credRotate.value.username,
      password: credRotate.value.password,
      purpose: credRotate.value.purpose
    };
    if (credRotate.value.purpose === "write") {
      payload.write_policy = credRotate.value.write_policy;
    }
    await updateSourceCredential(credTarget.value.source_code, payload);
    ElMessage.success(
      credRotate.value.purpose === "write"
        ? "写凭据已保存（密码不回显）；字典下发可用 medical_dict_push"
        : "只读凭据已轮换（密码不会回显）"
    );
    credDialog.value = false;
    loadSources();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "凭据写入失败"));
  }
}

async function onClearCred(row: AssetSourceItem, purpose: "readonly" | "write" = "readonly") {
  try {
    await ElMessageBox.confirm(
      purpose === "write"
        ? `清除 ${row.source_code} 的写凭据？将回落 write_policy=readonly。`
        : `清除 ${row.source_code} 的只读凭据？`,
      "确认",
      { type: "warning" }
    );
  } catch {
    return; // 用户取消
  }
  try {
    await clearSourceCredential(row.source_code, { purpose });
    ElMessage.success("已清除");
    loadSources();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "清除凭据失败"));
  }
}

async function onSetWritePolicy(row: AssetSourceItem, policy: string) {
  try {
    await patchSource(row.source_code, { write_policy: policy });
    ElMessage.success(`写策略已设为 ${policy}`);
    loadSources();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "更新写策略失败"));
  }
}

function writePolicyLabel(policy?: string | null) {
  if (policy === "medical_dict_push") return "字典下发写";
  if (policy === "platform_controlled") return "平台写";
  return "只读";
}

async function onDisableSource(row: AssetSourceItem) {
  try {
    await ElMessageBox.confirm(`禁用连接 ${row.source_code}？`, "确认", { type: "warning" });
  } catch {
    return; // 用户取消
  }
  try {
    await disableSource(row.source_code);
    ElMessage.success("已禁用");
    loadSources();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "禁用连接失败"));
  }
}

async function onSoftDisableSystem(code: string) {
  try {
    await ElMessageBox.confirm(`软停用系统 ${code}？存在连接/资产时不会物理删除。`, "确认", { type: "warning" });
  } catch {
    return; // 用户取消
  }
  try {
    await softDisableSystem(code);
    ElMessage.success("已软停用");
    loadSystems();
  } catch (error) {
    ElMessage.error(extractErrorDetail(error, "软停用系统失败"));
  }
}

function openAddConnection(systemCode: string) {
  connectionEditMode.value = false;
  addConnSystem.value = systemCode;
  addConnForm.value = emptyConnection();
  addConnCred.value = { username: "", password: "" };
  addConnDialog.value = true;
}

function openEditConnection(row: AssetSourceItem) {
  connectionEditMode.value = true;
  addConnSystem.value = row.system_code;
  addConnForm.value = { ...emptyConnection(), ...row };
  addConnCred.value = { username: "", password: "" };
  addConnDialog.value = true;
}

async function saveAddConnection() {
  const c = addConnForm.value;
  if (!c.source_code || !c.target_host) {
    ElMessage.warning("连接编码和目标地址必填");
    return;
  }
  try {
    if (connectionEditMode.value) {
      await patchSource(c.source_code, {
        source_name_cn: c.source_name_cn,
        db_type: c.db_type,
        target_host: c.target_host,
        port: c.port,
        service_mode: c.service_mode,
        service_name: c.service_name || null,
        database_name: c.database_name || null,
        default_schema: c.default_schema || null,
        environment: c.environment,
        connection_mode: c.connection_mode,
        collect_mode: c.collect_mode
      });
      ElMessage.success("连接信息已更新");
    } else {
      await addSystemConnection(addConnSystem.value, {
        ...c,
        write_policy: "readonly",
        username: addConnCred.value.username || undefined,
        password: addConnCred.value.password || undefined
      });
      ElMessage.success("连接已添加");
    }
    addConnDialog.value = false;
    loadSources();
    loadSystems();
  } catch (e: any) {
    ElMessage.error(extractErrorDetail(e, "添加失败"));
  }
}

function handleSourceMore(row: AssetSourceItem, command: string) {
  if (command === "readonly_credential") return openCredRotate(row, "readonly");
  if (command === "write_credential") return openCredRotate(row, "write");
  if (command === "policy_readonly") return onSetWritePolicy(row, "readonly");
  if (command === "policy_medical") return onSetWritePolicy(row, "medical_dict_push");
  if (command === "clear_readonly") return onClearCred(row, "readonly");
  if (command === "clear_write") return onClearCred(row, "write");
  if (command === "disable") return onDisableSource(row);
}

function openSchemaTables(sourceCode: string, namespace: string) {
  void router.push({ path: "/asset/tables", query: { source_code: sourceCode, schema: namespace } });
}

function dbLabel(code?: string | null) {
  if (!code) return "-";
  if (code === "vastbase") return "海量数据库（Vastbase）";
  return dbTypes.value.find(d => d.db_type === code)?.label || code;
}

function credStatusText(row: AssetSourceItem) {
  if (row.credential_configured || row.credential_status === "configured") {
    return row.credential_username_masked ? `已配置 (${row.credential_username_masked})` : "已配置";
  }
  return "未配置";
}

onMounted(async () => {
  if (["connections", "tree"].includes(String(route.query.tab || ""))) {
    activeTab.value = String(route.query.tab);
  }
  await loadDbTypes();
  await Promise.all([loadSystems(), loadSources(), loadResourceTree()]);
});
</script>

<template>
  <div class="systems-page">
    <RePageHeader
      title="业务系统与数据资源"
      subtitle="系统、连接、Schema/表。只读凭据与写凭据分离；密码只写不回显。字典下发请配置 write 策略与写账号。"
    >
      <template #actions>
        <el-button v-perms="'source.manage'" type="primary" @click="openCreate">新增系统与连接</el-button>
      </template>
    </RePageHeader>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="系统总览" name="overview">
        <el-card v-loading="loading" class="systems-card">
          <el-alert v-if="systemsError" type="error" :closable="false" show-icon class="mb-12" :title="systemsError">
            <template #default><el-button size="small" @click="loadSystems">重试</el-button></template>
          </el-alert>
          <el-row :gutter="16">
            <el-col v-for="s in systems" :key="s.id" :xs="24" :sm="12" :lg="8">
              <el-card shadow="hover" class="system-tile">
                <div class="system-tile-main">
                  <div>
                    <h4 class="system-title">{{ s.system_name_cn }}</h4>
                    <p class="system-code">{{ s.system_code }}</p>
                    <el-tag v-if="s.system_type" size="small">{{ s.system_type }}</el-tag>
                    <el-tag :type="s.status === 'active' ? 'success' : 'info'" size="small" class="status-tag">
                      {{ s.status === 'active' ? '启用' : s.status }}
                    </el-tag>
                    <p class="meta-line">
                      连接 {{ s.connection_count ?? 0 }} · 表 {{ s.table_count ?? 0 }}
                      <span v-if="s.target_host"> · {{ s.target_host }}</span>
                    </p>
                  </div>
                  <div class="tile-actions">
                    <el-button v-perms="'source.manage'" size="small" text @click="openAddConnection(s.system_code)">加连接</el-button>
                    <el-button v-perms="'source.manage'" size="small" text @click="openEdit(s)">编辑</el-button>
                    <el-button v-perms="'source.manage'" size="small" text type="danger" @click="onSoftDisableSystem(s.system_code)">停用</el-button>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
          <el-empty v-if="!loading && systems.length === 0" description="暂无系统" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="数据连接" name="connections">
        <el-card v-loading="sourcesLoading" class="systems-card">
          <el-alert v-if="sourcesError" type="error" :closable="false" show-icon class="mb-12" :title="sourcesError">
            <template #default><el-button size="small" @click="loadSources">重试</el-button></template>
          </el-alert>
          <el-alert
            class="mb-12"
            type="info"
            :closable="false"
            show-icon
            title="只读凭据用于探库/对账；写凭据用于诊断手术字典下发（medical_dict_push）。密码不回显、不进 Git。HIS/海量请分别配置写账号后，再到字典中心做 dry-run/apply。"
          />
          <div class="connection-filters">
            <el-select v-model="connectionFilters.system_code" clearable placeholder="筛选业务系统" style="width: 190px">
              <el-option v-for="system in systems" :key="system.system_code" :label="system.system_name_cn" :value="system.system_code" />
            </el-select>
            <el-select v-model="connectionFilters.db_type" clearable placeholder="筛选数据库类型" style="width: 180px">
              <el-option v-for="db in dbTypes" :key="db.db_type" :label="db.label" :value="db.db_type" />
            </el-select>
          </div>
          <el-table :data="pagedConnections.items" border stripe>
            <el-table-column label="业务系统" width="150">
              <template #default="{ row }">
                <span>{{ systems.find(s => s.system_code === row.system_code)?.system_name_cn || row.system_code || '-' }}</span>
                <small v-if="row.system_code" class="system-code-inline">{{ row.system_code }}</small>
              </template>
            </el-table-column>
            <el-table-column prop="source_code" label="连接编码" min-width="140" />
            <el-table-column prop="source_name_cn" label="连接名称" min-width="120" />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">{{ dbLabel(row.db_type) }}</template>
            </el-table-column>
            <el-table-column label="IP:端口" min-width="140">
              <template #default="{ row }">{{ row.target_host || row.host_masked || '-' }}:{{ row.port || '-' }}</template>
            </el-table-column>
            <el-table-column label="库/Service" min-width="110">
              <template #default="{ row }">{{ row.service_name || row.database_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="写策略" width="110">
              <template #default="{ row }">
                <el-tag
                  :type="row.write_policy === 'medical_dict_push' ? 'warning' : row.write_policy === 'platform_controlled' ? 'danger' : 'info'"
                  size="small"
                >
                  {{ writePolicyLabel(row.write_policy) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="只读凭据" width="120">
              <template #default="{ row }">
                <el-tag :type="row.credential_configured ? 'success' : 'info'" size="small">
                  {{ credStatusText(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="写凭据" width="120">
              <template #default="{ row }">
                <el-tag :type="row.write_credential_configured ? 'warning' : 'info'" size="small">
                  {{
                    row.write_credential_configured
                      ? row.write_username_masked
                        ? `已配置 (${row.write_username_masked})`
                        : "已配置"
                      : "未配置"
                  }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="检测" width="100">
              <template #default="{ row }">{{ connectionStatusLabel(row.last_test_status || row.last_check_status) }}</template>
            </el-table-column>
            <el-table-column prop="enabled" label="启用" width="70">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="250" fixed="right">
              <template #default="{ row }">
                <el-button v-perms="'source.test'" link type="primary" size="small" @click="onCheck(row.source_code)">测试</el-button>
                <el-button v-perms="'source.collect'" link type="primary" size="small" @click="onCollectMetadata(row.source_code)">采集</el-button>
                <el-button v-perms="'source.manage'" link type="primary" size="small" @click="openEditConnection(row)">编辑</el-button>
                <el-dropdown trigger="click" @command="(cmd: string) => handleSourceMore(row, cmd)">
                  <el-button link type="primary" size="small">更多</el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-perms="'source.credential_manage'" command="readonly_credential">只读凭据</el-dropdown-item>
                      <el-dropdown-item v-perms="'source.credential_manage'" command="write_credential">写凭据</el-dropdown-item>
                      <el-dropdown-item v-perms="'source.manage'" command="policy_readonly">写策略：只读</el-dropdown-item>
                      <el-dropdown-item v-perms="'source.manage'" command="policy_medical">写策略：字典下发</el-dropdown-item>
                      <el-dropdown-item v-perms="'source.credential_manage'" command="clear_readonly">清除只读凭据</el-dropdown-item>
                      <el-dropdown-item v-perms="'source.credential_manage'" command="clear_write">清除写凭据</el-dropdown-item>
                      <el-dropdown-item v-perms="'source.manage'" command="disable" divided>禁用连接</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            v-if="pagedConnections.total"
            v-model:current-page="connectionPage"
            v-model:page-size="connectionPageSize"
            :total="pagedConnections.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            class="connection-pagination"
          />
          <el-empty v-if="!sourcesLoading && !sourcesError && !pagedConnections.total" description="当前筛选下暂无连接" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="数据资源树" name="tree">
        <el-card class="systems-card resource-tree-card">
          <template #header>
            <span>业务系统 → 数据连接 → Schema/Owner → 表 → 字段</span>
          </template>
          <el-alert v-if="resourceTreeError" type="error" :closable="false" show-icon class="mb-12" :title="resourceTreeError">
            <template #default><el-button size="small" @click="loadResourceTree">重试</el-button></template>
          </el-alert>
          <el-collapse>
            <el-collapse-item v-for="node in resourceTree" :key="`${node.source_code}-${node.source_system}`" :name="`${node.source_code}-${node.source_system}`">
              <template #title>
                <strong>{{ node.system_name_cn || node.system_code }}</strong>
                <span class="tree-path">{{ node.source_name_cn }} · {{ node.table_count }} 张表</span>
              </template>
              <el-collapse>
                <el-collapse-item
                  v-for="schema in node.schemas"
                  :key="`${node.source_code}:${schema.namespace}`"
                  :name="`${node.source_code}:${schema.namespace}`"
                >
                  <template #title>
                    {{ schema.namespace_name_cn ? `${schema.namespace_name_cn}（${schema.namespace}）` : (schema.namespace || "默认Owner") }}
                    <el-tag size="small">{{ schema.table_count }} 表</el-tag>
                  </template>
                  <div class="tree-note">表和字段按需加载，进入「表资产」完整检索。</div>
                  <el-button size="small" link type="primary" @click="openSchemaTables(node.source_code, schema.namespace)">查看该 Schema 的表</el-button>
                </el-collapse-item>
              </el-collapse>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-if="!resourceTree.length" description="暂无数据资源" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增系统向导 -->
    <el-drawer v-model="drawerVisible" :title="editorMode === 'create' ? '新增系统与连接' : '编辑系统'" size="560px" destroy-on-close>
      <el-steps v-if="editorMode === 'create'" :active="wizardStep" finish-status="success" align-center class="wizard-steps">
        <el-step title="基本信息" />
        <el-step title="添加连接" />
        <el-step title="凭据" />
        <el-step title="确认保存" />
      </el-steps>

      <div v-loading="editorLoading" v-show="editorMode === 'edit' || wizardStep === 0" class="wizard-body">
        <el-form label-width="100px">
          <el-form-item label="系统编码" required>
            <el-input v-model="form.system_code" placeholder="如 HIS / NEW_SYSTEM" />
          </el-form-item>
          <el-form-item label="系统名称" required>
            <el-input v-model="form.system_name_cn" />
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="form.system_type" filterable allow-create class="full-width" placeholder="选择或保留原系统类型">
              <el-option v-for="option in systemTypeOptions" :key="option" :label="option" :value="option" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标地址">
            <el-input v-model="form.target_host" placeholder="系统主 IP，可选" />
          </el-form-item>
          <el-form-item label="说明">
            <el-input v-model="form.description_cn" type="textarea" />
          </el-form-item>
        </el-form>
      </div>

      <div v-if="editorMode === 'create'" v-show="wizardStep === 1" class="wizard-body">
        <el-form label-width="110px">
          <el-form-item label="连接编码" required>
            <el-input v-model="connectionForm.source_code" />
          </el-form-item>
          <el-form-item label="连接名称" required>
            <el-input v-model="connectionForm.source_name_cn" />
          </el-form-item>
          <el-form-item label="数据库类型" required>
            <el-select v-model="connectionForm.db_type" class="full-width">
              <el-option v-for="d in dbTypes" :key="d.db_type" :label="d.label" :value="d.db_type" />
            </el-select>
          </el-form-item>
          <el-form-item label="主机" required>
            <el-input v-model="connectionForm.target_host" placeholder="真实数据库 IP" />
          </el-form-item>
          <el-form-item label="端口" required>
            <el-input-number v-model="connectionForm.port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item v-if="connectionForm.db_type === 'oracle'" label="Service 模式">
            <el-select v-model="connectionForm.service_mode" class="full-width">
              <el-option label="Service Name" value="service_name" />
              <el-option label="SID" value="sid" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="connectionForm.db_type === 'oracle'" label="Service/SID">
            <el-input v-model="connectionForm.service_name" />
          </el-form-item>
          <el-form-item v-if="connectionForm.db_type !== 'oracle'" label="Database" required>
            <el-input v-model="connectionForm.database_name" />
          </el-form-item>
          <el-form-item v-if="['postgresql','vastbase','mysql','sqlserver'].includes(connectionForm.db_type)" label="默认 Schema">
            <el-input v-model="connectionForm.default_schema" />
          </el-form-item>
          <el-space>
            <el-button v-perms="'source.manage'" type="primary" plain @click="addConnectionToList">加入连接列表</el-button>
            <el-button v-perms="'source.test'" @click="onTestDraftForm">仅测试（不保存）</el-button>
          </el-space>
          <p v-if="checkResult" class="hint">{{ checkResult }}</p>
          <el-tag v-for="c in connections" :key="c.source_code" class="conn-tag" closable @close="connections = connections.filter(x => x.source_code !== c.source_code)">
            {{ c.source_code }} ({{ dbLabel(c.db_type) }})
          </el-tag>
        </el-form>
      </div>

      <div v-if="editorMode === 'create'" v-show="wizardStep === 2" class="wizard-body">
        <el-alert type="info" :closable="false" show-icon title="密码只写不回显；编辑时留空表示不轮换。业务源强制只读凭据。" class="mb-12" />
        <el-form label-width="100px">
          <el-form-item label="用户名">
            <el-input v-model="credForm.username" autocomplete="off" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="credForm.password" type="password" show-password autocomplete="new-password" />
          </el-form-item>
          <p class="hint">凭据将写入当前正在编辑的连接表单；先填凭据再「加入连接列表」，或保存后在连接 Tab 轮换。</p>
          <el-button v-perms="'source.manage'" @click="addConnectionToList">将凭据写入当前连接并加入列表</el-button>
        </el-form>
      </div>

      <div v-if="editorMode === 'create'" v-show="wizardStep === 3" class="wizard-body">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="系统">{{ form.system_code }} / {{ form.system_name_cn }}</el-descriptions-item>
          <el-descriptions-item label="连接数">{{ connections.length }}</el-descriptions-item>
          <el-descriptions-item label="连接">
            <div v-for="c in connections" :key="c.source_code">
              {{ c.source_code }} · {{ dbLabel(c.db_type) }} · {{ c.target_host }}:{{ c.port }}
              · 凭据 {{ c.username ? '将写入' : '未填' }}
            </div>
          </el-descriptions-item>
        </el-descriptions>
        <el-alert class="mt-12" type="warning" :closable="false" title="业务源库只读；连通检测在保存后于连接 Tab 执行。" />
      </div>

      <template #footer>
        <el-button v-if="editorMode === 'create' && wizardStep > 0" @click="wizardStep--">上一步</el-button>
        <el-button v-if="editorMode === 'create' && wizardStep < 3" type="primary" @click="nextWizardStep">下一步</el-button>
        <el-button v-if="editorMode === 'create' && wizardStep === 3" v-perms="'source.manage'" type="primary" @click="saveWizard">保存</el-button>
        <el-button v-if="editorMode === 'edit'" v-perms="'source.manage'" type="primary" :loading="editorSaving" @click="saveSystemEdit">保存修改</el-button>
        <el-button @click="drawerVisible = false">取消</el-button>
      </template>
    </el-drawer>

    <!-- 轮换凭据（只读 / 写） -->
    <el-dialog
      v-model="credDialog"
      :title="credRotate.purpose === 'write' ? '配置写凭据（字典下发，密码不回显）' : '轮换只读凭据（密码不回显）'"
      width="480px"
    >
      <el-alert
        v-if="credRotate.purpose === 'write'"
        type="warning"
        :closable="false"
        show-icon
        class="mb-12"
        title="写账号与只读账号分离。默认策略 medical_dict_push：仅允许字典单行新增/停用。密码只保存到服务器凭据文件。"
      />
      <el-form label-width="100px">
        <el-form-item label="连接">{{ credTarget?.source_code }}</el-form-item>
        <el-form-item v-if="credRotate.purpose === 'write'" label="写策略">
          <el-select v-model="credRotate.write_policy" class="full-width">
            <el-option label="字典下发写 medical_dict_push" value="medical_dict_push" />
            <el-option
              v-if="(credTarget?.system_code || '').toUpperCase() === 'ASSET_PLATFORM'"
              label="平台写 platform_controlled"
              value="platform_controlled"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名" required>
          <el-input v-model="credRotate.username" autocomplete="off" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="credRotate.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="credDialog = false">取消</el-button>
        <el-button v-perms="'source.credential_manage'" type="primary" @click="saveCredRotate">写入</el-button>
      </template>
    </el-dialog>

    <!-- 追加连接 -->
    <el-dialog v-model="addConnDialog" :title="connectionEditMode ? `编辑连接 ${addConnForm.source_code}` : `为 ${addConnSystem} 添加连接`" width="520px">
      <el-form label-width="110px">
        <el-form-item label="连接编码" required><el-input v-model="addConnForm.source_code" :disabled="connectionEditMode" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="addConnForm.source_name_cn" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="addConnForm.db_type" class="full-width">
            <el-option v-for="d in dbTypes" :key="d.db_type" :label="d.label" :value="d.db_type" />
          </el-select>
        </el-form-item>
        <el-form-item label="主机" required><el-input v-model="addConnForm.target_host" /></el-form-item>
        <el-form-item label="端口"><el-input-number v-model="addConnForm.port" :min="1" :max="65535" /></el-form-item>
        <el-form-item v-if="addConnForm.db_type === 'oracle'" label="Service/SID">
          <el-input v-model="addConnForm.service_name" />
        </el-form-item>
        <el-form-item v-else label="Database"><el-input v-model="addConnForm.database_name" /></el-form-item>
        <template v-if="!connectionEditMode">
          <el-form-item label="用户名"><el-input v-model="addConnCred.username" autocomplete="off" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="addConnCred.password" type="password" show-password autocomplete="new-password" /></el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="addConnDialog = false">取消</el-button>
        <el-button v-perms="'source.manage'" type="primary" @click="saveAddConnection">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.systems-page { padding: 4px; }
.systems-card {
  border-color: var(--border-light);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-sm);
  margin-bottom: 12px;
}
.connection-filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.connection-pagination {
  justify-content: flex-end;
  margin-top: 12px;
}
.system-tile :deep(.el-card__body) { padding: 16px; }
.system-tile-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.system-title { margin: 0 0 8px; font-size: 15px; color: var(--text-primary); }
.system-code { margin: 0 0 4px; font-size: 13px; color: var(--text-secondary); }
.meta-line { margin: 8px 0 0; font-size: 12px; color: var(--text-secondary); }
.status-tag { margin-left: 4px; }
.tile-actions { display: flex; flex-direction: column; align-items: flex-end; }
.tree-path { margin-left: 12px; color: var(--text-secondary); }
.tree-note { color: var(--text-secondary); font-size: 13px; }
.full-width { width: 100%; }
.wizard-steps { margin-bottom: 20px; }
.wizard-body { min-height: 280px; }
.conn-tag { margin: 8px 8px 0 0; }
.mb-12 { margin-bottom: 12px; }
.mt-12 { margin-top: 12px; }
.hint { font-size: 12px; color: var(--text-secondary); }
.system-code-inline { display: block; color: var(--text-secondary); font-size: 11px; }
</style>
