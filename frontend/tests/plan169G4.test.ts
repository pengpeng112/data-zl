import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";

import RelationGraph from "@/views/asset/components/RelationGraph.vue";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

function makeNode(id: string, nameCn: string, group = "HIS") {
  return {
    id,
    physical_key: id,
    display_id: id,
    label: id.split("|").pop() || id,
    system_code: group,
    schema_name: group,
    table_name: id,
    table_name_cn: nameCn
  };
}

/** 169 G4：SVG 降级布局——explore 走 radial；分层网格行距装得下多行标签。 */
describe("plan169 G4 SVG fallback layout", () => {
  it("routes explore with a center table to radial instead of the grid", () => {
    const src = source("src/views/asset/components/RelationGraph.vue");
    expect(src).toContain(
      'props.layoutMode === "force" && props.viewMode === "explore" && props.centerTable'
    );
    expect(src).toContain("return buildRadial(data.nodes, data.edges);");
    // 行距动态公式在位（固定 92 不再硬编码为唯一值）
    expect(src).toMatch(/Math\.max\(92, 46 \+ maxLines \* 15 \+ 24\)/);
  });

  it("gives multi-line labels enough vertical room (row gap grows with label lines)", async () => {
    // 5 行中文标签（每行 7 字上限内）——round-3 P3：固定 92px 会跨行压叠
    const longCn = "一二三四五六七\n八九一二三四五\n六七八九一二三\n四五六七八九一\n二三四五六七";
    const nodes = [
      makeNode("HIS|s||M|T1", longCn),
      makeNode("HIS|s||M|T2", longCn),
      makeNode("HIS|s||M|T3", longCn)
    ];
    const wrapper = mount(RelationGraph, {
      props: { nodes, edges: [], layoutMode: "force", groupBy: "schema" } as any,
      global: { plugins: [ElementPlus] }
    });
    await flushPromises();
    const ys = wrapper
      .findAll(".node-layer > g")
      .map(g => {
        const t = g.attributes("transform") || "";
        const m = t.match(/translate\(([\d.]+)[,\s]+([\d.]+)\)/) || t.match(/,\s*([\d.]+)\)/);
        return m ? Number(m[2]) : Number.NaN;
      })
      .filter(y => !Number.isNaN(y))
      .sort((a, b) => a - b);
    expect(ys.length).toBe(3);
    // 相邻 y 差 >= 150（5 行标签：46+5*15+24=145，向上取整验证 >=140 防浮点）
    const gaps = [ys[1] - ys[0], ys[2] - ys[1]];
    for (const gap of gaps) {
      expect(gap).toBeGreaterThanOrEqual(140);
    }
    wrapper.unmount();
  });
});
