import { describe, expect, it } from "vitest";
import {
  CANONICAL_SYSTEM_CODES,
  CATEGORY_LABEL,
  CATEGORY_ORDER,
  FORBIDDEN_CATEGORY_LABELS,
  isForbiddenCategoryLabel,
  kindLabel,
  scopeFromTreeNode,
  treeClickShouldReloadTables
} from "../src/views/asset/tables/hierarchy";

describe("plan90 hierarchy", () => {
  it("exposes ten peer system codes", () => {
    expect(CANONICAL_SYSTEM_CODES).toHaveLength(10);
    expect(CANONICAL_SYSTEM_CODES).toContain("DATA_CENTER");
    expect(CANONICAL_SYSTEM_CODES).toContain("HIS_SOURCE");
    expect(CANONICAL_SYSTEM_CODES).toContain("DOCARE");
    expect(CANONICAL_SYSTEM_CODES).toContain("LIS_SOURCE");
  });

  it("does not define external_business category order", () => {
    expect(CATEGORY_ORDER).toHaveLength(0);
    expect(CATEGORY_LABEL.external_business).toBeUndefined();
  });

  it("forbids 其他业务系统 label", () => {
    expect(isForbiddenCategoryLabel("其他业务系统")).toBe(true);
    expect(isForbiddenCategoryLabel("平台元数据系统")).toBe(true);
    expect(isForbiddenCategoryLabel("数据中心")).toBe(false);
    expect(FORBIDDEN_CATEGORY_LABELS).toContain("其他业务系统");
  });

  it("uses system/connection/schema labels", () => {
    expect(kindLabel("system")).toBe("业务系统");
    expect(kindLabel("connection")).toBe("数据连接");
    expect(kindLabel("schema")).toContain("Owner");
  });

  it("maps left-tree clicks to the right-side table filter", () => {
    expect(
      scopeFromTreeNode({ kind: "system", system_code: "HIS_SOURCE" })
    ).toEqual({
      system_code: "HIS_SOURCE",
      source_code: "",
      schema_name: "",
      table_name: ""
    });
    expect(
      scopeFromTreeNode({
        kind: "connection",
        system_code: "HIS_SOURCE",
        source_code: "his_source_10_10_10_15"
      })
    ).toEqual({
      system_code: "HIS_SOURCE",
      source_code: "his_source_10_10_10_15",
      schema_name: "",
      table_name: ""
    });
    expect(
      scopeFromTreeNode({
        kind: "schema",
        system_code: "HIS_SOURCE",
        source_code: "his_source_10_10_10_15",
        schema_name: "EXAM"
      })
    ).toEqual({
      system_code: "HIS_SOURCE",
      source_code: "his_source_10_10_10_15",
      schema_name: "EXAM",
      table_name: ""
    });
    expect(
      scopeFromTreeNode({
        kind: "table",
        system_code: "HIS_SOURCE",
        source_code: "his_source_10_10_10_15",
        schema_name: "EXAM",
        table_name: "EXAM_APPOINTS"
      })
    ).toEqual({
      system_code: "HIS_SOURCE",
      source_code: "his_source_10_10_10_15",
      schema_name: "EXAM",
      table_name: "EXAM_APPOINTS"
    });
    expect(
      scopeFromTreeNode({
        id: "placeholder:schema:his_source_10_10_10_15:EXAM",
        kind: "table",
        system_code: "HIS_SOURCE",
        source_code: "his_source_10_10_10_15",
        schema_name: "EXAM",
        table_name: "EXAM_APPOINTS"
      })
    ).toEqual({
      system_code: "HIS_SOURCE",
      source_code: "his_source_10_10_10_15",
      schema_name: "EXAM",
      table_name: ""
    });
  });

  it("reloads the table list for table and placeholder clicks", () => {
    expect(treeClickShouldReloadTables({ kind: "table", schema_name: "EXAM" })).toBe(true);
    expect(
      treeClickShouldReloadTables({ id: "placeholder:schema:x:EXAM", kind: "table" })
    ).toBe(true);
    expect(treeClickShouldReloadTables({ id: "search-hits" })).toBe(false);
  });
});
