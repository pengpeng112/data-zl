"""195 缺陷2：system-context 确定性排序与按系统取相关关系。

纯逻辑（内存 sqlite）：直接调用 system_context 函数，不触外部数据库。
覆盖三点：表清单确定性排序；关系段按端点系统身份取全系统相关关系
（不再因无序前 N 采样恒空）；total_relations 与清单同口径（非全库总数）。
"""
from __future__ import annotations

from app.api.v1.ai import system_context
from app.models import asset as asset_models



def _call(db, system_code="SYS_A", max_tables=30, max_relations=200):
    """直调端点函数：Query 参数必须显式传值（默认值是 FastAPI Query 对象）。"""
    return system_context(
        system_code=system_code, max_tables=max_tables,
        max_relations=max_relations, db=db,
    )


def _mk_table(system_code, schema, name, ns=None):
    return asset_models.AssetTable(
        system_code=system_code, schema_name=schema, namespace_name=ns,
        table_name=name, column_count=3,
    )


def _mk_rel(from_t, to_t, from_sys=None, to_sys=None, jid=1):
    return asset_models.AssetRelation(
        from_table=from_t, to_table=to_t, join_condition=f"k={jid}",
        from_system_code=from_sys, to_system_code=to_sys,
    )


def test_tables_exported_in_deterministic_order(db):
    """195 缺陷2a：无 ORDER BY 时前 N 表依赖数据库返回顺序；插入顺序与
    字典序相反时，limit 必须稳定取字典序在前者（可复现）。"""
    db.add_all([
        _mk_table("SYS_A", "zschema", "zzz"),
        _mk_table("SYS_A", "aschema", "aaa"),
        _mk_table("SYS_A", "aschema", "aab"),
    ])
    db.commit()
    resp = _call(db, max_tables=2)
    data = resp.data
    assert [t["name"] for t in data["tables"]] == ["aschema.aaa", "aschema.aab"]
    assert data["total_tables"] == 3 and data["exported_tables"] == 2


def test_relations_not_limited_to_sampled_tables(db):
    """195 缺陷2b：关系主条件按端点系统身份取全系统相关关系——即使
    采样表（前 N）本身无任何关系，系统内其他表之间的关系也必须出现在
    关系段（此前无序前 N 命中低关联表时关系段恒空）。"""
    db.add_all([
        _mk_table("SYS_A", "s", "t_alpha"),   # 会被采出（字典序在前）
        _mk_table("SYS_A", "s", "t_zulu"),    # 不在 max_tables=1 采样内
        _mk_table("SYS_B", "s", "t_other"),
    ])
    # 关系两端都在 SYS_A，但不在采样表 t_alpha 上
    db.add_all([
        _mk_rel("s.t_zulu", "s.t_zulu2", from_sys="SYS_A", to_sys="SYS_A", jid=1),
    ])
    db.commit()
    resp = _call(db, max_tables=1)
    data = resp.data
    assert [t["name"] for t in data["tables"]] == ["s.t_alpha"]
    names = [(r["from"], r["to"]) for r in data["relations"]]
    assert ("s.t_zulu", "s.t_zulu2") in names


def test_relations_include_legacy_null_endpoint_rows_via_name_match(db):
    """旧数据端点四元组为空：回落采样表名匹配仍然生效（兼容补充），
    且 matched_via 标记 legacy_table_name（202 D2-3：不冒充端点已确认）。"""
    db.add_all([_mk_table("SYS_A", "s", "t_alpha")])
    db.add(_mk_rel("s.t_alpha", "s.t_beta"))  # 无 system 端点码
    db.commit()
    resp = _call(db, max_tables=5)
    by_pair = {(r["from"], r["to"]): r for r in resp.data["relations"]}
    assert ("s.t_alpha", "s.t_beta") in by_pair
    assert by_pair[("s.t_alpha", "s.t_beta")]["matched_via"] == "legacy_table_name"


