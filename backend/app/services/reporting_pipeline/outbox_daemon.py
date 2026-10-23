"""outbox sender 独立装配与巡检（第一批批1-6）。

- OutboxSender 已有单轮 process_pending；本模块补运行装配：
  - OutboxDaemon.run_once / run_loop：独立进程循环（默认间隔、最大
    轮数、协作停止），不在抽取回调里同步 HTTP；
  - 进程退出/重启后从耐久仓储继续（PG outbox 是唯一状态源，无内存
    队列），重试退避由 next_attempt_at + Retry-After 驱动；
  - inspect：pending/queued/paused/needs_attention 分组清单（巡检）。
- relay 配置（base_url/secret）只经受控环境变量或显式 --config；缺
  配置即拒绝真实外发（R06 六项外部输入未齐前如实拒绝）。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Callable

from app.services.reporting_pipeline.alerts_client import RelayV2Client
from app.services.reporting_pipeline.alerts_outbox import OutboxSender, SenderBudget
from app.services.reporting_pipeline.contracts import ContractViolation
from app.services.reporting_pipeline.repositories import ControlRepository

RELAY_ENV_BASE_URL = "R189_T1_RELAY_BASE_URL"
RELAY_ENV_SECRET = "R189_T1_RELAY_SECRET_ENV"
RELAY_ENV_SOURCE_ID = "R189_T1_RELAY_SOURCE_ID"


class OutboxDaemonError(ContractViolation):
    """outbox 守护装配失败。"""


@dataclass
class DaemonConfig:
    interval_seconds: float = 30.0
    max_cycles: int | None = None  # None = 一直循环（受 stop 控制）
    per_cycle_budget: SenderBudget | None = None


class OutboxDaemon:
    """独立 outbox sender：一轮=process_pending；循环=固定间隔重跑。"""

    def __init__(
        self,
        repository: ControlRepository,
        client: RelayV2Client,
        *,
        config: DaemonConfig | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sender = OutboxSender(
            repository, client, budget=(config or DaemonConfig()).per_cycle_budget
        )
        self.repository = repository
        self.config = config or DaemonConfig()
        self._sleep = sleep_fn

    def run_once(self) -> dict:
        return self._sender.process_pending()

    def run_loop(self, *, stop: Callable[[], bool] | None = None) -> dict:
        """循环派发直到 stop() 为真或达到 max_cycles；返回累计摘要。"""
        cycles = 0
        totals: dict[str, int] = {}
        while True:
            if stop is not None and stop():
                break
            summary = self.run_once()
            for key, value in summary.items():
                if isinstance(value, int):
                    totals[key] = totals.get(key, 0) + value
            cycles += 1
            if self.config.max_cycles is not None and cycles >= self.config.max_cycles:
                break
            self._sleep(self.config.interval_seconds)
        totals["cycles"] = cycles
        return totals


def build_relay_client_from_env(
    *, source_id: str | None = None, transport=None
) -> RelayV2Client:
    """从受控环境变量构造 relay 客户端；缺配置即拒绝（不默认开外发）。

    secret_ref 存"环境变量名"（引用），secret 本体由 secret_resolver
    运行时读取——secret 不落配置文件、不进日志。
    """
    from app.services.reporting_pipeline.alerts_client import (
        RelayConfig,
        UrllibTransport,
    )

    base_url = os.environ.get(RELAY_ENV_BASE_URL, "").strip()
    secret_env = os.environ.get(RELAY_ENV_SECRET, "").strip()
    effective_source_id = source_id or os.environ.get(RELAY_ENV_SOURCE_ID, "").strip()
    if not base_url or not secret_env or not effective_source_id:
        raise OutboxDaemonError(
            "relay 外发配置不全（需环境变量 "
            f"{RELAY_ENV_BASE_URL}/{RELAY_ENV_SECRET}/{RELAY_ENV_SOURCE_ID}；"
            "R06 六项外部输入未齐前如实拒绝真实外发）"
        )
    if not os.environ.get(secret_env):
        raise OutboxDaemonError(f"环境变量 {secret_env} 未设置（secret 不落盘）")

    def resolve_secret(ref: str) -> bytes:
        value = os.environ.get(ref, "")
        if not value:
            raise OutboxDaemonError(f"secret 引用未解析: {ref}")
        return value.encode("utf-8")

    return RelayV2Client(
        transport=transport or UrllibTransport(),
        config=RelayConfig(
            base_url=base_url,
            source_id=effective_source_id,
            secret_ref=secret_env,
        ),
        secret_resolver=resolve_secret,
    )


def inspect_outbox(repository: ControlRepository) -> dict:
    """巡检视图：全量投递状态分组（含暂停/待人工/退避中）+ 近期事件。"""
    overview = repository.outbox_overview()
    counts = overview["counts"]
    return {
        "summary": {
            "not_sent": counts.get("NOT_SENT", 0),
            "backoff_retrying": counts.get("BACKOFF_RETRYING", 0),
            "ack_queued_awaiting_delivery": counts.get("ACK_QUEUED", 0),
            "paused_auth": counts.get("PAUSED_AUTH", 0),
            "needs_attention": counts.get("NEEDS_ATTENTION", 0),
            "delivered": counts.get("DELIVERED", 0),
        },
        "recent": overview["recent"],
        "note": "事件体不可变（immutable_body_bytes）；巡检不触发发送",
    }
