import { describe, expect, it } from "vitest";
import {
  impactTableLabel,
  impactTableValue,
  mergeTableOptions,
  optionFromCatalog,
  parseImpactTableQuery
} from "@/views/asset/lineage/lineagePicker";

describe("lineagePicker", () => {
  it("builds SCHEMA.TABLE from catalog fields", () => {
    expect(impactTableValue("HIS", "PAT_VISIT")).toBe("HIS.PAT_VISIT");
    expect(impactTableValue("", "PAT_VISIT")).toBe("PAT_VISIT");
    expect(impactTableValue("HIS", "")).toBe("");
  });

  it("shows Chinese name with technical name for picker labels", () => {
    expect(impactTableLabel({
      table_name_cn: "患者就诊记录",
      schema_name: "HIS",
      table_name: "PAT_VISIT",
      technical_name: "HIS.PAT_VISIT"
    })).toBe("患者就诊记录（HIS.PAT_VISIT）");
    expect(impactTableLabel({
      display_name: "HIS.PAT_VISIT",
      technical_name: "HIS.PAT_VISIT",
      table_name: "PAT_VISIT"
    })).toBe("HIS.PAT_VISIT");
  });

  it("maps catalog search items into select options", () => {
    expect(optionFromCatalog({
      display_name: "病案首页-业务类-输血信息",
      table_name_cn: "病案首页-业务类-输血信息",
      schema_name: "jhemr",
      table_name: "blood_transfusion",
      technical_name: "jhemr.blood_transfusion"
    })).toEqual({
      value: "jhemr.blood_transfusion",
      label: "病案首页-业务类-输血信息（jhemr.blood_transfusion）",
      schema: "jhemr",
      table: "blood_transfusion"
    });
    expect(optionFromCatalog({})).toBeNull();
  });

  it("reads table from route query without forcing hand-typed schema", () => {
    expect(parseImpactTableQuery({ table: "HIS.PAT_VISIT", system_code: "HIS" })).toEqual({
      systemCode: "HIS",
      schemaName: "HIS",
      table: "HIS.PAT_VISIT"
    });
    expect(parseImpactTableQuery({ schema: "MEDREC", table: "PAT_VISIT" })).toEqual({
      systemCode: "",
      schemaName: "MEDREC",
      table: "MEDREC.PAT_VISIT"
    });
  });

  it("keeps newly loaded catalog options in front and de-duplicates", () => {
    const merged = mergeTableOptions(
      [{ value: "HIS.PAT_VISIT", label: "旧" }],
      [{ value: "HIS.PAT_MASTER_INDEX", label: "患者主索引（HIS.PAT_MASTER_INDEX）" }, { value: "HIS.PAT_VISIT", label: "患者就诊（HIS.PAT_VISIT）" }]
    );
    expect(merged.map(item => item.value)).toEqual(["HIS.PAT_MASTER_INDEX", "HIS.PAT_VISIT"]);
    expect(merged[1].label).toBe("患者就诊（HIS.PAT_VISIT）");
  });
});
