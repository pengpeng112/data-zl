import { describe, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("@/utils/http", () => ({ http: { request } }));

import {
  generateRecipeSql,
  getRecipeVersion,
  listRecipeVersions,
  updateRecipeVersion,
  validateRecipeDraft
} from "@/api/recipes";

describe("relation recipe editor contract", () => {
  it("rejects empty or incomplete structured recipes", () => {
    expect(() => validateRecipeDraft("[]", "[]")).toThrow("至少填写一张主表");
    expect(() => validateRecipeDraft('[{"table":"HIS.A"},{"table":"HIS.B"}]', "[]")).toThrow("至少需要 1 条关联条件");
    expect(() => validateRecipeDraft("not-json", "[]")).toThrow("主表必须是合法的 JSON 数组");
    expect(() => validateRecipeDraft('[{"table":"HIS.A"}]', '[{"on": 1}]')).toThrow("缺少非空的 on");
    expect(() => validateRecipeDraft('[{"table":"HIS.A"}]', '[{}]')).toThrow("缺少非空的 on");
  });

  it("accepts one table and normalizes the JSON editor values", () => {
    expect(validateRecipeDraft('[{"table":"HIS.A","alias":"a"}]', "[]")).toEqual({
      primaryTables: [{ table: "HIS.A", alias: "a" }],
      joins: []
    });
  });

  it("uses the versioned read, update and SQL preview API paths", () => {
    request.mockResolvedValue({ data: {} });
    getRecipeVersion("r/1", 2);
    listRecipeVersions("r/1");
    updateRecipeVersion("r/1", 2, { primary_tables: [{ table: "HIS.A" }], joins: [] });
    generateRecipeSql("r/1", 2);
    expect(request.mock.calls.map(call => [call[0], call[1]])).toEqual([
      ["get", "/api/v1/recipes/r%2F1/versions/2"],
      ["get", "/api/v1/recipes/r%2F1/versions"],
      ["put", "/api/v1/recipes/r%2F1/versions/2"],
      ["post", "/api/v1/recipes/r%2F1/versions/2/sql"]
    ]);
  });
});
