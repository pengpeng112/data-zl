import { describe, expect, it } from "vitest";
import { matchInfectDiagDict } from "@/utils/infectDiagDict";

const items = [
  { code: "A00.1xx001", name: "霍乱", input_code: "HL" },
  { code: "B15.900", name: "甲型肝炎", input_code: "JXGYY" }
];

describe("matchInfectDiagDict", () => {
  it("matches Chinese name, pinyin initials and ICD code", () => {
    expect(matchInfectDiagDict(items, "霍").map(i => i.name)).toEqual(["霍乱"]);
    expect(matchInfectDiagDict(items, "hl").map(i => i.name)).toEqual(["霍乱"]);
    expect(matchInfectDiagDict(items, "A00").map(i => i.name)).toEqual(["霍乱"]);
    expect(matchInfectDiagDict(items, "肝炎").map(i => i.name)).toEqual(["甲型肝炎"]);
    expect(matchInfectDiagDict(items, "xyz")).toEqual([]);
  });
});
