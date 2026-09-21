import { describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { defineComponent, h, nextTick } from "vue";
import ElementPlus from "element-plus";
import LineagePage from "@/views/asset/lineage/index.vue";

const mockApi = vi.hoisted(() => ({
  getGraphOptions: vi.fn(),
  getGraphFilterOptions: vi.fn(),
  getTables: vi.fn(),
  searchGraphTables: vi.fn(),
  getImpactAnalysis: vi.fn(),
  getViewDependencies: vi.fn()
}));

const mockRoute = vi.hoisted(() => ({ query: {} as Record<string, unknown> }));

vi.mock("vue-router", () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() })
}));

vi.mock("@/api/asset", () => mockApi);

function stub(name: string) {
  return defineComponent({ name, setup: (_, { slots }) => () => h("div", { class: name }, slots.default?.()) });
}

function mountPage() {
  return mount(LineagePage, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        RePageHeader: stub("RePageHeader"),
        ReToolbar: stub("ReToolbar"),
        ReStatCard: stub("ReStatCard"),
        ReEmptyState: stub("ReEmptyState")
      }
    }
  });
}

describe("血缘与影响表选择", () => {
  it("用资产库下拉代替纯手敲表名", async () => {
    mockApi.getGraphOptions.mockResolvedValue({
      data: {
        systems: ["HIS"],
        sources: [],
        schemas: ["HIS"],
        domains: [],
        system_options: [{ value: "HIS", label: "HIS" }],
        schema_options: [{ value: "HIS", label: "HIS" }],
        view_modes: []
      }
    });
    mockApi.getGraphFilterOptions.mockResolvedValue({ data: { items: [{ value: "HIS", label: "HIS" }] } });
    mockApi.getTables.mockResolvedValue({
      data: { items: [{ schema_name: "HIS", table_name: "PAT_VISIT", table_name_cn: "患者就诊记录" }], total: 1 }
    });
    mockApi.searchGraphTables.mockResolvedValue({ data: { items: [], total: 0, query: "" } });
    mockApi.getViewDependencies.mockResolvedValue({ data: { items: [], total: 0 } });
    mockApi.getImpactAnalysis.mockResolvedValue({ data: { table: "HIS.PAT_VISIT", referencing_views: [], dependent_relations: [], total_views: 0, total_relations: 0 } });

    const wrapper = mountPage();
    await flushPromises();
    await nextTick();

    expect(wrapper.find(".system-select").exists()).toBe(true);
    expect(wrapper.find(".schema-select").exists()).toBe(true);
    expect(wrapper.find(".table-select").exists()).toBe(true);
    expect(wrapper.find("input[placeholder='例如 HIS.PAT_VISIT']").exists()).toBe(false);
    expect(wrapper.text()).toContain("从资产库带出");
    wrapper.unmount();
  });
});

describe("血缘影响分析（typed 分层展示 + 依赖联动）", () => {
  it("影响结果按下游/上游分跳展示，依赖表支持行内分析入口", async () => {
    mockRoute.query = { table: "HIS.PAT_VISIT" };
    mockApi.getGraphOptions.mockResolvedValue({
      data: {
        systems: ["HIS"],
        sources: [],
        schemas: ["HIS"],
        domains: [],
        system_options: [{ value: "HIS", label: "HIS" }],
        schema_options: [{ value: "HIS", label: "HIS" }],
        view_modes: []
      }
    });
    mockApi.getGraphFilterOptions.mockResolvedValue({ data: { items: [] } });
    mockApi.getTables.mockResolvedValue({ data: { items: [], total: 0 } });
    mockApi.searchGraphTables.mockResolvedValue({ data: { items: [], total: 0, query: "" } });
    // typed 血缘影响结果（138 结构）：表 → 视图（1 跳） → 查询（2 跳）
    mockApi.getImpactAnalysis.mockResolvedValue({
      data: {
        object_key: "HIS|HIS|raw|HIS|PAT_VISIT|table",
        direction: "downstream",
        downstream_nodes: [
          "HIS|HIS|raw|CORE2DB|BL_JZLGBL|view",
          "HIS|HIS|raw|QUERY|Q_001|query"
        ],
        upstream_nodes: [],
        downstream_edges: [
          { from: "HIS|HIS|raw|HIS|PAT_VISIT|table", to: "HIS|HIS|raw|CORE2DB|BL_JZLGBL|view", edge_type: "reads_from", from_type: "table", to_type: "view", hops: 1 },
          { from: "HIS|HIS|raw|CORE2DB|BL_JZLGBL|view", to: "HIS|HIS|raw|QUERY|Q_001|query", edge_type: "reads_from", from_type: "view", to_type: "query", hops: 2 }
        ],
        upstream_edges: [],
        total_edges: 2
      }
    });
    mockApi.getViewDependencies.mockResolvedValue({
      data: {
        items: [
          { id: 1, view_name: "CORE2DB_BL_JZLGBL", referenced_schema: "CORE2DB", referenced_table: "PAT_VISIT", alias: "PV", source_file: null },
          { id: 2, view_name: "CORE2DB_BL_JZLGBL", referenced_schema: "CORE2DB", referenced_table: "DATA_API_PATIENT", alias: null, source_file: null }
        ],
        total: 2
      }
    });

    const wrapper = mountPage();
    await flushPromises();
    await nextTick();

    const text = wrapper.text();
    // typed 统计卡与目标回显（ReStatCard 为 stub，label 不渲染，检查容器存在）
    expect(wrapper.find(".impact-stats").exists()).toBe(true);
    expect(text).toContain("分析对象：");
    // 按跳分层：直接依赖 + 类型中文标签 + 解析后的 schema.object 名
    expect(text).toContain("直接依赖（1 跳）");
    expect(text).toContain("间接依赖（2 跳）");
    expect(text).toContain("CORE2DB.BL_JZLGBL");
    expect(text).toContain("视图");
    expect(text).toContain("查询");
    // 依赖表：视图名 + schema 副标题 + 两张被引用表 + 行内操作
    expect(text).toContain("CORE2DB_BL_JZLGBL");
    expect(text).toContain("PAT_VISIT");
    expect(text).toContain("DATA_API_PATIENT");
    expect(wrapper.find(".view-schema").exists()).toBe(true);
    expect(wrapper.findAll(".table-link").length).toBe(2);
    expect(text).toContain("分析影响");
    wrapper.unmount();
  });
});
