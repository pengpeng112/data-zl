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

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() })
}));

vi.mock("@/api/asset", () => mockApi);

function stub(name: string) {
  return defineComponent({ name, setup: (_, { slots }) => () => h("div", { class: name }, slots.default?.()) });
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

    const wrapper = mount(LineagePage, {
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
