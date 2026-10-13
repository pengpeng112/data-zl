<script setup lang="ts">
/**
 * 186 W1：日常工作台。
 *
 * 结构：上方（我的待办 + 快捷入口）→ 中间（最近访问 + 常用功能）→
 * 下方（平台运行摘要）。大屏（/welcome）与资产统计（/asset/overview）
 * 是右上辅助入口，本页不重复其图表。
 *
 * 请求预算：首屏最多 2 个业务请求（我的质量任务 mine、运维摘要）；
 * 其余卡片全部本地数据。每卡独立 loading/错误/重试；无权限卡片零请求；
 * 不轮询；未知健康状态不显示「正常」。
 */
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { storageLocal } from "@pureadmin/utils";
import { userKey, type DataInfo } from "@/utils/auth";
import { hasUserPermissions } from "@/utils/permission";
import { getRecentVisits } from "@/utils/menuPreferences";
import { usePermissionStoreHook } from "@/store/modules/permission";
import { listQualityIssues } from "@/api/quality";
import { getOpsRuns } from "@/api/ops";
import RePageHeader from "@/components/RePageHeader/index.vue";

defineOptions({
  name: "Workbench"
});

const router = useRouter();

interface CardState {
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
}

function nowLabel(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes()
  ).padStart(2, "0")}`;
}

const profile = (() => {
  try {
    return storageLocal().getItem<DataInfo<number>>(userKey) ?? null;
  } catch {
    return null;
  }
})();

const can = (codes: string[]) => hasUserPermissions(codes, profile as any);

// ---------------------------------------------------------------------------
// 我的待办（mine 数据范围；无权隐藏 → 零请求）
// ---------------------------------------------------------------------------
const canReadIssue = computed(() => can(["quality.issue.read"]));
const todo = reactive<CardState>({ loading: false, error: null, updatedAt: null });
const todoItems = ref<Array<Record<string, any>>>([]);
const todoTotal = ref<number | null>(null);

async function loadTodo() {
  if (!canReadIssue.value) return;
  todo.loading = true;
  todo.error = null;
  try {
    const res: any = await listQualityIssues({
      scope: "mine",
      page: 1,
      page_size: 5
    });
    const data = res?.data ?? res;
    const items = Array.isArray(data?.items) ? data.items : [];
    // total 必须来自后端；接口未返回真实 total 时显示列表 + 「查看全部」，不推测总数
    todoTotal.value = typeof data?.total === "number" ? data.total : null;
    todoItems.value = items.map((item: any) => ({
      id: item.id,
      title: item.title ?? item.issue_code ?? `问题 #${item.id}`,
      severity: item.severity,
      status: item.status,
      due_date: item.due_date ?? item.target_date,
      overdue: Boolean(item.overdue)
    }));
    todo.updatedAt = nowLabel();
  } catch (exc: any) {
    todo.error = exc?.response?.data?.detail || exc?.message || "加载失败";
  } finally {
    todo.loading = false;
  }
}

// ---------------------------------------------------------------------------
// 平台运行摘要（仅 ops.run.view；用户手动刷新）
// ---------------------------------------------------------------------------
const canViewOps = computed(() => can(["ops.run.view"]));
const ops = reactive<CardState>({ loading: false, error: null, updatedAt: null });
const opsRuns = ref<Array<Record<string, any>>>([]);

async function loadOps() {
  if (!canViewOps.value) return;
  ops.loading = true;
  ops.error = null;
  try {
    const res: any = await getOpsRuns({ page: 1, page_size: 3 });
    const data = res?.data ?? res;
    const items = Array.isArray(data?.items) ? data.items : [];
    opsRuns.value = items.map((item: any) => ({
      id: item.id,
      name: item.name ?? item.title ?? `任务 #${item.id}`,
      status: item.status,
      finished_at: item.finished_at ?? item.updated_at
    }));
    ops.updatedAt = nowLabel();
  } catch (exc: any) {
    ops.error = exc?.response?.data?.detail || exc?.message || "加载失败";
  } finally {
    ops.loading = false;
  }
}

// ---------------------------------------------------------------------------
// 快捷入口与常用功能（权限过滤；含隐藏页的独立权限入口）
// ---------------------------------------------------------------------------
interface QuickLink {
  title: string;
  desc: string;
  path: string;
  perms: string[];
}