def test_endpoint_rows_marked_system_endpoint(db):
    """端点四元组命中的关系标记 system_endpoint。"""
    db.add_all([_mk_table("SYS_A", "s", "t_alpha")])
    db.add(_mk_rel("s.t_alpha", "s.t_zulu", from_sys="SYS_A", to_sys="SYS_A"))
    db.commit()
    resp = _call(db, max_tables=5)
    assert resp.data["relations"][0]["matched_via"] == "system_endpoint"


def test_legacy_fallback_restricted_to_current_system_tables(db):
    """202 D2-3：无四元组的他系统表名不得经 legacy 回落混入。"""
    db.add_all([_mk_table("SYS_A", "s", "t_alpha")])
    db.add(_mk_rel("b.t_x", "b.t_y"))  # 无四元组且不在 SYS_A 采样表内
    db.commit()
    resp = _call(db, max_tables=5)
    assert resp.data["relations"] == []
    assert resp.data["exported_relations"] == 0


def test_exported_relations_reflects_cap(db):
    """exported_relations=实际导出条数；截断时 exported<total（202 D2-3 契约）。"""
    db.add_all([_mk_table("SYS_A", "s", "t")])
    db.add_all([
        _mk_rel("s.b", "s.a", from_sys="SYS_A", to_sys="SYS_A", jid=1),
        _mk_rel("s.a", "s.z", from_sys="SYS_A", to_sys="SYS_A", jid=2),
        _mk_rel("s.a", "s.b", from_sys="SYS_A", to_sys="SYS_A", jid=3),
    ])
    db.commit()
    resp = _call(db, max_tables=5, max_relations=2)
    assert resp.data["exported_relations"] == 2
    assert resp.data["total_relations"] == 3  # 计数不随 cap 截断
    resp_full = _call(db, max_tables=5, max_relations=200)
    assert resp_full.data["exported_relations"] == 3
    assert resp_full.data["exported_relations"] == len(resp_full.data["relations"])


def test_relations_excluded_for_other_systems(db):
    """他系统关系不混入：from/to 端点都不是本系统且不匹配采样表名。"""
    db.add_all([_mk_table("SYS_A", "s", "t_alpha")])
    db.add(_mk_rel("o.t_x", "o.t_y", from_sys="SYS_B", to_sys="SYS_B"))
    db.commit()
    resp = _call(db, max_tables=5)
    assert resp.data["relations"] == []
    assert resp.data["total_relations"] == 0


def test_total_relations_scoped_not_global(db):
    """195 缺陷2c：无表命中时 total_relations 不再退化为全库关系总数。"""
    db.add_all([
        _mk_table("SYS_A", "s", "t_alpha"),
        _mk_table("SYS_B", "s", "t_b1"),
    ])
    db.add_all([
        _mk_rel("o1.t_x", "o1.t_y", from_sys="SYS_B", to_sys="SYS_B"),
        _mk_rel("o2.t_x", "o2.t_y", from_sys="SYS_B", to_sys="SYS_B"),
    ])
    db.commit()
    # SYS_A 无表关系：total=0，而非全库 2
    resp = _call(db, max_tables=10)
    assert resp.data["total_relations"] == 0
    # SYS_B：端点计数=2
    resp_b = _call(db, system_code="SYS_B", max_tables=10)
    assert resp_b.data["total_relations"] == 2
    assert len(resp_b.data["relations"]) == 2


def test_max_relations_cap_and_deterministic_relation_order(db):
    """关系确定性排序（from/to/id）与 max_relations 上限生效。"""
    db.add_all([_mk_table("SYS_A", "s", "t")])
    rels = [
        _mk_rel("s.b", "s.a", from_sys="SYS_A", to_sys="SYS_A", jid=1),
        _mk_rel("s.a", "s.z", from_sys="SYS_A", to_sys="SYS_A", jid=2),
        _mk_rel("s.a", "s.b", from_sys="SYS_A", to_sys="SYS_A", jid=3),
    ]
    db.add_all(rels)
    db.commit()
    resp = _call(db, max_tables=5, max_relations=2)
    names = [(r["from"], r["to"]) for r in resp.data["relations"]]
    assert names == [("s.a", "s.b"), ("s.a", "s.z")]
    assert resp.data["total_relations"] == 3  # 计数不受 cap 影响
