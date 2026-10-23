"""生产 ApplyPort 组装（第一批批1-2c）。

把 ApplyPort(production_mode=True) 的硬性三要件落到真实查询：
- PlatformApprovalVerifier.executor_lookup：查平台白名单表
  asset.asset_action_executors（executor_code + enabled）；
- PlatformApprovalVerifier.approval_lookup：查耐久批准登记表
  asset.asset_reporting_approval_refs（有效性窗 + 执行器绑定 + 目标范围）；
  管道自身永不写该表，登记仅经 reporting_ctl approval-register 管理动作；
- lease_validator：控制仓储 validate_fencing（本表写租约围栏 token）；
- VersionGuard：PgVersionRegistry（耐久版本账，按实例/Owner/表隔离）。

查询只读；不存在"传一组字符串就自认已批准"的路径。装配失败抛
ProductionApplyError（ContractViolation 子类），不静默降级模拟。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence

from app.services.reporting_pipeline.apply_port import (
    ApprovalDecision,
    ApplyPort,
    PlatformApprovalVerifier,
    VersionGuard,
)
from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.pg_repository import PgVersionRegistry
from app.services.reporting_pipeline.repositories import ControlRepository


class ProductionApplyError(ContractViolation):
    """生产 ApplyPort 装配失败。"""


def build_executor_lookup(session_factory) -> Callable[[str, str], Mapping | None]:
    """白名单执行器只读查询（asset_action_executors）。"""

    def lookup(executor_code: str, target_object: str) -> Mapping | None:
        from sqlalchemy import text

        with session_factory() as session:
            row = session.execute(
                text(
                    "SELECT executor_code, enabled, require_approval, "
                    "target_source_code, risk_level "
                    "FROM asset.asset_action_executors "
                    "WHERE executor_code = :code"
                ),
                {"code": executor_code},
            ).mappings().first()
            if row is None:
                return None
            record = dict(row)
        # 目标范围粗筛：执行器登记了 target_source_code 时须与目标实例
        # 前缀匹配（10.10.8.74 前置机实例）；未登记则交批准记录核范围
        declared = record.get("target_source_code")
        if declared and target_object and not target_object.startswith(
            str(declared)
        ):
            return None
        return record

    return lookup


def build_approval_lookup(session_factory) -> Callable[[str, str], Mapping | None]:
    """耐久批准登记只读查询（asset_reporting_approval_refs）。

    有效 = 当前时刻落在 [valid_from, valid_until) 且执行器匹配。
    目标范围核验由 ApplyPort 侧 target_object + 本查询 target_scope
    对齐（见 verify_with_scope）。
    """

    def lookup(approval_ref: str, executor_code: str) -> Mapping | None:
        from sqlalchemy import text

        with session_factory() as session:
            row = session.execute(
                text(
                    "SELECT approval_ref, executor_code, target_scope, "
                    "allowed_operations, valid_from, valid_until "
                    "FROM asset.asset_reporting_approval_refs "
                    "WHERE approval_ref = :ref AND executor_code = :code"
                ),
                {"ref": approval_ref, "code": executor_code},
            ).mappings().first()
            if row is None:
                return None
            record = dict(row)
        now = datetime.now(timezone.utc)
        valid_from = record.get("valid_from")
        valid_until = record.get("valid_until")
        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        record["valid"] = bool(valid_from <= now < valid_until)
        return record

    return lookup


class ScopedApprovalVerifier(PlatformApprovalVerifier):
    """平台核验 + 目标范围对齐：批准记录的 target_scope 必须与本次
    装载目标一致（不允许拿 A 表的批准去写 B 表）。"""

    def verify(
        self,
        *,
        approval_ref: str,
        executor_id: str,
        target_object: str,
        allowed_operations: Sequence = (),
    ) -> object:
        decision = super().verify(
            approval_ref=approval_ref,
            executor_id=executor_id,
            target_object=target_object,
            allowed_operations=allowed_operations,
        )
        if not decision.approved:
            return decision
        approval = self._approval_lookup(approval_ref, executor_id) or {}
        if str(approval.get("target_scope", "")) != target_object:
            return ApprovalDecision(
                False,
                self.trust_level,
                f"批准范围不符: 登记={approval.get('target_scope')} 本次={target_object}",
            )
        allowed = {
            part.strip().upper()
            for part in str(approval.get("allowed_operations") or "").split(",")
            if part.strip()
        }
        requested = {str(op).upper() for op in allowed_operations}
        if requested and not requested.issubset(allowed):
            return ApprovalDecision(
                False,
                self.trust_level,
                f"批准未覆盖请求操作: 请求={sorted(requested)} 批准={sorted(allowed)}",
            )
        return decision


def build_lease_validator(repository: ControlRepository) -> Callable[[str, int], None]:
    """围栏校验器：本表写租约 token（validate_fencing 含有效期核验）。"""

    def validator(resource: str, fencing_token: int) -> None:
        repository.validate_fencing(resource, int(fencing_token))

    return validator


def build_production_apply_port(
    *,
    session_factory,
    repository: ControlRepository,
    executor_codes,
) -> ApplyPort:
    """生产 ApplyPort：平台核验 + 耐久版本账 + 围栏校验器三要件齐备。"""
    verifier = ScopedApprovalVerifier(
        executor_lookup=build_executor_lookup(session_factory),
        approval_lookup=build_approval_lookup(session_factory),
    )
    version_guard = VersionGuard(PgVersionRegistry(session_factory))
    port = ApplyPort(
        whitelisted_executors=tuple(executor_codes),
        approval_verifier=verifier,
        version_guard=version_guard,
        lease_validator=build_lease_validator(repository),
        enforce_fence=True,
        production_mode=True,
    )
    if not port.production_mode:
        raise ProductionApplyError("生产 ApplyPort 组装结果非生产模式")
    return port


# -- 批准登记（管理动作；管道代码禁止调用） ----------------------------------


def register_approval(
    session_factory,
    *,
    approval_ref: str,
    executor_code: str,
    target_scope: str,
    valid_from: datetime,
    valid_until: datetime,
    registered_by: str,
    allowed_operations: str = "INSERT,UPDATE",
    note: str | None = None,
) -> dict:
    """登记耐久批准（reporting_ctl approval-register 专用）。

    仅运维显式调用；本函数不接受管道侧调用方（调用方=CLI 管理命令）。
    重复登记同一 (approval_ref, executor_code) 拒绝，不得静默改期。
    """
    from sqlalchemy import text

    if valid_from >= valid_until:
        raise ProductionApplyError("批准有效期非法（valid_from >= valid_until）")
    if not registered_by:
        raise ProductionApplyError("登记人不可为空（批准可追溯）")
    with session_factory() as session:
        existing = session.execute(
            text(
                "SELECT id FROM asset.asset_reporting_approval_refs "
                "WHERE approval_ref = :ref AND executor_code = :code"
            ),
            {"ref": approval_ref, "code": executor_code},
        ).first()
        if existing is not None:
            raise ProductionApplyError(
                f"批准已登记: {approval_ref}/{executor_code}（改期须先显式作废再登记）"
            )
        session.execute(
            text(
                "INSERT INTO asset.asset_reporting_approval_refs "
                "(approval_ref, executor_code, target_scope, allowed_operations, "
                " valid_from, valid_until, registered_by, note) "
                "VALUES (:ref, :code, :scope, :ops, :vf, :vu, :by, :note)"
            ),
            {
                "ref": approval_ref,
                "code": executor_code,
                "scope": target_scope,
                "ops": allowed_operations,
                "vf": valid_from,
                "vu": valid_until,
                "by": registered_by,
                "note": note,
            },
        )
        session.commit()
    return {
        "approval_ref": approval_ref,
        "executor_code": executor_code,
        "target_scope": target_scope,
        "valid_from": valid_from.isoformat(),
        "valid_until": valid_until.isoformat(),
        "registered_by": registered_by,
    }
