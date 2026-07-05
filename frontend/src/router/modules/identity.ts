const Layout = () => import("@/layout/index.vue");

export default {
  path: "/identity",
  name: "Identity",
  component: Layout,
  redirect: "/identity/persons",
  meta: {
    icon: "ep/user",
    title: "人员与科室",
    rank: 12
  },
  children: [
    {
      path: "/identity/departments",
      name: "IdentityDepartments",
      component: () => import("@/views/identity/departments/index.vue"),
      meta: {
        title: "科室基线",
        showLink: true
      }
    },
    {
      path: "/identity/persons",
      name: "IdentityPersons",
      component: () => import("@/views/identity/persons/index.vue"),
      meta: {
        title: "人员管理",
        showLink: true
      }
    },
    {
      path: "/identity/accounts",
      name: "IdentityAccounts",
      component: () => import("@/views/identity/accounts/index.vue"),
      meta: {
        title: "账号管理",
        showLink: true
      }
    },
    {
      path: "/identity/sync-diffs",
      name: "IdentitySyncDiffs",
      component: () => import("@/views/identity/sync-diffs/index.vue"),
      meta: {
        title: "同步差异",
        showLink: true
      }
    }
  ]
} satisfies RouteConfigsTable;
