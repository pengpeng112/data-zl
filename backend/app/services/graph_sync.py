"""图分析层同步抽象与适配器（98号 S0 / 100号修复）。

PostgreSQL 是唯一事实源；图分析层（Neo4j 或内存适配器）是单向、可重建、可降级的只读副本。

100号修复：
- 默认使用 UnavailableGraphAdapter（health=False），不再默认内存适配器；
- 物理键不接受缺失 system/source 的端点，未解析端点跳过并计入 unresolved_count；
- 同步批次支持 batch_id/idempotency_key 重试；
- checksum 覆盖关系内容而非仅 ID；
- 差集处理增加孤立节点清理；
- error_masked 真正脱敏。
"""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.asset import AssetRelation
from ..models.graph_sync import GraphSyncBatch
from .relation_identity import physical_node_key


def _relation_physical_keys(r: AssetRelation) -> tuple[Optional[str], Optional[str]]:
    """获取关系的起止物理键。缺失必要字段时返回 None（未解析）。"""
    from_key = physical_node_key(
        r.from_system_code, r.from_source_code,
        getattr(r, "from_namespace_name", None),
        r.from_schema_name, r.from_table_name,
    )
    to_key = physical_node_key(
        r.to_system_code, r.to_source_code,
        getattr(r, "to_namespace_name", None),
        r.to_schema_name, r.to_table_name,
    )
    return from_key, to_key


