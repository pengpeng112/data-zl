import { describe, expect, it } from "vitest";
import { classificationLabel, deptDisplay, employmentLabel, personTypeLabel } from "@/views/identity/persons/personLabels";

describe("personLabels", () => {
  it("does not show formal as a clinical type", () => {
    expect(personTypeLabel("formal")).toBe("正式");
    expect(classificationLabel("doctor")).toBe("医生");
    expect(employmentLabel("inactive")).toBe("停用");
  });

  it("falls back to department code only when name is missing", () => {
    expect(deptDisplay({ dept_code: "010101", dept_name_cn: "办公室" })).toBe("办公室");
    expect(deptDisplay({ dept_code: "010101" })).toBe("010101");
  });
});
