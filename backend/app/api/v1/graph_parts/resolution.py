"""215 E11 自 graph.py 拆出：端点解析与物理键（108号 §3 口径）。

物理键 = system_code|source_code|namespace_name|schema_name|table_name；
多命中一律不猜（返回 None），禁止退化成空前缀物理键。
"""
from __future__ import annotations

import hashlib
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....models.asset import AssetRelation, AssetTable
from ....models.candidate import AssetCandidateRelation
from ....services.relation_identity import resolve_endpoint, split_qualified_name

# 旧前端曾经把 HIS.PAT_VISIT 映射到 MEDREC.PAT_VISIT；保留仅用于旧 table 参数兼容。
LEGACY_TABLE_ALIASES = {
    "HIS.PAT_VISIT": "MEDREC.PAT_VISIT",
    "HIS.PAT_MASTER_INDEX": "MEDREC.PAT_MASTER_INDEX",
}
CANONICAL_TO_LEGACY = {v: k for k, v in LEGACY_TABLE_ALIASES.items()}

def _aliases_for(table: str) -> set[str]:
    names = {table}
    if table in LEGACY_TABLE_ALIASES:
        names.add(LEGACY_TABLE_ALIASES[table])
    if table in CANONICAL_TO_LEGACY:
        names.add(CANONICAL_TO_LEGACY[table])
    return names

def _physical_key(
    system_code: str | None,
    source_code: str | None,
    namespace_name: str | None,
    schema_name: str | None,
    table_name: str | None,
) -> str | None:
    """完整物理键 = system_code|source_code|namespace_name|schema_name|table_name。

    108号 §3.1：缺少 system/source/schema/table 的关系不能进入正式图层，不得退化成空前缀物理键。
    """
    if not system_code or not source_code or not schema_name or not table_name:
        return None
    return "|".join([
        system_code,
        source_code,
        namespace_name or "",
        schema_name,
        table_name,
    ])

def _display_id(schema_name: str | None, table_name: str | None) -> str | None:
    if schema_name and table_name:
        return f"{schema_name}.{table_name}"
    return table_name or schema_name or None

def _split_table_name(full_name: str) -> tuple[str | None, str | None, str | None]:
    """把 'SCHEMA.TABLE' 或 'NS.SCHEMA.TABLE' 拆成 (namespace, schema, table)。

    兼容 [VIEW] 前缀（依赖图专用）。
    """
    if not full_name:
        return None, None, None
    if full_name.startswith("[VIEW] "):
        return None, "VIEW", full_name.replace("[VIEW] ", "", 1)
    ns, schema, table = split_qualified_name(full_name)
    return ns, schema, table

def _resolve_endpoint_lenient(
    db: Session,
    schema_name: str | None,
    table_name: str | None,
) -> tuple[str | None, str | None]:
    """宽松物理来源反查：按 (schema, table) 收集 (system, source) 唯一 pair。

    与共享 resolve_endpoint 的区别：不限定 namespace 是否 NULL/""，兼容
    namespace_name=schema 的历史回填数据与 2 段式表名。多命中不猜（返回 None）。
    """
    if not schema_name or not table_name:
        return None, None
    rows = db.execute(
        select(AssetTable.system_code, AssetTable.source_code).where(
            AssetTable.schema_name == schema_name,
            AssetTable.table_name == table_name,
        )
    ).all()
    pairs = {(r[0], r[1]) for r in rows if r[0] and r[1]}
    if len(pairs) == 1:
        return next(iter(pairs))
    return None, None

