const Layout = () => import("@/layout/index.vue");

export default {
  path: "/quality-hub",
  name: "QualityHub",
  component: Layout,
  // 174 S7：质量管理默认入口从探查发现切到质量台账；旧 /probe-findings 保留
  redirect: "/quality/issues",
  meta: {
    icon: "ep/aim",
    title: "质量管理",
    rank: 16
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
      // 174：我的任务（同组件，默认 mine 范围）
      path: "/quality/issues/mine",
      name: "QualityIssuesMine",
      component: () => import("@/views/quality/issues/index.vue"),
      meta: {
        title: "我的任务",
        showLink: true,
        auths: ["quality.issue.read"]
      }
    },
    {
      // 174：科室任务（同组件，默认 department 范围）
      path: "/quality/issues/department",
      name: "QualityIssuesDepartment",
      component: () => import("@/views/quality/issues/index.vue"),
      meta: {
        title: "科室任务",
        showLink: true,
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
      // 174：质控清单
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
      // 174：观测记录（不可变观测流水）
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
      // 166 F4：探查发现页（165 E4 契约消费面）；174 起不再作为默认入口
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
