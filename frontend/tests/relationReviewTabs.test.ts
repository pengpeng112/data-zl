import { describe, expect, it } from "vitest";
import {
  displayRelationColumns,
  isReviewInboxTab,
  normalizeRelationClass,
  relationClassQuery,
  relationEvidenceKind,
  reviewStatusForTab
} from "@/views/asset/relation-review/relationReviewTabs";

describe("relationReviewTabs", () => {
  it("defaults empty tab to pending review queue", () => {
    expect(normalizeRelationClass("")).toBe("pending");
    expect(normalizeRelationClass(undefined)).toBe("pending");
    expect(normalizeRelationClass("unknown")).toBe("pending");
    expect(normalizeRelationClass("pending")).toBe("pending");
  });

  it("does not hide the real relation list behind empty draft inbox", () => {
    expect(isReviewInboxTab("pending")).toBe(false);
    expect(reviewStatusForTab("pending")).toBe("draft");
    expect(reviewStatusForTab("confirmed")).toBe("approved");
  });

  it("writes class into the route only for non-pending tabs", () => {
    expect(relationClassQuery("pending")).toEqual({});
    expect(relationClassQuery("lineage")).toEqual({ class: "lineage" });
  });

  it("labels view-parsed candidates without join keys", () => {
    expect(relationEvidenceKind("Vastbase pg_views definition", "", "")).toBe("view_ddl");
    expect(displayRelationColumns("", "PATIENT_ID+VISIT_ID")).toEqual({ text: "PATIENT_ID+VISIT_ID（推断）", inferred: true });
    expect(displayRelationColumns("", "")).toEqual({ text: "未解析", inferred: false });
  });
});
