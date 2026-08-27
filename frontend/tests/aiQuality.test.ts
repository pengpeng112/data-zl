import { describe, expect, it } from "vitest";
import { aiQualityErrorLabel, aiQualityStatusLabel, canSubmitAiQuality, limitFindingIds } from "@/views/asset/ai-quality/contracts";
import { liveDisplayText, objectText, renderReportHtml } from "@/views/asset/ai-quality/reportMarkdown";

describe("AI quality workbench contracts", () => {
  it("limits selection to 50 unique findings", () => {
    expect(limitFindingIds([...Array.from({ length: 55 }, (_, i) => i + 1), 1])).toHaveLength(50);
    expect(limitFindingIds([1, 1, Number.NaN])).toEqual([1]);
  });

  it("requires enabled/configured status and a safe preview before submit", () => {
    const preview = { request_id: "AQ-1", task_type: "finding_batch" as const, finding_ids: [1], fields: ["id"], item_count: 1, payload_bytes: 32, input_digest: "sha256" };
    expect(canSubmitAiQuality({ enabled: false, configured: true, provider: "dify" }, preview)).toBe(false);
    expect(canSubmitAiQuality({ enabled: true, configured: false, provider: "dify" }, preview)).toBe(false);
    expect(canSubmitAiQuality({ enabled: true, configured: true, provider: "hospital_llm" }, preview)).toBe(true);
    expect(canSubmitAiQuality({ enabled: true, configured: true, provider: "dify" }, preview)).toBe(true);
    expect(aiQualityStatusLabel({ enabled: false, configured: false })).toBe("已关闭");
    expect(aiQualityStatusLabel({ enabled: true, configured: false })).toBe("未配置");
  });

  it("blocks an oversized preview even if the UI selection was bypassed", () => {
    expect(canSubmitAiQuality({ enabled: true, configured: true, provider: "dify" }, { request_id: "AQ-2", task_type: "finding_batch", finding_ids: [], fields: [], item_count: 51, payload_bytes: 1, input_digest: "x" })).toBe(false);
  });

  it("supports all three task types", () => {
    expect(["finding", "finding_batch", "run_summary"]).toHaveLength(3);
  });

  it("uses result review/attach contract and partial status", () => {
    const reviewPath = "/api/v1/quality/ai/results/42/review";
    const attachPath = "/api/v1/quality/ai/results/42/attach";
    expect(reviewPath).toContain("/results/");
    expect(attachPath).toContain("/results/");
    expect(["accepted", "rejected", "partial"]).toContain("partial");
    expect({ recommendation_indexes: [0, 2], note: "复核" }).not.toHaveProperty("finding_ids");
  });

  it("explains empty table/field as catalog-level and renders report headings", () => {
    expect(objectText({ target_type: "relation", target_ref: "HIS.PAT_VISIT -> HIS.EXAM_MASTER" })).toContain("HIS.PAT_VISIT");
    expect(objectText({ table_name_cn: "就诊", table_name: "PAT_VISIT", schema_name: "HIS", column_name: "VISIT_ID" })).toBe("HIS.就诊.VISIT_ID");
    expect(objectText({})).toContain("没有单表字段");
    expect(renderReportHtml("## 结论\n- **孤儿率**需处理")).toContain("<h3>结论</h3>");
    expect(renderReportHtml("## 结论\n- **孤儿率**需处理")).toContain("<strong>孤儿率</strong>");
    expect(liveDisplayText('{"summary":"x"}')).toContain("中文说明");
    expect(liveDisplayText("【结论】字段缺注释，建议补目录。")).toContain("字段缺注释");
    expect(aiQualityErrorLabel("contract")).toContain("安全校验");
    expect(aiQualityErrorLabel("timeout")).toContain("超时");
  });
});
