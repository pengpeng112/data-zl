"""暂存层：批次载荷归档、完整清单校验、attempt 只增不覆写。

对应计划 §3.3/§5：
- stage 不等于正式；无完整清单不推断可装载。
- attempt 隔离：同一 batch 的多次暂存互相独立，旧 stage 不得覆盖新内容；
  只有 pagination_complete 且行分类守恒的 attempt 可标记 COMPLETE。
- 载荷在授权 worker 安全区（生产）；本模块提供逻辑对象与校验，不落盘明文。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Sequence

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    ContractViolation,
)


@dataclass
class StagedSlice:
    slice_id: str
    rows: list[tuple]
    row_bytes: int
    payload_sha256: str


@dataclass
class StagedAttempt:
    batch_id: str
    attempt_id: str
    slices: list[StagedSlice] = field(default_factory=list)
    state: str = "PARTIAL"  # PARTIAL / COMPLETE / SUPERSEDED

    def add_slice(self, slice_: StagedSlice) -> None:
        if any(s.slice_id == slice_.slice_id for s in self.slices):
            raise ContractViolation(
                f"分片重复入暂存: {slice_.slice_id}（attempt 内分片唯一）"
            )
        self.slices.append(slice_)

    def total_rows(self) -> int:
        return sum(len(s.rows) for s in self.slices)

    def total_bytes(self) -> int:
        return sum(s.row_bytes for s in self.slices)


class StageStore:
    """内存暂存（生产为授权 worker 暂存区仓储；语义一致）。"""

    def __init__(self) -> None:
        self._attempts: dict[tuple[str, str], StagedAttempt] = {}

    def begin_attempt(self, batch_id: str, attempt_id: str) -> StagedAttempt:
        key = (batch_id, attempt_id)
        if key in self._attempts:
            raise ContractViolation(f"attempt 已存在: {key}")
        attempt = StagedAttempt(batch_id=batch_id, attempt_id=attempt_id)
        self._attempts[key] = attempt
        return attempt

    def get_attempt(self, batch_id: str, attempt_id: str) -> StagedAttempt:
        attempt = self._attempts.get((batch_id, attempt_id))
        if attempt is None:
            raise ContractViolation(f"attempt 不存在: {(batch_id, attempt_id)}")
        return attempt

    def mark_complete_against_manifest(self, manifest: BatchManifest) -> StagedAttempt:
        """只有完整清单（分页完整+守恒）+分片齐全的 attempt 才能标 COMPLETE。"""
        if not manifest.pagination_complete:
            raise ContractViolation(
                f"[{manifest.batch_id}/{manifest.attempt_id}] 分页未完整，"
                "缺分片不得标记暂存完整或推进装载"
            )
        manifest.validate()
        attempt = self.get_attempt(manifest.batch_id, manifest.attempt_id)
        if attempt.state == "SUPERSEDED":
            raise ContractViolation("旧 stage 已被取代，不得复活")
        if attempt.total_rows() != manifest.rows.source_read_rows:
            raise ContractViolation(
                f"暂存行数 {attempt.total_rows()} != manifest 读取行数 "
                f"{manifest.rows.source_read_rows}"
            )
        if len(attempt.slices) != manifest.shard_count:
            raise ContractViolation(
                f"暂存分片 {len(attempt.slices)} != manifest 分片 {manifest.shard_count}"
            )
        payload_hash = hashlib.sha256(
            b"".join(bytes.fromhex(s.payload_sha256) for s in attempt.slices)
        ).hexdigest()
        if payload_hash != manifest.payload_sha256:
            raise ContractViolation("暂存载荷哈希与 manifest 不一致")
        attempt.state = "COMPLETE"
        return attempt

    def select_complete(self, batch_id: str) -> StagedAttempt:
        """选最新 COMPLETE attempt；旧 attempt 显式 SUPERSEDED，不覆盖新内容。"""
        completes = sorted(
            (a for (b, _), a in self._attempts.items()
             if b == batch_id and a.state == "COMPLETE"),
            key=lambda a: a.attempt_id,
        )
        if not completes:
            raise ContractViolation(
                f"[{batch_id}] 无 COMPLETE 暂存尝试（部分 stage 不能装载）"
            )
        chosen = completes[-1]
        for older in completes[:-1]:
            older.state = "SUPERSEDED"
        return chosen

    def attempts_of(self, batch_id: str) -> Sequence[StagedAttempt]:
        return [a for (b, _), a in sorted(self._attempts.items()) if b == batch_id]
