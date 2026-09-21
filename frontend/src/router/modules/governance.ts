const Layout = () => import("@/layout/index.vue");

// 186 N1：旧父级 /governance 保留为隐藏兼容路由；值域页已移至「标准与关系」分区。
export default {
  path: "/governance",
  name: "Governance",
  component: Layout,
  redirect: "/value-domains",
  meta: {
    icon: "ep/setting",
    title: "数据治理（兼容入口）",
    rank: 93,
    showLink: false
  },
  children: []
} satisfies RouteConfigsTable;