def _relation_to_graph_edge(r: AssetRelation) -> Optional[dict[str, Any]]:
    """把一条 AssetRelation 转成图边字典。端点未解析时返回 None。"""
    from_key, to_key = _relation_physical_keys(r)
    if not from_key or not to_key:
        return None
    return {
        "relation_id": r.id,
        "relation_layer": r.relation_layer,
        "from_physical_key": from_key,
        "to_physical_key": to_key,
        "from_columns": r.from_columns,
        "to_columns": r.to_columns,
        "join_condition": r.join_condition,
        "cardinality": r.cardinality,
        "confidence": r.confidence,
        "validation_status": r.validation_status,
        "relation_business_key": r.relation_business_key,
        "source_updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _edge_content_hash(edge: dict[str, Any]) -> str:
    """计算单条边的内容哈希（用于 checksum）。"""
    content = "|".join([
        str(edge.get("relation_id", "")),
        edge.get("from_physical_key", ""),
        edge.get("to_physical_key", ""),
        edge.get("from_columns", "") or "",
        edge.get("to_columns", "") or "",
        edge.get("join_condition", "") or "",
        edge.get("confidence", "") or "",
        edge.get("relation_layer", "") or "",
    ])
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def _compute_checksum(edges: list[dict[str, Any]]) -> str:
    """计算全部边的内容 checksum（覆盖关系内容，不仅是 ID）。"""
    parts = sorted(_edge_content_hash(e) for e in edges)
    combined = "".join(parts)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def _mask_error(exc: Exception) -> str:
    """脱敏错误信息：移除可能的凭据、连接串、IP。"""
    msg = str(exc).replace("\n", " ")[:200]
    msg = re.sub(r"(password|passwd|pwd|token|secret|api_key)\s*[=:]\s*\S+", r"\1=***", msg, flags=re.IGNORECASE)
    msg = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?", "***", msg)
    return msg


class GraphSyncAdapter:
    """图分析层适配器抽象基类。"""

    def clear(self) -> None:
        raise NotImplementedError

    def upsert_node(self, physical_key: str, properties: dict[str, Any]) -> None:
        raise NotImplementedError

    def upsert_edge(self, edge: dict[str, Any]) -> None:
        raise NotImplementedError

    def delete_edge(self, relation_id: int) -> bool:
        raise NotImplementedError

    def delete_node(self, physical_key: str) -> bool:
        raise NotImplementedError

    def count_nodes(self) -> int:
        raise NotImplementedError

    def count_edges(self) -> int:
        raise NotImplementedError

    def has_edge(self, relation_id: int) -> bool:
        raise NotImplementedError

    def all_relation_ids(self) -> set[int]:
        raise NotImplementedError

    def all_node_keys(self) -> set[str]:
        raise NotImplementedError

    def list_edges(self) -> list[dict[str, Any]]:
        """返回所有边（供图分析查询使用）。"""
        raise NotImplementedError

    def list_nodes(self) -> list[dict[str, Any]]:
        """返回所有节点（供图分析查询使用）。"""
        raise NotImplementedError

    def health(self) -> bool:
        return True


class UnavailableGraphAdapter(GraphSyncAdapter):
    """默认适配器：Neo4j 未配置时使用，health=False，所有操作抛异常。

    100号修复：默认不再是内存适配器，而是明确不可用状态。
    图分析 API 检测到 health=False 时返回 degraded 响应。
    """

    def health(self) -> bool:
        return False

    def clear(self) -> None:
        raise RuntimeError("graph adapter not configured")

    def upsert_node(self, physical_key: str, properties: dict[str, Any]) -> None:
        raise RuntimeError("graph adapter not configured")

    def upsert_edge(self, edge: dict[str, Any]) -> None:
        raise RuntimeError("graph adapter not configured")

    def delete_edge(self, relation_id: int) -> bool:
        raise RuntimeError("graph adapter not configured")

    def delete_node(self, physical_key: str) -> bool:
        raise RuntimeError("graph adapter not configured")

    def count_nodes(self) -> int:
        return 0

    def count_edges(self) -> int:
        return 0

    def has_edge(self, relation_id: int) -> bool:
        return False

    def all_relation_ids(self) -> set[int]:
        return set()

    def all_node_keys(self) -> set[str]:
        return set()

    def list_edges(self) -> list[dict[str, Any]]:
        return []

    def list_nodes(self) -> list[dict[str, Any]]:
        return []


class InMemoryGraphAdapter(GraphSyncAdapter):
    """内存适配器（仅测试或显式 PoC 启用）。"""

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[int, dict[str, Any]] = {}

    def clear(self) -> None:
        self._nodes.clear()
        self._edges.clear()

    def upsert_node(self, physical_key: str, properties: dict[str, Any]) -> None:
        self._nodes[physical_key] = dict(properties)

    def upsert_edge(self, edge: dict[str, Any]) -> None:
        rid = edge["relation_id"]
        self._edges[rid] = dict(edge)
        for side in ("from_physical_key", "to_physical_key"):
            pk = edge.get(side)
            if pk and pk not in self._nodes:
                self._nodes[pk] = {"physical_key": pk}

    def delete_edge(self, relation_id: int) -> bool:
        return self._edges.pop(relation_id, None) is not None

    def delete_node(self, physical_key: str) -> bool:
        return self._nodes.pop(physical_key, None) is not None

    def count_nodes(self) -> int:
        return len(self._nodes)

    def count_edges(self) -> int:
        return len(self._edges)

    def has_edge(self, relation_id: int) -> bool:
        return relation_id in self._edges

    def all_relation_ids(self) -> set[int]:
        return set(self._edges.keys())

    def all_node_keys(self) -> set[str]:
        return set(self._nodes.keys())

    def list_edges(self) -> list[dict[str, Any]]:
        return list(self._edges.values())

    def list_nodes(self) -> list[dict[str, Any]]:
        return list(self._nodes.values())

    def health(self) -> bool:
        return True


def _load_formal_relations(db: Session, since: Optional[datetime] = None) -> list[AssetRelation]:
    """加载正式层关系（formal/sync_mapping）。"""
    stmt = select(AssetRelation).where(
        AssetRelation.relation_layer.in_(["formal", "sync_mapping"])
    )
    if since:
        stmt = stmt.where(AssetRelation.updated_at > since)
    return list(db.scalars(stmt).all())


def _record_batch(
    db: Session,
    *,
    batch_id: str,
    mode: str,
    status: str,
    node_count: int = 0,
    edge_count: int = 0,
    upsert_count: int = 0,
    delete_count: int = 0,
    unresolved_count: int = 0,
    skipped_count: int = 0,
    checksum: Optional[str] = None,
    error_masked: Optional[str] = None,
) -> None:
    """写入或更新同步批次记录（幂等：同 batch_id 更新）。"""
    existing = db.get(GraphSyncBatch, batch_id)
    if existing:
        existing.finished_at = datetime.now(timezone.utc)
        existing.status = status
        existing.node_count = node_count
        existing.edge_count = edge_count
        existing.upsert_count = upsert_count
        existing.delete_count = delete_count
        existing.unresolved_count = unresolved_count
        existing.skipped_count = skipped_count
        existing.checksum = checksum
        existing.error_masked = error_masked
    else:
        db.add(GraphSyncBatch(
            batch_id=batch_id,
            finished_at=datetime.now(timezone.utc),
            status=status,
            mode=mode,
            node_count=node_count,
            edge_count=edge_count,
            upsert_count=upsert_count,
            delete_count=delete_count,
            unresolved_count=unresolved_count,
            skipped_count=skipped_count,
            checksum=checksum,
            error_masked=error_masked,
        ))
    db.commit()


def run_full_rebuild(
    db: Session, adapter: GraphSyncAdapter, batch_id: Optional[str] = None
) -> dict[str, Any]:
    """全量导出 + 从空图重建。幂等：重复执行结果一致。"""
    if not batch_id:
        batch_id = f"full-{uuid.uuid4().hex[:12]}"
    try:
        relations = _load_formal_relations(db)
        adapter.clear()
        upserts = 0
        unresolved = 0
        edges_for_checksum = []
        for r in relations:
            edge = _relation_to_graph_edge(r)
            if edge is None:
                unresolved += 1
                continue
            adapter.upsert_edge(edge)
            edges_for_checksum.append(edge)
            upserts += 1
        node_count = adapter.count_nodes()
        edge_count = adapter.count_edges()
        checksum = _compute_checksum(edges_for_checksum)
        _record_batch(
            db, batch_id=batch_id, mode="full_rebuild", status="success",
            node_count=node_count, edge_count=edge_count,
            upsert_count=upserts, delete_count=0,
            unresolved_count=unresolved, skipped_count=0,
            checksum=checksum, error_masked=None,
        )
        return {
            "batch_id": batch_id, "mode": "full_rebuild", "status": "success",
            "node_count": node_count, "edge_count": edge_count,
            "upsert_count": upserts, "delete_count": 0,
            "unresolved_count": unresolved, "is_degraded": False,
        }
    except Exception as exc:
        _record_batch(
            db, batch_id=batch_id, mode="full_rebuild", status="degraded",
            node_count=0, edge_count=0, upsert_count=0, delete_count=0,
            unresolved_count=0, skipped_count=0,
            checksum=None, error_masked=_mask_error(exc),
        )
        return {"batch_id": batch_id, "mode": "full_rebuild", "status": "degraded", "is_degraded": True}


def run_incremental_upsert(
    db: Session, adapter: GraphSyncAdapter, since: datetime,
    batch_id: Optional[str] = None,
) -> dict[str, Any]:
    """基于可靠 updated_at 的增量 upsert。只承担 upsert。"""
    if not batch_id:
        batch_id = f"incr-{uuid.uuid4().hex[:12]}"
    try:
        changed = _load_formal_relations(db, since=since)
        upserts = 0
        unresolved = 0
        for r in changed:
            edge = _relation_to_graph_edge(r)
            if edge is None:
                unresolved += 1
                continue
            adapter.upsert_edge(edge)
            upserts += 1
        _record_batch(
            db, batch_id=batch_id, mode="incremental", status="success",
            node_count=adapter.count_nodes(), edge_count=adapter.count_edges(),
            upsert_count=upserts, delete_count=0,
            unresolved_count=unresolved, skipped_count=0,
            checksum=None, error_masked=None,
        )
        return {
            "batch_id": batch_id, "mode": "incremental", "status": "success",
            "upsert_count": upserts, "unresolved_count": unresolved, "is_degraded": False,
        }
    except Exception as exc:
        _record_batch(
            db, batch_id=batch_id, mode="incremental", status="degraded",
            node_count=0, edge_count=0, upsert_count=0, delete_count=0,
            unresolved_count=0, skipped_count=0,
            checksum=None, error_masked=_mask_error(exc),
        )
        return {"batch_id": batch_id, "mode": "incremental", "status": "degraded", "is_degraded": True}


def run_daily_diff_check(
    db: Session, adapter: GraphSyncAdapter, batch_id: Optional[str] = None
) -> dict[str, Any]:
    """每日全量差集检测：删除、停用、降级、清理孤立节点。"""
    if not batch_id:
        batch_id = f"diff-{uuid.uuid4().hex[:12]}"
    try:
        relations = _load_formal_relations(db)
        pg_ids = {r.id for r in relations}
        graph_ids = adapter.all_relation_ids()
        stale = graph_ids - pg_ids
        deletes = 0
        for rid in stale:
            if adapter.delete_edge(rid):
                deletes += 1
        # 清理孤立节点（无任何边引用的节点）
        referenced_keys: set[str] = set()
        for edge in adapter.list_edges():
            fk = edge.get("from_physical_key")
            tk = edge.get("to_physical_key")
            if fk:
                referenced_keys.add(fk)
            if tk:
                referenced_keys.add(tk)
        orphan_deletes = 0
        for node_key in adapter.all_node_keys():
            if node_key not in referenced_keys:
                if adapter.delete_node(node_key):
                    orphan_deletes += 1
        _record_batch(
            db, batch_id=batch_id, mode="daily_diff", status="success",
            node_count=adapter.count_nodes(), edge_count=adapter.count_edges(),
            upsert_count=0, delete_count=deletes,
            unresolved_count=0, skipped_count=orphan_deletes,
            checksum=None, error_masked=None,
        )
        return {
            "batch_id": batch_id, "mode": "daily_diff", "status": "success",
            "delete_count": deletes, "orphan_nodes_cleaned": orphan_deletes,
            "is_degraded": False,
        }
    except Exception as exc:
        _record_batch(
            db, batch_id=batch_id, mode="daily_diff", status="degraded",
            node_count=0, edge_count=0, upsert_count=0, delete_count=0,
            unresolved_count=0, skipped_count=0,
            checksum=None, error_masked=_mask_error(exc),
        )
        return {"batch_id": batch_id, "mode": "daily_diff", "status": "degraded", "is_degraded": True}


def last_successful_batch(db: Session) -> Optional[GraphSyncBatch]:
    """查询最近一次成功的同步批次。"""
    return db.scalar(
        select(GraphSyncBatch)
        .where(GraphSyncBatch.status == "success")
        .order_by(GraphSyncBatch.finished_at.desc())
        .limit(1)
    )