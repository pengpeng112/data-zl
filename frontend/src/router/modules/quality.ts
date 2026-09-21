const Layout = () => import("@/layout/index.vue");

// 186 N1：质量治理分区（哪些问题需要处理、证据是什么）。
// 台账为主入口；检测规则/观测/探查发现/AI分析为上下游。
export default {
  path: "/quality-hub",
  name: "QualityHub",
  component: Layout,
  redirect: "/quality/issues",
  meta: {
    icon: "ep/aim",
    title: "质量治理",
    rank: 30
  },
  children: [
    {
      // 174：质量台账（Control→Observation→Issue 闭环主入口）
      path: "/quality/issues",
      name: "QualityIssues",
      component: () => import("@/views/quality/issues/index.vue"),
      meta: {
        title: "质量台账",
        showLink: true,
        auths: ["quality.issue.read"]
      }
    },
    {
      // 186 N1：侧栏不再重复三项；URL 保留，工作台与台账页内可直达
      path: "/quality/issues/mine",
      name: "QualityIssuesMine",
      component: () => import("@/views/quality/issues/index.vue"),
      meta: {
        title: "我的质量任务",
        showLink: false,
        activePath: "/quality/issues",
        auths: ["quality.issue.read"]
      }
    },
    {
      path: "/quality/issues/department",
      name: "QualityIssuesDepartment",
      component: () => import("@/views/quality/issues/index.vue"),
      meta: {
        title: "科室质量任务",
        showLink: false,
        activePath: "/quality/issues",
        auths: ["quality.issue.read"]
      }
    },
    {
      // 174：问题详情（时间线/观测/状态操作；不进菜单）
      path: "/quality/issues/:id",
      name: "QualityIssueDetail",
      component: () => import("@/views/quality/issue-detail/index.vue"),
      meta: {
        title: "问题详情",
        showLink: false,
        activePath: "/quality/issues",
        auths: ["quality.issue.read"]
      }
    },
    {
      path: "/quality/controls",
      name: "QualityControls",
      component: () => import("@/views/quality/controls/index.vue"),
      meta: {
        title: "质控清单",
        showLink: true,
        auths: ["quality.control.read"]
      }
    },
    {
      path: "/quality/observations",
      name: "QualityObservations",
      component: () => import("@/views/quality/observations/index.vue"),
      meta: {
        title: "观测记录",
        showLink: true,
        auths: ["quality.observation.read"]
      }
    },
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
    },
    {
      // 174：元数据质控（显示名与质量台账区分，语义不变）
      path: "/asset/quality",
      name: "AssetQuality",
      component: () => import("@/views/asset/quality/index.vue"),
      meta: {
        title: "元数据质控",
        showLink: true,
        auths: ["asset.quality.view"]
      }
    },
    {
      path: "/asset/ai-quality",
      name: "AssetAiQuality",
      component: () => import("@/views/asset/ai-quality/index.vue"),
      meta: {
        title: "AI质量分析",
        showLink: true,
        auths: ["asset.quality.ai.view"]
      }
    }
  ]
} satisfies RouteConfigsTable;
