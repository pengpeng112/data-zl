from pathlib import Path

from app.schemas.graph import GraphMeta, GraphNode


ROOT = Path(__file__).resolve().parents[1]


def test_all_graph_routes_have_router_level_view_permission():
    text = (ROOT / "app/api/v1/graph.py").read_text(encoding="utf-8")
    assert 'dependencies=[Depends(require_permission("asset.graph.view"))]' in text
    assert text.count("@router.get") >= 8


def test_neighbor_contract_exposes_degree_and_continuation_metadata():
    node = GraphNode(id="s|c||o|t", label="t", in_degree=2, out_degree=3)
    meta = GraphMeta(
        shown_count=5,
        actual_count=8,
        continuation_cursor="5",
    )
    assert (node.in_degree, node.out_degree) == (2, 3)
    assert meta.continuation_cursor == "5"


def test_neighbor_accepts_only_center_physical_key_for_new_client_contract():
    text = (ROOT / "app/api/v1/graph.py").read_text(encoding="utf-8")
    assert "center_physical_key: str | None" in text
    assert 'include 必须使用五段物理键' in text
    assert "le=3" in text
