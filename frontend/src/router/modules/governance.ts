const Layout = () => import("@/layout/index.vue");

export default {
  path: "/governance",
  name: "Governance",
  component: Layout,
  redirect: "/value-domains",
  meta: {
    icon: "ep/setting",
    title: "数据治理",
    rank: 15
  },
  children: [
    {
      // 166 F2：值域管理页（149 §8 方案 B 全量活化）
      path: "/value-domains",
      name: "ValueDomains",
      component: () => import("@/views/asset/value-domains/index.vue"),
      meta: {
        title: "值域知识库",
        showLink: true,
        auths: ["value_domain.read"]
      }
    }
  ]
} satisfies RouteConfigsTable;
