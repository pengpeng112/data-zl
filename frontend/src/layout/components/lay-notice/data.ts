import { formatTime } from "@/utils/format";
import type { QualityNotificationItem } from "@/api/quality";

export interface ListItem {
  avatar: string;
  title: string;
  datetime: string;
  type: string;
  description: string;
  status?: "primary" | "success" | "warning" | "info" | "danger";
  extra?: string;
}

export interface TabItem {
  key: string;
  name: string;
  list: ListItem[];
  emptyText: string;
}

// 215 E7：铃铛下拉改读后端站内待办（/api/v1/quality-notifications，207）。
// notify_type 值域来自 quality_execution_service：remind_due/overdue/escalate/
// vendor_overdue/recheck_failed/recheck_passed。
const TODO_TYPES = new Set([
  "remind_due",
  "overdue",
  "escalate",
  "vendor_overdue",
  "recheck_failed"
]);

const NOTIFY_LABELS: Record<string, string> = {
  remind_due: "整改到期提醒",
  overdue: "整改已逾期",
  escalate: "问题升级",
  vendor_overdue: "厂商督办逾期",
  recheck_failed: "复核不通过",
  recheck_passed: "复核通过"
};

export function notifyTypeLabel(notifyType: string): string {
  return NOTIFY_LABELS[notifyType] ?? "质量治理通知";
}

function notificationDescription(n: QualityNotificationItem): string {
  const issueCode = n.payload?.issue_code;
  if (typeof issueCode === "string" && issueCode) return `问题单 ${issueCode}`;
  return notifyTypeLabel(n.notify_type);
}

/** 把后端通知映射为铃铛三页签（通知/消息/待办）；纯函数，供 vitest 覆盖。 */
export function buildNoticesTabs(items: QualityNotificationItem[]): TabItem[] {
  const buckets: Record<string, ListItem[]> = { "1": [], "2": [], "3": [] };
  for (const n of items ?? []) {
    const item: ListItem = {
      avatar: "",
      title: notifyTypeLabel(n.notify_type),
      datetime: formatTime(n.created_at),
      type: "info",
      description: notificationDescription(n),
      status: n.read_at ? "info" : "warning",
      extra: n.read_at ? "已读" : "未读"
    };
    const tabKey = TODO_TYPES.has(n.notify_type) ? "3" : n.notify_type === "recheck_passed" ? "2" : "1";
    buckets[tabKey].push(item);
  }
  return [
    { key: "1", name: "通知", list: buckets["1"], emptyText: "暂无通知" },
    { key: "2", name: "消息", list: buckets["2"], emptyText: "暂无消息" },
    { key: "3", name: "待办", list: buckets["3"], emptyText: "暂无待办" }
  ];
}

/** 空态默认页签（后端不可达或无权限时保持，不阻塞顶栏）。 */
export const noticesData: TabItem[] = [
  {
    key: "1",
    name: "通知",
    list: [],
    emptyText: "暂无通知"
  },
  {
    key: "2",
    name: "消息",
    list: [],
    emptyText: "暂无消息"
  },
  {
    key: "3",
    name: "待办",
    list: [],
    emptyText: "暂无待办"
  }
];
