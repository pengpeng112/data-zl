const Layout = () => import("@/layout/index.vue");

// 186 N1：旧父级 /asset 不再作为展示分区，保留为隐藏兼容路由。
// 全部叶子已移至 catalog/standards/query/quality/ops 分区（path/name 不变，
// 深链由各分区子路由的绝对 path 直接匹配）。
export default {
  path: "/asset",
  name: "Asset",
  component: Layout,
  redirect: "/asset/systems",
  meta: {
    icon: "ep/data-board",
    title: "数据资产（兼容入口）",
    rank: 90,
    showLink: false
  },
  children: []
} satisfies RouteConfigsTable;
