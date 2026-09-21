const Layout = () => import("@/layout/index.vue");

// 186 N1：人员与权限分区。平台账号与业务系统账号用文案区分；
// roles/auths 原样保留（路径与名称未变）。
export default {
  path: "/identity",
  name: "Identity",
  component: Layout,
  redirect: "/identity/persons",
  meta: {
    icon: "ep/user",
    title: "人员与权限",
    rank: 50
  },
  children: [
    {
      path: "/identity/persons",
      name: "IdentityPersons",
      component: () => import("@/views/identity/persons/index.vue"),
      meta: {
        title: "人员管理",
        showLink: true,
        auths: ["identity.person.view"]
      }
    },
    {
      path: "/identity/departments",
      name: "IdentityDepartments",
      component: () => import("@/views/identity/departments/index.vue"),
      meta: {
        title: "科室基线",
        showLink: true,
        auths: ["identity.dept.view"]
      }
    },
    {
      path: "/identity/accounts",
      name: "IdentityAccounts",
      component: () => import("@/views/identity/accounts/index.vue"),
      meta: {
        title: "业务系统账号",
        showLink: true,
        auths: ["identity.account.view"]
      }
    },
    {
      path: "/identity/local-accounts",
      name: "IdentityLocalAccounts",
      component: () => import("@/views/identity/local-accounts/index.vue"),
      meta: {
        title: "平台本地账号",
        showLink: true,
        roles: ["identity_admin", "platform_admin"],
        auths: ["identity.local_account.manage", "identity.role.manage"]
      }
    },
    {
      path: "/identity/sync-diffs",
      name: "IdentitySyncDiffs",
      component: () => import("@/views/identity/sync-diffs/index.vue"),
      meta: {
        title: "人员同步差异",
        showLink: true,
        auths: ["identity.sync_diff.view"]
      }
    },
    {
      path: "/identity/sync-logs",
      name: "IdentitySyncLogs",
      component: () => import("@/views/identity/sync-logs/index.vue"),
      meta: {
        title: "人员同步日志",
        showLink: true,
        auths: ["identity.sync_diff.view"]
      }
    },
    {
      path: "/identity/roles",
      name: "IdentityRoles",
      component: () => import("@/views/identity/roles/index.vue"),
      meta: {
        title: "平台角色权限",
        showLink: true,
        roles: ["identity_admin", "platform_admin"],
        auths: ["identity.role.manage", "identity.role.grant"]
      }
    },
    {
      path: "/identity/authorizations",
      name: "IdentityAuthorizations",
      component: () => import("@/views/identity/authorizations/index.vue"),
      meta: {
        title: "人员授权",
        showLink: true,
        roles: ["identity_admin", "platform_admin"],
        auths: ["identity.role.grant"]
      }
    },
    {
      path: "/identity/permission-requests",
      name: "IdentityPermissionRequests",
      component: () => import("@/views/identity/permission-requests/index.vue"),
      meta: {
        title: "权限申请与审批",
        showLink: true,
        auths: ["identity.permission_request.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