const quickLinks = computed<QuickLink[]>(() => {
  const all: QuickLink[] = [
    {
      title: "查找资产",
      desc: "系统 → 表 → 字段 → 关系",
      path: "/asset/systems",
      perms: ["asset.system.view"]
    },
    {
      title: "查询中心",
      desc: "查询 / 指标 / 产品与运行记录",
      path: "/asset/queries",
      perms: ["query.view"]
    },
    {
      title: "我的质量任务",
      desc: "待处理问题与复测",
      path: "/quality/issues/mine",
      perms: ["quality.issue.read"]
    },
    {
      title: "AI辅助编写",
      desc: "按关系生成只读 SQL",
      path: "/asset/ai-sql",
      perms: ["ai.context.read"]
    }
  ];
  return all.filter(link => can(link.perms));
});

// 全部可用功能（含隐藏页独立权限兜底：快照/验证统计/AI上下文等）
const allFeatures = computed(() => {
  const menus = usePermissionStoreHook().wholeMenus || [];
  const leaves: Array<{ title: string; path: string; parent: string }> = [];
  const walk = (nodes: any[], parent: string) => {
    for (const node of nodes ?? []) {
      if (node?.children?.length) {
        walk(node.children, node.meta?.title ?? parent);
      } else if (node?.path && node?.meta?.title) {
        leaves.push({
          title: node.meta.title,
          path: node.path,
          parent: node.meta.parentTitle || parent
        });
      }
    }
  };
  walk(menus, "");
  return leaves.slice(0, 12);
});

// ---------------------------------------------------------------------------
// 最近访问（N2 用户隔离存储；权限变化由读取时求交保证）
// ---------------------------------------------------------------------------
const recentVisits = computed(() => {
  const menus = usePermissionStoreHook().wholeMenus || [];
  const accessible = new Map<string, { title: string; parent: string }>();
  const walk = (nodes: any[], parent: string) => {
    for (const node of nodes ?? []) {
      if (node?.children?.length) {
        walk(node.children, node.meta?.title ?? parent);
      } else if (node?.path && node?.meta?.title) {
        accessible.set(node.path, {
          title: node.meta.title,
          parent: node.meta.parentTitle || parent
        });
      }
    }
  };
  walk(menus, "");
  return getRecentVisits()
    .filter(item => accessible.has(item.path))
    .slice(0, 8)
    .map(item => ({
      path: item.path + (item.querySuffix ?? ""),
      title: accessible.get(item.path)!.title,
      parent: accessible.get(item.path)!.parent
    }));
});

const hasAnyFeature = computed(
  () => quickLinks.value.length > 0 || allFeatures.value.length > 0
);

function go(path: string) {
  router.push(path);
}

onMounted(() => {
  loadTodo();
  loadOps();
});
</script>

