import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/**
 * 177 R2-C4：图谱边标签 [object Object] 回归锁（171 P2）。
 * 根因：normalizeGraphData 会把 edge.label 包成 ECharts 风格对象
 * （{show, formatter, ...}），RelationGraph 两处消费点直接取对象/直接
 * String() 就渲染成 "[object Object]"。修复=统一走 edgeLabelText()。
 */
describe("plan177 R2-C4 graph edge label text extraction", () => {
  const src = source("src/views/asset/components/RelationGraph.vue");

  it("edgeLabelText resolves string label → label.formatter → from_columns string, else empty", () => {
    const start = src.indexOf("function edgeLabelText");
    expect(start).toBeGreaterThan(-1);
    const block = src.slice(start, src.indexOf("function ", start + 10));
    expect(block).toContain('typeof edge?.label === "string"');
    expect(block).toContain(".formatter");
    expect(block).toContain('typeof edge?.from_columns === "string"');
    expect(block).toContain(': "";');
  });

  it("both edge label sites route through edgeLabelText, never raw String(edge.label)", () => {
    expect(src).not.toMatch(/String\(edge\.label/);
    expect(src).toContain("label: edgeLabelText(edge)");
    expect(src).toContain("label: edgeLabelText(edge).slice(0, 16)");
  });
});

/**
 * 177 R2-C3：6 个漏挂写按钮补 v-perms（173 P2-2）。
 * 权限码与同页既有写按钮一致：probe.finding.transition /
 * value_domain.confirm / dict.general.edit（dict 页既有码，非 177 草案
 * 里的 dict.general.manage——后者在权限种子中不存在）。
 */
describe("plan177 R2-C3 write buttons carry v-perms", () => {
  it("probe-findings transition dialog submit requires probe.finding.transition", () => {
    const src = source("src/views/asset/probe-findings/index.vue");
    expect(src).toContain(`v-perms="'probe.finding.transition'"`);
    expect(src).toMatch(/submitTransition"?>确认迁移/);
  });

  it("value-domains confirm dialog submit requires value_domain.confirm", () => {
    const src = source("src/views/asset/value-domains/index.vue");
    expect(src).toContain(`v-perms="'value_domain.confirm'" type="primary" :loading="acting" @click="submitConfirm"`);
  });

  it("dict/general four save buttons require dict.general.edit", () => {
    const src = source("src/views/dict/general/index.vue");
    for (const handler of ["saveCategory", "saveStdItem", "saveSysItem", "saveMapping"]) {
      expect(src).toMatch(new RegExp(`v-perms="'dict\\.general\\.edit'" type="primary" :loading="[^"]+" @click="${handler}"`));
    }
  });
});
