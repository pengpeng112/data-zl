"""改写/撤销策略（第一批批1-4）：SNAPSHOT_DIFF CAS 分区 + 父存在性。

无可信源版本（视图无独立变更时间列）时，改写判据不是版本顺序而是
CAS：目标行内容必须等于本管道上次成功装载登记的源内容哈希
（耐久版本账 per-key 证据；采集时间不冒充源版本）。规则：

- 目标无行 → INSERT（合法组）；
- 源内容 == 目标内容 → NO_CHANGE（不写）；
- 目标内容 == 上次登记内容（我们写的还没被别人动）→ UPDATE（CAS 通过）；
- 目标存在但从未由本管道登记，或内容相对上次登记漂移（他人写者）
  → CONFLICT 组：坏组隔离留账，合法组继续，不整批中止；
- 子表行父键不在父表（目标侧）→ PENDING_PARENT 组：只阻对应子键组
  （BLOCKED_DEPENDENCY 留账），合法组继续。

分区结果写入隔离组账（record_quarantine_group），批次部分成功语义
由调用方（production_runtime.apply）落状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.readback_types import (
    ColumnMeta,
    content_fingerprint,
)

CAS_GROUP_KEY = "cas-conflict"
PENDING_PARENT_GROUP_KEY = "missing-parent"


class ApplyPolicyError(ContractViolation):
    """分区失败（输入不完整即拒绝，不猜）。"""


@dataclass
class ApplyPartition:
    """分区结果：合法组 + 各隔离组键集 + 逐键版本证据。"""

    ok_rows: list[Mapping] = field(default_factory=list)
    insert_keys: list[tuple] = field(default_factory=list)
    update_keys: list[tuple] = field(default_factory=list)
    no_change_keys: list[tuple] = field(default_factory=list)
    conflict_keys: list[tuple] = field(default_factory=list)
    missing_parent_keys: list[tuple] = field(default_factory=list)
    row_version_evidences: dict[tuple, str] = field(default_factory=dict)

    def ledger_summary(self) -> dict:
        return {
            "ok": len(self.ok_rows),
            "insert": len(self.insert_keys),
            "update": len(self.update_keys),
            "no_change": len(self.no_change_keys),
            "cas_conflict": len(self.conflict_keys),
            "missing_parent": len(self.missing_parent_keys),
        }


def snapshot_diff_partition(
    *,
    rows: Sequence[Mapping],
    key_columns: Sequence[str],
    metas: Sequence[ColumnMeta],
    target_rows: Mapping[tuple, Mapping],
    registered_version: Callable[[tuple], str | None],
    parent_present: Callable[[object], bool] | None = None,
    parent_key_column: str | None = None,
) -> ApplyPartition:
    """SNAPSHOT_DIFF CAS 分区（批1-4）。

    registered_version(key)：耐久版本账中该键上次登记的源内容哈希；
    None = 本管道从未写过该键。parent_present(parent_key)：目标侧父表
    存在性（已批量读取后闭包判定）。
    """
    if not key_columns:
        raise ApplyPolicyError("分区缺稳定键")
    partition = ApplyPartition()
    for row in rows:
        key = tuple(row.get(c) for c in key_columns)
        if parent_key_column is not None and parent_present is not None:
            parent_value = row.get(parent_key_column)
            if not parent_present(parent_value):
                partition.missing_parent_keys.append(key)
                continue
        source_fp = content_fingerprint(row, metas)
        partition.row_version_evidences[key] = source_fp
        target_row = target_rows.get(key)
        if target_row is None:
            partition.insert_keys.append(key)
            partition.ok_rows.append(row)
            continue
        if content_fingerprint(target_row, metas) == source_fp:
            partition.no_change_keys.append(key)
            continue
        registered = registered_version(key)
        if registered is not None and content_fingerprint(target_row, metas) == registered:
            # CAS 通过：目标仍是本管道上次写的样子
            partition.update_keys.append(key)
            partition.ok_rows.append(row)
        else:
            # 他人写者动过 / 从未由本管道登记 → 不盲覆盖
            partition.conflict_keys.append(key)
    return partition


def record_partition_ledger(
    repository,
    *,
    batch_id: str,
    canonical_table: str,
    partition: ApplyPartition,
) -> list[dict]:
    """把隔离组写入隔离组账；同组已登记（重放）则跳过。返回留账记录。"""
    recorded: list[dict] = []
    groups: list[tuple[str, str, str, list[tuple]]] = []
    if partition.conflict_keys:
        groups.append((
            CAS_GROUP_KEY,
            "SNAPSHOT_DIFF CAS 失败：目标内容相对上次登记漂移或非本管道登记",
            "VERSION_CONFLICT",
            partition.conflict_keys,
        ))
    if partition.missing_parent_keys:
        groups.append((
            PENDING_PARENT_GROUP_KEY,
            "父键不在目标父表：只阻对应子键组，父入库后重放",
            "PENDING_PARENT",
            partition.missing_parent_keys,
        ))
    for group_key, reason, error_code, keys in groups:
        exists = any(
            g.get("group_key") == group_key
            for g in repository.open_quarantine_groups(batch_id)
        )
        if not exists:
            repository.record_quarantine_group(
                batch_id=batch_id,
                canonical_table=canonical_table,
                group_key=group_key,
                reason=reason,
                error_code=error_code,
                rows_quarantined=len(keys),
                detail_ref=f"keys={len(keys)}",
            )
        recorded.append(
            {
                "group_key": group_key,
                "error_code": error_code,
                "rows": len(keys),
            }
        )
    return recorded


def build_parent_presence(
    *,
    parent_rows: Mapping[tuple, Mapping],
    parent_key_columns: Sequence[str],
) -> Callable[[object], bool]:
    """按已读取的父表行构造存在性判定（值 → 布尔）。

    子表父键列通常是单列（DCS_ID/ICH_ID）；父表键也是单列 ID。
    多列复合时按元组匹配。
    """

    def present(value: object) -> bool:
        if value is None:
            return False
        if len(parent_key_columns) == 1:
            return (value,) in parent_rows or value in {
                k[0] for k in parent_rows
            }
        return tuple(value) in parent_rows

    return present
