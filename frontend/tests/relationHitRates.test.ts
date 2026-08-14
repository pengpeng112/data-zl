import { describe, expect, it } from "vitest";
import {
  formatHitRate,
  hitRatePercent,
  pickHighlight,
  systemShortLabel
} from "@/views/asset/relation-rates/relationHitRates";

describe("relationHitRates", () => {
  it("formats rates and prefers ODS highlight over HISUSER", () => {
    expect(formatHitRate(0.9992)).toBe("99.92%");
    expect(formatHitRate(null)).toBe("-");
    expect(hitRatePercent(0.659)).toBe(65.9);
    expect(systemShortLabel("HIS_SOURCE")).toBe("HISUSER");
    const row = pickHighlight(
      [
        { scene: "exam_inpatient", from_system_code: "HIS_SOURCE" },
        { scene: "exam_inpatient", from_system_code: "DATA_CENTER" }
      ],
      "exam_inpatient"
    );
    expect(row?.from_system_code).toBe("DATA_CENTER");
  });
});
