import { describe, expect, it } from "vitest";
import { buildNoticesTabs, notifyTypeLabel } from "@/layout/components/lay-notice/data";
import type { QualityNotificationItem } from "@/api/quality";

function item(partial: Partial<QualityNotificationItem>): QualityNotificationItem {
  return {
    id: 1,
    issue_id: null,
    run_id: null,
    recipient: "tester",
    notify_type: "overdue",
    payload: {},
    read_at: null,
    created_at: "2026-10-13T10:00:00+08:00",
    ...partial
  };
}

describe("lay-notice buildNoticesTabs (215 E7)", () => {
  it("routes notify_type into todo/message/notice tabs with read state tags", () => {
    const tabs = buildNoticesTabs([
      item({ id: 1, notify_type: "overdue", payload: { issue_code: "QI-001" } }),
      item({ id: 2, notify_type: "recheck_passed", read_at: "2026-10-13T09:00:00+08:00" }),
      item({ id: 3, notify_type: "unknown_kind" })
    ]);
    expect(tabs.map(t => t.name)).toEqual(["通知", "消息", "待办"]);
    // 待办：需要行动的类型（overdue 等）
    expect(tabs[2].list).toHaveLength(1);
    expect(tabs[2].list[0].extra).toBe("未读");
    expect(tabs[2].list[0].status).toBe("warning");
    expect(tabs[2].list[0].description).toBe("问题单 QI-001");
    // 消息：复核通过为告知类
    expect(tabs[1].list).toHaveLength(1);
    expect(tabs[1].list[0].extra).toBe("已读");
    // 通知：未知类型兜底
    expect(tabs[0].list).toHaveLength(1);
    expect(tabs[0].list[0].title).toBe("质量治理通知");
  });

  it("keeps all tabs empty for null/empty input", () => {
    expect(buildNoticesTabs([]).every(t => t.list.length === 0)).toBe(true);
    expect(buildNoticesTabs(null as unknown as QualityNotificationItem[]).every(t => t.list.length === 0)).toBe(true);
    expect(notifyTypeLabel("overdue")).toBe("整改已逾期");
  });
});
