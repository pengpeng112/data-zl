const Layout = () => import("@/layout/index.vue");

export default {
  path: "/dict",
  name: "Dict",
  component: Layout,
  redirect: "/dict/medical",
  meta: {
    icon: "ep/collection",
    title: "字典中心",
    rank: 13
  },
  children: [
    {
      path: "/dict/medical",
      name: "DictMedical",
      component: () => import("@/views/dict/medical/index.vue"),
      meta: {
        title: "诊断与手术",
        showLink: true
      }
    },
    {
      path: "/dict/mappings",
      name: "DictMappings",
      component: () => import("@/views/dict/mappings/index.vue"),
      meta: {
        title: "编码对照",
        showLink: true
      }
    },
    {
      path: "/dict/general",
      name: "DictGeneral",
      component: () => import("@/views/dict/general/index.vue"),
      meta: {
        title: "通用字典",
        showLink: true
      }
    },
    {
      path: "/dict/sync-diffs",
      name: "DictSyncDiffs",
      component: () => import("@/views/dict/sync-diffs/index.vue"),
      meta: {
        title: "同步差异",
        showLink: true
      }
    }
  ]
} satisfies RouteConfigsTable;
