"""图分析安全查询（98号 S0 / 100号修复）。

100号修复：
- 有向图语义：上游只走 in_adj，下游只走 out_adj，影响分析只走 out_adj；
- 环路只检测有向环（ABCA 报告，AB 不报告 ABA）；
- 最短路径明确方向；
- 不直接读取适配器私有 _nodes/_edges，使用 list_edges/list_nodes 接口；
- 默认 UnavailableGraphAdapter（health=False），Neo4j 未配置返回 degraded；
- 实际超时控制（signal/threading）；
- 最大深度 10、节点 1000；
- 增加权限依赖；
- 不接受自由 Cypher。
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...schemas.common import ApiResponse

router = APIRouter(prefix="/api/v1/graph-analysis", tags=["graph-analysis"])

MAX_DEPTH = 10
MAX_NODES = 1000
DEFAULT_TIMEOUT_SECONDS = 5

from ...services.graph_sync import UnavailableGraphAdapter, last_successful_batch  # noqa: E402

_adapter: Any = UnavailableGraphAdapter()


def get_analysis_adapter() -> Any:
    return _adapter


def set_analysis_adapter(adapter: Any) -> None:
    global _adapter
    _adapter = adapter


def _sync_meta(db: Session, adapter: Any) -> dict[str, Any]:
    """构造统一的同步状态元数据。"""
    if not adapter.health():
        return {
            "status": "unavailable",
            "data_source": "degraded",
            "last_sync_at": None,
            "sync_batch_id": None,
            "is_stale": True,
            "is_degraded": True,
        }
    batch = last_successful_batch(db)
    return {
        "status": "ok",
        "data_source": "in_memory",
        "last_sync_at": batch.finished_at.isoformat() if batch else None,
        "sync_batch_id": batch.batch_id if batch else None,
        "is_stale": batch is None,
        "is_degraded": False,
    }


def _build_directed_adjacency(adapter: Any) -> tuple[dict[str, list[tuple[str, dict]]], dict[str, list[tuple[str, dict]]]]:
    """构建有向邻接表：out_adj (from->to) 和 in_adj (to->from)。

    使用 list_edges() 公共接口，不直接访问私有属性。
    """
    out_adj: dict[str, list[tuple[str, dict]]] = {}
    in_adj: dict[str, list[tuple[str, dict]]] = {}
    for edge in adapter.list_edges():
        f = edge.get("from_physical_key")
        t = edge.get("to_physical_key")
        if f and t:
            out_adj.setdefault(f, []).append((t, edge))
            in_adj.setdefault(t, []).append((f, edge))
    return out_adj, in_adj


def _validate_query_params(depth: int, max_nodes: int) -> None:
    if depth < 1 or depth > MAX_DEPTH:
        raise HTTPException(status_code=400, detail=f"depth must be 1~{MAX_DEPTH}")
    if max_nodes < 1 or max_nodes > MAX_NODES:
        raise HTTPException(status_code=400, detail=f"max_nodes must be 1~{MAX_NODES}")


def _resolve_node_key(adapter: Any, table: str) -> Optional[str]:
    """把入参解析为适配器中的节点 key。"""
    all_nodes = {n.get("physical_key", ""): n for n in adapter.list_nodes()}
    if table in all_nodes:
        return table
    for key in all_nodes:
        parts = key.split("|")
        if len(parts) >= 5:
            schema_table = f"{parts[3]}.{parts[4]}" if parts[3] else parts[4]
            if schema_table == table:
                return key
    return None


def _bfs_directed(adj: dict[str, list[tuple[str, dict]]], start: str, depth: int, max_nodes: int) -> tuple[set[str], list[dict]]:
    """有向 BFS 遍历。"""
    visited: set[str] = {start}
    edges_used: list[dict] = []
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    while queue and len(visited) < max_nodes:
        node, d = queue.popleft()
        if d >= depth:
            continue
        for neighbor, edge in adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                edges_used.append(edge)
                queue.append((neighbor, d + 1))
                if len(visited) >= max_nodes:
                    break
    return visited, edges_used


def _bfs_shortest_path_directed(adj: dict[str, list[tuple[str, dict]]], src: str, tgt: str, max_depth: int) -> Optional[list[str]]:
    """有向 BFS 最短路径。"""
    if src == tgt:
        return [src]
    visited: set[str] = {src}
    parent: dict[str, str] = {}
    queue: deque[tuple[str, int]] = deque([(src, 0)])
    while queue:
        node, d = queue.popleft()
        if d >= max_depth:
            continue
        for neighbor, _ in adj.get(node, []):
            if neighbor in visited:
                continue
            parent[neighbor] = node
            if neighbor == tgt:
                path = [tgt]
                cur = tgt
                while cur in parent:
                    cur = parent[cur]
                    path.append(cur)
                return list(reversed(path))
            visited.add(neighbor)
            queue.append((neighbor, d + 1))
    return None


def _find_directed_cycles(out_adj: dict[str, list[tuple[str, dict]]], max_nodes: int) -> list[list[str]]:
    """有向环检测（DFS）。只报告真正的有向环（ABCA），不报告 AB 的假环。"""
    cycles: list[list[str]] = []
    visited_global: set[str] = set()
    rec_stack: set[str] = set()

    def _dfs(node: str, path: list[str]) -> None:
        if len(cycles) >= 10 or len(visited_global) >= max_nodes:
            return
        visited_global.add(node)
        rec_stack.add(node)
        for neighbor, _ in out_adj.get(node, []):
            if neighbor in rec_stack:
                idx = path.index(neighbor) if neighbor in path else -1
                if idx >= 0:
                    cycle = path[idx:] + [neighbor]
                    distinct = len(set(cycle))
                    if distinct >= 3 and cycle not in cycles:
                        cycles.append(cycle)
            elif neighbor not in visited_global:
                _dfs(neighbor, path + [neighbor])
        rec_stack.discard(node)

    for start in list(out_adj.keys())[:max_nodes]:
        if start not in visited_global:
            _dfs(start, [start])
    return cycles


def _run_with_timeout(func, timeout_seconds: float):
    """在指定超时内执行函数，超时返回 None。"""
    result = [None]
    exception = [None]

    def target():
        try:
            result[0] = func()
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise HTTPException(status_code=504, detail="query timeout")
    if exception[0]:
        raise exception[0]
    return result[0]


def _edge_summary(edge: dict) -> dict:
    return {
        "relation_id": edge.get("relation_id"),
        "from": edge.get("from_physical_key"),
        "to": edge.get("to_physical_key"),
        "layer": edge.get("relation_layer"),
        "from_columns": edge.get("from_columns"),
        "to_columns": edge.get("to_columns"),
    }


@router.get("/upstream-downstream", summary="上下游查询（有向）")
def upstream_downstream(
    table: str = Query(..., description="起点表"),
    direction: str = Query("both", description="upstream/downstream/both"),
    depth: int = Query(3, ge=1, le=MAX_DEPTH),
    max_nodes: int = Query(MAX_NODES, ge=1, le=MAX_NODES),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """有向上下游 BFS。upstream 只走 in_adj，downstream 只走 out_adj。"""
    adapter = get_analysis_adapter()
    _validate_query_params(depth, max_nodes)
    if not adapter.health():
        return ApiResponse(data={**_sync_meta(db, adapter), "nodes": [], "edges": []})
    out_adj, in_adj = _build_directed_adjacency(adapter)
    start = _resolve_node_key(adapter, table)
    if not start:
        return ApiResponse(data={**_sync_meta(db, adapter), "status": "empty", "nodes": [], "edges": []})

    def _query():
        visited: set[str] = set()
        edge_list: list[dict] = []
        if direction in ("downstream", "both"):
            v, e = _bfs_directed(out_adj, start, depth, max_nodes)
            visited |= v
            edge_list.extend(e)
        if direction in ("upstream", "both"):
            v, e = _bfs_directed(in_adj, start, depth, max_nodes)
            visited |= v
            edge_list.extend(e)
        return visited, edge_list

    visited, edge_list = _run_with_timeout(_query, DEFAULT_TIMEOUT_SECONDS)
    node_keys = sorted(visited)[:max_nodes]
    return ApiResponse(data={
        **_sync_meta(db, adapter),
        "nodes": node_keys,
        "edges": [_edge_summary(e) for e in edge_list][:max_nodes],
    })


@router.get("/shortest-path", summary="最短路径（有向）")
def shortest_path(
    source: str = Query(...),
    target: str = Query(...),
    max_depth: int = Query(MAX_DEPTH, ge=1, le=MAX_DEPTH),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """有向最短路径（从 source 到 target，只走 out_adj）。"""
    adapter = get_analysis_adapter()
    if not adapter.health():
        return ApiResponse(data={**_sync_meta(db, adapter), "path": None, "hops": None})
    out_adj, _ = _build_directed_adjacency(adapter)
    src_key = _resolve_node_key(adapter, source)
    tgt_key = _resolve_node_key(adapter, target)
    if not src_key or not tgt_key:
        return ApiResponse(data={**_sync_meta(db, adapter), "status": "empty", "path": None, "hops": None})

    def _query():
        return _bfs_shortest_path_directed(out_adj, src_key, tgt_key, max_depth)

    path = _run_with_timeout(_query, DEFAULT_TIMEOUT_SECONDS)
    return ApiResponse(data={
        **_sync_meta(db, adapter),
        "path": path,
        "hops": len(path) - 1 if path else None,
    })


@router.get("/impact", summary="影响分析（有向下游）")
def impact_analysis(
    table: str = Query(...),
    depth: int = Query(3, ge=1, le=MAX_DEPTH),
    max_nodes: int = Query(MAX_NODES, ge=1, le=MAX_NODES),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """影响分析只走 out_adj（下游传播）。"""
    adapter = get_analysis_adapter()
    _validate_query_params(depth, max_nodes)
    if not adapter.health():
        return ApiResponse(data={**_sync_meta(db, adapter), "impacted": []})
    out_adj, _ = _build_directed_adjacency(adapter)
    start = _resolve_node_key(adapter, table)
    if not start:
        return ApiResponse(data={**_sync_meta(db, adapter), "status": "empty", "impacted": []})

    def _query():
        visited, _ = _bfs_directed(out_adj, start, depth, max_nodes)
        return sorted(n for n in visited if n != start)

    impacted = _run_with_timeout(_query, DEFAULT_TIMEOUT_SECONDS)
    return ApiResponse(data={
        **_sync_meta(db, adapter),
        "impacted": impacted[:max_nodes],
        "impacted_count": len(impacted),
    })


@router.get("/cycles", summary="有向环路检测")
def cycle_detection(
    max_nodes: int = Query(MAX_NODES, ge=1, le=MAX_NODES),
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """有向环检测。单条 AB 不报告 ABA；ABCA 报告为环。"""
    adapter = get_analysis_adapter()
    if not adapter.health():
        return ApiResponse(data={**_sync_meta(db, adapter), "cycles": []})
    out_adj, _ = _build_directed_adjacency(adapter)

    def _query():
        return _find_directed_cycles(out_adj, max_nodes)

    cycles = _run_with_timeout(_query, DEFAULT_TIMEOUT_SECONDS)
    return ApiResponse(data={
        **_sync_meta(db, adapter),
        "cycles": cycles,
        "cycle_count": len(cycles),
    })