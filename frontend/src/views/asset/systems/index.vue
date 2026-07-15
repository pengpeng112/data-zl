<script setup lang="ts">
import RePageHeader from "@/components/RePageHeader/index.vue";
import { ref, onMounted, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  getAssetTree,
  listSystems,
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
  disableSource,
  softDisableSystem,
  type AssetTreeNode,
  type AssetSystemItem,
  type AssetSourceItem,
  type DbTypeMeta
} from "@/api/asset";
import { collectMetadata } from "@/api/metadata";

const route = useRoute();
const activeTab = ref("overview");
const systems = ref<AssetSystemItem[]>([]);
const sources = ref<AssetSourceItem[]>([]);
const resourceTree = ref<AssetTreeNode[]>([]);
const dbTypes = ref<DbTypeMeta[]>([]);
const loading = ref(false);
const sourcesLoading = ref(false);

// wizard
const drawerVisible = ref(false);
const wizardStep = ref(0);
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

// credential rotate dialog
const credDialog = ref(false);
const credTarget = ref<AssetSourceItem | null>(null);
const credRotate = ref({ username: "", password: "" });

// add connection to existing system
const addConnDialog = ref(false);
const addConnSystem = ref("");
const addConnForm = ref(emptyConnection());
const addConnCred = ref({ username: "", password: "" });

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
  try {
    const res = await listSystems();
    // 不再硬编码过滤 HIS/HRP/DATA_CENTER；展示后端返回的非 merged 系统
    systems.value = res.data || [];
  } finally {
    loading.value = false;
  }
}

async function loadSources() {
  sourcesLoading.value = true;
  try {
    // physical connections with aliases folded (plan 76)
    const res = await listConnections({ include_aliases: false });
    sources.value = (res.data || []) as AssetSourceItem[];
  } catch {
    const res = await listSources();
    sources.value = res.data || [];
  } finally {
    sourcesLoading.value = false;
  }
}

async function loadResourceTree() {
  try {
    const res = await getAssetTree({ include_tables: false });
    resourceTree.value = res.data || [];
  } catch {
    resourceTree.value = [];
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
  wizardStep.value = 0;
  form.value = { system_code: "", system_name_cn: "", system_type: "business", target_host: "", description_cn: "", status: "active" };
  connections.value = [];
  connectionForm.value = emptyConnection();
  credForm.value = { username: "", password: "" };
  checkResult.value = "";
  drawerVisible.value = true;
}

function openEdit(row: AssetSystemItem) {
  form.value = {
    system_code: row.system_code,
    system_name_cn: row.system_name_cn,
    system_type: row.system_type || "business",
    target_host: row.target_host || "",
    description_cn: "",
    status: row.status || "active"
  };
  ElMessageBox.confirm("仅更新系统基本信息（不含连接）？", "编辑系统", { type: "info" })
    .then(async () => {
      await upsertSystem(form.value);
      ElMessage.success("已更新");
      loadSystems();
    })
    .catch(() => undefined);
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
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  }
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
    ElMessage.error(e?.response?.data?.detail || "检测失败");
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
    ElMessage.error(e?.response?.data?.detail || "draft 测试失败");
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
    ElMessage.error(e?.response?.data?.detail || "采集失败");
  }
}

function openCredRotate(row: AssetSourceItem) {
  credTarget.value = row;
  credRotate.value = { username: "", password: "" };
  credDialog.value = true;
}

async function saveCredRotate() {
  if (!credTarget.value) return;
  if (!credRotate.value.username || !credRotate.value.password) {
    ElMessage.warning("用户名和密码必填；留空表示取消");
    return;
  }
  try {
    await updateSourceCredential(credTarget.value.source_code, credRotate.value);
    ElMessage.success("凭据已轮换（密码不会回显）");
    credDialog.value = false;
    loadSources();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "凭据写入失败");
  }
}

async function onClearCred(row: AssetSourceItem) {
  try {
    await ElMessageBox.confirm(`清除 ${row.source_code} 的凭据？`, "确认", { type: "warning" });
    await clearSourceCredential(row.source_code);
    ElMessage.success("已清除");
    loadSources();
  } catch {
    /* cancel */
  }
}

async function onDisableSource(row: AssetSourceItem) {
  try {
    await ElMessageBox.confirm(`禁用连接 ${row.source_code}？`, "确认", { type: "warning" });
    await disableSource(row.source_code);
    ElMessage.success("已禁用");
    loadSources();
  } catch {
    /* cancel */
  }
}

