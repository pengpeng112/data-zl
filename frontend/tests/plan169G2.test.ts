import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { shouldDowngradeOverview } from "@/views/asset/graph/graphLoadPolicy";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** 169 G2：首屏韧性三件——错误态保留工具栏 / overview 超时分级 / 失败自动降级。 */
describe("plan169 G2 first-screen resilience", () => {
  it("keeps the toolbar mounted in error state (only loading hides it)", () => {
    const src = source("src/views/asset/graph/index.vue");
    expect(src).toContain('<template v-if="state !== \'loading\'">');
    expect(src).not.toContain("!isErrorState && state !== 'loading'");
    // 错误面板改为独立 v-if，与工具栏并存（不再被 v-else-if 链互斥）；
    // 171 T3 加严：面板还须处于错误态（成功/空态后残留 errorInfo 不得继续盖版）
    expect(src).toContain('<div v-if="errorInfo && isErrorState" class="graph-error-panel">');
    expect(src).not.toContain('<div v-else-if="errorInfo" class="graph-error-panel">');
  });

  it("gives graph overview its own 30s timeout (global is 10s)", () => {
    const api = source("src/api/asset.ts");
    const overviewFn = api.slice(api.indexOf("getGraphOverview"));
    expect(overviewFn.slice(0, 900)).toContain("timeout: 30000");
  });

  it("downgrades to system level at most once per session", () => {
    expect(shouldDowngradeOverview("schema", false)).toBe(true);
    expect(shouldDowngradeOverview("object", false)).toBe(true);
    expect(shouldDowngradeOverview("field", false)).toBe(true);
    // system 已是最低层级；已降过不再降（防重试死循环）
    expect(shouldDowngradeOverview("system", false)).toBe(false);
    expect(shouldDowngradeOverview("schema", true)).toBe(false);
    expect(shouldDowngradeOverview("system", true)).toBe(false);
  });

  it("loadData wires the pure decision and resets eligibility on manual retry/reset", () => {
    const src = source("src/views/asset/graph/index.vue");
    expect(src).toContain("shouldDowngradeOverview(overviewLevel.value, overviewDowngraded)");
    expect(src).toContain("已自动降级到业务系统层重试");
    // 手动重试/重置恢复降级资格（两处；另有声明处初始化）
    const resets = src.match(/overviewDowngraded = false; \/\/ 169 G2：手动/g) || [];
    expect(resets.length).toBe(2);
    expect(src).toContain("let overviewDowngraded = false;");
  });

  it("starts explore from a pure physical-table neighborhood", () => {
    const src = source("src/views/asset/graph/index.vue");
    expect(src).toContain('.filter(id => id.split("|").length === 5)');
    expect(src).toContain("include: heldPhysicalKeys");
    expect(src).toContain("graphData.value = response.data;");
    expect(src).toContain("exploreState = createExploreState(response.data);");
    expect(src).not.toContain("include: graphData.value.nodes.map(node => node.id)");
  });
});
