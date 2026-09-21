const Layout = () => import("@/layout/index.vue");

// 186 N1：旧父级 /metadata 保留为隐藏兼容路由；叶子已移至「资产目录」分区。
export default {
  path: "/metadata",
  name: "Metadata",
  component: Layout,
  redirect: "/metadata/changes",
  meta: {
    icon: "ep/monitor",
    title: "变更检测（兼容入口）",
    rank: 92,
    showLink: false
  },
  children: []
} satisfies RouteConfigsTable;
