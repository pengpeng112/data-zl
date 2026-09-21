import { describe, expect, it } from "vitest";
import { isCompetitionCaptureQuery } from "../src/layout/captureMode";

describe("competition capture mode", () => {
  it("enables only for an explicit query value", () => {
    expect(isCompetitionCaptureQuery({ capture: "1" })).toBe(true);
    expect(isCompetitionCaptureQuery({ presentation: "1" })).toBe(true);
    expect(isCompetitionCaptureQuery({ capture: "0" })).toBe(false);
    expect(isCompetitionCaptureQuery({}, "?capture=1")).toBe(true);
    expect(isCompetitionCaptureQuery({}, "?presentation=1")).toBe(true);
    expect(isCompetitionCaptureQuery({})).toBe(false);
  });
});
