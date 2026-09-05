import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/**
 * 178 R2（C6，承接 173 P3-3 / 177 C6 WARN）：GraphToolbar 单向数据流。
 * 子组件不得再直接改 props（模板 v-model 与 script 赋值双路径），
 * 统一 emit update:locate / update:filters 由父组件 Object.assign 合并。
 */
describe("plan178 R2 GraphToolbar one-way data flow", () => {
  const toolbar = source("src/views/asset/components/GraphToolbar.vue");
  const parent = source("src/views/asset/graph/index.vue");

  it("template never binds v-model directly onto locate/filters props", () => {
    expect(toolbar).not.toContain('v-model="locate.');
    expect(toolbar).not.toContain('v-model="filters.');
    // 本地 ref（抽屉开关）不受限，必须保留。
    expect(toolbar).toContain('v-model="advancedVisible"');
  });

  it("script never assigns into props.filters / props.locate (changeDisplay included)", () => {
    expect(toolbar).not.toContain("props.filters.layout_mode =");
    expect(toolbar).not.toMatch(/props\.(filters|locate)\.[A-Za-z_]+\s*=/);
  });

  it("parent graph/index.vue wires update:locate / update:filters onto the toolbar", () => {
    expect(parent).toContain("@update:locate=");
    expect(parent).toContain("@update:filters=");
    expect(parent).toMatch(/function onUpdateFilters\(next: typeof filters\) \{\s*\n\s*Object\.assign\(filters, next\);/);
    expect(parent).toMatch(/function onUpdateLocate\(next: typeof locate\) \{\s*\n\s*Object\.assign\(locate, next\);/);
  });

  it("changeDisplay routes through update:filters emit, no props mutation", () => {
    const start = toolbar.indexOf("function changeDisplay");
    expect(start).toBeGreaterThan(-1);
    const block = toolbar.slice(start, toolbar.indexOf("function ", start + 10));
    expect(block).toContain('emit("update:filters"');
    // 只禁赋值；{ ...props.filters, ... } 的只读展开是计划规定的写法。
    expect(block).not.toMatch(/props\.(filters|locate)\.[A-Za-z_]+\s*=/);
  });

  it("controlled bindings use explicit per-field payloads, not literal-key objects", () => {
    // 代表形态三处（输入框 / segmented / select）必须逐字段展开，禁止 { field: val } 字面键。
    expect(toolbar).toContain("emit('update:locate', { ...locate, table: String($event ?? '') })");
    expect(toolbar).toContain("emit('update:locate', { ...locate, depth: Number($event) as 1 | 2 | 3 })");
    expect(toolbar).toContain("emit('update:filters', { ...filters, system_code: String($event ?? '') })");
    expect(toolbar).toContain("emit('update:filters', { ...filters, limit: Number($event) })");
    expect(toolbar).not.toMatch(/\{\s*field\s*:/);
  });
});
