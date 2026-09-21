// 186 R0：真实模块导入导出路由清单（path/name/title/parent/showLink/roles/auths/redirect）
// 输出到 开发起步包/output_r186/r0_route_inventory.json，作为菜单迁移基线。
import { describe, it, expect } from "vitest";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

import homeRoutes from "@/router/modules/home";
import assetRoutes from "@/router/modules/asset";
import opsRoutes from "@/router/modules/ops";
import identityRoutes from "@/router/modules/identity";
import dictRoutes from "@/router/modules/dict";
import metadataRoutes from "@/router/modules/metadata";
import governanceRoutes from "@/router/modules/governance";
import qualityRoutes from "@/router/modules/quality";
import catalogRoutes from "@/router/modules/catalog";
import standardsRoutes from "@/router/modules/standards";
import queryRoutes from "@/router/modules/query";
import remainingRoutes from "@/router/modules/remaining";

type AnyRoute = Record<string, any>;

function moduleList(mod: AnyRoute | AnyRoute[]): AnyRoute[] {
  return Array.isArray(mod) ? mod : [mod];
}

interface FlatRoute {
  parent: string;
  parentTitle: string;
  path: string;
  name: string;
  title: string;
  showLink: boolean;
  roles?: string[];
  auths?: string[];
  redirect?: string | unknown;
  activePath?: string;
  hasComponent: boolean;
}

function flatten(mod: AnyRoute): FlatRoute[] {
  const out: FlatRoute[] = [];
  for (const child of mod.children ?? []) {
    out.push({
      parent: mod.path,
      parentTitle: mod.meta?.title ?? "",
      path: child.path,
      name: child.name,
      title: child.meta?.title ?? "",
      showLink: child.meta?.showLink !== false,
      roles: child.meta?.roles,
      auths: child.meta?.auths,
      redirect: typeof child.redirect === "string" ? child.redirect : child.redirect ? "(dynamic)" : undefined,
      activePath: child.meta?.activePath,
      hasComponent: Boolean(child.component)
    });
  }
  return out;
}

describe("plan186 R0 route inventory", () => {
  it("dumps full route table without duplicate name/path", () => {
    const modules = [
      homeRoutes,
      catalogRoutes,
      standardsRoutes,
      qualityRoutes,
      queryRoutes,
      identityRoutes,
      opsRoutes,
      assetRoutes,
      dictRoutes,
      metadataRoutes,
      governanceRoutes
    ];
    const rows: FlatRoute[] = [];
    for (const m of modules) for (const r of moduleList(m)) rows.push(...flatten(r));

    const names = rows.map(r => r.name).filter(Boolean);
    const paths = rows.map(r => r.path);
    expect(new Set(names).size).toBe(names.length);
    expect(new Set(paths).size).toBe(paths.length);

    const visible = rows.filter(r => r.showLink);
    const payload = {
      generated_at: new Date().toISOString(),
      visible_leaf_count: visible.length,
      total_leaf_count: rows.length,
      visible_by_parent: visible.reduce<Record<string, number>>((acc, r) => {
        acc[r.parent] = (acc[r.parent] ?? 0) + 1;
        return acc;
      }, {}),
      remaining_routes: moduleList(remainingRoutes as any).map(r => ({
        path: r.path,
        name: r.name ?? "",
        title: r.meta?.title ?? ""
      })),
      routes: rows
    };
    const outPath = resolve(
      __dirname,
      "../../开发起步包/output_r186/r0_route_inventory.json"
    );
    writeFileSync(outPath, JSON.stringify(payload, null, 2), "utf-8");
    expect(visible.length).toBeGreaterThan(0);
  });
});
