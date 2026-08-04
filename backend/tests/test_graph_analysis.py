"""图分析查询的纯逻辑测试（100号修复）。

不依赖数据库或 TestClient，直接测试有向图算法逻辑。
覆盖：有向上游/下游、影响分析、无向假环不报告、真实有向环报告、
默认未配置返回 degraded、超时与结果限制、多关系不被错误去重。
"""
from __future__ import annotations

import pytest

from app.services.graph_sync import InMemoryGraphAdapter, UnavailableGraphAdapter
from app.api.v1.graph_analysis import (
    _build_directed_adjacency,
    _bfs_directed,
    _bfs_shortest_path_directed,
    _find_directed_cycles,
    _resolve_node_key,
)


def _make_adapter_with_edges(edges: list[dict]) -> InMemoryGraphAdapter:
    adapter = InMemoryGraphAdapter()
    for edge in edges:
        adapter.upsert_edge(edge)
    return adapter


def _edge(rid, from_key, to_key, **kw):
    return {
        "relation_id": rid,
        "from_physical_key": from_key,
        "to_physical_key": to_key,
        "relation_layer": "formal",
        "from_columns": kw.get("from_columns", "PID"),
        "to_columns": kw.get("to_columns", "PID"),
        "join_condition": kw.get("join_condition", "a=b"),
        "confidence": "A",
        "validation_status": "verified",
        "relation_business_key": f"bk-{rid}",
    }


class TestDirectedUpDownstream:
    def test_downstream_only_out_adj(self):
        """下游只走 out_adj（from->to）。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
            _edge(2, "A|s||S|T2", "A|s||S|T3"),
        ])
        out_adj, in_adj = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(out_adj, "A|s||S|T1", 3, 100)
        assert "A|s||S|T2" in visited
        assert "A|s||S|T3" in visited

    def test_upstream_only_in_adj(self):
        """上游只走 in_adj（to->from）。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
            _edge(2, "A|s||S|T2", "A|s||S|T3"),
        ])
        out_adj, in_adj = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(in_adj, "A|s||S|T3", 3, 100)
        assert "A|s||S|T2" in visited
        assert "A|s||S|T1" in visited

    def test_downstream_does_not_go_backwards(self):
        """下游不会反向遍历。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(out_adj, "A|s||S|T2", 3, 100)
        assert "A|s||S|T1" not in visited

    def test_upstream_does_not_go_forwards(self):
        """上游不会正向遍历。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
        ])
        _, in_adj = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(in_adj, "A|s||S|T1", 3, 100)
        assert "A|s||S|T2" not in visited


class TestDirectedImpact:
    def test_impact_only_downstream(self):
        """影响分析只走 out_adj。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
            _edge(2, "A|s||S|T3", "A|s||S|T1"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(out_adj, "A|s||S|T1", 3, 100)
        impacted = {n for n in visited if n != "A|s||S|T1"}
        assert "A|s||S|T2" in impacted
        assert "A|s||S|T3" not in impacted


class TestDirectedShortestPath:
    def test_path_follows_direction(self):
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
            _edge(2, "A|s||S|T2", "A|s||S|T3"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        path = _bfs_shortest_path_directed(out_adj, "A|s||S|T1", "A|s||S|T3", 10)
        assert path == ["A|s||S|T1", "A|s||S|T2", "A|s||S|T3"]

    def test_reverse_path_not_found(self):
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        path = _bfs_shortest_path_directed(out_adj, "A|s||S|T2", "A|s||S|T1", 10)
        assert path is None

    def test_same_node_self_path(self):
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        path = _bfs_shortest_path_directed(out_adj, "A|s||S|T1", "A|s||S|T1", 10)
        assert path == ["A|s||S|T1"]


class TestDirectedCycles:
    def test_single_edge_ab_no_false_cycle(self):
        """单条 AB 不报告 ABA 假环。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|A", "A|s||S|B"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        cycles = _find_directed_cycles(out_adj, 100)
        assert len(cycles) == 0

    def test_real_directed_cycle_abca(self):
        """ABCA 应报告为环。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|A", "A|s||S|B"),
            _edge(2, "A|s||S|B", "A|s||S|C"),
            _edge(3, "A|s||S|C", "A|s||S|A"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        cycles = _find_directed_cycles(out_adj, 100)
        assert len(cycles) >= 1
        cycle_nodes = set()
        for c in cycles:
            cycle_nodes.update(c)
        assert "A|s||S|A" in cycle_nodes
        assert "A|s||S|B" in cycle_nodes
        assert "A|s||S|C" in cycle_nodes

    def test_bidirectional_ab_not_cycle(self):
        """A->B 和 B->A 两条边不构成环（长度2排除）。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|A", "A|s||S|B"),
            _edge(2, "A|s||S|B", "A|s||S|A"),
        ])
        out_adj, _ = _build_directed_adjacency(adapter)
        cycles = _find_directed_cycles(out_adj, 100)
        assert len(cycles) == 0


class TestDefaultUnavailable:
    def test_unavailable_health_false(self):
        """默认未配置返回 degraded。"""
        adapter = UnavailableGraphAdapter()
        assert adapter.health() is False

    def test_unavailable_returns_empty(self):
        adapter = UnavailableGraphAdapter()
        assert adapter.list_edges() == []
        assert adapter.list_nodes() == []
        assert adapter.count_nodes() == 0


class TestResultLimits:
    def test_max_nodes_respected(self):
        edges = [_edge(i, f"S|s||S|T{i}", f"S|s||S|T{i+1}") for i in range(20)]
        adapter = _make_adapter_with_edges(edges)
        out_adj, _ = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(out_adj, "S|s||S|T0", 10, 5)
        assert len(visited) <= 5

    def test_max_depth_respected(self):
        edges = [_edge(i, f"S|s||S|T{i}", f"S|s||S|T{i+1}") for i in range(20)]
        adapter = _make_adapter_with_edges(edges)
        out_adj, _ = _build_directed_adjacency(adapter)
        visited, _ = _bfs_directed(out_adj, "S|s||S|T0", 2, 1000)
        assert len(visited) <= 3


class TestMultiRelationNotDeduped:
    def test_multiple_edges_same_nodes(self):
        """同一对节点的多条关系（不同字段/条件）不被错误去重。"""
        adapter = _make_adapter_with_edges([
            _edge(1, "A|s||S|T1", "A|s||S|T2", from_columns="PID", join_condition="a.pid=b.pid"),
            _edge(2, "A|s||S|T1", "A|s||S|T2", from_columns="VID", join_condition="a.vid=b.vid"),
        ])
        assert adapter.count_edges() == 2
        out_adj, _ = _build_directed_adjacency(adapter)
        assert len(out_adj.get("A|s||S|T1", [])) == 2