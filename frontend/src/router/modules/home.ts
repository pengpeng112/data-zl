const Layout = () => import("@/layout/index.vue");

export default {
  path: "/",
  name: "Home",
  component: Layout,
  // 186 N1：首页默认指向日常工作台；/welcome 大屏保留为「运行总览」
  redirect: "/workbench",
  meta: {
    icon: "ep/home-filled",
    title: "工作台",
    rank: 0,
    showLink: true
  },
  children: [
    {
      // 186 W1：日常工作台（我的待办/快捷入口/最近访问/运行摘要）
      path: "/workbench",
      name: "Workbench",
      component: () => import("@/views/workbench/index.vue"),
      meta: {
        title: "日常工作台",
        showLink: true
      }
    },
    {
      path: "/welcome",
      name: "Welcome",
      component: () => import("@/views/welcome/index.vue"),
      meta: {
        title: "运行总览",
        showLink: true
      }
    },
    {
      // 186 N1：资产统计归入工作台分区；保留独立视觉与既有数据获取
      path: "/asset/overview",
      name: "AssetOverview",
      component: () => import("@/views/asset/overview/index.vue"),
      meta: {
        title: "资产统计",
        showLink: true,
        auths: ["asset.overview.view"]
      }
    },
    {
      path: "/asset/system-map",
      name: "AssetSystemMap",
      component: () => import("@/views/asset/system-map/index.vue"),
      meta: {
        title: "平台能力全景",
        showLink: true,
        auths: ["asset.overview.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
