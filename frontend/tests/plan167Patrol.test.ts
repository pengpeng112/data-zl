import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const page = readFileSync(resolve(process.cwd(), "src/views/asset/ai-quality/index.vue"), "utf8");
const api = readFileSync(resolve(process.cwd(), "src/api/asset.ts"), "utf8");
const backend = readFileSync(resolve(process.cwd(), "../backend/app/api/v1/ai_quality.py"), "utf8");

describe("plan167 AI patrol presentation", () => {
  it("keeps the existing analysis workflow intact", () => {
    expect(page).toContain("previewAiQuality");
    expect(page).toContain("createAiQualityJob");
    expect(page).toContain("renderReportHtml");
    expect(page).toContain("POLL_TIMEOUT_MS = 10 * 60 * 1000");
  });

  it("shows a static demo-only schedule without scheduler controls", () => {
    expect(page).toContain("演示形态（未启用调度）");
    expect(page).toContain("定时执行未启用");
    expect(page).not.toContain("QualityTask");
    expect(backend).not.toContain("QualityTask");
  });

  it("uses the patrol endpoints and dotted permissions", () => {
    expect(api).toContain("/patrol/targets");
    expect(api).toContain("/patrol/runs");
    expect(api).toContain("/patrol/run");
    expect(page).toContain("asset.quality.ai.analyze");
  });

  it("provides evidence timestamps and explicit offline replay", () => {
    expect(page).toContain("target.evidence.rule_id");
    expect(page).toContain("target.evidence.data_as_of");
    expect(page).toContain("离线回放");
    expect(page).toContain("最近成功巡查");
  });
});
