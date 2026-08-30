import "./helpers/memoryLocalStorage";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { storageLocal } from "@pureadmin/utils";

// B10：不做真实 router mount——router/utils ↔ router/index 存在导入环，
// 被 SSR 变换放大成 TDZ；filterNoPermissionTree 不依赖 router 单例，mock 掉。
vi.mock("@/router/index", () => ({ router: {} }));

import governanceRoute from "@/router/modules/governance";
import qualityRoute from "@/router/modules/quality";
import { filterNoPermissionTree } from "@/router/utils";
import { userKey } from "@/utils/auth";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** 166 D1 验收：路由 meta.auths 源码断言（plan146 先例，B10 不做真实 router mount）。 */
describe("plan166 D1 route skeleton", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("registers /value-domains under 数据治理 group with dot-form value_domain.read", () => {
    const src = source("src/router/modules/governance.ts");
    expect(src).toContain('title: "数据治理"');
    expect(src).toContain('auths: ["value_domain.read"]');
    expect(src).not.toContain("value_domain:"); // B3：点号权限码
    const child = (governanceRoute as any).children.find((r: any) => r.path === "/value-domains");
    expect(child.meta.auths).toEqual(["value_domain.read"]);
    expect(child.meta.showLink).toBe(true);
  });

  it("registers /probe-findings under 质量管理 group with dot-form probe.finding.read", () => {
    const src = source("src/router/modules/quality.ts");
    expect(src).toContain('title: "质量管理"');
    expect(src).toContain('auths: ["probe.finding.read"]');
    expect(src).not.toContain("probe.finding:"); // B3：点号权限码
    const child = (qualityRoute as any).children.find((r: any) => r.path === "/probe-findings");
    expect(child.meta.auths).toEqual(["probe.finding.read"]);
    expect(child.meta.showLink).toBe(true);
  });

  it("keeps the probe API layer in src/api/probe.ts and value-domain calls in src/api/asset.ts", () => {
    // B11：新接口进 src/api/；视图层禁直打 http.request（源码断言在 D2/D3 组件测试叠加）
    expect(resolve(process.cwd(), "src/api/probe.ts")).toBeDefined();
    const probeSrc = source("src/api/probe.ts");
    expect(probeSrc).toContain('"/api/v1/probe-findings"');
    expect(probeSrc).toContain('`/api/v1/probe-findings/${id}/transition`');
    expect(probeSrc).toContain('"/api/v1/probe-findings/export"');
    const assetSrc = source("src/api/asset.ts");
    expect(assetSrc).toContain('"/api/v1/value-domains"');
    expect(assetSrc).toContain('`/api/v1/value-domains/${domainId}/versions`');
    expect(assetSrc).toContain('`/api/v1/value-domains/${domainId}/resolve-conflict`');
    expect(assetSrc).toContain('"/api/v1/value-domains/export"');
  });

  it("filterNoPermissionTree gates the two new menus by dot-form codes (B10 pure function)", () => {
    const seed = (permissions: string[]) =>
      storageLocal().setItem(userKey, {
        accessToken: "",
        refreshToken: "",
        expires: 0,
        username: "t",
        nickname: "t",
        roles: [],
        permissions
      });

    seed(["value_domain.read"]);
    let tree = filterNoPermissionTree([governanceRoute, qualityRoute] as any);
    expect(tree.map((r: any) => r.name)).toEqual(["Governance"]);

    seed(["probe.finding.read"]);
    tree = filterNoPermissionTree([governanceRoute, qualityRoute] as any);
    expect(tree.map((r: any) => r.name)).toEqual(["QualityHub"]);

    seed(["*:*:*"]);
    tree = filterNoPermissionTree([governanceRoute, qualityRoute] as any);
    expect(tree.map((r: any) => r.name).sort()).toEqual(["Governance", "QualityHub"]);

    seed(["asset.table.view"]);
    tree = filterNoPermissionTree([governanceRoute, qualityRoute] as any);
    expect(tree).toEqual([]);
  });
});
