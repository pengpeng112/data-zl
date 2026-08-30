import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// 161 P0-2：防回归扫描（round-2 核查 P1——筛选事件把选中值当页码导致后端 422，筛选整页报废）。
// 判定规则：模板事件首参是"选中值/事件对象"必须改 doSearch 或箭头包装；首参是"页码"（current-change）保留。
const RELATION_REVIEW = "src/views/asset/relation-review/index.vue";

const FORBIDDEN_BINDINGS = [
  '@change="loadRelations"',
  '@size-change="loadRelations"',
  '@keyup.enter="loadRelations"',
  '@clear="loadRelations"'
];

describe("plan161 relation-review template bindings", () => {
  const source = readFileSync(resolve(process.cwd(), RELATION_REVIEW), "utf8");

  it("does not bind filter/pager events directly to the loadData alias", () => {
    for (const binding of FORBIDDEN_BINDINGS) {
      expect(source).not.toContain(binding);
    }
  });

  it("wires filters to doSearch and keeps page-number semantics on the pager", () => {
    expect(source).toContain('@change="doSearch"');
    expect(source).toContain('@keyup.enter="doSearch"');
    expect(source).toContain('@clear="doSearch"');
    expect(source).toContain('@current-change="loadRelations"');
    expect(source).toContain('@size-change="() => loadRelations(1)"');
  });
});
