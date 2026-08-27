export interface SnapshotOption {
  id: number;
  label?: string | null;
  snapshot_time?: string | null;
}

export function snapshotOrderError(
  fromId: number | null,
  toId: number | null,
  snapshots: SnapshotOption[]
): string | null {
  if (fromId == null || toId == null) return "请选择起始和目标快照";
  if (fromId === toId) return "起始和目标快照不能相同";
  const from = snapshots.find(item => item.id === fromId);
  const to = snapshots.find(item => item.id === toId);
  if (!from || !to) return "所选快照已不属于当前数据连接";
  const fromTime = Date.parse(from.snapshot_time || "");
  const toTime = Date.parse(to.snapshot_time || "");
  if (Number.isFinite(fromTime) && Number.isFinite(toTime) && fromTime >= toTime) {
    return "起始快照时间必须早于目标快照";
  }
  return null;
}
