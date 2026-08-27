import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import assetRoute from "@/router/modules/asset";
import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import { parseParameterObject } from "@/views/ops/sql-workbench/contracts";
import OverviewPanel from "@/views/dict/medical/components/OverviewPanel.vue";

const dictApi = vi.hoisted(() => ({
  getMedicalCodeSets: vi.fn(),
  getMedicalMappings: vi.fn(),
  getMedicalPushConfig: vi.fn()
}));

vi.mock("@/api/dict", () => dictApi);

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

describe("plan146 stage A", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("A1 removes the dead candidate page/API and preserves redirect query", () => {
    expect(existsSync(resolve(process.cwd(), "src/views/asset/candidates/index.vue"))).toBe(false);
    const apiSource = source("src/api/asset.ts");
    expect(apiSource).not.toContain("getCandidates");
    expect(apiSource).not.toContain("promoteCandidate");
    expect(apiSource).not.toContain("rejectCandidate");

    const candidateRoute = (assetRoute as any).children.find((route: any) => route.name === "AssetCandidates");
    const redirect = candidateRoute.redirect({ query: { from: "A", to: "B" } });
    expect(candidateRoute.meta.showLink).toBe(false);
    expect(redirect).toEqual({
      path: "/asset/relation-review",
      query: { from: "A", to: "B", class: "candidate" }
    });
  });

  it("A2 removes permission demo assets and stale permission codes", () => {
    expect(existsSync(resolve(process.cwd(), "src/views/permission/button/index.vue"))).toBe(false);
    expect(existsSync(resolve(process.cwd(), "src/views/permission/page/index.vue"))).toBe(false);
    expect(source("mock/login.ts")).not.toContain("permission:btn:");
    expect(source("src/utils/sso.ts")).not.toContain("/permission/page/index");
  });

  it("A3 keeps layered SVG layout distinct from circular and removes dead helpers", async () => {
    const nodes = [
      { id: "S|A||ONE|T1", label: "T1", schema_name: "ONE", table_name: "T1" },
      { id: "S|A||TWO|T2", label: "T2", schema_name: "TWO", table_name: "T2" }
    ];
    const layered = mount(RelationGraph, {
      props: { nodes, edges: [], layoutMode: "layered", groupBy: "schema" } as any,
      global: { plugins: [ElementPlus] }
    });
    await flushPromises();
    expect(layered.findAll("g.group-band")).toHaveLength(2);
    expect(source("src/views/asset/components/RelationGraph.vue")).not.toContain("function buildForce");
    expect(source("src/views/asset/tables/index.vue").match(/@media \(max-width: 1100px\)/g)).toHaveLength(1);
    layered.unmount();
  });

  it("A4 rejects invalid or non-object parameter JSON", () => {
    expect(parseParameterObject('{"id":1}')).toEqual({ id: 1 });
    expect(() => parseParameterObject("[]")).toThrow("参数 JSON 必须是对象");
    expect(() => parseParameterObject("not-json")).toThrow();
    const workbench = source("src/views/ops/sql-workbench/index.vue");
    expect(workbench).not.toContain("write_allowed: true");
    expect(workbench).toContain("目标数据库加载失败");
  });

  it("A5 loads diagnosis/operation statistics and the real push_enabled field", async () => {
    dictApi.getMedicalCodeSets.mockImplementation(({ category_code }: any) =>
      Promise.resolve({ data: category_code === "diagnosis" ? [{}, {}] : [{}] })
    );
    dictApi.getMedicalMappings.mockImplementation(({ category_code }: any) =>
      Promise.resolve({ data: { total: category_code === "diagnosis" ? 12 : 7, items: [] } })
    );
    dictApi.getMedicalPushConfig.mockResolvedValue({ data: { push_enabled: true, enabled: false } });

    const wrapper = mount(OverviewPanel, { global: { plugins: [ElementPlus] } });
    await flushPromises();
    expect(wrapper.text()).toContain("诊断编码体系");
    expect(wrapper.text()).toContain("映射关系 12 条");
    expect(wrapper.text()).toContain("手术编码体系");
    expect(wrapper.text()).toContain("映射关系 7 条");
    expect(wrapper.text()).toContain("已开启");
    expect(dictApi.getMedicalCodeSets).toHaveBeenCalledWith({ category_code: "operation" });
    wrapper.unmount();
  });
});
