const Layout = () => import("@/layout/index.vue");

export default {
  path: "/ops",
  name: "Ops",
  component: Layout,
  redirect: "/ops/tools",
  meta: {
    icon: "ep/setting",
    title: "运维工具",
    rank: 11
  },
  children: [
    {
      path: "/ops/sql-workbench",
      name: "OpsSqlWorkbench",
      component: () => import("@/views/ops/sql-workbench/index.vue"),
      meta: {
        title: "SQL 工作台",
        showLink: true,
        auths: ["ops.sql.view"]
      }
    },
    {
      path: "/ops/tools",
      name: "OpsTools",
      component: () => import("@/views/ops/tools/index.vue"),
      meta: {
        title: "工具模板",
        showLink: true,
        auths: ["ops.tool.manage"]
      }
    },
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
      path: "/ops/audit",
      name: "OpsAudit",
      component: () => import("@/views/ops/audit/index.vue"),
      meta: {
        title: "运维审计",
        showLink: true,
        auths: ["ops.audit.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
