const Layout = () => import("@/layout/index.vue");

// 186 N1：平台运维分区（如何维护平台、追溯操作）。
// 运维执行与业务取数分开；治理配置/AI接入自 asset.ts 移入。
export default {
  path: "/ops",
  name: "Ops",
  component: Layout,
  redirect: "/ops/runs",
  meta: {
    icon: "ep/setting",
    title: "平台运维",
    rank: 60
  },
  children: [
    {
      path: "/ops/runs",
      name: "OpsRuns",
      component: () => import("@/views/ops/runs/index.vue"),
      meta: {
        title: "运维任务",
        showLink: true,
        auths: ["ops.run.view"]
      }
    },
    {
      path: "/ops/sql-workbench",
      name: "OpsSqlWorkbench",
      component: () => import("@/views/ops/sql-workbench/index.vue"),
      meta: {
        title: "受控SQL运维",
        showLink: true,
        auths: ["ops.sql.view"]
      }
    },
    {
      path: "/ops/tools",
      name: "OpsTools",
      component: () => import("@/views/ops/tools/index.vue"),
      meta: {
        title: "运维工具模板",
        showLink: true,
        auths: ["ops.tool.manage"]
      }
    },
    {
      path: "/ops/audit",
      name: "OpsAudit",
      component: () => import("@/views/ops/audit/index.vue"),
      meta: {
        title: "操作审计",
        showLink: true,
        auths: ["ops.audit.view"]
      }
    },
    {
      // 186 N1/O1：治理基础配置自 asset.ts 移入；页内按 owners/terms/tokens/snapshots 分区
      path: "/asset/admin",
      name: "AssetAdmin",
      component: () => import("@/views/asset/admin/index.vue"),
      meta: {
        title: "治理基础配置",
        showLink: true,
        auths: ["asset.admin.view"]
      }
    },
    {
      path: "/asset/ai-tools",
      name: "AssetAiTools",
      component: () => import("@/views/asset/ai-tools/index.vue"),
      meta: {
        title: "AI接入与协作",
        showLink: true,
        auths: ["asset.ai_draft.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
