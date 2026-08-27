import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { renderReportHtml } from "@/views/asset/ai-quality/reportMarkdown";

function source(path: string) {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

describe("146 stage E1/E2 relation entries", () => {
  it("keeps /asset/relations as a hidden redirect into graph path mode with query passthrough", () => {
    const routes = source("src/router/modules/asset.ts");
    expect(routes).toContain('path: "/asset/relations"');
    expect(routes).toContain('path: "/asset/graph"');
    expect(routes).toContain("...to.query");
    expect(routes).toContain('view_mode: to.query.view_mode ?? "path"');
    expect(routes).not.toContain('component: () => import("@/views/asset/relations/index.vue")');
    expect(routes).toMatch(/title: "关系路径（兼容入口）"[\s\S]{0,80}showLink: false/);
    expect(routes).toMatch(/title: "血缘与影响"[\s\S]{0,60}showLink: false/);
  });

  it("graph page implements the path submode against the existing endpoint", () => {
    const graph = source("src/views/asset/graph/index.vue");
    expect(graph).toContain("getRelationPath(pathForm.from, pathForm.to");
    expect(graph).toContain('"both" | "out" | "in"');
    expect(graph).toContain("max_hops");
    expect(graph).toContain("pathState");
    expect(graph).toContain("routeQueryText(route.query.view_mode) || routeQueryText(route.query.mode)");
    expect(graph).toContain("未找到关联路径");
    expect(graph).toContain("center");
  });

  it("relation-rates links rows into graph path mode and filters server-side", () => {
    const rates = source("src/views/asset/relation-rates/index.vue");
    expect(rates).toContain('path: "/asset/graph"');
    expect(rates).toContain('view_mode: "path"');
    expect(rates).toContain("hit_rate_min");
    expect(rates).toContain("hit_rate_max");
    expect(rates).not.toContain("filteredItems");
  });

  it("lineage keeps a light entry with expand-in-graph action", () => {
    const lineage = source("src/views/asset/lineage/index.vue");
    expect(lineage).toContain("在图谱中展开");
    expect(lineage).toContain('{ path: "/asset/graph", query: { center: physicalKey } }');
  });
});

describe("146 stage E3 ai-quality", () => {
  it("renders markdown tables and ordered lists safely", () => {
    const html = renderReportHtml(
      ["## 结论", "", "| 表 | 命中 |", "| --- | --- |", "| PAT_VISIT | 99% |", "", "1. 第一步", "2. 第二步", "- 无序项"].join("\n")
    );
    expect(html).toContain('<table class="md-table"><thead><tr><th>表</th><th>命中</th></tr></thead><tbody><tr><td>PAT_VISIT</td><td>99%</td></tr></tbody></table>');
    expect(html).toContain("<ol><li>第一步</li><li>第二步</li></ol>");
    expect(html).toContain("<ul><li>无序项</li></ul>");
    expect(renderReportHtml("<script>alert(1)</script>")).not.toContain("<script>");
  });

  it("caps polling at 10 minutes with exponential backoff", () => {
    const page = source("src/views/asset/ai-quality/index.vue");
    expect(page).toContain("POLL_TIMEOUT_MS");
    expect(page).toContain("10 * 60 * 1000");
    expect(page).toContain("Math.min(interval * 2, 10000)");
    expect(page).toContain("onUnmounted(() => stopWatch())");
  });
});

describe("146 stage E4 admin token", () => {
  it("shows the token exactly once in a modal instead of native prompt", () => {
    const admin = source("src/views/asset/admin/index.vue");
    expect(admin).not.toContain("prompt(");
    expect(admin).toContain("tokenOnce");
    expect(admin).toContain("仅显示一次");
    expect(admin).toContain("token-once");
    expect(admin).toContain("copyTokenOnce");
  });
});

describe("146 stage E5/E6/E7/E9/E10/E11 contracts", () => {
  it("table detail isolates by source and preserves list state on back", () => {
    const detail = source("src/views/asset/table-detail/index.vue");
    expect(detail).toContain("sourceCode.value || undefined");
    expect(detail).toContain("notFound");
    expect(detail).toContain("back_query");
    const tables = source("src/views/asset/tables/index.vue");
    expect(tables).toContain("query.source_code = row.source_code");
    expect(tables).toContain("query.back_query = back");
  });

  it("accounts page uses server pagination and audited unbind", () => {
    const accounts = source("src/views/identity/accounts/index.vue");
    expect(accounts).toContain("unbindAccount(row.id");
    expect(accounts).toContain("el-pagination");
    expect(accounts).toContain("v-perms=\"'identity.local_account.manage'\"");
    const identityApi = source("src/api/identity.ts");
    expect(identityApi).toContain("/api/v1/identity/accounts/${accountId}/binding");
  });

  it("local-accounts and login share the 8-18 password policy", () => {
    const local = source("src/views/identity/local-accounts/index.vue");
    expect(local).toContain("8-18");
    expect(local).not.toContain("至少 12 位");
    const login = source("src/views/login/index.vue");
    expect(login).toContain("8-18");
  });

  it("403 page shows only safe account/permission context", () => {
    const forbidden = source("src/views/error/403.vue");
    expect(forbidden).toContain("requiredAuth");
    expect(forbidden).toContain("currentAccount");
    expect(forbidden).toContain("返回上一页");
    expect(forbidden).not.toContain("localStorage");
    expect(forbidden).not.toContain("sessionStorage");
  });

  it("snapshots page archives softly and changes page batches", () => {
    const snapshots = source("src/views/metadata-changes/snapshots/index.vue");
    expect(snapshots).toContain("archiveMetadataSnapshot");
    expect(snapshots).toContain("软归档");
    const changes = source("src/views/metadata-changes/changes/index.vue");
    expect(changes).toContain("batchUpdateMetadataChanges");
    expect(changes).toContain("批量重开");
  });

  it("recipes page wires the backend state machine with dot permissions", () => {
    const recipes = source("src/views/asset/relation-recipes/index.vue");
    for (const action of ["submitRecipeVersion", "approveRecipeVersion", "rejectRecipeVersion", "activateRecipeVersion", "deprecateRecipeVersion"]) {
      expect(recipes).toContain(action);
    }
    expect(recipes).toContain("v-perms=\"'recipe.review'\"");
    expect(recipes).toContain("v-perms=\"'recipe.activate'\"");
  });

  it("ops pages consume new pagination and audit endpoints", () => {
    const tools = source("src/views/ops/tools/index.vue");
    expect(tools).toContain("getOpsTools({ page: page.value");
    const audit = source("src/views/ops/audit/index.vue");
    expect(audit).toContain("getAuditLogsSummary");
    expect(audit).toContain("exportAuditLogs");
    const runs = source("src/views/ops/runs/index.vue");
    expect(runs).toContain("run_id");
  });
});
