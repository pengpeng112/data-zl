const Layout = () => import("@/layout/index.vue");

// 186 N1：标准与关系分区（数据含义、编码与关系是否可信）。
// 值域/字典自 governance.ts、dict.ts 移入；关系复核/配方自 asset.ts 移入；
// 叶子 path/name/component/auths 与迁移前一致。
export default {
  path: "/standards",
  name: "Standards",
  component: Layout,
  redirect: "/value-domains",
  meta: {
    icon: "ep/collection",
    title: "标准与关系",
    rank: 20
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
    },
    {
      path: "/dict/medical",
      name: "DictMedical",
      component: () => import("@/views/dict/medical/index.vue"),
      meta: {
        title: "诊断手术字典",
        showLink: true,
        auths: ["dict.medical.view"]
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
      path: "/dict/mappings",
      name: "DictMappings",
      component: () => import("@/views/dict/mappings/index.vue"),
      meta: {
        title: "编码映射",
        showLink: true,
        auths: ["dict.mapping.view", "dict.medical.view"]
      }
    },
    {
      path: "/dict/sync-diffs",
      name: "DictSyncDiffs",
      component: () => import("@/views/dict/sync-diffs/index.vue"),
      meta: {
        title: "字典同步差异",
        showLink: true,
        auths: ["dict.sync_diff.view"]
      }
    },
    {
      path: "/asset/relation-review",
      name: "AssetRelationReview",
      component: () => import("@/views/asset/relation-review/index.vue"),
      meta: {
        title: "关系复核",
        showLink: true,
        auths: ["asset.relation.review"]
      }
    },
    {
      path: "/asset/relation-recipes",
      name: "AssetRelationRecipes",
      component: () => import("@/views/asset/relation-recipes/index.vue"),
      meta: { title: "关系配方", showLink: true, auths: ["asset.recipe.view"] }
    },
    {
      // 页内入口：验证统计（自关系复核页进入；独立权限保留）
      path: "/asset/relation-rates",
      name: "AssetRelationRates",
      component: () => import("@/views/asset/relation-rates/index.vue"),
      meta: {
        title: "关系验证统计",
        showLink: false,
        activePath: "/asset/relation-review",
        auths: ["asset.relation.view"]
      }
    },
    {
      // 页内入口：AI 上下文预览（自关系配方页进入；独立权限保留）
      path: "/asset/ai-context",
      name: "AssetAiContext",
      component: () => import("@/views/asset/ai-context/index.vue"),
      meta: {
        title: "AI上下文预览",
        showLink: false,
        activePath: "/asset/relation-recipes",
        auths: ["asset.ai_context.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
