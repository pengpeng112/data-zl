"""人工视图整改工单闭环：状态机 + 复核取证 + 旧 stage 复用判定。

对应计划 §7：
- 状态：OPEN → WAITING_HUMAN → FIX_REPORTED → REVERIFYING → VERIFIED/CLOSED
  或 REOPENED。用户说"改完"只触发新取证（FIX_REPORTED→REVERIFYING），
  不能直接 CLOSED。
- 修好后比定义/依赖与字段指纹，复核该问题及受影响上下游；明确旧 stage
  是可重放还是必须重新抽取——旧字节/错 ID 载荷不能不加判断直接复用。
- 每张工单含 ticket_id、规范表/源身份/视图、指纹、问题类别、SQL 位置、
  影响范围、受影响批次/组、修正建议、期望输出与验收 SQL 引用、责任角色、
  阻塞范围、状态与恢复动作。
- never_auto_close：AI 不自动关单。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.services.reporting_pipeline.contracts import ContractViolation

TICKET_STATES = (
    "OPEN", "WAITING_HUMAN", "FIX_REPORTED", "REVERIFYING",
    "VERIFIED", "CLOSED", "REOPENED",
)

_ALLOWED = {
    "OPEN": {"WAITING_HUMAN", "CANCELLED"},
    "WAITING_HUMAN": {"FIX_REPORTED"},
    "FIX_REPORTED": {"REVERIFYING"},  # 用户报修好 → 只触发新取证
    "REVERIFYING": {"VERIFIED", "REOPENED"},
    "VERIFIED": {"CLOSED", "REOPENED"},
    "CLOSED": {"REOPENED"},
    "REOPENED": {"WAITING_HUMAN", "FIX_REPORTED"},
}


class TicketTransitionError(ContractViolation):
    """非法工单转换。"""


@dataclass
class ManualTicket:
    ticket_id: str
    tables: list[str]
    source_identity: str | None
    view_object: str | None
    problem_category: str  # INVALID_VIEW / MISSING_FIELD / TIME_BASIS / JOIN_LOGIC / NO_CHANGE_EVIDENCE / VALUE_DOMAIN / UNSTABLE_ID / OTHER
    definition_fingerprint: str | None = None
    dependency_fingerprints: dict[str, str] = field(default_factory=dict)
    sql_location_ref: str | None = None
    impact_scope: str | None = None
    affected_batches: list[str] = field(default_factory=list)
    fix_suggestion: str | None = None
    expected_output_ref: str | None = None  # 期望输出与验收 SQL 的受控引用
    owner_role: str = "USER_HUMAN"
    blocking_scope: str = "affected_table_or_group_only"
    state: str = "OPEN"
    history: list[dict] = field(default_factory=list)
    detail_ref: str | None = None
    action: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if self.state not in TICKET_STATES:
            raise ContractViolation(f"非法工单状态: {self.state}")
        if not self.ticket_id:
            raise ContractViolation("工单需要 ticket_id")
        # tables 允许为空：写者交接/凭据等全局范围工单无单表归属
        self.history.append({"to": self.state, "reason": "init"})

    def transition(self, target: str, *, reason: str, evidence: str | None = None) -> str:
        if target not in _ALLOWED.get(self.state, set()):
            raise TicketTransitionError(
                f"[{self.ticket_id}] 非法转换 {self.state} -> {target}"
            )
        if target == "VERIFIED" and not evidence:
            raise TicketTransitionError(
                f"[{self.ticket_id}] VERIFIED 需要复核取证证据（新指纹/验收SQL结果）"
            )
        self.state = target
        self.history.append(
            {"to": target, "reason": reason, "evidence": evidence}
        )
        return target

    def to_dict(self) -> dict:
        return {
            "ticket_id": self.ticket_id, "tables": self.tables,
            "source_identity": self.source_identity,
            "view_object": self.view_object,
            "problem_category": self.problem_category,
            "definition_fingerprint": self.definition_fingerprint,
            "dependency_fingerprints": self.dependency_fingerprints,
            "sql_location_ref": self.sql_location_ref,
            "impact_scope": self.impact_scope,
            "affected_batches": self.affected_batches,
            "fix_suggestion": self.fix_suggestion,
            "expected_output_ref": self.expected_output_ref,
            "owner_role": self.owner_role, "blocking_scope": self.blocking_scope,
            "state": self.state, "detail_ref": self.detail_ref,
            "action": self.action, "note": self.note,
            "history": self.history,
        }


@dataclass
class ReverifyEvidence:
    """复核取证：新定义/依赖指纹 + 字段核对 + 上下游影响。"""

    new_definition_fingerprint: str
    new_dependency_fingerprints: dict[str, str]
    field_check_passed: bool
    upstream_downstream_checked: bool
    acceptance_result_ref: str


def decide_stage_reuse(
    ticket: ManualTicket,
    evidence: ReverifyEvidence,
    *,
    stage_fingerprint_matches_current: bool,
) -> dict:
    """旧 stage 复用判定：指纹未变+字段核对通过才可复用，否则重抽。

    旧字节/错 ID 载荷不能不加判断直接复用；定义指纹变化的批次必须重抽。
    """
    definition_changed = (
        evidence.new_definition_fingerprint != ticket.definition_fingerprint
    )
    if definition_changed or not stage_fingerprint_matches_current:
        decision = "REEXTRACT_AFFECTED_SCOPE"
        reason = (
            "定义指纹已变化或旧 stage 与当前定义不一致：受影响范围重新抽取"
        )
    elif evidence.field_check_passed and evidence.upstream_downstream_checked:
        decision = "REPLAY_OLD_STAGE_WITH_CHECK"
        reason = "定义未变且字段核对通过：旧 stage 可受控重放（先按受影响键回读核对）"
    else:
        decision = "REEXTRACT_AFFECTED_SCOPE"
        reason = "字段核对或上下游复核未通过：重抽"
    return {
        "ticket_id": ticket.ticket_id,
        "decision": decision,
        "reason": reason,
        "definition_changed": definition_changed,
        "blocking_scope": ticket.blocking_scope,
    }


class TicketRegistry:
    """工单登记簿：AI 登记与复核，不自动关单（never_auto_close）。"""

    def __init__(self) -> None:
        self._tickets: dict[str, ManualTicket] = {}

    def register(self, ticket: ManualTicket) -> ManualTicket:
        if ticket.ticket_id in self._tickets:
            raise ContractViolation(f"工单已存在: {ticket.ticket_id}")
        self._tickets[ticket.ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> ManualTicket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise ContractViolation(f"工单不存在: {ticket_id}")
        return ticket

    def report_fixed(self, ticket_id: str) -> ManualTicket:
        """用户报'改完'：只触发新取证，不得直接关闭。"""
        ticket = self.get(ticket_id)
        if ticket.state == "OPEN":
            ticket.transition("WAITING_HUMAN", reason="已派工人工")
        ticket.transition("FIX_REPORTED", reason="用户报告修复，待取证复核")
        ticket.transition("REVERIFYING", reason="启动复核取证")
        return ticket

    def verify(
        self,
        ticket_id: str,
        evidence: ReverifyEvidence,
        *,
        stage_fingerprint_matches_current: bool,
    ) -> dict:
        ticket = self.get(ticket_id)
        reuse = decide_stage_reuse(
            ticket, evidence,
            stage_fingerprint_matches_current=stage_fingerprint_matches_current,
        )
        if evidence.field_check_passed and evidence.upstream_downstream_checked:
            ticket.transition(
                "VERIFIED", reason="复核取证通过",
                evidence=evidence.acceptance_result_ref,
            )
            ticket.definition_fingerprint = evidence.new_definition_fingerprint
            ticket.dependency_fingerprints = dict(evidence.new_dependency_fingerprints)
        else:
            ticket.transition("REOPENED", reason="复核未通过，退回人工")
        reuse["state"] = ticket.state
        return reuse

    def open_tickets_for_table(self, table: str) -> list[ManualTicket]:
        return [
            t for t in self._tickets.values()
            if table in t.tables and t.state not in ("CLOSED",)
        ]

    def all_tickets(self) -> Sequence[ManualTicket]:
        return list(self._tickets.values())

    def export_machine_json(self) -> list[dict]:
        return [t.to_dict() for t in self._tickets.values()]


def seed_tickets_from_package(seed_doc: dict) -> TicketRegistry:
    """从 E01已知人工工单种子.json 装载登记簿（保留 detail_ref/action）。"""
    registry = TicketRegistry()
    for item in seed_doc.get("tickets", []):
        tables = item.get("tables") or ([item["table"]] if item.get("table") else [])
        registry.register(
            ManualTicket(
                ticket_id=item["ticket"],
                tables=list(tables),
                source_identity=None,
                view_object=None,
                problem_category="OTHER",
                detail_ref=item.get("detail_ref"),
                action=item.get("action"),
                state="OPEN",
                note=item.get("state"),
            )
        )
    return registry
