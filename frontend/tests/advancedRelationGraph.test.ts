/**
 * 119 号回归测试：AdvancedRelationGraph 的 G6 输入契约。
 *
 * 背景：normalizeGraphData 会把节点 label 覆盖为 echarts 风格对象 {show, formatter, ...}，
 * 组件若直接把它当作 labelText 传给 G6，G6 文本布局对非字符串调用 .split，
 * 抛 "TypeError: xxx.split is not a function"，真实浏览器中图谱整页渲染失败。
 * 该故障无法被 jsdom/类型检查覆盖（需要真实 G6 Canvas），故用 Mock Graph
 * 捕获 setData 输入，断言传入 G6 的每个 labelText 都是字符串。
 */
import { describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";

const mockG6 = vi.hoisted(() => ({
  instances: [] as any[]
}));

vi.mock("@antv/g6", () => {
  class MockGraph {
    data: any = null;
    destroyed = false;
    constructor(public options: any) {
      mockG6.instances.push(this);
    }
    on() {}
    setData(data: any) {
      this.data = data;
    }
    setOptions() {}
    async render() {}
    // 渲染后视口适配（与真实 G6 v5 API 对齐）：fitView + 最小缩放兜底
    async fitView() {}
    async fitCenter() {}
    async zoomTo() {}
    getZoom() {
      return 1;
    }
    resize() {}
    destroy() {
      this.destroyed = true;
    }
  }
  return {
    Graph: MockGraph,
    EdgeEvent: { CLICK: "edge:click" },
    NodeEvent: { CLICK: "node:click" }
  };
});

import AdvancedRelationGraph from "@/views/asset/components/AdvancedRelationGraph.vue";

function makeNode(id: string, displayId: string, table: string) {
  return {
    id,
    physical_key: id,
    display_id: displayId,
    label: table,
    table_name: table,
    table_name_cn: `${table}中文名`,
    system_code: "DATA_CENTER",
    source_code: "ods_8_216",
    schema_name: displayId.split(".")[0]
  };
}

function makeEdge(id: string, source: string, target: string) {
  return {
    id,
    source,
    target,
    display_source: source,
    display_target: target,
    relation_type: "formal",
    confidence: "A",
    validation_status: "verified",
    from_columns: "PATIENT_ID",
    to_columns: "PATIENT_ID"
  };
}

const N1 = "DATA_CENTER|ods_8_216||HIS|PAT_VISIT";
const N2 = "DATA_CENTER|ods_8_216||HIS|PAT_MASTER_INDEX";

async function flushRenderQueue() {
  // 渲染队列 = nextTick + Promise 链，多等几拍确保完成
  for (let i = 0; i < 6; i++) {
    await nextTick();
    await Promise.resolve();
  }
}

describe("AdvancedRelationGraph G6 输入契约（119 回归）", () => {
  it("normalize 后 label 为对象时，传给 G6 的 labelText 必须是字符串", async () => {
    const wrapper = mount(AdvancedRelationGraph, {
      props: {
        nodes: [makeNode(N1, "HIS.PAT_VISIT", "PAT_VISIT"), makeNode(N2, "HIS.PAT_MASTER_INDEX", "PAT_MASTER_INDEX")],
        edges: [makeEdge("biz-key-1", N1, N2)]
      },
      attachTo: document.body
    });
    await flushRenderQueue();

    expect(mockG6.instances.length).toBeGreaterThan(0);
    const graph = mockG6.instances.at(-1);
    expect(graph.data).toBeTruthy();
    expect(graph.data.nodes.length).toBe(2);
    for (const node of graph.data.nodes) {
      expect(typeof node.style.labelText).toBe("string");
      expect(node.style.labelText).not.toBe("[object Object]");
      expect(node.style.labelText.length).toBeGreaterThan(0);
    }
    const label0 = graph.data.nodes[0].style.labelText as string;
    expect(label0.replace(/\n/g, "")).toContain("PAT_VISIT中文名");
    expect(label0.includes("...")).toBe(false);
    expect(label0.includes("…")).toBe(false);
    // 130p2：Neo4j 式圆点节点——标题（caption）置于节点下方
    expect(graph.data.nodes[0].style.labelPlacement).toBe("bottom");
    expect(graph.data.nodes[0].type).toBe("circle");
    // 169 P4：labelMaxLines/labelWordWrap/labelTextOverflow 系死配置已删（G6 不消费，
    // 文本由 formatGraphNodeLabel 预换行）——改为断言死配置不再下发+预换行仍生效
    expect(graph.data.nodes[0].style.labelMaxLines).toBeUndefined();
    expect(graph.data.nodes[0].style.labelWordWrap).toBeUndefined();
    expect(graph.data.nodes[0].style.labelTextOverflow).toBeUndefined();
    expect(label0).toContain("\n");
    expect(graph.data.nodes[0].style.labelFontSize).toBeGreaterThanOrEqual(12);
    expect(graph.options.devicePixelRatio).toBeGreaterThanOrEqual(2);
    expect(wrapper.emitted("render-error")).toBeUndefined();
    wrapper.unmount();
  });

  it("表节点按连字符和语义后缀换行，不把数据表拆开", async () => {
    const wrapper = mount(AdvancedRelationGraph, {
      props: {
        nodes: [
          {
            id: "JHEMR|jhemr||jhemr|blood_transfusion",
            display_id: "jhemr.blood_transfusion",
            label: { show: true, formatter: "病案首页-业务类-输血信息" },
            table_name: "blood_transfusion",
            table_name_cn: "病案首页-业务类-输血信息",
            system_code: "JHEMR",
            schema_name: "jhemr"
          },
          {
            id: "JHEMR|jhemr||jhemr|dc_cda_doctype",
            display_id: "jhemr.dc_cda_doctype",
            label: { show: true, formatter: "新电子病历区数据表" },
            table_name: "dc_cda_doctype",
            table_name_cn: "新电子病历区数据表",
            system_code: "JHEMR",
            schema_name: "jhemr"
          }
        ],
        edges: []
      },
      attachTo: document.body
    });
    await flushRenderQueue();

    const graph = mockG6.instances.at(-1);
    const labels = graph.data.nodes.map((node: any) => node.style.labelText);
    expect(labels).toContain("病案首页\n业务类\n输血信息\nblood_transfusion");
    expect(labels).toContain("新电子病历区\n数据表\ndc_cda_doctype");
    expect(labels.some((label: string) => label.includes("病案首页-业"))).toBe(false);
    expect(labels.some((label: string) => /区数|数\n据表/.test(label))).toBe(false);
    wrapper.unmount();
  });

  it("G6 边使用渲染内唯一 ID，不直接复用后端证据 ID", async () => {
    const wrapper = mount(AdvancedRelationGraph, {
      props: {
        nodes: [makeNode(N1, "HIS.PAT_VISIT", "PAT_VISIT"), makeNode(N2, "HIS.PAT_MASTER_INDEX", "PAT_MASTER_INDEX")],
        edges: [makeEdge("biz-key-1", N1, N2)]
      },
      attachTo: document.body
    });
    await flushRenderQueue();

    const graph = mockG6.instances.at(-1);
    const ids = graph.data.edges.map((edge: any) => edge.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).not.toContain("biz-key-1");
    // 原始关系保留在 data.raw 供证据抽屉使用
    expect(graph.data.edges[0].data.raw.id).toBe("biz-key-1");
    wrapper.unmount();
  });
});
