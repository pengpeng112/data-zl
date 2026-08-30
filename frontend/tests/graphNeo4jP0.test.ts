import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { collapseExpansion, createExploreState, mergeExpansion } from "@/views/asset/graph/graphExploreState";
import type { GraphData } from "@/api/asset";

const node = (id: string) => ({ id, physical_key: id, label: id });
const edge = (id: string, source: string, target: string) => ({ id, source, target, relation_type: "formal", confidence: "A" });
const graph = (nodes: string[], edges: Array<[string, string, string]>): GraphData => ({
  nodes: nodes.map(node), edges: edges.map(item => edge(...item))
});
const source = (relative: string) => readFileSync(resolve(process.cwd(), relative), "utf8");

describe("Neo4j 式图谱 P0 状态契约", () => {
  it("增量展开按节点和边 ID 去重", () => {
    const base = graph(["a"], []);
    const state = createExploreState(base);
    const result = mergeExpansion(base, graph(["a", "b"], [["ab", "a", "b"]]), "a", state);
    expect(result.nodes.map(item => item.id)).toEqual(["a", "b"]);
    expect(result.edges).toHaveLength(1);
  });

  it("重复双击展开保持幂等", () => {
    const base = graph(["a"], []);
    const state = createExploreState(base);
    const once = mergeExpansion(base, graph(["a", "b"], [["ab", "a", "b"]]), "a", state);
    expect(mergeExpansion(once, graph(["a", "b"], [["ab", "a", "b"]]), "a", state)).toBe(once);
  });

  it("双中心共享邻域折叠其一不误删", () => {
    const base = graph(["a", "c"], []);
    const state = createExploreState(base);
    const first = mergeExpansion(base, graph(["b"], [["ab", "a", "b"]]), "a", state);
    const second = mergeExpansion(first, graph(["b"], [["cb", "c", "b"]]), "c", state);
    const collapsed = collapseExpansion(second, "a", state);
    expect(collapsed.nodes.some(item => item.id === "b")).toBe(true);
    expect(collapsed.edges.some(item => item.id === "cb")).toBe(true);
  });

  it("保护选中节点不被折叠删除", () => {
    const base = graph(["a"], []);
    const state = createExploreState(base);
    const expanded = mergeExpansion(base, graph(["b"], [["ab", "a", "b"]]), "a", state);
    expect(collapseExpansion(expanded, "a", state, ["b"]).nodes.some(item => item.id === "b")).toBe(true);
  });

  it("知识图谱绑定 force，layered 仅为预设坐标", () => {
    const text = source("src/views/asset/components/AdvancedRelationGraph.vue");
    expect(text).toContain('layoutMode: "force"');
    expect(text).toContain('props.layoutMode === "layered"');
    expect(text).toContain('type: "force"');
  });

  it("双击判定为 250ms 且提供 Enter 等价入口", () => {
    const text = source("src/views/asset/components/AdvancedRelationGraph.vue");
    expect(text).toContain("<= 250");
    expect(text).toContain('@keydown.enter="activateSelected"');
  });

  it("工具栏统一搜索并将布局收进显示菜单", () => {
    const text = source("src/views/asset/components/GraphToolbar.vue");
    expect(text).toContain("搜索并聚焦");
    expect(text).toContain("高级筛选");
    expect(text).toContain('command="force"');
  });

  it("Inspector 固定布局且 SQL 仅显示 hash 与摘要", () => {
    const text = source("src/views/asset/components/GraphInspector.vue");
    expect(text).toContain("SQL Hash");
    expect(text).toContain("sql_snippet");
    expect(text).not.toContain("join_condition");
  });
});
