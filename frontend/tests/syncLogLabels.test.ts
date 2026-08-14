import { describe, expect, it } from "vitest";
import { formatDuration, syncStatusLabel, syncStatusTag } from "@/views/identity/sync-logs/syncLogLabels";

describe("syncLogLabels", () => {
  it("uses Chinese status for nightly monitoring", () => {
    expect(syncStatusLabel("partial_success")).toBe("部分成功");
    expect(syncStatusTag("failed")).toBe("danger");
    expect(formatDuration(125000)).toBe("2 分 5 秒");
  });
});
