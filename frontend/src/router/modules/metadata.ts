const Layout = () => import("@/layout/index.vue");

export default {
  path: "/metadata",
  name: "Metadata",
  component: Layout,
  redirect: "/metadata/changes",
  meta: {
    icon: "ep/monitor",
    title: "变更检测",
    rank: 14
  },
  children: [
    {
      path: "/metadata/changes",
      name: "MetadataChanges",
      component: () => import("@/views/metadata-changes/changes/index.vue"),
      meta: {
        title: "变更事件",
        showLink: true
      }
    },
    {
      path: "/metadata/snapshots",
      name: "MetadataSnapshots",
      component: () => import("@/views/metadata-changes/snapshots/index.vue"),
      meta: {
        title: "快照管理",
        showLink: true
      }
    },
    {
      path: "/metadata/diff",
      name: "MetadataDiff",
      component: () => import("@/views/metadata-changes/diff/index.vue"),
      meta: {
        title: "快照对比",
        showLink: true
      }
    }
  ]
} satisfies RouteConfigsTable;
