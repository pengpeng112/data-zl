# -*- coding: utf-8 -*-
"""r198 B2 验收用例 T01—T08（纯逻辑，无数据库）。

运行：python -m pytest tools/tests/test_r198_sql_parse.py -q
不加载 backend/tests/conftest.py（无清库 fixture）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import r198_sql_parse as rsp  # noqa: E402


def edges(sql):
    return rsp.parse_sql(sql)['edges']


def unresolved(sql):
    return rsp.parse_sql(sql)['unresolved']


# ---------------------------------------------------------------- T01
def test_t01_explicit_join_directions():
    e = edges('SELECT a.id FROM T_A a LEFT JOIN T_B b ON a.id=b.id')[0]
    assert e['join_type'] == 'left' and e['l_table'] == 'T_A' and e['r_table'] == 'T_B'
    assert e['l_col'] == 'ID' and e['r_col'] == 'ID'

    e = edges('SELECT a.id FROM T_A a RIGHT JOIN T_B b ON a.id=b.id')[0]
    assert e['join_type'] == 'right'

    e = edges('SELECT a.id FROM T_A a FULL OUTER JOIN T_B b ON a.id=b.id')[0]
    assert e['join_type'] == 'full'

    e = edges('SELECT a.id FROM T_A a INNER JOIN T_B b ON a.id=b.id')[0]
    assert e['join_type'] == 'inner'

    e = edges('SELECT a.id FROM T_A a JOIN T_B b ON a.id=b.id')[0]
    assert e['join_type'] == 'inner'

    # 逗号 JOIN（Oracle 旧式）默认 inner，不带 plus
    e = edges('SELECT a.id FROM T_A a, T_B b WHERE a.id=b.id')[0]
    assert e.get('join_type') not in ('left', 'right', 'full')
    assert e['plus_side'] is None


def test_t01_oracle_plus_direction():
    # (+) 在右 → 右侧 null 补齐 → 语义 LEFT JOIN（保留左）
    e = edges('SELECT a.id FROM T_A a, T_B b WHERE a.id=b.id(+)')[0]
    assert e['plus_side'] == 'R'
    # (+) 在左 → 保留右
    e = edges('SELECT a.id FROM T_A a, T_B b WHERE a.id(+) = b.id')[0]
    assert e['plus_side'] == 'L'


# ---------------------------------------------------------------- T02
def test_t02_or_not_composed_and_same_node_only():
    sql = 'SELECT a.id FROM T_A a, T_B b WHERE a.id=b.id OR a.alt=b.alt'
    es = edges(sql)
    assert len(es) == 2
    assert es[0]['branch'] != es[1]['branch'] or es[0]['raw'] != es[1]['raw']
    # 复合键生成层（tools.r198_familybuild）只合 AND 同节点——此处锁分支路径不同
    assert {tuple(e['branch']) for e in es} == {(0,), (1,)}

    sql = 'SELECT a.id FROM T_A a, T_B b WHERE a.id=b.id AND a.alt=b.alt'
    es = edges(sql)
    assert len(es) == 2 and all(tuple(e['branch']) == () for e in es)

    # AND 内含 OR：OR 分支内的等值不得与 AND 顶层等值合并
    sql = 'SELECT a.id FROM T_A a, T_B b WHERE a.k=b.k AND (a.x=b.x OR a.y=b.y)'
    es = edges(sql)
    assert len(es) == 3
    top = [e for e in es if tuple(e['branch']) == ()]
    br = [e for e in es if tuple(e['branch']) != ()]
    assert len(top) == 1 and len(br) == 2


# ---------------------------------------------------------------- T03
def test_t03_nested_alias_reuse_no_scope_bleed():
    # 两个不同相关子查询都用 b，指向不同表；两条边必须各自正确
    sql = ("SELECT (SELECT COUNT(*) FROM T_B b WHERE b.x=a.x) c1,"
           " (SELECT COUNT(*) FROM T_C b WHERE b.y=a.y) c2 FROM T_A a")
    es = edges(sql)
    pairs = {(e['l_table'], e['l_col'], e['r_table'], e['r_col']) for e in es}
    assert ('T_B', 'X', 'T_A', 'X') in pairs or ('T_A', 'X', 'T_B', 'X') in pairs
    assert ('T_C', 'Y', 'T_A', 'Y') in pairs or ('T_A', 'Y', 'T_C', 'Y') in pairs
    assert len(es) == 2


def test_t03_union_branches_isolated():
    sql = ('SELECT a.id FROM T_A a, T_B b WHERE a.id=b.id '
           'UNION ALL SELECT c.id FROM T_C c, T_D d WHERE c.id=d.id')
    es = edges(sql)
    tabs = {frozenset((e['l_table'], e['r_table'])) for e in es}
    assert frozenset(('T_A', 'T_B')) in tabs
    assert frozenset(('T_C', 'T_D')) in tabs


# ---------------------------------------------------------------- T04
def test_t04_self_join_kept_as_two_instances():
    sql = 'SELECT a.id FROM T_A a, T_A b WHERE a.parent_id=b.id'
    es = edges(sql)
    assert len(es) == 1
    e = es[0]
    assert e['l_table'] == 'T_A' and e['r_table'] == 'T_A'
    assert e['l_instance'] != e['r_instance']
    assert e['l_alias'] == 'A' and e['r_alias'] == 'B'
    assert e['l_col'] == 'PARENT_ID' and e['r_col'] == 'ID'


def test_t04_cte_and_derived_not_physical():
    sql = ('WITH cfg AS (SELECT id FROM T_CFG) '
           'SELECT a.id FROM T_A a JOIN cfg c ON a.id=c.id')
    res = rsp.parse_sql(sql)
    es = res['edges']
    assert len(es) == 1
    e = es[0]
    assert e['r_kind'] == 'cte' and e['r_table'] == 'CFG'
    phys = rsp.physical_tables(res)
    cte_inst = e['r_instance']
    assert phys[cte_inst] == {'T_CFG'}  # 溯源到物理表，CTE 本身不当物理表
    sql2 = 'SELECT a.id FROM T_A a, (SELECT id FROM T_D) d WHERE a.id=d.id'
    res2 = rsp.parse_sql(sql2)
    e2 = res2['edges'][0]
    assert e2['r_kind'] == 'subquery'
    assert rsp.physical_tables(res2)[e2['r_instance']] == {'T_D'}


# ---------------------------------------------------------------- T05
def test_t05_qualified_names_kept_distinct():
    sql = ('SELECT a.id FROM INPBILL.T_A a, ODS.T_A b, T_A c, HIS.T_A@SJZX d '
           'WHERE a.id=b.id AND b.alt=c.alt AND c.k=d.k')
    res = rsp.parse_sql(sql)
    tabs = {r['table'] for blk in res['blocks'].values() for r in blk['refs']}
    assert tabs == {'INPBILL.T_A', 'ODS.T_A', 'T_A', 'HIS.T_A@SJZX'}


# ---------------------------------------------------------------- T06
def test_t06_function_wrapped_key_not_silent_eq():
    sql = 'SELECT a.id FROM T_A a, T_B b WHERE TO_CHAR(a.dt)=TO_CHAR(b.dt)'
    es = edges(sql)
    assert es == []  # 函数包裹不降级为裸等值
    ur = unresolved(sql)
    assert any(r['reason'] == 'leaf-unclassified' for r in ur)


def test_t06_col_const_and_bind_params():
    res = rsp.parse_sql(
        "SELECT a.id FROM T_A a WHERE a.status='3' AND a.dt >= DATE '2024-01-01' AND a.name LIKE ?")
    f = res['filters']
    ops = {(x['col'], x['op'], x['val_kind']) for x in f}
    assert ('STATUS', '=', 'str') in ops
    assert ('NAME', 'LIKE', 'bind') in ops


# ---------------------------------------------------------------- T07
def test_t07_comments_credentials_do_not_leak():
    sql = ("SELECT a.id -- password: s3cret\n"
           "FROM T_A a /* token=abc123 */ WHERE a.id=1")
    res = rsp.parse_sql(sql)
    flat = str(res)
    assert 's3cret' not in flat and 'abc123' not in flat
    assert any(r['table'] == 'T_A' for blk in res['blocks'].values() for r in blk['refs'])


def test_t07_masked_placeholder_and_constants_preserved():
    # 脱敏占位（?）与业务常量在 filter 中保真
    res = rsp.parse_sql("SELECT a.id FROM T_A a WHERE a.oper_status=2 AND a.org='49557032X'")
    f = res['filters']
    assert any(x['col'] == 'OPER_STATUS' and x['val_kind'] == 'num' for x in f)
    assert any(x['col'] == 'ORG' and x['val_kind'] == 'str' for x in f)


# ---------------------------------------------------------------- T08
def test_t08_concat_not_dynamic_fake_edge():
    # 普通 || 字符串拼接不产生边，也不误报 unresolved 成表
    sql = "SELECT a.id FROM T_A a WHERE a.name='x' || a.tag"
    res = rsp.parse_sql(sql)
    assert res['edges'] == []
    tabs = {r['table'] for blk in res['blocks'].values() for r in blk['refs']}
    assert tabs == {'T_A'}


def test_t08_unparseable_gives_unresolved_not_edge():
    sql = 'EXECUTE IMMEDIATE ''SELECT ... dynamic'''
    res = rsp.parse_sql(sql)
    assert res['edges'] == []
    # 未解析事实显式存在（warnings/unresolved/blocks 任一通道），不静默
    assert res['warnings'] or res['unresolved'] or res['blocks']
