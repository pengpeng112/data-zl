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
        title: "诊断手术维护",
        showLink: true,
        auths: ["dict.medical.view"]
      }
    },
    {
      path: "/dict/mappings",
      name: "DictMappings",
      component: () => import("@/views/dict/mappings/index.vue"),
      meta: {
        title: "编码关系明细",
        showLink: true,
        auths: ["dict.mapping.view"]
      }
    },
    {
      path: "/dict/general",
      name: "DictGeneral",
      component: () => import("@/views/dict/general/index.vue"),
      meta: {
        title: "通用字典",
        showLink: true,
        auths: ["dict.general.view"]
      }
    },
    {
      path: "/dict/sync-diffs",
      name: "DictSyncDiffs",
      component: () => import("@/views/dict/sync-diffs/index.vue"),
      meta: {
        title: "同步差异",
        showLink: true,
        auths: ["dict.sync_diff.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