class _EndpointResolver:
    """一次性预载 asset_tables 的端点反查索引（C1 批量化）。

    resolve() 的语义与「resolve_endpoint 精确 + _resolve_endpoint_lenient 宽松」
    逐分支等价：先按 (namespace, schema, table) 精确唯一命中（namespace 缺失
    视为 NULL/""，schema 缺失视为 NULL），未命中再按 (schema, table) 的唯一
    非空 (system, source) pair 宽松反查；多命中一律不猜。
    """

    def __init__(self, rows: list[tuple[str | None, str | None, str | None, str | None, str | None]]):
        by_table: dict[str | None, list[tuple[str | None, str | None, str | None, str | None]]] = defaultdict(list)
        for namespace_name, schema_name, table_name, system_code, source_code in rows:
            by_table[table_name].append((namespace_name, schema_name, system_code, source_code))
        self._by_table = by_table
        # 供孤儿引用检测复用同一份预载行，避免再拉一次全表实体。
        self.schema_table_names = {
            f"{schema_name}.{table_name}"
            for namespace_name, schema_name, table_name, _sys, _src in rows
            if schema_name and table_name
        }

    @classmethod
    def load(cls, db: Session) -> _EndpointResolver:
        rows = db.execute(
            select(
                AssetTable.namespace_name,
                AssetTable.schema_name,
                AssetTable.table_name,
                AssetTable.system_code,
                AssetTable.source_code,
            )
        ).all()
        return cls([tuple(row) for row in rows])

    def resolve_exact(
        self, namespace_name: str | None, schema_name: str | None, table_name: str | None,
    ) -> tuple[str | None, str | None]:
        if not table_name:
            return None, None
        entries = self._by_table.get(table_name, [])
        if schema_name:
            entries = [e for e in entries if e[1] == schema_name]
        else:
            entries = [e for e in entries if e[1] is None]
        if namespace_name:
            entries = [e for e in entries if e[0] == namespace_name]
        else:
            entries = [e for e in entries if e[0] is None or e[0] == ""]
        pairs = {(e[2], e[3]) for e in entries}
        if len(pairs) == 1:
            return next(iter(pairs))
        return None, None

    def resolve_lenient(
        self, schema_name: str | None, table_name: str | None,
    ) -> tuple[str | None, str | None]:
        if not schema_name or not table_name:
            return None, None
        entries = self._by_table.get(table_name, [])
        pairs = {(e[2], e[3]) for e in entries if e[1] == schema_name and e[2] and e[3]}
        if len(pairs) == 1:
            return next(iter(pairs))
        return None, None

    def resolve(
        self, namespace_name: str | None, schema_name: str | None, table_name: str | None,
    ) -> tuple[str | None, str | None]:
        system_code, source_code = self.resolve_exact(namespace_name, schema_name, table_name)
        if system_code is None or source_code is None:
            system_code, source_code = self.resolve_lenient(schema_name, table_name)
        return system_code, source_code

