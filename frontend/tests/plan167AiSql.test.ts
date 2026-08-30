import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const page = readFileSync(resolve(process.cwd(), "src/views/asset/ai-sql/index.vue"), "utf8");
const routes = readFileSync(resolve(process.cwd(), "src/router/modules/asset.ts"), "utf8");
const api = readFileSync(resolve(process.cwd(), "src/api/asset.ts"), "utf8");

describe("plan167 AI SQL workbench", () => {
  it("is an async route with the dotted read permission", () => {
    expect(routes).toContain('path: "/asset/ai-sql"');
    expect(routes).toContain('import("@/views/asset/ai-sql/index.vue")');
    expect(routes).toContain('auths: ["ai.context.read"]');
  });
  it("locks generation to DATA_CENTER and never offers execution", () => {
    expect(page).toContain('system_code: "DATA_CENTER"');
    expect(page).toContain("生成 SQL 永不执行");
    expect(page).not.toContain("执行 SQL");
    expect(page).not.toContain("Monaco");
  });
  it("supports table selection, risk result, copy and own history", () => {
    expect(page).toContain("selectedTables");
    expect(page).toContain("riskBlocked");
    expect(page).toContain("copySql");
    expect(page).toContain("getAiSqlHistory");
  });
  it("uses only the dedicated generate and history endpoints", () => {
    expect(api).toContain('"/api/v1/ai/ai-sql/generate"');
    expect(api).toContain('"/api/v1/ai/ai-sql/history"');
    expect(page).not.toContain("sql-workbench");
  });
});
