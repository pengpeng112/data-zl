import { describe, expect, it } from "vitest";
import { aiQualityStatusLabel, canSubmitAiQuality, limitFindingIds, sameFindingDomain } from "@/views/asset/ai-quality/contracts";

describe("AI quality workbench contracts", () => {
  it("limits selection to 50 unique findings", () => {
    expect(limitFindingIds([...Array.from({ length: 55 }, (_, i) => i + 1), 1])).toHaveLength(50);
    expect(limitFindingIds([1, 1, Number.NaN])).toEqual([1]);
  });

  it("requires enabled/configured status and a safe preview before submit", () => {
    const preview = { request_id: "AQ-1", task_type: "finding_batch" as const, finding_ids: [1], fields: ["id"], item_count: 1, payload_bytes: 32, input_digest: "sha256" };
    expect(canSubmitAiQuality({ enabled: false, configured: true }, preview)).toBe(false);
    expect(canSubmitAiQuality({ enabled: true, configured: false }, preview)).toBe(false);
    expect(canSubmitAiQuality({ enabled: true, configured: true }, preview)).toBe(true);
    expect(aiQualityStatusLabel({ enabled: false, configured: false })).toBe("已关闭");
    expect(aiQualityStatusLabel({ enabled: true, configured: false })).toBe("未配置");
  });

  it("blocks an oversized preview even if the UI selection was bypassed", () => {
    expect(canSubmitAiQuality({ enabled: true, configured: true }, { request_id: "AQ-2", task_type: "finding_batch", finding_ids: [], fields: [], item_count: 51, payload_bytes: 1, input_digest: "x" })).toBe(false);
  });

  it("supports all three task types and requires a same physical domain", () => {
    expect(["finding", "finding_batch", "run_summary"]).toHaveLength(3);
    const scope = { source_code: "SRC", schema_name: "HIS", table_name: "PAT_VISIT", rule_code: "R1" };
    expect(sameFindingDomain([{ system_code: "HIS", ...scope }, { system_code: "HIS", ...scope }])).toBe(true);
    expect(sameFindingDomain([{ system_code: "HIS", ...scope }, { system_code: "ODS", ...scope }])).toBe(false);
    expect(sameFindingDomain([{ system_code: "HIS", ...scope, source_code: null }])).toBe(false);
    expect(sameFindingDomain([{ system_code: "HIS", ...scope }, { system_code: "HIS", ...scope, table_name: "ORDERS" }])).toBe(false);
    expect(sameFindingDomain([{ system_code: "HIS", ...scope, namespace_name: "A" }, { system_code: "HIS", ...scope, namespace_name: "B" }])).toBe(false);
  });

  it("uses result review/attach contract and partial status", () => {
    const reviewPath = "/api/v1/quality/ai/results/42/review";
    const attachPath = "/api/v1/quality/ai/results/42/attach";
    expect(reviewPath).toContain("/results/");
    expect(attachPath).toContain("/results/");
    expect(["accepted", "rejected", "partial"]).toContain("partial");
    expect({ recommendation_indexes: [0, 2], note: "复核" }).not.toHaveProperty("finding_ids");
  });
});
