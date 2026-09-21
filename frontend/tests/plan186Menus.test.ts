// 186 N1/N2/N3 行为验收：七分区菜单、旧路径兼容、用户隔离偏好、静态路由短路。
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import "./helpers/memoryLocalStorage";

vi.mock("@/router/index", () => ({ router: {} }));

import homeRoute from "@/router/modules/home";
import catalogRoute from "@/router/modules/catalog";
import standardsRoute from "@/router/modules/standards";
import qualityRoute from "@/router/modules/quality";
import queryRoute from "@/router/modules/query";
import identityRoute from "@/router/modules/identity";
import opsRoute from "@/router/modules/ops";
import assetRoute from "@/router/modules/asset";
import dictRoute from "@/router/modules/dict";
import metadataRoute from "@/router/modules/metadata";
import governanceRoute from "@/router/modules/governance";
import {
  MENU_TITLE_ALIASES,
  PURGE_LEGACY_TEST_KEYS,
  clearCurrentUserPreferences,
  currentUserScope,
  getRecentVisits,
  purgeLegacyKeys,
  recordRecentVisit,
  sanitizeQuery,
  searchCollect,
  searchHistory,
  titleMatchesAlias
} from "@/utils/menuPreferences";
import { storageLocal } from "@pureadmin/utils";
import { userKey } from "@/utils/auth";

const modules = [
  homeRoute,
  catalogRoute,
  standardsRoute,
  qualityRoute,
  queryRoute,
  identityRoute,
  opsRoute,
  assetRoute,
  dictRoute,
  metadataRoute,
  governanceRoute
] as any[];

const allLeaves = modules.flatMap(m => m.children ?? []);
const visibleLeaves = allLeaves.filter(l => l.meta?.showLink !== false);

function seedUser(username: string, permissions: string[] = []) {
  storageLocal().setItem(userKey, {
    accessToken: "",
    refreshToken: "",
    expires: 0,
    username,
    nickname: username,
    roles: [],
    permissions
  });
}

describe("plan186 N1 七分区静态菜单", () => {
  it("七个业务分区按 rank 排序且标题正确", () => {
    const partitions = modules.filter(m => m.meta?.showLink !== false && m.meta?.rank < 90);
    const sorted = [...partitions].sort((a, b) => a.meta.rank - b.meta.rank);
    expect(sorted.map(m => m.meta.title)).toEqual([
      "工作台",
      "资产目录",
      "标准与关系",
      "质量治理",
      "查询与指标",
      "人员与权限",
      "平台运维"
    ]);
  });

  it("可见叶子共 40 个（4/5/7/6/3/9/6），与 186 §4.7-4 目标一致", () => {
    expect(visibleLeaves.length).toBe(40);
    const byParent: Record<string, number> = {};
    for (const m of modules) {
      const visible = (m.children ?? []).filter(
        (l: any) => l.meta?.showLink !== false
      );
      if (visible.length) byParent[m.meta.title] = visible.length;
    }
    expect(byParent).toEqual({
      工作台: 4,
      资产目录: 5,
      标准与关系: 7,
      质量治理: 6,
      查询与指标: 3,
      "人员与权限": 9,
      平台运维: 6
    });
  });

  it("全 path/name 无重复（N1 验收）", () => {
    const paths = allLeaves.map(l => l.path);
    const names = allLeaves.map(l => l.name).filter(Boolean);
    expect(new Set(paths).size).toBe(paths.length);
    expect(new Set(names).size).toBe(names.length);
  });

  it("首页默认指向 /workbench；welcome 保留为运行总览", () => {
    expect((homeRoute as any).redirect).toBe("/workbench");
    const welcome = (homeRoute as any).children.find(
      (c: any) => c.path === "/welcome"
    );
    expect(welcome.meta.showLink).toBe(true);
    expect(welcome.meta.title).toBe("运行总览");
  });

  it("旧父级 /asset /dict /metadata /governance 保留隐藏兼容重定向", () => {
    expect(assetRoute.redirect).toBe("/asset/systems");
    expect(assetRoute.meta.showLink).toBe(false);
    expect(dictRoute.redirect).toBe("/dict/medical");
    expect(metadataRoute.redirect).toBe("/metadata/changes");
    expect(governanceRoute.redirect).toBe("/value-domains");
  });

  it("旧深链兼容入口保留并透传 query（sources/relations/candidates）", () => {
    const sources = allLeaves.find(l => l.name === "AssetSources");
    expect(sources.redirect).toBe("/asset/systems?tab=connections");
    const relations = allLeaves.find(l => l.name === "AssetRelations");
    expect(relations.meta.showLink).toBe(false);
    const redirected = relations.redirect({ query: { view_mode: undefined, x: "1" } });
    expect(redirected.path).toBe("/asset/graph");
    expect(redirected.query.view_mode).toBe("path");
    expect(redirected.query.x).toBe("1");
    const candidates = allLeaves.find(l => l.name === "AssetCandidates");
    expect(
      candidates.redirect({ query: { status: "draft" } }).query
    ).toMatchObject({ status: "draft", class: "candidate" });
  });

  it("隐藏页设置正确 activePath 且权限不变", () => {
    const expectations: Array<[string, string | undefined, string[] | undefined]> = [
      ["AssetTableDetail", "/asset/tables", undefined],
      ["MetadataSnapshots", "/metadata/changes", ["metadata.snapshot.view"]],
      ["MetadataDiff", "/metadata/changes", ["metadata.diff.view"]],
      ["AssetRelationRates", "/asset/relation-review", ["asset.relation.view"]],
      ["AssetAiContext", "/asset/relation-recipes", ["asset.ai_context.view"]],
      ["QualityIssuesMine", "/quality/issues", ["quality.issue.read"]]
    ];
    for (const [name, activePath, auths] of expectations) {
      const leaf = allLeaves.find(l => l.name === name);
      expect(leaf, name).toBeTruthy();
      expect(leaf.meta.showLink, name).toBe(false);
      expect(leaf.meta.activePath, name).toBe(activePath);
      if (auths) expect(leaf.meta.auths, name).toEqual(auths);
    }
    // 血缘恢复可见，权限保持 asset.lineage.view
    const lineage = allLeaves.find(l => l.name === "AssetLineage");
    expect(lineage.meta.showLink).toBe(true);
    expect(lineage.meta.auths).toEqual(["asset.lineage.view"]);
  });

  it("编码映射页对 dict_admin 的 dict.medical.view 可见", () => {
    const mappings = allLeaves.find(l => l.name === "DictMappings");
    expect(mappings.meta.auths).toEqual([
      "dict.mapping.view",
      "dict.medical.view"
    ]);
  });

  it("叶子 auths 全部在后端资源目录内（不新增权限）", () => {
    const catalog = readFileSync(
      resolve(process.cwd(), "../backend/app/api/v1/permissions.py"),
      "utf8"
    );
    const codes = [
      ...new Set(
        modules
          .flatMap((m: any) => m.children ?? [])
          .flatMap((l: any) => l.meta?.auths ?? [])
      )
    ];
    expect(codes.length).toBeGreaterThan(20);
    for (const code of codes) {
      expect(catalog, `missing permission seed: ${code}`).toContain(
        `"code": "${code}"`
      );
    }
  });
});

