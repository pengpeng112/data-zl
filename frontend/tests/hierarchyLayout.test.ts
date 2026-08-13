/**
 * 129号：分层树状布局算法契约测试。
 * 包含边（relation_type=hierarchy）决定层深；关系边不参与分层；成环数据不崩溃。
 */
import { describe, expect, it } from "vitest";
import { computeHierarchyPositions } from "@/views/asset/graph/hierarchyLayout";

const N = (id: string) => ({ id });
const H = (source: string, target: string) => ({ source, target, relation_type: "hierarchy" });
const R = (source: string, target: string) => ({ source, target, relation_type: "formal" });

describe("computeHierarchyPositions（129 分层树状）", () => {
  it("按包含边分层：系统 0 层、连接 1 层、Schema 2 层、表 3 层", () => {
    const nodes = [N("sys"), N("src"), N("sch"), N("tbl")];
    const edges = [H("sys", "src"), H("src", "sch"), H("sch", "tbl")];
    const { positions } = computeHierarchyPositions(nodes, edges, { xGap: 200, yGap: 150, topMargin: 80 });
    expect(positions.get("sys")!.y).toBe(80);
    expect(positions.get("src")!.y).toBe(230);
    expect(positions.get("sch")!.y).toBe(380);
    expect(positions.get("tbl")!.y).toBe(530);
  });

  it("关系边不影响分层（同层节点不被关系边压深）", () => {
    const nodes = [N("A"), N("B")];
    const { positions } = computeHierarchyPositions(nodes, [R("A", "B")], { topMargin: 80, yGap: 150 });
    expect(positions.get("A")!.y).toBe(80);
    expect(positions.get("B")!.y).toBe(80);
  });

  it("同父兄弟节点相邻且同层", () => {
    const nodes = [N("p"), N("c1"), N("c2"), N("c3")];
    const edges = [H("p", "c1"), H("p", "c2"), H("p", "c3")];
    const { positions } = computeHierarchyPositions(nodes, edges, { xGap: 200 });
    const ys = [positions.get("c1")!.y, positions.get("c2")!.y, positions.get("c3")!.y];
    expect(new Set(ys).size).toBe(1);
    const xs = [positions.get("c1")!.x, positions.get("c2")!.x, positions.get("c3")!.x].sort((a, b) => a - b);
    expect(xs[1] - xs[0]).toBe(200);
    expect(xs[2] - xs[1]).toBe(200);
  });

  it("无包含边时全部节点在第 0 层一行排开", () => {
    const nodes = [N("s1"), N("s2"), N("s3")];
    const { positions } = computeHierarchyPositions(nodes, [], { topMargin: 80 });
    for (const n of nodes) {
      expect(positions.get(n.id)!.y).toBe(80);
    }
  });

  it("成环包含数据不崩溃，兜底落位", () => {
    const nodes = [N("x"), N("y")];
    const edges = [H("x", "y"), H("y", "x")];
    const { positions } = computeHierarchyPositions(nodes, edges);
    expect(positions.get("x")).toBeTruthy();
    expect(positions.get("y")).toBeTruthy();
  });

  it("单层超宽折行：25 个同层节点按 12 个一行折成 3 行", () => {
    const nodes = Array.from({ length: 25 }, (_, i) => N(`t${i}`));
    const { positions } = computeHierarchyPositions(nodes, [], { topMargin: 80, yGap: 150, maxPerRow: 12 });
    const ys = new Set(nodes.map(n => positions.get(n.id)!.y));
    expect(ys.size).toBe(3);
    expect(Math.min(...ys)).toBe(80);
    expect(Math.max(...ys)).toBe(380);
  });
});
