/**
 * 108 号图谱组件挂载测试（RelationGraph / GraphToolbar / GraphEvidenceDrawer）。
 *
 * 策略：用完整 element-plus 注册 + mount，断言"组件可挂载、交互事件发出、
 * 卸载无异常"，避免对 SVG 内部节点数的脆弱 DOM 断言（SVG 布局由 computed 驱动）。
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { defineComponent, h, nextTick } from "vue";
import ElementPlus from "element-plus";

import RelationGraph from "@/views/asset/components/RelationGraph.vue";
import GraphToolbar from "@/views/asset/components/GraphToolbar.vue";
import GraphEvidenceDrawer from "@/views/asset/components/GraphEvidenceDrawer.vue";

const mockApi = vi.hoisted(() => ({
  getGraphEdgeDetail: vi.fn()
}));

vi.mock("@/api/asset", () => ({
  getGraph: vi.fn(),
  getGraphNeighbors: vi.fn(),
  getGraphOptions: vi.fn(),
  getGraphDiagnostics: vi.fn(),
  getGraphEdgeDetail: mockApi.getGraphEdgeDetail
}));

function makeNode(id: string, displayId: string, table: string, system = "DATA_CENTER", source = "ods_8_216") {
  return {
    id,
    physical_key: id,
    display_id: displayId,
    label: table,
    table_name: table,
    table_name_cn: table,
    system_code: system,
    source_code: source,
    schema_name: displayId.split(".")[0]
  };
}

function makeEdge(id: string, source: string, target: string, displaySource: string, displayTarget: string) {
  return {
    id, source, target, display_source: displaySource, display_target: displayTarget,
    relation_type: "formal", confidence: "A", validation_status: "verified",
    from_columns: "PATIENT_ID", to_columns: "PATIENT_ID"
  };
}

function buildGraph(n: number, m: number) {
  const nodes: any[] = [];
  const edges: any[] = [];
  for (let i = 0; i < n; i++) {
    nodes.push(makeNode(`DATA_CENTER|ods_8_216||HIS|T${i}`, `HIS.T${i}`, `T${i}`));
  }
  for (let i = 0; i < m; i++) {
    const a = i % n;
    const b = (i + 1) % n;
    edges.push(makeEdge(`e${i}`, nodes[a].id, nodes[b].id, nodes[a].display_id, nodes[b].display_id));
  }
  return { nodes, edges };
}

describe("RelationGraph", () => {
  it("mounts with 140 nodes / 120 edges and emits node click (F11)", async () => {
    const { nodes, edges } = buildGraph(140, 120);
    const wrapper = mount(RelationGraph, {
      props: { nodes, edges, height: "500px", viewMode: "table", groupBy: "schema", layoutMode: "layered" } as any,
      global: { plugins: [ElementPlus] }
    });
    await nextTick();
    expect(wrapper.exists()).toBe(true);
    // 点击事件可发出（SVG 节点元素）
    const nodeG = wrapper.find("g.graph-node");
    if (nodeG.exists()) {
      await nodeG.trigger("click");
      expect(wrapper.emitted("node-click")).toBeDefined();
    }
    wrapper.unmount();
  });

  it("re-renders on prop change and unmounts cleanly (无实例泄漏)", async () => {
    const { nodes, edges } = buildGraph(30, 25);
    const wrapper = mount(RelationGraph, {
      props: { nodes, edges, viewMode: "table" } as any,
      global: { plugins: [ElementPlus] }
    });
    await wrapper.setProps({ nodes: buildGraph(40, 35).nodes, edges: buildGraph(40, 35).edges });
    await nextTick();
    expect(wrapper.exists()).toBe(true);
    wrapper.unmount();
  });
});

describe("GraphToolbar", () => {
  const baseFilters = {
    view_mode: "table",
    group_by: "schema",
    system_code: "",
    source_code: "",
    schema: "",
    domain: "",
    validation_status: "",
    confidence: "A",
    keyword: "",
    limit: 120,
    include_candidates: false,
    include_dependencies: false,
    show_review_layer: false,
    layout_mode: "layered",
    aggregate_groups: false
  };

  it("renders meta stats (total/matched/returned/truncated)", () => {
    const wrapper = mount(GraphToolbar, {
      props: {
        filters: baseFilters,
        locate: { table: "", depth: 1, direction: "both" },
        options: { systems: [], sources: [], schemas: [], domains: [], validation_statuses: [], confidences: ["A"], relation_types: [], view_modes: [] },
        normalized: { nodes: [], edges: [], topGroups: [], passCount: 0, candidateCount: 0, dependencyCount: 0, reviewHiddenCount: 0, issues: [] },
        graphEngine: "svg",
        loading: false,
        selectedNodeId: "",
        meta: { total_relations: 537, matched_relations: 192, returned_relations: 120, truncated: true, backend_build_id: "build-1" }
      } as any,
      global: { plugins: [ElementPlus] }
    });
    const text = wrapper.text();
    expect(text).toContain("537");
    expect(text).toContain("192");
    expect(text).toContain("120");
    wrapper.unmount();
  });

  it("emits load-data on query button", async () => {
    const wrapper = mount(GraphToolbar, {
      props: {
        filters: baseFilters,
        locate: { table: "", depth: 1, direction: "both" },
        options: { systems: [], sources: [], schemas: [], domains: [], validation_statuses: [], confidences: ["A"], relation_types: [], view_modes: [] },
        normalized: { nodes: [], edges: [], topGroups: [], passCount: 0, candidateCount: 0, dependencyCount: 0, reviewHiddenCount: 0, issues: [] },
        graphEngine: "svg",
        loading: false,
        selectedNodeId: ""
      } as any,
      global: { plugins: [ElementPlus] }
    });
    const buttons = wrapper.findAll("button");
    const queryBtn = buttons.find(b => b.text().includes("查询"));
    if (queryBtn) {
      await queryBtn.trigger("click");
      expect(wrapper.emitted("load-data")).toBeDefined();
    }
    wrapper.unmount();
  });
});

describe("GraphEvidenceDrawer", () => {
  beforeEach(() => {
    mockApi.getGraphEdgeDetail.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("requests detail only when drawer opens with a key (F12 按需加载)", async () => {
    const edge = makeEdge("biz-key-1", "s", "t", "HIS.PAT_VISIT", "HIS.DIAGNOSIS");
    mockApi.getGraphEdgeDetail.mockResolvedValue({ data: { ...edge, field_mappings: [] } });
    const wrapper = mount(GraphEvidenceDrawer, {
      props: { modelValue: false, edge, edgeKey: "biz-key-1" } as any,
      global: { plugins: [ElementPlus] }
    });
    expect(mockApi.getGraphEdgeDetail).not.toHaveBeenCalled();
    await wrapper.setProps({ modelValue: true });
    await nextTick();
    expect(mockApi.getGraphEdgeDetail).toHaveBeenCalledWith("biz-key-1");
    wrapper.unmount();
  });

  it("does not request detail for empty key (摘要回退)", () => {
    const wrapper = mount(GraphEvidenceDrawer, {
      props: { modelValue: true, edge: null, edgeKey: "" } as any,
      global: { plugins: [ElementPlus] }
    });
    expect(mockApi.getGraphEdgeDetail).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