describe("plan186 N2 用户隔离偏好", () => {
  beforeEach(() => {
    localStorage.clear();
    clearCurrentUserPreferences();
  });

  it("未登录不落任何偏好", () => {
    expect(currentUserScope()).toBeNull();
    recordRecentVisit({ path: "/asset/systems", name: "AssetSystems" });
    expect(getRecentVisits()).toEqual([]);
  });

  it("A 用户的历史对 B 用户不可见（键隔离）", () => {
    seedUser("alice");
    searchHistory.write([{ path: "/asset/systems", meta: { title: "系统" } }]);
    recordRecentVisit({ path: "/asset/tables", name: "AssetTables" });
    seedUser("bob");
    expect(searchHistory.read()).toEqual([]);
    expect(getRecentVisits()).toEqual([]);
    expect(currentUserScope()?.userId).toBe("bob");
  });

  it("recent 上限 20 条且去重置顶", () => {
    seedUser("alice");
    for (let i = 0; i < 25; i++) {
      recordRecentVisit({ path: `/p/${i}` });
    }
    recordRecentVisit({ path: "/p/24" }); // 重复访问置顶
    const visits = getRecentVisits();
    expect(visits.length).toBe(20);
    expect(visits[0].path).toBe("/p/24");
  });

  it("敏感 query 不持久化，白名单 query 保留", () => {
    seedUser("alice");
    recordRecentVisit({
      path: "/asset/queries",
      name: "AssetQueries",
      query: { sql: "SELECT * FROM PAT_VISIT", patient_id: "P001", tab: "runs" }
    });
    const visit = getRecentVisits()[0];
    expect(visit.querySuffix).toBe("?tab=runs");
    expect(visit.querySuffix).not.toContain("sql");
    expect(visit.querySuffix).not.toContain("patient_id");
  });

  it("旧通用键读取即清理（不导入当前用户）", () => {
    localStorage.setItem(
      "menu-search-history",
      JSON.stringify([{ path: "/asset/systems" }])
    );
    seedUser("alice");
    purgeLegacyKeys();
    expect(localStorage.getItem("menu-search-history")).toBeNull();
    expect(searchHistory.read()).toEqual([]);
  });

  it("旧中文名别名可命中新标题；同义词区分人员/字典同步", () => {
    expect(titleMatchesAlias("人员同步日志", "同步日志")).toBe(true);
    expect(titleMatchesAlias("查询、指标与产品", "查询中心")).toBe(true);
    expect(titleMatchesAlias("日常工作台", "首页")).toBe(true);
    expect(titleMatchesAlias("AI辅助编写", "AI写SQL")).toBe(true);
    // 同名旧词只指向一个新标题（人员同步日志），不误匹配字典侧
    expect(titleMatchesAlias("字典同步差异", "同步日志")).toBe(false);
    expect(Object.keys(MENU_TITLE_ALIASES).length).toBeGreaterThan(20);
  });
});

describe("plan186 N3 静态路由短路", () => {
  it("默认静态模式不请求 /get-async-routes（源码契约）", () => {
    const src = readFileSync(
      resolve(process.cwd(), "src/api/routes.ts"),
      "utf8"
    );
    // 短路必须先于请求；动态分支仅在显式环境变量下启用
    expect(src.indexOf("return { success: true, data: [] }")).toBeGreaterThan(-1);
    expect(src).toContain("VITE_ENABLE_ASYNC_ROUTES");
    // 动态失败不再伪装 success（保留故障可见性）
    expect(src).toContain("success: false");
  });

  it("getTopMenu 兜底指向工作台（源码契约）", () => {
    const src = readFileSync(
      resolve(process.cwd(), "src/router/utils.ts"),
      "utf8"
    );
    expect(src).toContain('path: "/workbench", name: "Workbench"');
  });
});
