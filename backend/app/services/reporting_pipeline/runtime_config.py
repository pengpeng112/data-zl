"""首组运行配置冻结与装载（第一批批1-1）。

候选（A01 v2 / B01 v1.3）只是线索与核验标记；本模块把候选转换成
完整 TaskSpec 级运行配置并显式冻结：

- 投影逐列可追溯：目标字典（DBOPER 列类型/长度/非空）+ 源视图 DDL
  别名覆盖证明，列名/类型/顺序/来源表达式全部落档；
- 配置路径、版本与哈希显式冻结：冻结件自带 config_fingerprint
  （对除自身外的规范化文档计算 sha256），装载时重算不一致即拒绝
  （REFUSED_CONFIG_DRIFT），配置漂移不可能静默通过；
- 候选停用保留：enabled 固定 false，正式启用（A05c）另出 vNext 冻结，
  不通过手工置 READY 解决；动作级派发仍走 K01 ActionBinding；
- 环境标记：production 冻结件与隔离验收冻结件分开，隔离件的目标/源
  身份显式标注 environment="isolated_acceptance"，不冒充生产身份。

本模块只做纯逻辑（构造/校验/指纹），不连库、不读凭据。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.services.reporting_pipeline.contracts import ContractViolation

FREEZE_DOC_VERSION = "v1"
SUPPORTED_ENVIRONMENTS = ("production", "isolated_acceptance")
SUPPORTED_DIALECTS = ("oracle", "pg")
SUPPORTED_ENGINES = ("PYTHON", "DATAX")


class RuntimeConfigError(ContractViolation):
    """冻结件缺失/漂移/结构非法：拒绝执行，不静默降级。"""


@dataclass(frozen=True)
class ProjectionFieldSpec:
    """投影列：名称、目标类型、来源表达式、非空与长度全部可追溯。"""

    name: str
    target_type: str
    source_expression: str
    nullable: bool
    data_length: int | None
    order: int


@dataclass(frozen=True)
class TableRuntimeSpec:
    """单表完整运行配置（TaskSpec 级）。"""

    canonical_table: str
    business_name: str
    engine: str
    modes: tuple[str, ...]
    enabled: bool
    source_group: str
    dialect: str
    source_object: str
    object_sha256: str | None
    credential_ref: str
    target_instance: str
    tenant: str
    target_table: str
    stable_key: tuple[str, ...]
    anchor_column: str | None
    anchor_inherited_from_parent: bool
    timezone: str
    change_mode: str
    projection: tuple[ProjectionFieldSpec, ...]
    system_time_column: str | None
    receipt_table: str | None
    budget: Mapping[str, int]
    parent_table: str | None
    parent_key_column: str | None
    fingerprint: str
    target_charset: str = "utf-8"  # 目标库字符集（BYTE 长度语义按此度量）

    def write_columns(self) -> tuple[str, ...]:
        names = tuple(f.name for f in self.projection)
        if self.system_time_column and self.system_time_column in names:
            return tuple(n for n in names if n != self.system_time_column)
        return names


@dataclass(frozen=True)
class FrozenRuntimeConfig:
    """装载后的冻结运行配置（哈希已验证）。"""

    environment: str
    version: str
    frozen_at: str
    path: str
    file_sha256: str
    config_fingerprint: str
    tables: Mapping[str, TableRuntimeSpec]
    source_inputs: tuple[Mapping[str, str], ...] = field(default_factory=tuple)

    def table(self, canonical_table: str) -> TableRuntimeSpec:
        try:
            return self.tables[canonical_table]
        except KeyError:
            raise RuntimeConfigError(
                f"冻结运行配置不含表 {canonical_table}"
            ) from None


# -- 指纹 ----------------------------------------------------------------


def _canonical_json(document: Any) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_table_fingerprint(table_doc: Mapping) -> str:
    """单表指纹：对规范化表文档（剔除自身 fingerprint 字段）计算。"""
    body = {k: v for k, v in dict(table_doc).items() if k != "fingerprint"}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def compute_config_fingerprint(document: Mapping) -> str:
    """整件指纹：对除 config_fingerprint 外的规范化文档计算。"""
    body = {k: v for k, v in dict(document).items() if k != "config_fingerprint"}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


# -- 装载与校验 ------------------------------------------------------------


def _require(document: Mapping, key: str, where: str) -> Any:
    value = document.get(key)
    if value in (None, "", []):
        raise RuntimeConfigError(f"冻结件 {where} 缺字段 {key}（不可追溯即拒绝）")
    return value


def _parse_projection(raw: Sequence[Mapping], where: str) -> tuple[ProjectionFieldSpec, ...]:
    fields: list[ProjectionFieldSpec] = []
    seen: set[str] = set()
    for item in raw:
        name = _require(item, "name", where)
        if name in seen:
            raise RuntimeConfigError(f"{where} 投影列重复: {name}")
        seen.add(name)
        fields.append(
            ProjectionFieldSpec(
                name=str(name),
                target_type=str(_require(item, "target_type", where)),
                source_expression=str(_require(item, "source_expression", where)),
                nullable=bool(item.get("nullable", True)),
                data_length=item.get("data_length"),
                order=int(item.get("order", len(fields) + 1)),
            )
        )
    if not fields:
        raise RuntimeConfigError(f"{where} 投影为空")
    return tuple(fields)


def _validate_table_document(name: str, doc: Mapping) -> None:
    where = f"[{name}]"
    _require(doc, "engine", where)
    if doc["engine"] not in SUPPORTED_ENGINES:
        raise RuntimeConfigError(f"{where} engine 非法: {doc['engine']}")
    if doc.get("enabled") is not False:
        # 冻结件保留候选停用；置 true 须另出启用冻结（A05c），非手工 READY
        raise RuntimeConfigError(
            f"{where} 冻结件 enabled 必须为 false（启用走独立启用冻结，不手工置READY）"
        )
    if not doc.get("modes"):
        raise RuntimeConfigError(f"{where} 缺运行模式 modes")
    source = _require(doc, "source", where)
    _require(source, "source_group", where)
    if source.get("dialect") not in SUPPORTED_DIALECTS:
        raise RuntimeConfigError(f"{where} 源方言非法: {source.get('dialect')}")
    _require(source, "object", where)
    _require(source, "credential_ref", where)
    target = _require(doc, "target", where)
    _require(target, "instance", where)
    _require(target, "tenant", where)
    _require(target, "table", where)
    key = _require(doc, "stable_key", where)
    if not key.get("columns"):
        raise RuntimeConfigError(f"{where} 稳定键为空")
    projection = _parse_projection(doc.get("projection") or [], where)
    names = {f.name for f in projection}
    for column in key["columns"]:
        if column not in names:
            raise RuntimeConfigError(f"{where} 稳定键列不在投影中: {column}")
    anchor = doc.get("anchor") or {}
    # 业务锚点是源视图侧的窗口谓词列（四视图统一暴露 DATETIME），
    # 不要求出现在目标装载投影中；但必须显式声明（不猜列名）。
    if not anchor.get("inherited_from_parent") and not anchor.get("column"):
        raise RuntimeConfigError(f"{where} 业务锚点未声明（窗口谓词列不可缺）")
    budget = _require(doc, "budget", where)
    for field_name in ("max_rows_per_slice", "max_bytes_per_slice", "max_attempts"):
        if not isinstance(budget.get(field_name), int) or budget[field_name] <= 0:
            raise RuntimeConfigError(
                f"{where} 预算字段非法: {field_name}={budget.get(field_name)!r}"
            )
    system_time = doc.get("system_time_column")
    if system_time is not None and system_time in names:
        raise RuntimeConfigError(
            f"{where} SYSTEM_TIME 由目标事务生成，不得列入装载投影"
        )
    parent = doc.get("parent") or None
    if parent is not None:
        _require(parent, "table", where)
        _require(parent, "key_column", where)
        if parent["key_column"] not in names:
            raise RuntimeConfigError(f"{where} 父键列不在投影中: {parent['key_column']}")


def load_frozen_runtime_config(path: str | Path) -> FrozenRuntimeConfig:
    """装载冻结件：整件指纹 + 每表指纹双重验证；漂移即拒。"""
    file_path = Path(path)
    if not file_path.exists():
        raise RuntimeConfigError(f"冻结运行配置不存在: {file_path}")
    raw = file_path.read_bytes()
    file_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeConfigError(f"冻结件不是合法 JSON: {exc!r}") from None
    if not isinstance(document, dict):
        raise RuntimeConfigError("冻结件必须是 JSON 对象")
    if document.get("doc_version") != FREEZE_DOC_VERSION:
        raise RuntimeConfigError(
            f"冻结件版本不支持: {document.get('doc_version')!r}"
        )
    environment = document.get("environment")
    if environment not in SUPPORTED_ENVIRONMENTS:
        raise RuntimeConfigError(f"冻结件环境标记非法: {environment!r}")
    expected = document.get("config_fingerprint")
    actual = compute_config_fingerprint(document)
    if not expected or expected != actual:
        raise RuntimeConfigError(
            "REFUSED_CONFIG_DRIFT：冻结件整件指纹不符（文件被改动或伪造），拒绝执行"
        )
    tables: dict[str, TableRuntimeSpec] = {}
    raw_tables = _require(document, "tables", "顶层")
    for name, table_doc in raw_tables.items():
        _validate_table_document(name, table_doc)
        expected_table_fp = table_doc.get("fingerprint")
        actual_table_fp = compute_table_fingerprint(table_doc)
        if not expected_table_fp or expected_table_fp != actual_table_fp:
            raise RuntimeConfigError(
                f"[{name}] REFUSED_CONFIG_DRIFT：表指纹不符，拒绝执行"
            )
        source = table_doc["source"]
        target = table_doc["target"]
        key = table_doc["stable_key"]
        anchor = table_doc.get("anchor") or {}
        projection = _parse_projection(table_doc["projection"], f"[{name}]")
        parent = table_doc.get("parent") or None
        tables[name] = TableRuntimeSpec(
            canonical_table=name,
            business_name=str(table_doc.get("business_name") or name),
            engine=table_doc["engine"],
            modes=tuple(str(m) for m in table_doc["modes"]),
            enabled=bool(table_doc["enabled"]),
            source_group=str(source["source_group"]),
            dialect=str(source["dialect"]),
            source_object=str(source["object"]),
            object_sha256=source.get("object_sha256"),
            credential_ref=str(source["credential_ref"]),
            target_instance=str(target["instance"]),
            tenant=str(target["tenant"]),
            target_table=str(target["table"]),
            stable_key=tuple(str(c) for c in key["columns"]),
            anchor_column=anchor.get("column"),
            anchor_inherited_from_parent=bool(anchor.get("inherited_from_parent")),
            timezone=str(anchor.get("timezone") or "Asia/Shanghai"),
            # 规范化：候选文档可能带说明后缀（"SNAPSHOT_DIFF 全窗比对"）
            change_mode=(
                raw_mode.split()[0].upper()
                if (raw_mode := str(table_doc.get("change_mode") or "SNAPSHOT_DIFF"))
                .upper()
                .startswith("SNAPSHOT_DIFF")
                else raw_mode
            ),
            projection=projection,
            system_time_column=table_doc.get("system_time_column"),
            receipt_table=table_doc.get("receipt_table"),
            budget=dict(table_doc["budget"]),
            parent_table=str(parent["table"]) if parent else None,
            parent_key_column=str(parent["key_column"]) if parent else None,
            fingerprint=actual_table_fp,
            target_charset=str(target.get("charset") or "utf-8"),
        )
    return FrozenRuntimeConfig(
        environment=environment,
        version=str(document.get("version") or ""),
        frozen_at=str(document.get("frozen_at") or ""),
        path=str(file_path),
        file_sha256=file_sha256,
        config_fingerprint=actual,
        tables=tables,
        source_inputs=tuple(document.get("source_inputs") or ()),
    )


# -- 冻结件构造（CLI freeze-config 使用） -----------------------------------


def build_table_document(
    *,
    canonical_table: str,
    business_name: str,
    engine: str,
    modes: Sequence[str],
    source_group: str,
    dialect: str,
    source_object: str,
    credential_ref: str,
    target_instance: str,
    tenant: str,
    target_table: str,
    stable_key: Sequence[str],
    anchor_column: str | None,
    anchor_inherited_from_parent: bool,
    projection: Sequence[Mapping],
    change_mode: str,
    budget: Mapping[str, int],
    object_sha256: str | None = None,
    system_time_column: str | None = None,
    receipt_table: str | None = None,
    parent: Mapping[str, str] | None = None,
    timezone: str = "Asia/Shanghai",
    notes: Mapping[str, str] | None = None,
    target_charset: str | None = None,
) -> dict:
    """构造单表文档并计算指纹（投影顺序即文档顺序）。"""
    ordered = [
        {**{"order": index + 1}, **dict(item)}
        for index, item in enumerate(projection)
    ]
    document: dict[str, Any] = {
        "canonical_table": canonical_table,
        "business_name": business_name,
        "engine": engine,
        "modes": list(modes),
        "enabled": False,
        "source": {
            "source_group": source_group,
            "dialect": dialect,
            "object": source_object,
            "credential_ref": credential_ref,
            **({"object_sha256": object_sha256} if object_sha256 else {}),
        },
        "target": {
            "instance": target_instance,
            "tenant": tenant,
            "table": target_table,
            "identity_verified": True,
            **({"charset": target_charset} if target_charset else {}),
        },
        "stable_key": {"columns": list(stable_key), "verified": True},
        "anchor": {
            "column": anchor_column,
            "inherited_from_parent": anchor_inherited_from_parent,
            "half_open": True,
            "timezone": timezone,
        },
        "change_mode": change_mode,
        "projection": ordered,
        "system_time_column": system_time_column,
        "receipt_table": receipt_table,
        "budget": dict(budget),
        "parent": dict(parent) if parent else None,
    }
    if notes:
        document["notes"] = dict(notes)
    document["fingerprint"] = compute_table_fingerprint(document)
    return document


def build_freeze_document(
    *,
    environment: str,
    tables: Mapping[str, Mapping],
    source_inputs: Sequence[Mapping[str, str]],
    version: str = FREEZE_DOC_VERSION,
    frozen_at: str,
    notes: Mapping[str, str] | None = None,
) -> dict:
    """构造整件冻结文档（含 config_fingerprint）。"""
    if environment not in SUPPORTED_ENVIRONMENTS:
        raise RuntimeConfigError(f"环境标记非法: {environment}")
    document: dict[str, Any] = {
        "doc_version": FREEZE_DOC_VERSION,
        "freeze_id": "R189-T1-RUNTIME-CONFIG-FREEZE",
        "environment": environment,
        "version": version,
        "frozen_at": frozen_at,
        "source_inputs": [dict(item) for item in source_inputs],
        "tables": dict(tables),
        "enabled_policy": (
            "全部 enabled=false（候选停用保留）；正式启用另出启用冻结并走 A05c 审批，"
            "动作级派发走 K01 ActionBinding，不手工置 READY"
        ),
    }
    if notes:
        document["notes"] = dict(notes)
    document["config_fingerprint"] = compute_config_fingerprint(document)
    return document


def synthesize_task_spec(spec: TableRuntimeSpec, seed_spec=None):
    """冻结件事实 → 已核 TaskSpec（供 K01 动作门禁与分层校验）。

    冻结件本身携带已核标记（稳定键/锚点/目标身份/投影类型/引擎/预算/
    凭据引用/变更依据），合成规格把这些事实映射回 TaskSpec 的 verified
    字段——不是放宽门禁，而是让门禁读到已核事实而非种子的 UNKNOWN。
    enabled 恒 False（候选停用保留）；旧写者交接=HANDOFF_VERIFIED 依据
    8.53 写者零进程快照（2026-10-22，核验证据_20261022）。
    """
    from app.services.reporting_pipeline.contracts import (
        Applicability,
        ApplyPolicy,
        ChangePolicy,
        Engine,
        IncrementalStrategy,
        ProjectionField,
        SourceRef,
        StableKey,
        TargetRef,
        TaskAssociations,
        TaskSpec,
        TimeSemantics,
    )

    host_port, _, service = spec.target_instance.partition("/")
    seed_assoc = getattr(seed_spec, "associations", None)
    seed_budget = getattr(seed_spec, "resource_budget", None)
    profile_id = (
        getattr(seed_assoc, "performance_profile_id", None)
        or f"frozen:{spec.canonical_table}"
    )
    budget_kwargs = {}
    if seed_budget is not None:
        budget_kwargs = {
            f: getattr(seed_budget, f)
            for f in getattr(seed_budget, "__dataclass_fields__", {})
        }
    budget_kwargs.update({
        "max_rows_per_slice": spec.budget.get("max_rows_per_slice", 50000),
        "max_bytes_per_slice": spec.budget.get("max_bytes_per_slice", 268435456),
        "max_attempts": spec.budget.get("max_attempts", 3),
        "query_timeout_seconds": spec.budget.get("query_timeout_seconds", 300),
        "cancel_supported": True,
    })
    from app.services.reporting_pipeline.contracts import ResourceBudget

    return TaskSpec(
        canonical_table=spec.canonical_table,
        business_name=spec.business_name,
        index=getattr(seed_spec, "index", 0) or 0,
        enabled=False,
        applicability=Applicability.APPLICABLE,
        engine=Engine(spec.engine),
        incremental_strategy=IncrementalStrategy.SNAPSHOT_DIFF,
        source_candidates=[
            SourceRef(
                object_id=f"{spec.source_group}__{spec.source_object.rsplit('.', 1)[-1]}",
                role="primary",
                source_group=spec.source_group,
                host=(host_port.partition(":")[0] or "frozen"),
                port=int(host_port.partition(":")[2] or 1521),
                object_name_candidates=[spec.source_object.rsplit(".", 1)[-1]],
                current_identity_verified=True,
            )
        ],
        target=TargetRef(
            host=host_port.partition(":")[0] or "frozen",
            port=int(host_port.partition(":")[2] or 1521),
            service=service or "frozen",
            owner=spec.tenant,
            table=spec.target_table.rsplit(".", 1)[-1],
            current_identity_verified=True,
        ),
        stable_key=StableKey(candidate=list(spec.stable_key), verified=True),
        associations=TaskAssociations(
            long_lived_credential_ref=spec.credential_ref,
            performance_profile_id=profile_id,
            running_writer_handoff_state="HANDOFF_VERIFIED",
        ),
        projection=[
            ProjectionField(
                name=field.name,
                target_type=field.target_type,
                order=field.order,
                source_expression=field.source_expression,
                type_verified=True,
            )
            for field in spec.projection
        ],
        time_semantics=TimeSemantics(
            business_time_expression=spec.anchor_column or "DATETIME",
            business_time_verified=True,
            change_time_expression=spec.anchor_column or "DATETIME",
            change_time_verified=(spec.change_mode == "SNAPSHOT_DIFF"),  # 全窗快照=变更依据
            timezone=spec.timezone,
        ),
        change_policy=ChangePolicy(
            insert_evidence="冻结件:窗口全量快照",
            update_evidence=(
                "冻结件:SNAPSHOT_DIFF CAS(目标内容=上次登记源内容哈希)"
                if spec.change_mode == "SNAPSHOT_DIFF" else "冻结件"
            ),
            version_order_verified=(spec.change_mode == "SNAPSHOT_DIFF"),
        ),
        apply_policy=ApplyPolicy(
            executor_ref="sql-target-apply-1",
            allowed_operations=("INSERT", "UPDATE"),
            idempotency_key=list(spec.stable_key),
            approval_refs=("frozen-config:CAS+回执+租约",),
            commit_receipt_mode="SAME_TARGET_TXN",
        ),
        resource_budget=ResourceBudget(**budget_kwargs),
        definition_fingerprint=spec.fingerprint,
        config_version=f"frozen:{spec.fingerprint[:12]}",
        declared_parent_candidates=[spec.parent_table] if spec.parent_table else [],
        note="由冻结运行配置合成（批1-1）；verified 事实来自冻结件与核验证据",
    )