async function onSoftDisableSystem(code: string) {
  try {
    await ElMessageBox.confirm(`软停用系统 ${code}？存在连接/资产时不会物理删除。`, "确认", { type: "warning" });
    await softDisableSystem(code);
    ElMessage.success("已软停用");
    loadSystems();
  } catch {
    /* cancel */
  }
}

function openAddConnection(systemCode: string) {
  addConnSystem.value = systemCode;
  addConnForm.value = emptyConnection();
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
    await addSystemConnection(addConnSystem.value, {
      ...c,
      write_policy: "readonly",
      username: addConnCred.value.username || undefined,
      password: addConnCred.value.password || undefined
    });
    ElMessage.success("连接已添加");
    addConnDialog.value = false;
    loadSources();
    loadSystems();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "添加失败");
  }
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
  if (route.query.tab === "connections") activeTab.value = "connections";
  await loadDbTypes();
  await Promise.all([loadSystems(), loadSources(), loadResourceTree()]);
});
</script>

<template>
  <div class="systems-page">
    <RePageHeader
      title="业务系统与数据资源"
      subtitle="唯一入口：系统、数据库连接、Schema/Owner、表与字段。密码只写不回显；业务源库只读。"
    >
      <template #actions>
        <el-button type="primary" @click="openCreate">新增系统与连接</el-button>
      </template>
    </RePageHeader>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="系统总览" name="overview">
        <el-card v-loading="loading" class="systems-card">
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
                    <el-button size="small" text @click="openAddConnection(s.system_code)">加连接</el-button>
                    <el-button size="small" text @click="openEdit(s)">编辑</el-button>
                    <el-button size="small" text type="danger" @click="onSoftDisableSystem(s.system_code)">停用</el-button>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
          <el-empty v-if="!loading && systems.length === 0" description="暂无系统" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="数据库连接" name="connections">
        <el-card v-loading="sourcesLoading" class="systems-card">
          <el-table :data="sources" border stripe>
            <el-table-column prop="system_code" label="系统标签" width="110" />
            <el-table-column prop="source_code" label="连接编码" min-width="140" />
            <el-table-column prop="source_name_cn" label="名称" min-width="120" />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">{{ dbLabel(row.db_type) }}</template>
            </el-table-column>
            <el-table-column label="IP:端口" min-width="140">
              <template #default="{ row }">{{ row.target_host || row.host_masked || '-' }}:{{ row.port || '-' }}</template>
            </el-table-column>
            <el-table-column label="库/Service" min-width="110">
              <template #default="{ row }">{{ row.service_name || row.database_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="别名" width="80">
              <template #default="{ row }">
                <el-tag v-if="(row as any).aliases?.length" size="small">{{ (row as any).aliases.length }}</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="凭据" width="120">
              <template #default="{ row }">
                <el-tag :type="row.credential_configured ? 'success' : 'info'" size="small">
                  {{ credStatusText(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="检测" width="100">
              <template #default="{ row }">{{ (row as any).last_test_status || row.last_check_status || '-' }}</template>
            </el-table-column>
            <el-table-column prop="enabled" label="启用" width="70">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="320" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="onCheck(row.source_code)">测试</el-button>
                <el-button link type="primary" size="small" @click="onCollectMetadata(row.source_code)">采集</el-button>
                <el-button link type="primary" size="small" @click="openCredRotate(row)">轮换凭据</el-button>
                <el-button link type="warning" size="small" @click="onClearCred(row)">清凭据</el-button>
                <el-button link type="danger" size="small" @click="onDisableSource(row)">禁用</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!sourcesLoading && !sources.length" description="暂无连接" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="数据资源树" name="tree">
        <el-card class="systems-card resource-tree-card">
          <template #header>
            <span>系统 → 连接/库 → Schema/Owner → 表 → 字段</span>
          </template>
          <el-collapse>
            <el-collapse-item v-for="node in resourceTree" :key="`${node.source_code}-${node.source_system}`" :name="`${node.source_code}-${node.source_system}`">
              <template #title>
                <strong>{{ node.system_code }}</strong>
                <span class="tree-path">{{ node.source_name_cn }} · {{ node.table_count }} 张表</span>
              </template>
              <el-collapse>
                <el-collapse-item
                  v-for="schema in node.schemas"
                  :key="`${node.source_code}:${schema.namespace}`"
                  :name="`${node.source_code}:${schema.namespace}`"
                >
                  <template #title>
                    {{ schema.namespace || "(default)" }}
                    <el-tag size="small">{{ schema.table_count }} 表</el-tag>
                  </template>
                  <div class="tree-note">表和字段按需加载，进入「表资产」完整检索。</div>
                </el-collapse-item>
              </el-collapse>
            </el-collapse-item>
          </el-collapse>
          <el-empty v-if="!resourceTree.length" description="暂无数据资源" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增系统向导 -->
    <el-drawer v-model="drawerVisible" title="新增系统与连接" size="560px" destroy-on-close>
      <el-steps :active="wizardStep" finish-status="success" align-center class="wizard-steps">
        <el-step title="基本信息" />
        <el-step title="添加连接" />
        <el-step title="凭据" />
        <el-step title="确认保存" />
      </el-steps>

      <div v-show="wizardStep === 0" class="wizard-body">
        <el-form label-width="100px">
          <el-form-item label="系统编码" required>
            <el-input v-model="form.system_code" placeholder="如 HIS / NEW_SYSTEM" />
          </el-form-item>
          <el-form-item label="系统名称" required>
            <el-input v-model="form.system_name_cn" />
          </el-form-item>
          <el-form-item label="类型">
            <el-input v-model="form.system_type" placeholder="business" />
          </el-form-item>
          <el-form-item label="目标地址">
            <el-input v-model="form.target_host" placeholder="系统主 IP，可选" />
          </el-form-item>
          <el-form-item label="说明">
            <el-input v-model="form.description_cn" type="textarea" />
          </el-form-item>
        </el-form>
      </div>

      <div v-show="wizardStep === 1" class="wizard-body">
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
            <el-button type="primary" plain @click="addConnectionToList">加入连接列表</el-button>
            <el-button @click="onTestDraftForm">仅测试（不保存）</el-button>
          </el-space>
          <p v-if="checkResult" class="hint">{{ checkResult }}</p>
          <el-tag v-for="c in connections" :key="c.source_code" class="conn-tag" closable @close="connections = connections.filter(x => x.source_code !== c.source_code)">
            {{ c.source_code }} ({{ dbLabel(c.db_type) }})
          </el-tag>
        </el-form>
      </div>

      <div v-show="wizardStep === 2" class="wizard-body">
        <el-alert type="info" :closable="false" show-icon title="密码只写不回显；编辑时留空表示不轮换。业务源强制只读凭据。" class="mb-12" />
        <el-form label-width="100px">
          <el-form-item label="用户名">
            <el-input v-model="credForm.username" autocomplete="off" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="credForm.password" type="password" show-password autocomplete="new-password" />
          </el-form-item>
          <p class="hint">凭据将写入当前正在编辑的连接表单；先填凭据再「加入连接列表」，或保存后在连接 Tab 轮换。</p>
          <el-button @click="addConnectionToList">将凭据写入当前连接并加入列表</el-button>
        </el-form>
      </div>

      <div v-show="wizardStep === 3" class="wizard-body">
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
        <el-button v-if="wizardStep > 0" @click="wizardStep--">上一步</el-button>
        <el-button v-if="wizardStep < 3" type="primary" @click="wizardStep++">下一步</el-button>
        <el-button v-if="wizardStep === 3" type="primary" @click="saveWizard">保存</el-button>
        <el-button @click="drawerVisible = false">取消</el-button>
      </template>
    </el-drawer>

    <!-- 轮换凭据 -->
    <el-dialog v-model="credDialog" title="轮换凭据（密码不回显）" width="420px">
      <el-form label-width="80px">
        <el-form-item label="连接">{{ credTarget?.source_code }}</el-form-item>
        <el-form-item label="用户名" required>
          <el-input v-model="credRotate.username" autocomplete="off" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="credRotate.password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="credDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCredRotate">写入</el-button>
      </template>
    </el-dialog>

    <!-- 追加连接 -->
    <el-dialog v-model="addConnDialog" :title="`为 ${addConnSystem} 添加连接`" width="520px">
      <el-form label-width="110px">
        <el-form-item label="连接编码" required><el-input v-model="addConnForm.source_code" /></el-form-item>
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
        <el-form-item label="用户名"><el-input v-model="addConnCred.username" autocomplete="off" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="addConnCred.password" type="password" show-password autocomplete="new-password" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addConnDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAddConnection">保存</el-button>
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
</style>
