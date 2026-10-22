"""告警 outbox sender：不可变事件派发与投递跟踪（与任务状态解耦）。

对应设计 §5：
- sender 独立处理 outbox，不在任务错误回调里同步 HTTP 阻塞抽取。
- POST 202 → 保存 relay_event_id、ACK_QUEUED，转状态查询；查询按轮询预算。
- 全部期望目标 sent 且无不确定 → DELIVERED；零目标 → ROUTE_UNRESOLVED。
- 告警发送失败不阻止合法独立业务组推进（调用方语义；本层不抛出阻断）。
- relay 不健康时不递归向 relay 发"relay 失败"告警（NEEDS_ATTENTION 只留本地）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.services.reporting_pipeline.alerts_client import (
    PollOutcome,
    RelayV2Client,
    SendOutcome,
)
from app.services.reporting_pipeline.repositories import (
    ControlRepository,
    OutboxEvent,
)


@dataclass
class SenderBudget:
    max_send_batch: int = 20
    poll_interval_seconds: int = 30
    max_polls_per_cycle: int = 3


class OutboxSender:
    """告警 outbox sender（R06 泛化：内存/PG 仓储同一契约）。

    - 独立处理 outbox，不在任务错误回调里同步 HTTP 阻塞抽取；
    - 耐久仓储下多 sender 并发由 update_outbox_delivery 的行锁/条件更新
      保护（领取语义在仓储实现），本层幂等发送、逐目标轮询；
    - relay 不健康时不递归向 relay 发"relay 失败"告警。
    """

    def __init__(
        self,
        repository: ControlRepository,
        client: RelayV2Client,
        *,
        budget: SenderBudget | None = None,
    ) -> None:
        self.repository = repository
        self.client = client
        self.budget = budget or SenderBudget()

    def process_pending(self) -> dict:
        """一轮派发：POST 未入队事件 + 轮询已入队事件。不抛异常阻断业务。"""
        sent = 0
        queued_for_poll = 0
        paused = 0
        for event in self.repository.pending_outbox()[: self.budget.max_send_batch]:
            outcome: SendOutcome = self.client.send_event(
                source_event_id=event.source_event_id,
                body_bytes=event.immutable_body_bytes,
                previous_attempts=event.attempts,
            )
            update = {
                "attempts_increment": 1,
                "last_http_code": outcome.http_code,
                "last_error_class": outcome.error_class,
            }
            if outcome.acceptance_state in ("ACK_QUEUED", "DUPLICATE"):
                update.update(
                    acceptance_state=outcome.acceptance_state,
                    relay_event_id=outcome.relay_event_id,
                )
                queued_for_poll += 1
            elif outcome.acceptance_state == "RETRY_SCHEDULED":
                update["next_attempt_at"] = _now_plus(outcome.retry_after_seconds or 60)
            elif outcome.acceptance_state == "PAUSED_AUTH":
                update["delivery_state"] = "PAUSED_AUTH"
                paused += 1
            elif outcome.acceptance_state == "REJECTED_PERMANENT":
                update["acceptance_state"] = "REJECTED_PERMANENT"
                update["needs_attention_reason"] = "永久报文错误：需修代码/配置"
            elif outcome.acceptance_state == "NEEDS_ATTENTION":
                update["delivery_state"] = "NEEDS_ATTENTION"
                update["needs_attention_reason"] = outcome.error_class
            self.repository.update_outbox_delivery(
                event.source_event_id, **update
            )
            sent += 1
        polled = self.poll_queued()
        return {
            "send_attempted": sent,
            "newly_queued": queued_for_poll,
            "paused_auth": paused,
            "polls": polled,
        }

    def poll_queued(self) -> int:
        polls = 0
        for event in self._ack_queued_events():
            if polls >= self.budget.max_polls_per_cycle:
                break
            if event.relay_event_id is None:
                continue
            outcome: PollOutcome = self.client.poll_event(
                relay_event_id=event.relay_event_id,
                source_event_id=event.source_event_id,
            )
            polls += 1
            update = {
                "poll_increment": 1,
                "last_http_code": outcome.http_code,
            }
            if outcome.delivery_state == "DELIVERED":
                update["delivery_state"] = "DELIVERED"
                update["target_status_summary"] = outcome.target_status_summary
            elif outcome.delivery_state == "ROUTE_UNRESOLVED":
                update["delivery_state"] = "ROUTE_UNRESOLVED"
                update["needs_attention_reason"] = "零目标：管理员核订阅"
            elif outcome.delivery_state == "NEEDS_ATTENTION":
                update["delivery_state"] = "NEEDS_ATTENTION"
                update["target_status_summary"] = outcome.target_status_summary
                update["needs_attention_reason"] = "存在 dead/cancelled/不确定目标"
            elif outcome.delivery_state == "PAUSED_AUTH":
                update["delivery_state"] = "PAUSED_AUTH"
            elif outcome.delivery_state == "RETRY_SCHEDULED":
                retry_after = outcome.target_status_summary.get("retry_after", 60)
                update["next_attempt_at"] = _now_plus(int(retry_after))
            # PENDING：按轮询预算下轮再看，不改投递态
            if outcome.target_status_summary and "retry_after" not in outcome.target_status_summary:
                update.setdefault("target_status_summary", outcome.target_status_summary)
            self.repository.update_outbox_delivery(event.source_event_id, **update)
        return polls

    def _ack_queued_events(self) -> list[OutboxEvent]:
        return self.repository.queued_outbox()


def _now_plus(seconds: int):
    from app.services.reporting_pipeline.repositories import _utcnow

    return _utcnow() + timedelta(seconds=seconds)