<template>
  <div class="workbench px-4 py-3">
    <RePageHeader
      title="日常工作台"
      subtitle="今天要做什么：待办任务、常用入口与平台运行摘要"
    >
      <template #actions>
        <el-button
          v-if="can(['asset.overview.view'])"
          text
          type="primary"
          @click="go('/welcome')"
        >
          运行总览
        </el-button>
        <el-button
          v-if="can(['asset.overview.view'])"
          text
          type="primary"
          @click="go('/asset/overview')"
        >
          资产统计
        </el-button>
      </template>
    </RePageHeader>

    <!-- 无任何业务权限：说明而非空白/循环 -->
    <el-empty
      v-if="!hasAnyFeature"
      description="当前账号暂无业务功能权限，请联系管理员分配后使用"
      :image-size="90"
    />

    <template v-else>
      <!-- 上：我的待办 + 快捷入口 -->
      <el-row :gutter="12" class="mb-3">
        <el-col :xs="24" :sm="24" :md="14">
          <el-card shadow="never" class="h-full">
            <template #header>
              <div class="card-head">
                <span>我的质量任务</span>
                <span v-if="todo.updatedAt" class="muted">更新于 {{ todo.updatedAt }}</span>
              </div>
            </template>
            <div v-if="!canReadIssue" class="muted pad">无质量任务查看权限</div>
            <div v-else v-loading="todo.loading" class="card-body">
              <el-alert
                v-if="todo.error"
                type="error"
                :closable="false"
                :title="todo.error"
              >
                <el-button size="small" text type="primary" @click="loadTodo">
                  重试
                </el-button>
              </el-alert>
              <template v-else-if="todoItems.length">
                <div
                  v-for="item in todoItems"
                  :key="item.id"
                  class="todo-item"
                  @click="go(`/quality/issues/${item.id}`)"
                >
                  <span class="todo-title">
                    {{ item.title }}
                    <el-tag v-if="item.overdue" type="danger" size="small">已逾期</el-tag>
                  </span>
                  <el-tag size="small" :type="item.status === 'open' ? 'warning' : 'info'">
                    {{ item.status }}
                  </el-tag>
                </div>
                <div class="card-foot">
                  <span v-if="todoTotal !== null" class="muted">
                    共 {{ todoTotal }} 条待处理
                  </span>
                  <el-button
                    v-else
                    link
                    type="primary"
                    size="small"
                    @click="go('/quality/issues/mine')"
                  >
                    查看全部
                  </el-button>
                  <el-button
                    v-if="todoTotal !== null"
                    link
                    type="primary"
                    size="small"
                    @click="go('/quality/issues/mine')"
                  >
                    查看全部
                  </el-button>
                </div>
              </template>
              <div v-else-if="!todo.loading" class="muted pad">
                暂无待办任务
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="24" :md="10">
          <el-card shadow="never" class="h-full">
            <template #header><span>快捷入口</span></template>
            <div class="quick-grid">
              <div
                v-for="link in quickLinks"
                :key="link.path"
                class="quick-item"
                @click="go(link.path)"
              >
                <div class="quick-title">{{ link.title }}</div>
                <div class="muted quick-desc">{{ link.desc }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 中：最近访问 + 常用功能（213 UI-07：不等高拉伸） -->
      <el-row :gutter="12" class="mb-3" align="top" style="align-items: flex-start;">
        <el-col :xs="24" :sm="24" :md="12">
          <el-card shadow="never" class="h-full">
            <template #header><span>最近访问</span></template>
            <div v-if="recentVisits.length" class="feature-list">
              <div
                v-for="item in recentVisits"
                :key="item.path"
                class="feature-item"
                @click="go(item.path)"
              >
                <span>{{ item.title }}</span>
                <el-tag size="small" effect="plain" type="info">{{ item.parent }}</el-tag>
              </div>
            </div>
            <div v-else class="muted pad">
              暂无访问记录——首次登录可从下方功能或快捷入口开始
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="24" :md="12">
          <el-card shadow="never" class="h-full">
            <template #header><span>常用功能</span></template>
            <div v-if="allFeatures.length" class="feature-list">
              <div
                v-for="item in allFeatures"
                :key="item.path"
                class="feature-item"
                @click="go(item.path)"
              >
                <span>{{ item.title }}</span>
                <el-tag size="small" effect="plain" type="info">{{ item.parent }}</el-tag>
              </div>
            </div>
            <div v-else class="muted pad">当前账号没有可用的业务功能</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 下：平台运行摘要 -->
      <el-card shadow="never" v-if="canViewOps">
        <template #header>
          <div class="card-head">
            <span>平台运行摘要（最近运维任务）</span>
            <span>
              <span v-if="ops.updatedAt" class="muted mgr8">更新于 {{ ops.updatedAt }}</span>
              <el-button size="small" text type="primary" @click="loadOps">
                刷新
              </el-button>
            </span>
          </div>
        </template>
        <div v-loading="ops.loading" class="card-body">
          <el-alert v-if="ops.error" type="error" :closable="false" :title="ops.error">
            <el-button size="small" text type="primary" @click="loadOps">重试</el-button>
          </el-alert>
          <template v-else-if="opsRuns.length">
            <div v-for="run in opsRuns" :key="run.id" class="todo-item">
              <span class="todo-title">{{ run.name }}</span>
              <el-tag
                size="small"
                :type="
                  run.status === 'success'
                    ? 'success'
                    : run.status === 'failed'
                      ? 'danger'
                      : 'info'
                "
              >
                {{ run.status }}
              </el-tag>
            </div>
          </template>
          <div v-else-if="!ops.loading" class="muted pad">暂无运维任务记录</div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped lang="scss">
.workbench {
  max-width: 1440px;
  margin: 0 auto;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.card-body {
  min-height: 120px;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px;
  cursor: pointer;
  border-bottom: 1px dashed var(--el-border-color-lighter);

  &:last-of-type {
    border-bottom: none;
  }

  .todo-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.quick-item {
  padding: 10px;
  cursor: pointer;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;

  .quick-title {
    font-weight: 600;
  }

  .quick-desc {
    margin-top: 2px;
    font-size: 12px;
  }

  &:hover {
    border-color: var(--el-color-primary-light-5);
  }
}

.feature-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 16px;
}

.feature-item {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  padding: 6px 4px;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;

  span:first-child {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :deep(.el-tag) {
    flex-shrink: 0;
  }

  &:hover {
    background: var(--el-fill-color-light);
  }
}

.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 400;
}

.mgr8 {
  margin-right: 8px;
}

.pad {
  padding: 12px 4px;
}

@media (max-width: 992px) {
  .feature-list,
  .quick-grid {
    grid-template-columns: 1fr;
  }
}
</style>
