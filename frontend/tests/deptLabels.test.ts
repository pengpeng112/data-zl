import { describe, expect, it } from "vitest";
import { deptReviewLabel, deptStatusLabel, deptTypeLabel } from "@/views/identity/departments/deptLabels";

describe("deptLabels", () => {
  it("maps HIS OUTP_OR_INP codes to Chinese names", () => {
    expect(deptTypeLabel("0")).toBe("门诊");
    expect(deptTypeLabel("1")).toBe("住院");
    expect(deptTypeLabel("2")).toBe("门诊住院");
    expect(deptTypeLabel("9")).toBe("其他");
  });

  it("uses Chinese status instead of raw active", () => {
    expect(deptStatusLabel("active")).toBe("启用");
    expect(deptReviewLabel("unreviewed")).toBe("未复核");
  });
});
