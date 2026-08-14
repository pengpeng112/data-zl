import { describe, expect, it } from "vitest";
import {
  checkScopeLabel,
  constraintLevelLabel,
  executionModeLabel,
  findingColumnText,
  findingDbText,
  findingProblemText,
  findingTableCode,
  findingTableTitle,
  formatFindingRate,
  ruleCategoryLabel,
  ruleTargetText
} from "@/views/asset/quality/qualityRuleLabels";

describe("qualityRuleLabels", () => {
  it("uses the four common quality dimensions the user asked for", () => {
    expect(ruleCategoryLabel("UNIQUE")).toBe("唯一性");
    expect(ruleCategoryLabel("COMPLETE")).toBe("缺失性");
    expect(ruleCategoryLabel("RELATION")).toBe("关联性");
    expect(ruleCategoryLabel("ACCURACY")).toBe("一致性");
  });

  it("keeps table cells compact by showing object instead of empty name space", () => {
    expect(ruleTargetText({
      namespace_name: "HIS",
      target_table: "PAT_VISIT",
      target_field: "PATIENT_ID,VISIT_ID"
    })).toBe("HIS.PAT_VISIT.PATIENT_ID,VISIT_ID");
    expect(ruleTargetText({
      target_table: "DIAGNOSIS",
      target_field: "PATIENT_ID,VISIT_ID",
      related_table: "PAT_VISIT",
      related_field: "PATIENT_ID,VISIT_ID"
    })).toBe("DIAGNOSIS.PATIENT_ID,VISIT_ID → PAT_VISIT.PATIENT_ID,VISIT_ID");
    expect(ruleTargetText({})).toBe("平台元数据");
  });

  it("explains a finding beyond severity", () => {
    expect(findingProblemText({
      problem: "字段缺少中文名：住院就诊"
    })).toBe("字段缺少中文名：住院就诊");
    expect(findingProblemText({
      rule_name: "数据连接不可用",
      source_name_cn: "无纸化病案"
    })).toBe("数据连接不可用：无纸化病案");
    expect(formatFindingRate(0.82)).toBe("82.0%");
    expect(formatFindingRate(82)).toBe("82.0%");
  });

  it("splits a finding into database, table and column for analysts", () => {
    expect(findingDbText({
      schema_name: "HIS",
      related_schema: "CDA"
    })).toBe("HIS → CDA");
    expect(findingTableTitle({
      table_name_cn: "住院就诊",
      table_name: "PAT_VISIT",
      related_table_cn: "出院诊断",
      related_table: "DIAGNOSIS"
    })).toBe("住院就诊 → 出院诊断");
    expect(findingTableCode({
      table_name_cn: "住院就诊",
      table_name: "PAT_VISIT",
      related_table_cn: "出院诊断",
      related_table: "DIAGNOSIS"
    })).toBe("PAT_VISIT → DIAGNOSIS");
    expect(findingColumnText({
      column_name: "PATIENT_ID,VISIT_ID",
      related_field: "PATIENT_ID,VISIT_ID"
    })).toBe("PATIENT_ID,VISIT_ID → PATIENT_ID,VISIT_ID");
    expect(findingColumnText({ table_name: "PAT_VISIT" } as { column_name?: string })).toBe("-");
  });

  it("labels execution mode without a wide extra column", () => {
    expect(executionModeLabel("metadata_only")).toBe("元数据");
    expect(executionModeLabel("sql_template")).toBe("SQL 建议");
    expect(checkScopeLabel("TABLE_RELATION")).toBe("表间");
    expect(constraintLevelLabel("HARD")).toBe("硬约束");
  });
});
