"""三甲前置机三表字段修正：固定模板、平台批准、旧值保护和同事务凭据。

无 CLI、无凭据解析、无连接创建、无自动登记/启用、无 DDL。
生产维护入口须注入平台查询、目标连接、备份校验、租约校验和审计回调。
不能把调用方提供的批准字符串或旧入院记录试点当成生产批准。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol


EXECUTOR_CODE = "r189_ich_field_update"
TARGET = "10.10.8.74:1521/orcl:DBOPER"
LEASE_RESOURCE = "qianzhiji_874:ich_field_update"
GROUPS = MappingProxyType({
    "HOME_STAY": ("EMR_ICH", ("INPATIENT_DAY",)),
    "HOME_DEATH": ("EMR_ICH", ("IS_DEATH", "DISCHARGE_TYPE_CODE", "DISCHARGE_TYPE_NAME")),
    "HOME_OUTCOME": ("EMR_ICH", ("DIS_OUTCOME_CODE", "DIS_OUTCOME_NAME")),
    "HOME_UNPLANNED": ("EMR_ICH", ("SFFJHZRY",)),
    "HOME_DAY_WARD": ("EMR_ICH", ("SFRJBF",)),
    "DIAG_OUTCOME": ("EMR_ICH_DIAGNOSIS", ("DIS_OUTCOME_CODE", "DIS_OUTCOME_NAME")),
    "OP_GRADE": ("EMR_ICH_OPERATION", ("OPERATION_GRADE",)),
    "OP_INCISION": ("EMR_ICH_OPERATION", ("INCISION_CATEGORY",)),
    "FEE_CLASS_AMOUNT": ("EMR_ICH_CHARGE", ("CHARGE_TYPE_CODE", "CHARGE_TYPE", "CHARGE_AMOUNT")),
})
OUTCOMES = MappingProxyType({"1": "治愈", "2": "好转", "3": "稳定", "4": "恶化", "5": "死亡", "6": "未愈", "9": "其他"})


class UpdateRefused(ValueError):
    """无敏感值的门禁拒绝。"""


def _value(value: Any) -> str | Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.rstrip() or None
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise UpdateRefused("不支持的字段类型")
    result = Decimal(value)
    if not result.is_finite():
        raise UpdateRefused("非有限数值")
    return result


@dataclass(frozen=True)
class FieldChange:
    group: str
    record_id: str = field(repr=False)
    before: Mapping[str, Any] = field(repr=False)
    after: Mapping[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        if self.group not in GROUPS:
            raise UpdateRefused("字段组不在白名单")
        if not isinstance(self.record_id, str) or not self.record_id.startswith("49557032X|") or len(self.record_id.encode()) > 100:
            raise UpdateRefused("住院记录键格式不符")
        fields = GROUPS[self.group][1]
        if set(self.before) != set(fields) or set(self.after) != set(fields):
            raise UpdateRefused("字段超出白名单或字段不完整")
        # WHERE旧值绑定保留原始字符串，避免VARCHAR尾空格被规范化后误判并发。
        before = {key: self.before[key] if isinstance(self.before[key], str) else _value(self.before[key]) for key in fields}
        after = {key: _value(self.after[key]) for key in fields}
        if {key: _value(value) for key, value in before.items()} == after:
            raise UpdateRefused("无差异记录不应派发更新")
        if any(value is None for value in after.values()) and self.group not in ("HOME_UNPLANNED", "HOME_DAY_WARD"):
            raise UpdateRefused("缺值保留待补，不自动清空目标")
        if self.group in ("HOME_STAY", "OP_GRADE"):
            value = next(iter(after.values()))
            if not isinstance(value, Decimal) or value != value.to_integral_value() or value < 1:
                raise UpdateRefused("非法整数值")
            if self.group == "OP_GRADE" and value > 4:
                raise UpdateRefused("手术等级超出1至4")
        elif self.group in ("HOME_UNPLANNED", "HOME_DAY_WARD"):
            if next(iter(after.values())) not in ("1", "2", None):
                raise UpdateRefused("登记标志仅允许1、2或未知空值")
        elif self.group == "FEE_CLASS_AMOUNT":
            code=after["CHARGE_TYPE_CODE"]
            if code not in {str(i) for i in range(1,25)} | {"901", "101", "102", "131"}:
                raise UpdateRefused("费用分类不在核准代码范围")
            name=after["CHARGE_TYPE"]
            amount=after["CHARGE_AMOUNT"]
            if not self.record_id.endswith("|"+code) or not isinstance(name,str) or not name or len(name.encode('utf8'))>32:
                raise UpdateRefused("费用分类名称或ID后缀不一致")
            if not isinstance(amount,Decimal) or amount.as_tuple().exponent < -2 or abs(amount)>Decimal('9999999.99'):
                raise UpdateRefused("费用金额精度或范围不符")
        elif self.group == "OP_INCISION":
            if after["INCISION_CATEGORY"] not in ("1", "2", "3", "4"):
                raise UpdateRefused("切口类别不合法")
        elif self.group in ("HOME_OUTCOME", "DIAG_OUTCOME"):
            if OUTCOMES.get(after["DIS_OUTCOME_CODE"]) != after["DIS_OUTCOME_NAME"]:
                raise UpdateRefused("转归代码和名称不一致")
        else:
            death = after["IS_DEATH"]
            code = after["DISCHARGE_TYPE_CODE"]
            name = after["DISCHARGE_TYPE_NAME"]
            if death not in ("0", "1") or code not in ("1", "2", "3", "4", "5", "9"):
                raise UpdateRefused("死亡或离院方式值不合法")
            if (death == "1") != (code == "5") or (code == "5") != (name == "死亡"):
                raise UpdateRefused("死亡标志与离院方式不一致")
            if not isinstance(name, str) or len(name.encode("utf8")) > 50:
                raise UpdateRefused("离院名称超长")
        object.__setattr__(self, "before", MappingProxyType(before))
        object.__setattr__(self, "after", MappingProxyType(after))


def update_sql(group: str) -> str:
    if group not in GROUPS:
        raise UpdateRefused("字段组不在白名单")
    table, fields = GROUPS[group]
    sets = ", ".join(f"{name}=:new_{i}" for i, name in enumerate(fields))
    old = " AND ".join(f"({name}=:old_{i} OR ({name} IS NULL AND :old_{i} IS NULL))" for i, name in enumerate(fields))
    return f"UPDATE DBOPER.{table} SET {sets} WHERE ID=:record_id AND {old}"


@dataclass(frozen=True)
class UpdateBatch:
    operation_id: str
    approval_ref: str
    changes: tuple[FieldChange, ...] = field(repr=False)
    backup_ref: str
    backup_sha256: str
    source_sha256: str
    fencing_token: int
    executor_code: str = EXECUTOR_CODE
    target: str = TARGET
    lease_resource: str = LEASE_RESOURCE

    def __post_init__(self) -> None:
        object.__setattr__(self, "changes", tuple(self.changes))
        if self.executor_code != EXECUTOR_CODE or self.target != TARGET or self.lease_resource != LEASE_RESOURCE:
            raise UpdateRefused("目标或执行器不匹配")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", self.operation_id):
            raise UpdateRefused("操作号不合法")
        if not self.approval_ref or not 1 <= len(self.changes) <= 200 or isinstance(self.fencing_token, bool) or not isinstance(self.fencing_token, int) or self.fencing_token < 1:
            raise UpdateRefused("批准引用、批大小或围栏不合法")
        if any(not isinstance(change, FieldChange) for change in self.changes):
            raise UpdateRefused("更新组类型不合法")
        if any(not re.fullmatch(r"[0-9a-f]{64}", x) for x in (self.backup_sha256, self.source_sha256)):
            raise UpdateRefused("缺少备份或源内容指纹")
        if not self.backup_ref.startswith("/opt/data-asset/evidence/") or ".." in self.backup_ref.split("/"):
            raise UpdateRefused("备份必须位于受控目录")
        if len({(c.group, c.record_id) for c in self.changes}) != len(self.changes):
            raise UpdateRefused("重复字段更新组")

    @property
    def manifest_hash(self) -> str:
        def packed(value: Any) -> Any:
            if not isinstance(value, Decimal):
                return value
            # normalize()受当前Decimal精度影响，会把大整数舍入成相同指纹。
            sign, digits, exponent = value.as_tuple()
            digits = list(digits)
            if not any(digits):
                return {"decimal": "0"}
            while digits[-1] == 0:
                digits.pop()
                exponent += 1
            return {"decimal": f"{sign}:{''.join(str(d) for d in digits)}:{exponent}"}
        items = [dict(group=c.group, key=c.record_id, before={k: packed(v) for k, v in c.before.items()}, after={k: packed(v) for k, v in c.after.items()}) for c in sorted(self.changes, key=lambda c: (c.group, c.record_id))]
        payload = dict(operation_id=self.operation_id, target=self.target, executor=self.executor_code, changes=items, backup_ref=self.backup_ref, backup_sha256=self.backup_sha256, source_sha256=self.source_sha256)
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    @property
    def unique_records(self) -> int:
        return len({(GROUPS[c.group][0], c.record_id) for c in self.changes})


class PlatformFieldUpdateAuthority:
    """Lookup须由平台维护入口注入；批准记录必须绑定本批完整指纹。"""

    def __init__(self, executor_lookup: Callable, approval_lookup: Callable, now: Callable = lambda: datetime.now(timezone.utc)):
        self._executor_lookup = executor_lookup
        self._approval_lookup = approval_lookup
        self._now = now

    def verify(self, batch: UpdateBatch) -> None:
        executor = self._executor_lookup(batch.executor_code)
        if not executor or executor.get("enabled") is not True:
            raise UpdateRefused("本次字段更新执行器未登记或未启用")
        expected = {"executor_code": EXECUTOR_CODE, "execution_mode": "controlled_field_update", "target_system_code": "qianzhiji_874", "target_source_code": "dboper_orcl", "require_approval": True}
        if any(executor.get(k) != v for k, v in expected.items()):
            raise UpdateRefused("执行器登记范围不匹配")
        approval = self._approval_lookup(batch.approval_ref, batch.executor_code)
        if not approval or approval.get("valid") is not True:
            raise UpdateRefused("缺少平台有效批准记录")
        try:
            expires = approval["expires_at"]
            now = self._now()
            if not isinstance(expires, datetime) or expires.tzinfo is None or now.tzinfo is None or expires <= now:
                raise UpdateRefused("平台批准已过期")
            checks = {"approval_ref": batch.approval_ref, "executor_code": EXECUTOR_CODE, "target": TARGET, "manifest_hash": batch.manifest_hash, "backup_sha256": batch.backup_sha256}
            if any(approval.get(k) != v for k, v in checks.items()):
                raise UpdateRefused("平台批准与本次目标或内容不匹配")
            if set(approval.get("operations", ())) != {"UPDATE"}:
                raise UpdateRefused("批准动作不是指定字段UPDATE")
            if not {c.group for c in batch.changes} <= set(approval.get("groups", ())):
                raise UpdateRefused("字段组超出平台批准范围")
            if len(batch.changes) > int(approval.get("max_changes", 0)):
                raise UpdateRefused("批大小超出平台批准范围")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            if isinstance(exc, UpdateRefused):
                raise
            raise UpdateRefused("平台批准结构不完整") from None


class FieldUpdateTransport(Protocol):
    def verify_target(self) -> None: ...
    def receipt(self, operation_id: str) -> Mapping | None: ...
    def patch(self, change: FieldChange) -> int: ...
    def read(self, change: FieldChange) -> Mapping: ...
    def write_receipt(self, batch: UpdateBatch, affected: int) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@dataclass(frozen=True)
class UpdateResult:
    state: str
    unique_records: int = 0
    field_groups: int = 0


class ControlledFieldUpdater:
    """只接收平台装配的目标连接及真实备份/租约/审计回调，无宽松默认值。"""

    def __init__(self, authority: PlatformFieldUpdateAuthority, transport: FieldUpdateTransport, *, backup_verifier: Callable[[UpdateBatch], bool], lease_validator: Callable[[UpdateBatch], bool], audit: Callable[[UpdateBatch, UpdateResult], None]):
        if not isinstance(authority, PlatformFieldUpdateAuthority) or not all(callable(x) for x in (backup_verifier, lease_validator, audit)):
            raise UpdateRefused("缺少生产门禁装配")
        self.authority, self.transport = authority, transport
        self.backup_verifier, self.lease_validator, self.audit = backup_verifier, lease_validator, audit

    def execute(self, batch: UpdateBatch) -> UpdateResult:
        self.authority.verify(batch)
        if not self.backup_verifier(batch) or not self.lease_validator(batch):
            raise UpdateRefused("备份或单写者租约未通过")
        self.transport.verify_target()
        existing = self.transport.receipt(batch.operation_id)
        if existing:
            if existing.get("MANIFEST_HASH") != batch.manifest_hash or existing.get("ROWS_AFFECTED") != len(batch.changes):
                raise UpdateRefused("操作号已有不同提交凭据")
            result = UpdateResult("REPLAY_CONFIRMED", batch.unique_records, len(batch.changes))
            try:
                self.audit(batch, result)
            except Exception:
                return UpdateResult("REPLAY_CONFIRMED_AUDIT_PENDING", batch.unique_records, len(batch.changes))
            return result
        try:
            for change in sorted(batch.changes, key=lambda c: (GROUPS[c.group][0], c.record_id, c.group)):
                if not self.lease_validator(batch):
                    raise UpdateRefused("单写者租约失效")
                if self.transport.patch(change) != 1:
                    raise UpdateRefused("目标旧值变化或ID不存在")
                actual = self.transport.read(change)
                if {key: _value(actual.get(key)) for key in change.after} != dict(change.after):
                    raise UpdateRefused("更新后回读不一致")
            self.authority.verify(batch)
            if not self.lease_validator(batch):
                raise UpdateRefused("提交前单写者租约失效")
            self.transport.write_receipt(batch, len(batch.changes))
        except Exception:
            try:
                self.transport.rollback()
            except Exception:
                return UpdateResult("ROLLBACK_UNCONFIRMED")
            raise UpdateRefused("本批已回滚，需核查冲突或回读结果") from None
        try:
            self.transport.commit()
        except Exception:
            # 不能把提交异常解释为已回滚；需另连接按同事务凭据裁定。
            return UpdateResult("COMMIT_UNKNOWN")
        result = UpdateResult("COMMITTED", batch.unique_records, len(batch.changes))
        try:
            self.audit(batch, result)
        except Exception:
            return UpdateResult("COMMITTED_AUDIT_PENDING", batch.unique_records, len(batch.changes))
        return result


class OracleFieldUpdateTransport:
    """由受控入口注入专用写连接；此类不解析/创建连接或凭据。"""

    def __init__(self, connection):
        self._connection = connection
        self._cursor = connection.cursor()

    def verify_target(self) -> None:
        if getattr(self._connection, "autocommit", None) is not False:
            raise UpdateRefused("目标连接必须关闭自动提交")
        if getattr(self._connection, "transaction_in_progress", False):
            raise UpdateRefused("目标连接已有事务，必须使用独立写连接")
        timeout = getattr(self._connection, "call_timeout", 0)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or not 0 < timeout <= 30000:
            raise UpdateRefused("目标连接必须设置不超过30秒的调用超时")
        dsn = str(getattr(self._connection, "dsn", "")).strip().lower()
        easy = re.fullmatch(r"(?://)?10\.10\.8\.74:1521/orcl", dsn)
        descriptor = (
            re.findall(r"\(host\s*=\s*([^()\s]+)\s*\)", dsn) == ["10.10.8.74"]
            and re.findall(r"\(port\s*=\s*([^()\s]+)\s*\)", dsn) == ["1521"]
            and re.findall(r"\(service_name\s*=\s*([^()\s]+)\s*\)", dsn) == ["orcl"]
        )
        if not (easy or descriptor):
            raise UpdateRefused("目标连接地址不是核准的前置机")
        self._cursor.execute("SELECT SYS_CONTEXT('USERENV','SESSION_USER'),SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual")
        row = self._cursor.fetchone()
        if not row or tuple(str(v).upper() for v in row) != ("DBOPER", "DBOPER"):
            raise UpdateRefused("目标账号或Schema不是DBOPER")
        self._cursor.execute("SELECT COUNT(*) FROM all_tab_columns WHERE owner='DBOPER' AND table_name='ASSET_APPLY_RECEIPTS' AND column_name IN ('OPERATION_ID','BATCH_ID','MANIFEST_HASH','TARGET_OBJECT','SCOPE_SUMMARY','ROWS_AFFECTED')")
        if self._cursor.fetchone()[0] != 6:
            raise UpdateRefused("目标同事务凭据表未就绪；本执行器不建表")

    def receipt(self, operation_id: str) -> Mapping | None:
        self._cursor.execute("SELECT MANIFEST_HASH,ROWS_AFFECTED FROM DBOPER.ASSET_APPLY_RECEIPTS WHERE OPERATION_ID=:operation_id", {"operation_id": operation_id})
        row = self._cursor.fetchone()
        return {"MANIFEST_HASH": row[0], "ROWS_AFFECTED": row[1]} if row else None

    def patch(self, change: FieldChange) -> int:
        fields = GROUPS[change.group][1]
        params = {"record_id": change.record_id}
        params.update({f"old_{i}": change.before[name] for i, name in enumerate(fields)})
        params.update({f"new_{i}": change.after[name] for i, name in enumerate(fields)})
        self._cursor.execute(update_sql(change.group), params)
        return self._cursor.rowcount

    def read(self, change: FieldChange) -> Mapping:
        table, fields = GROUPS[change.group]
        self._cursor.execute("SELECT " + ",".join(fields) + f" FROM DBOPER.{table} WHERE ID=:record_id", {"record_id": change.record_id})
        row = self._cursor.fetchone()
        return dict(zip(fields, row)) if row else {}

    def write_receipt(self, batch: UpdateBatch, affected: int) -> None:
        self._cursor.execute("INSERT INTO DBOPER.ASSET_APPLY_RECEIPTS (OPERATION_ID,BATCH_ID,MANIFEST_HASH,TARGET_OBJECT,SCOPE_SUMMARY,ROWS_AFFECTED) VALUES (:operation_id,:batch_id,:manifest,:target_object,:scope,:affected)", {"operation_id": batch.operation_id, "batch_id": "ICH_FIELD_UPDATE", "manifest": batch.manifest_hash, "target_object": ",".join(sorted({"DBOPER." + GROUPS[c.group][0] for c in batch.changes})), "scope": "UPDATE_ONLY:" + ",".join(sorted({c.group for c in batch.changes})), "affected": affected})

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()
