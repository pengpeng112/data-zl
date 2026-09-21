const Layout = () => import("@/layout/index.vue");

// 186 N1：资产目录分区（有什么数据、在哪、如何关联）。
// 叶子 path/name/component/auths 与迁移前完全一致（自 asset.ts / metadata.ts 移入）。
export default {
  path: "/catalog",
  name: "Catalog",
  component: Layout,
  redirect: "/asset/systems",
  meta: {
    icon: "ep/folder-opened",
    title: "资产目录",
    rank: 10
  },
  children: [
    {
      path: "/asset/systems",
      name: "AssetSystems",
      component: () => import("@/views/asset/systems/index.vue"),
      meta: {
        title: "系统与数据资源",
        showLink: true,
        auths: ["asset.system.view"]
      }
    },
    {
      path: "/datasets",
      name: "DatasetCatalog",
      component: () => import("@/views/datasets/catalog/index.vue"),
      meta: {
        title: "数据集目录",
        showLink: true,
        auths: ["query.view"]
      }
    },
    {
      path: "/asset/tables",
      name: "AssetTables",
      component: () => import("@/views/asset/tables/index.vue"),
      meta: {
        title: "表与字段",
        showLink: true,
        auths: ["asset.table.view"]
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
      // 186 N1：恢复可见（146 E1 曾隐藏）；权限仍为 asset.lineage.view
      path: "/asset/lineage",
      name: "AssetLineage",
      component: () => import("@/views/asset/lineage/index.vue"),
      meta: {
        title: "血缘与影响",
        showLink: true,
        auths: ["asset.lineage.view"]
      }
    },
    {
      path: "/metadata/changes",
      name: "MetadataChanges",
      component: () => import("@/views/metadata-changes/changes/index.vue"),
      meta: {
        title: "元数据变更",
        showLink: true,
        auths: ["metadata.change.view"]
      }
    },
    {
      // 隐藏页：详情/兼容入口（不删路由，activePath 指向主入口）
      path: "/asset/tables/:schema/:table",
      name: "AssetTableDetail",
      component: () => import("@/views/asset/table-detail/index.vue"),
      meta: {
        title: "表详情",
        showLink: false,
        activePath: "/asset/tables",
        // QA ST-005：与兄弟路由同口径要求表查看权限，防 URL 直敲绕过。
        auths: ["asset.table.view"]
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
      // 146 E1 兼容入口保留 URL，query 原样传递并默认进入图谱路径模式
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
      // 页内常驻入口在「元数据变更」页（快照管理与快照对比；独立权限）
      path: "/metadata/snapshots",
      name: "MetadataSnapshots",
      component: () => import("@/views/metadata-changes/snapshots/index.vue"),
      meta: {
        title: "快照管理",
        showLink: false,
        activePath: "/metadata/changes",
        auths: ["metadata.snapshot.view"]
      }
    },
    {
      path: "/metadata/diff",
      name: "MetadataDiff",
      component: () => import("@/views/metadata-changes/diff/index.vue"),
      meta: {
        title: "快照对比",
        showLink: false,
        activePath: "/metadata/changes",
        auths: ["metadata.diff.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;

