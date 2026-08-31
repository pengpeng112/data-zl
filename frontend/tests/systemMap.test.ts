import "./helpers/memoryLocalStorage";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { createPinia } from "pinia";

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn() })
}));
vi.mock("@/router/index", () => ({ router: {} }));

const api = vi.hoisted(() => ({
  getSummary: vi.fn(),
  listValueDomains: vi.fn(),
  getAuditLogsSummary: vi.fn()
}));
vi.mock("@/api/asset", () => ({
  getDashboardSummary: api.getSummary,
  listValueDomains: api.listValueDomains
}));
vi.mock("@/api/ops", () => ({ getAuditLogsSummary: api.getAuditLogsSummary }));

import assetRoute from "@/router/modules/asset";
import SystemMap from "@/views/asset/system-map/index.vue";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

beforeEach(() => {
  vi.clearAllMocks();
  api.getSummary.mockResolvedValue({
    data: {
      assets: { tables: 12702, columns: 65742, relations: 1329, domains: 8 },
      systems: 20,
      sources_total: 22,
      quality_rules: 36,
      quality_findings_open: 5,
      metadata_snapshots: 12,
      relation_by_confidence: [
        { name: "A", count: 400 },
        { name: "B", count: 600 },
        { name: "C", count: 329 }
      ]
    }
  });
  api.listValueDomains.mockResolvedValue({ data: { total: 61, items: [] } });
  api.getAuditLogsSummary.mockResolvedValue({ data: { total: 24680 } });
});

function mountPage() {
  return mount(SystemMap, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body
  });
}

describe("system-map: 数据资产系统图（六步治理链路）", () => {
  it("route registered under 数据资产 with asset.overview.view", () => {
    const child = (assetRoute as any).children.find((r: any) => r.path === "/asset/system-map");
    expect(child).toBeTruthy();
    expect(child.meta.auths).toEqual(["asset.overview.view"]);
    expect(child.meta.showLink).toBe(true);
    expect(child.meta.title).toBe("数据资产系统图");
  });

  it("renders six governance steps and real KPI numbers from APIs", async () => {
    const w = mountPage();
    await flushPromises();
    const text = w.text();
    // 六步链路标题
    for (const name of ["资产可知", "关系可信", "标准统一", "质控可检", "过程可溯", "结果可复用"]) {
      expect(text).toContain(name);
    }
    // KPI 与链路内真实数字（getSummary/值域/审计 mock 值）
    expect(text).toContain("12,702");
    expect(text).toContain("65,742");
    expect(text).toContain("1,329");
    expect(text).toContain("400"); // A 级关系数
    expect(text).toContain("36"); // 质量规则
    expect(text).toContain("61"); // 确认值域
    expect(text).toContain("24,680"); // 审计留痕
    // 口径横幅
    expect(text).toContain("可信 · 可解释 · 可追溯 · 可复用");
    w.unmount();
  });

  it("steps carry platform module jump targets", () => {
    const src = source("src/views/asset/system-map/index.vue");
    for (const path of ["/asset/tables", "/asset/graph", "/value-domains", "/asset/quality", "/asset/admin", "/asset/queries"]) {
      expect(src).toContain(`"${path}"`);
    }
  });

  it("page mounts without console errors when APIs fail (empty-safe)", async () => {
    api.getSummary.mockRejectedValue({ response: { data: { detail: "服务不可用" } } });
    api.listValueDomains.mockRejectedValue({});
    api.getAuditLogsSummary.mockRejectedValue({});
    const w = mountPage();
    await flushPromises();
    expect(w.text()).toContain("资产可知");
    expect(w.find(".graph-error-panel").exists()).toBe(false);
    w.unmount();
  });
});
