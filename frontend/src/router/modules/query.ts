const Layout = () => import("@/layout/index.vue");

// 186 N1：查询与指标分区（如何取得可信结果）。
// 叶子自 asset.ts 移入，path/name/component/auths 不变；
// 运行/看板/调度仍作为查询中心页内 tab（tab 参数可定位）。
export default {
  path: "/query",
  name: "QueryZone",
  component: Layout,
  redirect: "/asset/queries",
  meta: {
    icon: "ep/search",
    title: "查询与指标",
    rank: 40
  },
  children: [
    {
      path: "/asset/ai-sql",
      name: "AssetAiSql",
      component: () => import("@/views/asset/ai-sql/index.vue"),
      meta: {
        title: "AI辅助编写",
        showLink: true,
        auths: ["ai.context.read"]
      }
    },
    {
      path: "/asset/queries",
      name: "AssetQueries",
      component: () => import("@/views/query-center/queries/index.vue"),
      meta: {
        title: "查询、指标与产品",
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
    }
  ]
} satisfies RouteConfigsTable;
