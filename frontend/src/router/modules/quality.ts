const Layout = () => import("@/layout/index.vue");

export default {
  path: "/quality-hub",
  name: "QualityHub",
  component: Layout,
  redirect: "/probe-findings",
  meta: {
    icon: "ep/aim",
    title: "质量管理",
    rank: 16
  },
  children: [
    {
      // 166 F4：探查发现页（165 E4 契约消费面）
      path: "/probe-findings",
      name: "ProbeFindings",
      component: () => import("@/views/asset/probe-findings/index.vue"),
      meta: {
        title: "探查发现",
        showLink: true,
        auths: ["probe.finding.read"]
      }
    }
  ]
} satisfies RouteConfigsTable;
