"""关系端点身份、分层与业务键的统一计算工具（98号 S0 / 100号修复）。

集中维护从 from_table/to_table 文本推导端点五元组、业务幂等键、分层的逻辑，
供 candidates.py(候选转正式)、asset_import_upsert.py(导入)、relations.py(审核编辑)
和 graph_sync.py(同步) 共用，避免多处复制导致口径漂移。

100号修复：
- 拆分规则统一为 1/2/3 段式（纯表名/二段式/三段式）；
- 新增 namespace_name 支持；
- 业务键包含完整物理身份（system/source/namespace/schema/table）；
- 未解析端点（缺 system/source）标记为 unresolved，不退化。
"""
from __future__ import annotations

import hashlib
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.asset import AssetRelation, AssetTable


def split_qualified_name(qualified: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """把限定表名拆成 (namespace_name, schema_name, table_name)。

    统一规则（100号 A1）：
    - 纯表名 PAT_VISIT           => (None, None, PAT_VISIT)
    - 二段式 MEDREC.PAT_VISIT    => (None, MEDREC, PAT_VISIT)
    - 三段式 rmcloudlis7.dbo.V_X => (rmcloudlis7, dbo, V_X)

    空/None => (None, None, None)
    """
    if not qualified:
        return None, None, None
    qualified = qualified.strip()
    if not qualified:
        return None, None, None
    parts = qualified.split(".")
    if len(parts) == 1:
        return None, None, parts[0]
    elif len(parts) == 2:
        return None, parts[0], parts[1]
    else:
        return parts[0], parts[1], ".".join(parts[2:])


def split_schema_table(qualified: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """向后兼容：返回 (schema_name, table_name)，忽略 namespace。"""
    _, schema, table = split_qualified_name(qualified)
    return schema, table


def resolve_endpoint(
    db: Session,
    namespace_name: Optional[str],
    schema_name: Optional[str],
    table_name: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """按 (namespace_name, schema_name, table_name) 反查 asset_tables 取 (system_code, source_code)。

    安全约束：只返回唯一命中的 pair；多命中（跨系统同名表）或未命中时返回 (None, None)。
    对 (system_code, source_code) pair 去重后判断唯一性（100号 A2）。
    """
    if not table_name:
        return None, None
    stmt = select(AssetTable.system_code, AssetTable.source_code).where(
        AssetTable.table_name == table_name,
    )
    if schema_name:
        stmt = stmt.where(AssetTable.schema_name == schema_name)
    else:
        stmt = stmt.where(AssetTable.schema_name.is_(None))
    if namespace_name:
        stmt = stmt.where(AssetTable.namespace_name == namespace_name)
    else:
        stmt = stmt.where(
            (AssetTable.namespace_name.is_(None)) | (AssetTable.namespace_name == "")
        )
    rows = db.execute(stmt).all()
    pairs = {(r[0], r[1]) for r in rows}
    if len(pairs) == 1:
        sc, src = next(iter(pairs))
        return sc, src
    return None, None


def physical_node_key(
    system_code: Optional[str],
    source_code: Optional[str],
    namespace_name: Optional[str],
    schema_name: Optional[str],
    table_name: Optional[str],
) -> Optional[str]:
    """图节点物理唯一键 = system_code|source_code|namespace_name|schema_name|table_name。

    正式图层要求 system_code/source_code/table_name 均不为空。
    缺失任何必要字段时返回 None（表示未解析，不进入正式图层）。
    """
    if not system_code or not source_code or not table_name:
        return None
    return "|".join([
        system_code,
        source_code,
        namespace_name or "",
        schema_name or "",
        table_name,
    ])


def display_node_key(
    schema_name: Optional[str],
    table_name: Optional[str],
) -> Optional[str]:
    """图节点展示键 = SCHEMA.TABLE（仅用于显示，不作为唯一身份）。

    108号：节点唯一键使用 physical_node_key；display_key 只供界面展示。
    """
    if schema_name and table_name:
        return f"{schema_name}.{table_name}"
    return table_name or schema_name or None


def compute_business_key(
    from_table: Optional[str],
    to_table: Optional[str],
    from_columns: Optional[str],
    to_columns: Optional[str],
    join_condition: Optional[str],
    from_system_code: Optional[str] = None,
    from_source_code: Optional[str] = None,
    to_system_code: Optional[str] = None,
    to_source_code: Optional[str] = None,
) -> Optional[str]:
    """计算稳定的业务幂等键 md5。

    100号修复：业务键包含完整物理身份（system/source），保证跨系统同名表不碰撞。
    """
    if not from_table or not to_table:
        return None
    raw = "|".join([
        from_system_code or "",
        from_source_code or "",
        from_table,
        to_system_code or "",
        to_source_code or "",
        to_table,
        from_columns or "",
        to_columns or "",
        join_condition or "",
    ]).lower()
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def derive_layer(confidence: Optional[str], validation_status: Optional[str]) -> str:
    """按现有 confidence/validation_status 推导 relation_layer。"""
    if (confidence or "").upper() == "D":
        return "deferred"
    if (validation_status or "").startswith("user_confirmed_sync"):
        return "sync_mapping"
    if validation_status == "candidate":
        return "candidate"
    if validation_status in (
        "verified", "partial", "user_confirmed", "user_confirmed_mapping",
        "user_confirmed_parallel_sources", "manual_reviewed", "A_rechecked",
    ):
        return "formal"
    return "candidate"


def populate_endpoint_fields(
    db: Session,
    relation: AssetRelation,
) -> None:
    """为一条 AssetRelation 填充端点五元组、业务键和分层（写前调用）。"""
    from_ns, from_schema, from_tbl = split_qualified_name(relation.from_table)
    to_ns, to_schema, to_tbl = split_qualified_name(relation.to_table)

    relation.from_namespace_name = from_ns
    relation.from_schema_name = from_schema
    relation.from_table_name = from_tbl
    relation.to_namespace_name = to_ns
    relation.to_schema_name = to_schema
    relation.to_table_name = to_tbl

    relation.from_system_code, relation.from_source_code = resolve_endpoint(
        db, from_ns, from_schema, from_tbl
    )
    relation.to_system_code, relation.to_source_code = resolve_endpoint(
        db, to_ns, to_schema, to_tbl
    )

    relation.relation_business_key = compute_business_key(
        relation.from_table, relation.to_table,
        relation.from_columns, relation.to_columns, relation.join_condition,
        relation.from_system_code, relation.from_source_code,
        relation.to_system_code, relation.to_source_code,
    )
    relation.relation_layer = derive_layer(relation.confidence, relation.validation_status)