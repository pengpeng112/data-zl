import "./helpers/memoryLocalStorage";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { storageLocal } from "@pureadmin/utils";

vi.mock("vue-router", () => ({ useRoute: () => ({ query: {} }), useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/router/index", () => ({ router: {} }));

import { filterNoPermissionTree } from "@/router/utils";
import { userKey } from "@/utils/auth";
import assetRoute from "@/router/modules/asset";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** 171 R3①：Inspector 中文名 displayName 兜底链契约（169 G5 修复回归锁）。 */
describe("plan171 R3 Inspector displayName fallback chain", () => {
  const src = source("src/views/asset/components/GraphInspector.vue");

  it("template renders displayName, never the raw label (object would dump JSON)", () => {
    expect(src).toContain("{{ displayName }}");
    expect(src).not.toMatch(/\{\{\s*node\.label\s*\}\}/);
  });

  it("displayName priority: table_name_cn → string label → label.formatter → display_id", () => {
    const start = src.indexOf("const displayName");
    const end = src.indexOf("watch(", start);
    const block = src.slice(start, end);
    expect(block).toContain("node.table_name_cn");
    expect(block).toContain('typeof label === "string"');
    expect(block).toContain('typeof label.formatter === "string"');
    expect(block).toContain('node.display_id || "-"');
    // 兜底顺序：中文名必须最先判，display_id 只能作最后兜底
    expect(block.indexOf("table_name_cn")).toBeLessThan(block.indexOf("typeof label"));
    expect(block.lastIndexOf("display_id")).toBeGreaterThan(block.indexOf("label.formatter"));
  });
});

/** 171 R3②：system-map 菜单可见性——filterNoPermissionTree 功能级验证（T3 第⑥查的测试面）。 */
describe("plan171 R3 system-map menu visibility (filterNoPermissionTree)", () => {

  const seed = (permissions: string[]) => {
    storageLocal().setItem(userKey, {
      accessToken: "",
      expires: 4102444800000,
      refreshToken: "",
      username: "t",
      roles: ["asset_viewer"],
      permissions
    });
    return filterNoPermissionTree([assetRoute as any]).find((r: any) => r.path === "/asset");
  };

  it("platform-style wildcard permission sees the menu entry", () => {
    const asset = seed(["*:*:*"]);
    expect(asset?.children.some((c: any) => c.path === "/asset/system-map")).toBe(true);
  });

  it("exactly asset.overview.view is enough (仅该权限用户可见)", () => {
    const asset = seed(["asset.overview.view"]);
    expect(asset?.children.some((c: any) => c.path === "/asset/system-map")).toBe(true);
  });

  it("unrelated permission codes hide the menu entry", () => {
    const asset = seed(["dict.sync.view", "asset.tables.view"]);
    expect(asset?.children.some((c: any) => c.path === "/asset/system-map")).toBe(false);
  });

  it("empty permission list hides the menu entry", () => {
    const asset = seed([]);
    expect(asset?.children.some((c: any) => c.path === "/asset/system-map")).toBe(false);
  });
});

/** 171 T3② 根因修复回归锁：搜索聚焦后不得误报错误面板（169 域 graph/index.vue）。 */
describe("plan171 R3 graph false-error-panel regression locks", () => {
  const src = source("src/views/asset/graph/index.vue");

  it("error panel renders only in error state (stale errorInfo cannot cover success)", () => {
    expect(src).toMatch(/v-if="errorInfo && isErrorState"/);
    expect(src).not.toMatch(/v-if="errorInfo"/);
  });

  it("globalSearch isolates canvas focusNode failure from api_error classification", () => {
    // focusNode 必须被独立 try 包裹（视觉增强失败≠接口错误）
    expect(src).toMatch(/try\s*\{\s*await graphRef\.value\?\.focusNode\?\.\(physicalKey\);[\s\S]{0,200}?\}\s*catch\s*\{/);
  });
});
