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
      path: "/ops/tools",
      name: "OpsTools",
      component: () => import("@/views/ops/tools/index.vue"),
      meta: {
        title: "工具模板",
        showLink: true
      }
    },
    {
      path: "/ops/runs",
      name: "OpsRuns",
      component: () => import("@/views/ops/runs/index.vue"),
      meta: {
        title: "运维任务",
        showLink: true
      }
    },
    {
      path: "/ops/audit",
      name: "OpsAudit",
      component: () => import("@/views/ops/audit/index.vue"),
      meta: {
        title: "运维审计",
        showLink: true
      }
    }
  ]
} satisfies RouteConfigsTable;
