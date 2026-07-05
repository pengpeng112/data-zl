const Layout = () => import("@/layout/index.vue");

export default {
  path: "/asset",
  name: "Asset",
  component: Layout,
  redirect: "/asset/overview",
  meta: {
    icon: "ep/data-board",
    title: "数据资产",
    rank: 10
  },
      children: [
    {
      path: "/asset/overview",
      name: "AssetOverview",
      component: () => import("@/views/asset/overview/index.vue"),
      meta: {
        title: "资产总览",
        showLink: true
      }
    },
    {
      path: "/asset/systems",
      name: "AssetSystems",
      component: () => import("@/views/asset/systems/index.vue"),
      meta: {
        title: "系统总览",
        showLink: true
      }
    },
    {
      path: "/asset/sources",
      name: "AssetSources",
      component: () => import("@/views/asset/sources/index.vue"),
      meta: {
        title: "数据源与库",
        showLink: true
      }
    },
    {
      path: "/asset/tables",
      name: "AssetTables",
      component: () => import("@/views/asset/tables/index.vue"),
      meta: {
        title: "表资产",
        showLink: true
      }
    },
    {
      path: "/asset/tables/:schema/:table",
      name: "AssetTableDetail",
      component: () => import("@/views/asset/table-detail/index.vue"),
      meta: {
        title: "表详情",
        showLink: false
      }
    },
    {
      path: "/asset/graph",
      name: "AssetGraph",
      component: () => import("@/views/asset/graph/index.vue"),
      meta: {
        title: "关系图谱",
        showLink: true
      }
    },
    {
      path: "/asset/relations",
      name: "AssetRelations",
      component: () => import("@/views/asset/relations/index.vue"),
      meta: {
        title: "关系路径",
        showLink: true
      }
    },
    {
      path: "/asset/ai-context",
      name: "AssetAiContext",
      component: () => import("@/views/asset/ai-context/index.vue"),
      meta: {
        title: "AI上下文",
        showLink: true
      }
    },
    {
      path: "/asset/lineage",
      name: "AssetLineage",
      component: () => import("@/views/asset/lineage/index.vue"),
      meta: {
        title: "血缘与影响",
        showLink: true
      }
    },
    {
      path: "/asset/candidates",
      name: "AssetCandidates",
      component: () => import("@/views/asset/candidates/index.vue"),
      meta: {
        title: "候选关系",
        showLink: true
      }
    },
    {
      path: "/asset/relation-review",
      name: "AssetRelationReview",
      component: () => import("@/views/asset/relation-review/index.vue"),
      meta: {
        title: "关系复核",
        showLink: true
      }
    },
    {
      path: "/asset/quality",
      name: "AssetQuality",
      component: () => import("@/views/asset/quality/index.vue"),
      meta: {
        title: "数据质量",
        showLink: true
      }
    },
    {
      path: "/asset/ai-tools",
      name: "AssetAiTools",
      component: () => import("@/views/asset/ai-tools/index.vue"),
      meta: {
        title: "AI 协作",
        showLink: true
      }
    },
    {
      path: "/asset/admin",
      name: "AssetAdmin",
      component: () => import("@/views/asset/admin/index.vue"),
      meta: {
        title: "治理管理",
        showLink: true
      }
    }
  ]
} satisfies RouteConfigsTable;