def _resolve_relation_endpoint(
    db: Session,
    r: AssetRelation,
    side: str,
    resolver: _EndpointResolver | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """从一条 AssetRelation 提取端点的五元组 + 展示名。

    返回 (system, source, namespace, schema, table, display_id)。
    优先使用已回填的物理字段；缺失时回退到 from_table/to_table 文本拆分；
    仍未解析出 system/source 时按 asset_tables 唯一物理匹配反查（多命中不猜，返回 None）。
    传入 resolver 时用预载索引反查（C1 批量化，已回填行天然零查询）。
    """
    if side == "from":
        sys_c = r.from_system_code
        src_c = r.from_source_code
        ns = r.from_namespace_name
        schema = r.from_schema_name
        table = r.from_table_name
        raw = r.from_table
    else:
        sys_c = r.to_system_code
        src_c = r.to_source_code
        ns = r.to_namespace_name
        schema = r.to_schema_name
        table = r.to_table_name
        raw = r.to_table
    if not sys_c or not src_c or not schema or not table:
        # 物理字段缺失时尝试从文本拆分（namespace/schema/table）
        if raw:
            ns2, schema2, table2 = _split_table_name(raw)
            ns = ns or ns2
            schema = schema or schema2
            table = table or table2
    if (not sys_c or not src_c) and schema and table:
        # 按 (namespace, schema, table) 唯一反查 system/source；多命中不猜（返回 None）。
        # 先精确（含 namespace），再宽松（仅 schema+table 唯一 pair）。
        if resolver is not None:
            sys_c, src_c = resolver.resolve(ns, schema, table)
        else:
            sys_c, src_c = resolve_endpoint(db, ns, schema, table)
            if sys_c is None or src_c is None:
                sys_c, src_c = _resolve_endpoint_lenient(db, schema, table)
    display = _display_id(schema, table)
    return sys_c, src_c, ns, schema, table, display

def _endpoint_physical_key(
    db: Session, r: AssetRelation, side: str, resolver: _EndpointResolver | None = None,
) -> str | None:
    sys_c, src_c, ns, schema, table, _ = _resolve_relation_endpoint(db, r, side, resolver=resolver)
    return _physical_key(sys_c, src_c, ns, schema, table)

def _stable_edge_id(
    r: AssetRelation,
    from_key: str | None,
    to_key: str | None,
) -> str:
    """稳定边 ID = relation_business_key；缺失时用 rel:{db_id}（可反查，不随环境漂移）。

    数据库自增 id 只作为 db_id 属性保留，不作为跨环境永久身份（108号 §3.2）。
    对已回填业务键的正式关系，返回业务键；未回填的旧行退化为 rel:{id}。
    """
    if r.relation_business_key:
        return r.relation_business_key
    return f"rel:{r.id}"

def _candidate_edge_id(cr: AssetCandidateRelation) -> str:
    raw = "|".join([
        cr.from_table or "", cr.from_columns or "",
        cr.to_table or "", cr.to_columns or "",
        cr.join_condition or "", cr.source_view or "",
    ]).lower()
    return f"candidate:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

def _resolve_table_filter(db: Session, table: str) -> list[tuple[str, str, str, str]]:
    """把旧 table=SCHEMA.TABLE 参数解析为物理端点 (system, source, schema, table)。

    多命中返回多条，调用方决定 409 或空图；禁止随机选择（108号 P1-05）。
    """
    candidates: set[tuple[str, str, str, str]] = set()
    names = _aliases_for(table)
    rows = db.scalars(
        select(AssetTable).where(
            (AssetTable.schema_name + "." + AssetTable.table_name).in_(list(names))
        )
    ).all()
    for t in rows:
        if t.system_code and t.source_code and t.schema_name and t.table_name:
            candidates.add((t.system_code, t.source_code, t.schema_name, t.table_name))
    return sorted(candidates)

def _resolve_neighbor_target(
    db: Session,
    *,
    physical_key: str | None,
    system_code: str | None,
    source_code: str | None,
    schema: str | None,
    table: str | None,
) -> str:
    """邻居查询目标：优先物理键或 system/source/schema/table；旧 table 参数唯一兼容。"""
    if physical_key:
        return physical_key
    if system_code and source_code and schema and table:
        key = _physical_key(system_code, source_code, None, schema, table)
        if not key:
            raise HTTPException(status_code=422, detail="system/source/schema/table 不能为空")
        return key
    if table:
        matches = _resolve_table_filter(db, table)
        if not matches:
            raise HTTPException(status_code=404, detail=f"未找到表 {table} 的物理端点")
        if len(matches) > 1:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"表 {table} 存在多个物理来源，请指定 system_code/source_code/schema/table 或 physical_key",
                    "candidates": [
                        {
                            "physical_key": _physical_key(m[0], m[1], None, m[2], m[3]),
                            "system_code": m[0],
                            "source_code": m[1],
                            "schema_name": m[2],
                            "table_name": m[3],
                        }
                        for m in matches
                    ],
                },
            )
        m = matches[0]
        key = _physical_key(m[0], m[1], None, m[2], m[3])
        return key or ""
    raise HTTPException(status_code=422, detail="必须提供 physical_key 或 system/source/schema/table，或唯一 table")
