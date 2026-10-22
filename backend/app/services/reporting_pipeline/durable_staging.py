"""耐久暂存（R02）：受控目录分块落盘 + 原子清单 + 重启恢复。

对应整改计划 §R02：
- 原始行只进入批准的受控暂存目录，按 attempt 分目录隔离；旧 attempt 不
  覆盖新内容（只增不覆写）。
- 分块（chunk）写文件：临时名 + 原子 rename，进程崩溃最多留下未完成
  分块，不会出现"半文件被当完整"。
- COMPLETE 清单（manifest.json）最后一步原子写入，包含范围、源身份、
  列/定义哈希、行/字节、逐块校验摘要和完整结束证据；缺任一分块、缺
  完整结束证据、被取消的 attempt 一律不得标完整。
- 读取按块流式迭代，不把整月数据塞进内存。
- 本模块不落明文患者数据进 Git/日志；目录由部署方按受控暂存区授权。
- 内存 StageStore 保留为模拟实现；生产装配必须用本耐久实现（或等价
  对象存储实现，接口一致）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from app.services.reporting_pipeline.contracts import (
    BatchManifest,
    ContractViolation,
)

_ATTEMPT_DIR_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
MANIFEST_FILENAME = "manifest.json"
COMPLETION_MARKER = "complete.json"
CHUNK_PREFIX = "chunk-"
CHUNK_SUFFIX = ".bin"


@dataclass(frozen=True)
class ChunkInfo:
    chunk_id: str
    row_count: int
    byte_count: int
    sha256: str


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DurableFileStageStore:
    """受控目录耐久暂存：attempt 目录 + 分块文件 + 原子完成清单。

    纯文件系统实现，重启后 scan 恢复；PG 控制面（attempt 表）与本目录
    各自记账，装载选择以本目录的 COMPLETE 清单为准。
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- 路径与安全 ---------------------------------------------------------

    def _attempt_dir(self, batch_id: str, attempt_id: str) -> Path:
        for part in (batch_id, attempt_id):
            if not _ATTEMPT_DIR_RE.match(part):
                raise ContractViolation(f"非法 attempt 路径段: {part!r}")
        return self.root / batch_id / attempt_id

    def attempts_of(self, batch_id: str) -> list[str]:
        batch_dir = self.root / batch_id
        if not batch_dir.exists():
            return []
        return sorted(p.name for p in batch_dir.iterdir() if p.is_dir())

    # -- 写入 ---------------------------------------------------------------

    def begin_attempt(self, batch_id: str, attempt_id: str) -> Path:
        """创建 attempt 目录；已存在即拒绝（attempt 只增不覆写）。"""
        directory = self._attempt_dir(batch_id, attempt_id)
        if directory.exists():
            raise ContractViolation(f"attempt 已存在: {batch_id}/{attempt_id}")
        directory.mkdir(parents=True)
        return directory

    def write_chunk(self, batch_id: str, attempt_id: str, chunk_id: str,
                    payload: bytes, row_count: int) -> ChunkInfo:
        """写一个分块：临时文件 + 原子 rename；同 chunk_id 不得重复写。"""
        if not _ATTEMPT_DIR_RE.match(chunk_id):
            raise ContractViolation(f"非法 chunk_id: {chunk_id!r}")
        directory = self._attempt_dir(batch_id, attempt_id)
        if not directory.exists():
            raise ContractViolation("attempt 未 begin 即写分块（拒绝裸写）")
        final_path = directory / f"{CHUNK_PREFIX}{chunk_id}{CHUNK_SUFFIX}"
        if final_path.exists():
            raise ContractViolation(f"分块重复写入: {chunk_id}（attempt 内唯一）")
        tmp_path = directory / f".tmp-{chunk_id}-{os.getpid()}"
        tmp_path.write_bytes(payload)
        os.replace(tmp_path, final_path)  # 原子可见
        info = ChunkInfo(
            chunk_id=chunk_id,
            row_count=row_count,
            byte_count=len(payload),
            sha256=_sha_bytes(payload),
        )
        (directory / f"{CHUNK_PREFIX}{chunk_id}.meta.json").write_text(
            json.dumps(
                {
                    "chunk_id": info.chunk_id,
                    "row_count": info.row_count,
                    "byte_count": info.byte_count,
                    "sha256": info.sha256,
                }
            ),
            encoding="utf-8",
        )
        return info

    def write_chunk_stream(self, batch_id: str, attempt_id: str, chunk_id: str,
                           rows: Sequence[Sequence[object]], row_count: int) -> ChunkInfo:
        """行序列 → JSON 行分块（每行一个 JSON，换行分隔；字节确定性编码）。"""
        payload = b"".join(
            json.dumps(list(row), ensure_ascii=False, default=str).encode("utf-8") + b"\n"
            for row in rows
        )
        return self.write_chunk(batch_id, attempt_id, chunk_id, payload, row_count)

    def cancel_attempt(self, batch_id: str, attempt_id: str) -> None:
        """取消：删除分块与临时文件，写 CANCELLED 标记（不得再标完整）。"""
        directory = self._attempt_dir(batch_id, attempt_id)
        if not directory.exists():
            return
        for item in directory.iterdir():
            if item.name.startswith(CHUNK_PREFIX):
                item.unlink(missing_ok=True)
            elif item.name.startswith(".tmp-"):
                item.unlink(missing_ok=True)
        (directory / "CANCELLED").write_text(
            "cancelled_at_unknown_clock", encoding="utf-8"
        )

    # -- 完整性清单 ----------------------------------------------------------

    def mark_complete_against_manifest(
        self,
        batch_id: str,
        attempt_id: str,
        manifest: BatchManifest,
        *,
        source_identity: str,
        definition_fingerprint: str | None,
    ) -> dict:
        """核验分块齐全/行数字节/哈希后原子写 COMPLETE 清单。

        - manifest 分页不完整 → 拒绝；
        - 有 CANCELLED 标记 → 拒绝（取消的 attempt 不得复活为完整）；
        - 分块数与 manifest.shard_count 不一致 → 拒绝；
        - 行数与 manifest.rows.source_read_rows 不一致 → 拒绝；
        - 逐块哈希与整体载荷哈希对不上 → 拒绝；
        - 已有 COMPLETE 清单 → 幂等返回（字节一致时）。
        """
        if not manifest.pagination_complete:
            raise ContractViolation(
                f"[{batch_id}/{attempt_id}] 分页未完整，缺分片不得标记暂存完整"
            )
        manifest.validate()
        directory = self._attempt_dir(batch_id, attempt_id)
        if (directory / "CANCELLED").exists():
            raise ContractViolation("已取消的 attempt 不得标记完整")
        chunks = self.read_chunk_infos(batch_id, attempt_id)
        if len(chunks) != manifest.shard_count:
            raise ContractViolation(
                f"暂存分块 {len(chunks)} != manifest 分片 {manifest.shard_count}"
            )
        total_rows = sum(c.row_count for c in chunks)
        if total_rows != manifest.rows.source_read_rows:
            raise ContractViolation(
                f"暂存行数 {total_rows} != manifest 读取行数 "
                f"{manifest.rows.source_read_rows}"
            )
        combined = hashlib.sha256()
        for chunk in chunks:
            combined.update(bytes.fromhex(chunk.sha256))
        if combined.hexdigest() != manifest.payload_sha256:
            # 兼容"整载荷哈希"口径：逐块哈希串接对不上时，再用原始字节整体校验
            whole = hashlib.sha256()
            for chunk in chunks:
                whole.update(self._chunk_path(batch_id, attempt_id, chunk.chunk_id).read_bytes())
            if whole.hexdigest() != manifest.payload_sha256:
                raise ContractViolation("暂存载荷哈希与 manifest 不一致")
        document = {
            "batch_id": batch_id,
            "attempt_id": attempt_id,
            "source_identity": source_identity,
            "definition_fingerprint": definition_fingerprint,
            "window_fingerprint": manifest.window_fingerprint,
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "row_count": c.row_count,
                    "byte_count": c.byte_count,
                    "sha256": c.sha256,
                }
                for c in chunks
            ],
            "total_rows": total_rows,
            "total_bytes": sum(c.byte_count for c in chunks),
            "payload_sha256": manifest.payload_sha256,
            "end_reason": manifest.end_reason.value,
            "completion_evidence": {
                "pagination_complete": True,
                "rows_conserved": total_rows == manifest.rows.source_read_rows,
                "chunks_verified": len(chunks),
            },
        }
        marker = directory / COMPLETION_MARKER
        if marker.exists():
            existing = json.loads(marker.read_text(encoding="utf-8"))
            if existing.get("payload_sha256") != document["payload_sha256"]:
                raise ContractViolation(
                    "COMPLETE 清单已存在且内容不同（attempt 不可变，需新 attempt）"
                )
            return existing
        tmp = directory / ".tmp-complete"
        tmp.write_text(
            json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(tmp, marker)
        return document

    # -- 恢复与读取 ----------------------------------------------------------

    def read_chunk_infos(self, batch_id: str, attempt_id: str) -> list[ChunkInfo]:
        """扫描 attempt 目录的块元数据（重启恢复入口）。"""
        directory = self._attempt_dir(batch_id, attempt_id)
        if not directory.exists():
            raise ContractViolation(f"attempt 不存在: {batch_id}/{attempt_id}")
        infos: list[ChunkInfo] = []
        for meta in sorted(directory.glob(f"{CHUNK_PREFIX}*.meta.json")):
            document = json.loads(meta.read_text(encoding="utf-8"))
            infos.append(
                ChunkInfo(
                    chunk_id=document["chunk_id"],
                    row_count=int(document["row_count"]),
                    byte_count=int(document["byte_count"]),
                    sha256=document["sha256"],
                )
            )
        return infos

    def _chunk_path(self, batch_id: str, attempt_id: str, chunk_id: str) -> Path:
        return (
            self._attempt_dir(batch_id, attempt_id)
            / f"{CHUNK_PREFIX}{chunk_id}{CHUNK_SUFFIX}"
        )

    def verify_chunk_integrity(self, batch_id: str, attempt_id: str) -> dict:
        """逐块重算哈希：损坏/被篡改/半文件（rename 前崩溃不会出现半块，
        但外力截断会出现）在装载前被拒。"""
        results = {"chunks": 0, "mismatch": [], "missing": []}
        for info in self.read_chunk_infos(batch_id, attempt_id):
            path = self._chunk_path(batch_id, attempt_id, info.chunk_id)
            if not path.exists():
                results["missing"].append(info.chunk_id)
                continue
            results["chunks"] += 1
            if _sha_bytes(path.read_bytes()) != info.sha256:
                results["mismatch"].append(info.chunk_id)
        return results

    def iter_chunk_rows(self, batch_id: str, attempt_id: str) -> Iterator[list]:
        """流式读取行（每块一个 JSON 行）；装载/回读逐块迭代不整月进内存。"""
        for info in self.read_chunk_infos(batch_id, attempt_id):
            path = self._chunk_path(batch_id, attempt_id, info.chunk_id)
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    yield json.loads(line)

    def is_complete(self, batch_id: str, attempt_id: str) -> bool:
        directory = self._attempt_dir(batch_id, attempt_id)
        return (directory / COMPLETION_MARKER).exists()

    def load_complete_document(self, batch_id: str, attempt_id: str) -> dict:
        directory = self._attempt_dir(batch_id, attempt_id)
        marker = directory / COMPLETION_MARKER
        if not marker.exists():
            raise ContractViolation(
                f"[{batch_id}/{attempt_id}] 无 COMPLETE 清单（部分 stage 不能装载）"
            )
        return json.loads(marker.read_text(encoding="utf-8"))

    def select_complete(self, batch_id: str) -> dict:
        """选最新 COMPLETE attempt 的清单；无完整版本时报未完整。"""
        chosen: tuple[str, dict] | None = None
        for attempt_id in self.attempts_of(batch_id):
            if self.is_complete(batch_id, attempt_id):
                document = self.load_complete_document(batch_id, attempt_id)
                if chosen is None or attempt_id > chosen[0]:
                    chosen = (attempt_id, document)
        if chosen is None:
            raise ContractViolation(
                f"[{batch_id}] 无 COMPLETE 暂存尝试（部分 stage 不能装载）"
            )
        return chosen[1]

    def discard_attempt(self, batch_id: str, attempt_id: str) -> None:
        """整 attempt 丢弃（失败重试前清理；不触碰其他 attempt）。"""
        directory = self._attempt_dir(batch_id, attempt_id)
        if directory.exists():
            shutil.rmtree(directory)
