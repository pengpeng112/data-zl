"""扩表冻结件生成器（A1，2026-10-24）：B01 v1.3 逐表 → v4 约定冻结文档。

首组四表的 freeze-config 只认 A01 v2 结构；本模块把 B01 v1.3 的
73 项候选按批转换成与生产 v4 冻结件同构的表文档（字段约定直接照抄
首组先例，不另发明）。只做纯逻辑转换与拒绝语义：不连库、不读凭据。

输入证据与拒绝规则：
- B01 items：目标身份/稳定键须 verified，锚点须有 verified 列；
  3 张工单表（T-B01-65/61/44）一律拒绝冻结，待工单处置；
- 目标字典（target_dict_bulk 预处理）：投影列名/类型/长度/NULLABLE，
  CHAR 语义列型保留原样，SYSTEM_TIME 存在即定为事务时钟列并剔出投影；
- 源组绑定（操作者按平台元数据准备的覆写）：方言/dsn/凭据引用/
  逐表对象名——生成器不猜库型、不猜库名；
- ODS 源额外做视图列覆盖证明（目标列 ⊆ 视图暴露列，08 快照 DDL
  别名法），覆盖不全默认拒绝，--allow-view-gap 须人工核因后强制并留痕；
- 预算：画像候选有值用之，缺省 {50000 行, 256MiB, 3 次}。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.services.reporting_pipeline.runtime_config import (
    SUPPORTED_DIALECTS,
    build_freeze_document,
    build_table_document,
)

# 工单表：目标无唯一约束/定源未决/视图无业务时间列，扩表一律跳过
TICKET_TABLES: Mapping[str, str] = {
    "EMR_INFOR_SPEC_EXAM_TREAT": "T-B01-65(目标无唯一约束)",
    "EMR_NURSE_PLAN": "T-B01-61(定源未决)",
    "EMR_HOS_SAVE_RECORD": "T-B01-44(视图无业务时间列)",
}

DEFAULT_BUDGET: Mapping[str, int] = {
    "max_rows_per_slice": 50000,
    "max_bytes_per_slice": 268435456,
    "max_attempts": 3,
}


class FreezeBatchError(Exception):
    """批冻结生成拒绝（输入证据不齐/表未核/覆盖不全）。"""


def build_batch_freeze(
    *,
    environment: str,
    batch_label: str,
    b01_items: Sequence[Mapping],
    table_names: Sequence[str],
    target_columns: Mapping[str, Sequence[Mapping]],
    source_bindings: Mapping[str, Mapping],
    target_overrides: Mapping[str, Mapping],
    parent_overrides: Mapping[str, Mapping] | None = None,
    object_sha256_by_view: Mapping[str, str] | None = None,
    view_aliases_by_name: Mapping[str, set[str]] | None = None,
    budgets_by_table: Mapping[str, Mapping] | None = None,
    frozen_at: str,
    allow_view_gap: bool = False,
    source_inputs: Sequence[Mapping[str, str]] = (),
) -> tuple[dict, dict]:
    """生成批冻结件 + 决策报告（document, report）。

    target_columns 键=目标库裸表名；source_bindings 键=物理源组，
    值含 dialect/dsn/credential_ref/source_objects{表:对象全名}；
    target_overrides 键=canonical_table，值含 instance/tenant/table/charset。
    """
    items_by_name = {str(item.get("canonical_table")): item for item in b01_items}
    parent_overrides = dict(parent_overrides or {})
    object_sha256_by_view = dict(object_sha256_by_view or {})
    view_aliases_by_name = dict(view_aliases_by_name or {})
    budgets_by_table = dict(budgets_by_table or {})

    tables: dict[str, dict] = {}
    coverage_problems: list[str] = []
    report_tables: dict[str, dict] = {}
    problems: list[str] = []

    for name in table_names:
        item = items_by_name.get(name)
        if item is None:
            raise FreezeBatchError(f"B01 候选不含表 {name}")
        if name in TICKET_TABLES:
            raise FreezeBatchError(
                f"[{name}] 工单表拒绝冻结：{TICKET_TABLES[name]}（待工单处置）"
            )
        verify = item.get("b01_verification") or {}
        target_identity = (verify.get("target_identity") or {}).get("verified")
        if target_identity is not True:
            raise FreezeBatchError(f"[{name}] B01 目标身份未核验，拒绝冻结")
        key = item.get("stable_key") or {}
        if key.get("verified") is not True or not key.get("candidate"):
            raise FreezeBatchError(f"[{name}] B01 稳定键未核验，拒绝冻结")
        anchors = [a for a in (verify.get("anchor") or []) if a.get("verified")]
        if not anchors:
            raise FreezeBatchError(f"[{name}] B01 锚点无 verified 列，拒绝冻结")
        anchor_column = str(anchors[0]["column"])

        source = (item.get("source_candidates") or [{}])[0]
        group = str(source.get("source_group") or "")
        binding = source_bindings.get(group)
        if not binding:
            raise FreezeBatchError(
                f"[{name}] 源绑定缺物理源组 {group!r}（不猜连接，操作者按平台元数据补）"
            )
        dialect = str(binding.get("dialect") or "")
        if dialect not in SUPPORTED_DIALECTS:
            raise FreezeBatchError(
                f"[{name}] 源方言非法: {dialect!r}（支持 {SUPPORTED_DIALECTS}）"
            )
        credential_ref = binding.get("credential_ref")
        if not credential_ref:
            raise FreezeBatchError(f"[{name}] 源绑定缺 credential_ref")
        source_object = (binding.get("source_objects") or {}).get(name)
        if not source_object:
            raise FreezeBatchError(
                f"[{name}] 源绑定缺 source_objects[{name}]（对象全名须显式，不拼不猜）"
            )

        target_candidate = item.get("target_candidate") or {}
        target_override = dict(target_overrides.get(name) or {})
        target_table = target_override.get("table") or (
            f"{target_candidate.get('owner')}.{target_candidate.get('table')}"
        )
        bare_table = str(target_table).rsplit(".", 1)[-1]
        cols = target_columns.get(bare_table)
        if not cols:
            raise FreezeBatchError(
                f"[{name}] 目标字典缺表 {bare_table}（target_dict_bulk）"
            )
        target_column_names = {str(c["name"]) for c in cols}
        system_time_column = (
            "SYSTEM_TIME" if "SYSTEM_TIME" in target_column_names else None
        )
        projection = [
            {
                "name": c["name"],
                "target_type": c["target_type"],
                "source_expression": c["name"],
                "nullable": c["nullable"],
                "data_length": c["data_length"],
            }
            for c in sorted(cols, key=lambda item_: str(item_["name"]))
            if str(c["name"]) != system_time_column
        ]
        projection_names = {str(p["name"]) for p in projection}
        for key_column in key["candidate"]:
            if key_column not in projection_names:
                raise FreezeBatchError(
                    f"[{name}] 稳定键列不在投影中: {key_column}"
                )

        # 父关系：B01 declared_parent_candidates（child_key 须在投影内），
        # parent_overrides 可覆写（表名/键列以批核验为准）
        parent_doc = None
        parent_candidates = item.get("declared_parent_candidates") or []
        if parent_candidates:
            first = parent_candidates[0]
            parent_doc = {
                "table": str(first.get("parent")),
                "key_column": str(first.get("child_key")),
            }
        if name in parent_overrides:
            override = parent_overrides[name] or {}
            if override.get("table"):
                parent_doc = {
                    "table": str(override["table"]),
                    "key_column": str(override.get("key_column")),
                }
        if parent_doc and parent_doc["key_column"] not in projection_names:
            raise FreezeBatchError(
                f"[{name}] 父键列不在投影中: {parent_doc['key_column']}"
            )

        # ODS 视图列覆盖证明 + 定义哈希；独立源无 DDL，试点回读核验
        view_name = binding.get("view_by_table", {}).get(name)
        object_sha256 = None
        missing: list[str] = []
        if view_name:
            object_sha256 = object_sha256_by_view.get(str(view_name))
            aliases = view_aliases_by_name.get(str(view_name))
            if aliases is None:
                raise FreezeBatchError(
                    f"[{name}] 视图 {view_name} 无 DDL 别名证据（08 快照缺该视图）"
                )
            missing = sorted(
                name_ for name_ in projection_names if name_.upper() not in aliases
            )
            if missing:
                coverage_problems.append(
                    f"{name}: 视图 {view_name} 未暴露 {len(missing)} 列"
                    f"（如 {missing[:3]}）"
                )

        budget = dict(DEFAULT_BUDGET)
        measured = budgets_by_table.get(name) or {}
        for field_name in tuple(budget):
            value = measured.get(field_name)
            if isinstance(value, int) and value > 0:
                budget[field_name] = value

        notes = {
            "batch": batch_label,
            "anchor_evidence": (
                f"b01_verification.anchor verified 列 {anchor_column}"
                f"（views={anchors[0].get('views')}）"
            ),
            "key_evidence": "B01 stable_key verified（目标PK=ID）",
            "engine_disposition": str(
                (verify.get("engine_disposition") or "PYTHON_PLANNED")
            ),
            "view_column_coverage": (
                "verified" if (view_name and not missing) else (
                    f"missing={len(missing)}" if view_name
                    else "独立源无DDL，试点回读核验"
                )
            ),
        }

        tables[name] = build_table_document(
            canonical_table=name,
            business_name=str(item.get("business_name") or name),
            engine=str(binding.get("engine") or "PYTHON"),
            modes=["T1", "HISTORICAL"],
            source_group=group,
            dialect=dialect,
            source_object=str(source_object),
            credential_ref=str(credential_ref),
            target_instance=str(
                target_override.get("instance")
                or f"{target_candidate.get('host')}:{target_candidate.get('port')}"
                f"/{target_candidate.get('service')}"
            ),
            tenant=str(
                target_override.get("tenant") or target_candidate.get("owner")
            ),
            target_table=str(target_table),
            stable_key=[str(column) for column in key["candidate"]],
            anchor_column=anchor_column,
            anchor_inherited_from_parent=False,
            projection=projection,
            change_mode="SNAPSHOT_DIFF 全窗比对",
            budget=budget,
            object_sha256=object_sha256,
            system_time_column=system_time_column,
            receipt_table=None,
            parent=parent_doc,
            target_charset=str(target_override.get("charset") or "ZHS16GBK"),
            notes=notes,
        )
        report_tables[name] = {
            "source_group": group,
            "dialect": dialect,
            "source_object": str(source_object),
            "anchor_column": anchor_column,
            "system_time_column": system_time_column,
            "projection_columns": len(projection),
            "parent": parent_doc,
            "budget": budget,
            "view_coverage_missing": missing or None,
        }

    if coverage_problems and not allow_view_gap:
        raise FreezeBatchError(
            "视图列覆盖不完整，拒绝冻结（--allow-view-gap 人工核因后强制并留痕）: "
            + "; ".join(coverage_problems)
        )

    document = build_freeze_document(
        environment=environment,
        tables=tables,
        source_inputs=list(source_inputs),
        frozen_at=frozen_at,
        notes={
            "batch": batch_label,
            "coverage_problems": coverage_problems or [],
            "enabled": "全部 false（候选停用；启用走独立启用冻结）",
        },
    )
    report: dict[str, Any] = {
        "batch": batch_label,
        "tables": report_tables,
        "coverage_problems": coverage_problems or [],
        "problems": problems,
    }
    return document, report
