import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** 169 G3：force 布局白名单契约（round-3 P2 裁决锁死，防死配置/负斥力回归）。 */
describe("plan169 G3 force layout whitelist", () => {
  const src = source("src/views/asset/components/AdvancedRelationGraph.vue");

  it("force options only contain keys @antv/layout actually supports", () => {
    // @antv/layout/lib/algorithm/force/types.d.ts 已核清单（169 §1 铁律 3）
    const whitelist = [
      "type", "linkDistance", "nodeStrength", "edgeStrength", "preventOverlap",
      "nodeSize", "collideStrength", "gravity", "damping", "maxSpeed",
      "coulombDisScale", "factor", "interval", "centripetalOptions"
    ];
    const start = src.indexOf("// force = Neo4j");
    const end = src.indexOf("function ", start + 10); // force 块到下一个函数为止
    const forceBlock = src.slice(start, end);
    const keys = Array.from(forceBlock.matchAll(/^\s{2,6}(\w+):\s/gm)).map(m => m[1]);
    expect(keys.length).toBeGreaterThanOrEqual(8);
    for (const key of keys) {
      expect(whitelist).toContain(key);
    }
  });

  it("never reintroduces dead d3-force-only options or negative repulsion", () => {
    const start = src.indexOf("// force = Neo4j");
    const end = src.indexOf("function ", start + 10);
    const forceBlock = src.slice(start, end);
    // 带冒号匹配代码属性形态（注释中的教育性提及不含冒号；radial/force-atlas2
    // 分支的 nodeSpacing 属其布局合法项，不在 force 块内）
    for (const dead of [/\balpha:\s/, /\balphaDecay:\s/, /\balphaMin:\s/, /\bforceSimulation:\s/, /\bnodeSpacing:\s/]) {
      expect(forceBlock).not.toMatch(dead);
    }
    // nodeStrength 必须为正（负值经 repulsive weight 变吸引 → 中心坍缩，round-3 P2 根因）
    expect(forceBlock).toMatch(/nodeStrength: (\d+)/);
    expect(Number(forceBlock.match(/nodeStrength: (\d+)/)![1])).toBeGreaterThan(0);
    // gravity 弱向心（默认 10 会持续拉向中心）
    expect(Number(forceBlock.match(/gravity: (\d+(?:\.\d+)?)/)![1])).toBeLessThanOrEqual(5);
    // edgeStrength 回默认量级（0.45 较默认 50 削弱 99%）
    expect(Number(forceBlock.match(/edgeStrength: (\d+(?:\.\d+)?)/)![1])).toBeGreaterThanOrEqual(30);
    // preventOverlap 必须配 nodeSize=真实直径上界（66 中心节点；88 与实际不符致碰撞检测失效）
    expect(Number(forceBlock.match(/nodeSize: (\d+)/)![1])).toBeLessThanOrEqual(70);
  });

  it("label style drops the dead wrap config (text pre-wrapped in graphTransform)", () => {
    for (const dead of [/\blabelWordWrap:\s/, /\blabelMaxWidth:\s/, /\blabelMaxLines:\s/, /\blabelTextOverflow:\s/]) {
      expect(src).not.toMatch(dead);
    }
    // 有效标签项保留
    expect(src).toContain("labelPlacement");
    expect(src).toContain("labelLineHeight");
  });
});
