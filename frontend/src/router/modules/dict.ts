const Layout = () => import("@/layout/index.vue");

// 186 N1：旧父级 /dict 保留为隐藏兼容路由；叶子已移至「标准与关系」分区。
export default {
  path: "/dict",
  name: "Dict",
  component: Layout,
  redirect: "/dict/medical",
  meta: {
    icon: "ep/collection",
    title: "字典中心（兼容入口）",
    rank: 91,
    showLink: false
  },
  children: []
} satisfies RouteConfigsTable;
