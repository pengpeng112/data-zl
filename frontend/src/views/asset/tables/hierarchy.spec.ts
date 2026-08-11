import { describe, expect, it } from "vitest";
import {
  CANONICAL_SYSTEM_CODES,
  CATEGORY_LABEL,
  CATEGORY_ORDER,
  FORBIDDEN_CATEGORY_LABELS,
  isForbiddenCategoryLabel,
  kindLabel
} from "./hierarchy";

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
});
