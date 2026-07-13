import { describe, expect, it } from "vitest";
import { buildEvidenceMetricRows, buildFieldMappingRows, deferredRelationVerificationText, evidenceSourceText, fieldMappingSummary, rawEvidenceMetrics } from "@/views/asset/graph/graphEvidence";
import type { GraphEdge } from "@/api/asset";

function edge(overrides: Partial<GraphEdge>): GraphEdge {
  return { id: "e1", source: "A", target: "B", ...overrides };
}

describe("graphEvidence", () => {
  it("builds field mapping rows from explicit mapping or column strings", () => {
    expect(buildFieldMappingRows(edge({ field_mappings: [{ from_column: "PATIENT_ID", to_column: "PATIENT_ID" }] }))).toEqual([{ from_column: "PATIENT_ID", to_column: "PATIENT_ID" }]);
    expect(buildFieldMappingRows(edge({ from_columns: "PATIENT_ID,VISIT_ID", to_columns: "PATIENT_ID,VISIT_ID" }))).toEqual([
      { from_column: "PATIENT_ID", to_column: "PATIENT_ID" },
      { from_column: "VISIT_ID", to_column: "VISIT_ID" }
    ]);
    expect(fieldMappingSummary(edge({ from_columns: "TEST_NO", to_columns: "TEST_NO" }))).toBe("TEST_NO -> TEST_NO");
  });

  it("formats coverage orphan and sample metrics for evidence drawer", () => {
    const rows = buildEvidenceMetricRows(edge({ validation_metrics: JSON.stringify({ coverage_rate: 0.9823, orphan_rate: 0.0177, sample_size: 500 }) }));
    expect(rows).toContainEqual({ key: "coverage_rate", label: "覆盖率", value: "98.23%" });
    expect(rows).toContainEqual({ key: "orphan_rate", label: "孤儿率", value: "1.77%" });
    expect(rows).toContainEqual({ key: "sample_size", label: "样本量", value: "500" });
  });

  it("keeps raw metrics text and resolves source evidence", () => {
    expect(buildEvidenceMetricRows(edge({ validation_metrics: "sample_pass; orphan_rate=0" }))).toEqual([]);
    expect(rawEvidenceMetrics(edge({ validation_metrics: "sample_pass; orphan_rate=0" }))).toBe("sample_pass; orphan_rate=0");
    expect(evidenceSourceText(edge({ validation_metrics: JSON.stringify({ source_document: "39_secondary_relationships" }), note: "fallback" }))).toBe("39_secondary_relationships");
    expect(evidenceSourceText(edge({ note: "10_关系验证报告" }))).toBe("10_关系验证报告");
  });

  it("describes deferred cross-system verification scope", () => {
    const text = deferredRelationVerificationText();
    expect(text).toContain("EMR");
    expect(text).toContain("LIS");
    expect(text).toContain("PACS");
    expect(text).toContain("护理");
    expect(text).toContain("手麻");
    expect(text).toContain("不能作为正式血缘/ER 依据");
  });
});