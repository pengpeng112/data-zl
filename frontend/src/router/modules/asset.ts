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
        showLink: true,
        auths: ["asset.overview.view"]
      }
    },
    {
      // 170：数据资产系统图——六步持续治理链路全景（高质量专题数据集叙事）
      path: "/asset/system-map",
      name: "AssetSystemMap",
      component: () => import("@/views/asset/system-map/index.vue"),
      meta: {
        title: "数据资产系统图",
        showLink: true,
        auths: ["asset.overview.view"]
      }
    },
    {
      path: "/asset/systems",
      name: "AssetSystems",
      component: () => import("@/views/asset/systems/index.vue"),
      meta: {
        title: "业务系统与数据资源",
        showLink: true,
        auths: ["asset.system.view"]
      }
    },
    {
      path: "/asset/sources",
      name: "AssetSources",
      redirect: "/asset/systems?tab=connections",
      meta: {
        title: "数据连接（兼容入口）",
        showLink: false
      }
    },
    {
      path: "/asset/tables",
      name: "AssetTables",
      component: () => import("@/views/asset/tables/index.vue"),
      meta: {
        title: "表资产",
        showLink: true,
        auths: ["asset.table.view"]
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
        showLink: true,
        auths: ["asset.graph.view"]
      }
    },
    {
      // 146 E1：兼容入口保留 URL，query 原样传递并默认进入图谱路径模式
      path: "/asset/relations",
      name: "AssetRelations",
      redirect: to => ({
        path: "/asset/graph",
        query: { ...to.query, view_mode: to.query.view_mode ?? "path" }
      }),
      meta: {
        title: "关系路径（兼容入口）",
        showLink: false
      }
    },
    {
      path: "/asset/relation-rates",
      name: "AssetRelationRates",
      component: () => import("@/views/asset/relation-rates/index.vue"),
      meta: {
        title: "关系命中率",
        showLink: true,
        auths: ["asset.relation.view"]
      }
    },
    {
      path: "/asset/ai-context",
      name: "AssetAiContext",
      component: () => import("@/views/asset/ai-context/index.vue"),
      meta: {
        title: "AI上下文",
        showLink: true,
        auths: ["asset.ai_context.view"]
      }
    },
    {
      path: "/asset/relation-recipes",
      name: "AssetRelationRecipes",
      component: () => import("@/views/asset/relation-recipes/index.vue"),
      meta: { title: "关系配方库", showLink: true, auths: ["asset.recipe.view"] }
    },
    {
      // 146 E1：轻入口，仅隐藏菜单，URL 保留
      path: "/asset/lineage",
      name: "AssetLineage",
      component: () => import("@/views/asset/lineage/index.vue"),
      meta: {
        title: "血缘与影响",
        showLink: false,
        auths: ["asset.lineage.view"]
      }
    },
    {
      path: "/asset/candidates",
      name: "AssetCandidates",
      redirect: to => ({
        path: "/asset/relation-review",
        query: { ...to.query, class: to.query.class ?? "candidate" }
      }),
      meta: {
        title: "候选关系（兼容入口）",
        showLink: false
      }
    },
    {
      path: "/asset/relation-review",
      name: "AssetRelationReview",
      component: () => import("@/views/asset/relation-review/index.vue"),
      meta: {
        title: "关系复核中心",
        showLink: true,
        auths: ["asset.relation.review"]
      }
    },
    {
      path: "/asset/quality",
      name: "AssetQuality",
      component: () => import("@/views/asset/quality/index.vue"),
      meta: {
        title: "数据质量",
        showLink: true,
        auths: ["asset.quality.view"]
      }
    },
    {
      path: "/asset/ai-quality",
      name: "AssetAiQuality",
      component: () => import("@/views/asset/ai-quality/index.vue"),
      meta: {
        title: "AI质控分析",
        showLink: true,
        auths: ["asset.quality.ai.view"]
      }
    },
    {
      path: "/asset/ai-sql",
      name: "AssetAiSql",
      component: () => import("@/views/asset/ai-sql/index.vue"),
      meta: {
        title: "AI 写 SQL",
        showLink: true,
        auths: ["ai.context.read"]
      }
    },
    {
      path: "/asset/queries",
      name: "AssetQueries",
      component: () => import("@/views/query-center/queries/index.vue"),
      meta: {
        title: "查询与指标中心",
        showLink: true,
        auths: ["query.view"]
      }
    },
    {
      path: "/asset/queries/accuracy",
      name: "AssetQueryAccuracy",
      component: () => import("@/views/query-center/accuracy/index.vue"),
      meta: {
        title: "准确性与反馈",
        showLink: true,
        auths: ["query.view"]
      }
    },
    {
      path: "/asset/ai-tools",
      name: "AssetAiTools",
      component: () => import("@/views/asset/ai-tools/index.vue"),
      meta: {
        title: "AI 接入与协作",
        showLink: true,
        auths: ["asset.ai_draft.view"]
      }
    },
    {
      path: "/asset/admin",
      name: "AssetAdmin",
      component: () => import("@/views/asset/admin/index.vue"),
      meta: {
        title: "治理管理",
        showLink: true,
        auths: ["asset.admin.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
